"""Real browser regression check against a local fixture board.

Set PLAYWRIGHT_EXECUTABLE_PATH to run with an installed Chromium browser.
"""
import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from campus_agent.models import Source
from campus_agent.sources import browser_jobs, SourceError


@pytest.mark.skipif(not os.getenv("PLAYWRIGHT_EXECUTABLE_PATH"), reason="Set a Chromium executable to run browser integration")
def test_browser_collects_multiple_links_and_pages_without_duplicates(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == "/jobs":
                structured = json.dumps({
                    "@context": "https://schema.org", "@type": "JobPosting",
                    "title": "Student Events Assistant", "url": "/detail/one",
                    "description": "Customer service and teamwork supporting campus events.",
                })
                body = f'''<script type="application/ld+json">{structured}</script>
                    <main><a class="job" href="/detail/one">Student Events Assistant</a>
                    <a class="job" href="/detail/two">Library Assistant</a></main>
                    <button aria-label="Next page" onclick="
                    document.querySelector('main').innerHTML = '&lt;a class=job href=/detail/three&gt;Cafe Assistant&lt;/a&gt;';
                    this.disabled = true;">Next page</button>'''
            else:
                body = "<main>Customer service, teamwork, and event support at the campus.</main>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source = Source(id="test", name="Test campus", url=f"http://127.0.0.1:{server.server_port}/jobs",
                        allowed_hosts=["127.0.0.1"], job_selector="a.job", wait_seconds=0)
        jobs = asyncio.run(browser_jobs(source, tmp_path))
        assert {job.title for job in jobs} == {"Student Events Assistant", "Library Assistant", "Cafe Assistant"}
        assert len({job.identity for job in jobs}) == len(jobs) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(not os.getenv("PLAYWRIGHT_EXECUTABLE_PATH"), reason="Set a Chromium executable to run browser integration")
@pytest.mark.parametrize("reported_total", [2, 3])
def test_adp_custom_components_and_completeness(tmp_path, reported_total):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = '''<a href="#" data-id="CurrentOpenings" onclick="list()">Current Openings</a>
            <main id="content"></main><script>
            function list() {
              history.replaceState({}, '', '/jobs');
              document.getElementById('content').innerHTML = '<h1 id="tileCurrentOpenings">Current Openings (2 of TOTAL)</h1>' +
                [1,2].map(i => `<sdf-link id="lblTitle_${i}" onclick="detail(${i})">Student Assistant ${i}</sdf-link>`).join('');
            }
            function detail(i) {
              history.pushState({}, '', '/jobs?jobId=' + i);
              document.getElementById('content').innerHTML = `<h2 class="job-description-title">Student Assistant ${i}</h2>
                <div class="job-description-data">Customer service and teamwork supporting campus events.</div>
                <label class="job-description-location-item">Test campus</label>
                <button id="recruitment_jobDescription_back" onclick="list()">Back</button>`;
            }
            </script>'''.replace('TOTAL', str(reported_total))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source = Source(id="adp-test", name="Test ADP campus", kind="adp",
                        url=f"http://127.0.0.1:{server.server_port}/jobs",
                        allowed_hosts=["127.0.0.1"], wait_seconds=0)
        if reported_total == 3:
            with pytest.raises(SourceError, match="refusing a partial scan"):
                asyncio.run(browser_jobs(source, tmp_path))
        else:
            jobs = asyncio.run(browser_jobs(source, tmp_path))
            assert len(jobs) == 2
            assert {str(job.url).split('jobId=')[1] for job in jobs} == {'1', '2'}
            assert {job.location for job in jobs} == {'Test campus'}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
