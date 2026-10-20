from __future__ import annotations
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx
from bs4 import BeautifulSoup
from .models import Job, Source

class SourceError(RuntimeError):
    pass

def checked_url(value: str, source: Source) -> str:
    if urlsplit(value).scheme not in {"http", "https"} or urlsplit(value).hostname not in source.allowed_hosts:
        raise SourceError("A job URL left the source's configured host allowlist")
    return value

def text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]):
        node.decompose()
    return " ".join(soup.stripped_strings)

def structured_jobs(html: str, source: Source) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            types = node.get("@type", [])
            if types == "JobPosting" or isinstance(types, list) and "JobPosting" in types:
                if not node.get("url"):
                    return
                url = checked_url(urljoin(str(source.url), node["url"]), source)
                employer = node.get("hiringOrganization", {})
                found.append(Job(source_id=source.id, employer=employer.get("name", source.name) if isinstance(employer, dict) else source.name,
                                 title=node["title"], url=url, description=text(node.get("description", ""))))
            if "@graph" in node:
                walk(node["@graph"])
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.get_text()))
        except (ValueError, TypeError, KeyError):
            continue
    return found

def listing_links(html: str, source: Source, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for node in soup.select(source.job_selector):
        href = node.get("href") or node.get("data-url")
        title_node = node.select_one(source.title_selector) if source.title_selector else node
        title = title_node.get_text(" ", strip=True) if title_node else ""
        if href and len(title) > 1:
            url = checked_url(urljoin(base, href), source)
            result[url] = title
    return list(result.items())

def fetch_html(url: str, source: Source) -> str:
    # Redirects are checked before each follow-up request.
    with httpx.Client(timeout=30, headers={"User-Agent": "CampusJobAgent/0.1 (personal job alerts)"}) as client:
        for _ in range(6):
            checked_url(url, source)
            response = client.get(url)
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            return response.text
    raise SourceError("Too many redirects")

def html_jobs(source: Source) -> list[Job]:
    html = fetch_html(str(source.url), source)
    jobs = structured_jobs(html, source)
    if jobs:
        return jobs
    for url, title in listing_links(html, source, str(source.url)):
        detail = fetch_html(url, source)
        soup = BeautifulSoup(detail, "html.parser")
        main = soup.select_one(source.description_selector) or soup.body or soup
        jobs.append(Job(source_id=source.id, employer=source.name, title=title, url=url, description=text(str(main))))
    if not jobs and not (source.empty_selector and BeautifulSoup(html, "html.parser").select_one(source.empty_selector)):
        raise SourceError("No job cards or explicit empty-state marker found; check job_selector. This is not treated as an empty successful scan.")
    return jobs

def json_jobs(source: Source) -> list[Job]:
    payload = json.loads(fetch_html(str(source.url), source))
    records = payload if isinstance(payload, list) else payload["jobs"]
    if not isinstance(records, list):
        raise SourceError("JSON feed must be an array, or an object with a jobs array")
    return [Job(source_id=source.id, employer=record.get("employer", source.name),
                title=record["title"], url=checked_url(urljoin(str(source.url), record["url"]), source),
                description=text(record["description"]), location=record.get("location", "Long Beach, CA")) for record in records]

async def adp_jobs(page, source: Source) -> list[Job]:
    """Read ADP's rendered components, using their actual detail navigation URLs."""
    titles = 'sdf-link[id^="lblTitle_"]'
    await page.locator('a[data-id="CurrentOpenings"]').wait_for(timeout=45000)
    await page.wait_for_timeout(source.wait_seconds * 1000)
    cookie_close = page.locator('#onetrust-banner-sdk .banner-close-button')
    if await cookie_close.is_visible():
        await cookie_close.click()
    await page.locator('a[data-id="CurrentOpenings"]').click(timeout=45000)
    await page.locator('#tileCurrentOpenings').wait_for(timeout=45000)
    await page.wait_for_timeout(source.wait_seconds * 1000)
    await page.locator('#career-center-busy-ind').wait_for(state="hidden", timeout=45000)
    result = {}
    expected_total = None
    for _ in range(20):
        heading = await page.locator('#tileCurrentOpenings').inner_text()
        count = re.search(r'\((\d+)\s+of\s+(\d+)\)', heading)
        if not count:
            raise SourceError("ADP listing count was not found; refusing a partial scan")
        expected_total = int(count[2])
        if expected_total == 0:
            return []
        await page.locator(titles).first.wait_for(timeout=30000)
        ids = await page.locator(titles).evaluate_all('(nodes) => nodes.map(node => node.id)')
        if not ids:
            raise SourceError("ADP reported vacancies without usable job components")
        for item_id in ids:
            item = page.locator(f'[id="{item_id}"]')
            title = (await item.inner_text()).strip()
            await item.click()
            await page.locator('.job-description-title').wait_for(timeout=30000)
            await page.wait_for_url(lambda url: bool(re.search(r'[?&]jobId=\d+', url)), timeout=30000)
            description = page.locator('.job-description-data')
            await description.wait_for(timeout=30000)
            job = Job(source_id=source.id, employer=source.name, title=title,
                      url=checked_url(page.url, source), description=await description.inner_text(),
                      location=await page.locator('.job-description-location-item').first.inner_text())
            result[job.identity] = job
            await page.locator('#recruitment_jobDescription_back').click()
            await page.locator(f'[id="{item_id}"]').wait_for(timeout=30000)
        if len(result) == expected_total:
            return list(result.values())
        next_page = page.locator('button[aria-label="Next page"], sdf-button[aria-label="Next page"]').first
        if not await next_page.count() or not await next_page.is_enabled():
            raise SourceError(f"ADP returned {len(result)} of {expected_total} roles; refusing a partial scan")
        await next_page.click()
        await page.wait_for_function('(before) => JSON.stringify(Array.from(document.querySelectorAll(\'sdf-link[id^="lblTitle_"]\'), n => n.id)) !== JSON.stringify(before)', arg=ids, timeout=30000)
    raise SourceError("ADP exceeded 20 pages; refusing a partial scan")

async def browser_jobs(source: Source, diagnostics: Path) -> list[Job]:
    from playwright.async_api import async_playwright
    jobs = {}
    diagnostics.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        options = {"headless": True}
        if os.getenv("PLAYWRIGHT_EXECUTABLE_PATH"):
            options["executable_path"] = os.environ["PLAYWRIGHT_EXECUTABLE_PATH"]
        browser = await p.chromium.launch(**options)
        context = await browser.new_context()
        async def navigation_guard(route):
            request = route.request
            if request.is_navigation_request() and request.frame == page.main_frame:
                try:
                    checked_url(request.url, source)
                except SourceError:
                    await route.abort()
                    return
            await route.continue_()
        page = await context.new_page()
        await page.route("**/*", navigation_guard)
        try:
            response = await page.goto(str(source.url), wait_until="domcontentloaded", timeout=45000)
            if response and response.status >= 400:
                raise SourceError(f"Job board returned HTTP {response.status}")
            if source.kind == "adp":
                try:
                    return await adp_jobs(page, source)
                except Exception:
                    await page.screenshot(path=str(diagnostics / f"{source.id}-adp-error.png"), full_page=True)
                    raise
            # Bound the settling window; do not require a tracking-heavy page to become network-idle.
            await page.wait_for_timeout(source.wait_seconds * 1000)
            try:
                await page.locator(source.job_selector).first.wait_for(state="attached", timeout=20000)
            except Exception:
                pass  # JSON-LD and explicitly configured empty states are checked below.
            for _ in range(20):
                html = await page.content()
                for job in structured_jobs(html, source):
                    jobs[str(job.url)] = job
                links = listing_links(html, source, page.url)
                for url, title in links:
                    jobs.setdefault(url, (url, title))
                next_button = page.locator("button[aria-label='Next page'], button[title='Next page']").first
                if not await next_button.count() or not await next_button.is_enabled():
                    break
                before = html
                await next_button.click()
                await page.wait_for_timeout(source.wait_seconds * 1000)
                if await page.content() == before:
                    raise SourceError("Pagination did not advance; refusing a partial scan")
            else:
                raise SourceError("Board exceeded 20 pages; increase adapter coverage")
            if not jobs:
                if source.empty_selector and await page.locator(source.empty_selector).count():
                    return []
                await page.screenshot(path=str(diagnostics / f"{source.id}-empty.png"), full_page=True)
                raise SourceError("No listings found. Inspect diagnostics and configure job_selector or empty_selector for this board.")
            details = await context.new_page()
            async def detail_guard(route):
                if route.request.is_navigation_request() and route.request.frame == details.main_frame:
                    try:
                        checked_url(route.request.url, source)
                    except SourceError:
                        await route.abort()
                        return
                await route.continue_()
            await details.route("**/*", detail_guard)
            result = {}
            for value in jobs.values():
                if isinstance(value, Job):
                    result[value.identity] = value
                    continue
                url, title = value
                response = await details.goto(url, wait_until="domcontentloaded", timeout=45000)
                if response and response.status >= 400:
                    raise SourceError(f"Job detail returned HTTP {response.status}")
                await details.wait_for_timeout(source.wait_seconds * 1000)
                detail_html = await details.content()
                structured = structured_jobs(detail_html, source)
                if structured:
                    for job in structured:
                        result[job.identity] = job
                else:
                    soup = BeautifulSoup(detail_html, "html.parser")
                    main = soup.select_one(source.description_selector) or soup.body or soup
                    job = Job(source_id=source.id, employer=source.name, title=title, url=url, description=text(str(main)))
                    result[job.identity] = job
            return list(result.values())
        finally:
            await context.close()
            await browser.close()

async def scrape(source: Source, diagnostics: Path) -> list[Job]:
    if source.kind == "json":
        return json_jobs(source)
    if source.kind == "html":
        return html_jobs(source)
    return await browser_jobs(source, diagnostics)
