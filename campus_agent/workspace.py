from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from pydantic import Field

from .connectors import ConnectorBridge, ConnectorError
from .documents import generate_documents
from .mail import build_email, save_preview
from .models import Experience, Job, Profile, StrictModel, utcnow
from .store import Store
from .tailor import prepare_text, terms
from .role_types import DEFAULT_ROLE_TYPES, matched_types, validate_types, example_types


class Preferences(StrictModel):
    role_types: list[str] = Field(default_factory=lambda: list(DEFAULT_ROLE_TYPES))
    use_custom_keywords: bool = False
    keywords: list[str] = Field(default_factory=lambda: ["IT systems specialist", "Power Platform automation", "AI enablement"])
    location: str = "Melbourne Victoria Australia"
    timezone: str = "Australia/Melbourne"
    interval_minutes: int = Field(default=60, ge=10, le=1440)
    schedule_enabled: bool = False
    email_query: str = 'newer_than:30d (from:seek.com.au OR from:jora.com OR from:indeed.com OR from:linkedin.com) ("job alert" OR "jobs for you" OR "new jobs")'
    drive_folder_id: str = ""
    active_resume_id: str = ""
    morning_enabled: bool = False
    standout_enabled: bool = False
    application_sync_enabled: bool = False
    morning_recipient: str = ""
    morning_max_packets: int = Field(default=3, ge=1, le=10)
    morning_save_drive: bool = True
    auto_top_enabled: bool = True
    auto_top_threshold: int = Field(default=80, ge=0, le=100)


def source_text(result):
    value = result.get("content")
    if isinstance(value, str):
        return value
    return result.get("structuredContent", {}).get("content") or result.get("text", "")


def clean_excerpt(text):
    from .listing_info import clean_summary
    return clean_summary(text)


def stated_closing_date(text):
    from .listing_info import extract_dates
    value = extract_dates(text)['closes_on']
    return datetime.fromisoformat(value).date() if value else None


def readable_listing(text, title):
    from .listing_view import without_site_footer
    text = re.sub(r'(?m)^L\d+: ?', '', text)
    lines = text.splitlines()
    title_words = terms(title)
    start = next((i for i, line in enumerate(lines) if line.startswith('#') and len(terms(line) & title_words) >= min(2, len(title_words))), None)
    if start is not None:
        text = "\n".join(lines[start:])
    text = re.split(r'\n(?:\[Input|Full name\s*\*|Application received|© \d{4})', text, maxsplit=1)[0]
    text = re.split(r'\n(?:#+\s*)?(?:Similar jobs|People also viewed|More jobs like this|Explore more jobs)\b', text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r'【\d+†([^】]*)】', r'\1', text)
    text = re.sub(r'[^]*|【[^】]*】|\[wordlim \d+\]', '', text)
    text = re.sub(r'(?m)^L\d+: ?', '', text)
    return without_site_footer(text).strip()


def resume_profile(text: str, email: str = "") -> Profile:
    """Conservative extraction: preserve original résumé statements, never generate facts."""
    text = text.replace("\r", "")
    text = re.sub(r'(?m)^[^\n]{1,160}?\s*\|\s*Page \d+ of \d+', '\n', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = lines[0]
    address = next((line for line in lines[:8] if "@" in line), "")
    mail = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', address)
    phone = re.search(r'\b(?:\+61\s?|0)\d[\d\s]{7,14}\d\b', address)
    location = address.split("|")[0].strip() if "|" in address else ""
    summary = re.search(r'Professional summary\s*(.*?)(?:Core capabilities:|Professional experience)', text, re.S | re.I)
    if not summary:
        raise ValueError("Résumé layout could not be mapped. Paste your confirmed facts in Profile instead.")
    summary_value = re.sub(r'\s+', ' ', summary[1]).strip()
    experience_section = re.split(r'Professional experience', text, maxsplit=1, flags=re.I)[1]
    experience_section = re.split(r'Selected technical projects|Technical skills|Education and training', experience_section, flags=re.I)[0]
    role_header = re.search(r'([^\n]+?)\s+((?:January|February|March|April|May|June|July|August|September|October|November|December|\d{4})[^\n]*?(?:Present|present|\d{4}))\s*\n([^\n]+)', experience_section)
    role, dates, organization = (role_header[1].strip(), role_header[2].strip(), role_header[3].strip()) if role_header else ("", "", "")
    headings = {"AI enablement and adoption", "Process automation", "Stakeholder collaboration and delivery", "IT systems, network and support", "Professional experience (continued)"}
    bullets, current = [], ""
    for line in experience_section.splitlines():
        line = line.strip()
        if not line or line in headings:
            if current:
                bullets.append(current)
                current = ""
            continue
        if line.startswith(("- ", "• ")):
            if current:
                bullets.append(current)
            current = line[2:]
        elif current:
            current += " " + line
    if current:
        bullets.append(current)
    if not bullets or not role_header:
        raise ValueError("Employment facts need a manual review before importing this résumé.")
    skills_match = re.search(r'Technical skills\s*(.*?)(?:Education and training|Education|Interests|$)', text, re.S | re.I)
    skills = []
    if skills_match:
        joined = re.sub(r'\s+', ' ', skills_match[1])
        joined = re.sub(r'\b(?:AI tools and practice|Power Platform and Microsoft 365|Development and integration|Enterprise systems):', ';', joined)
        skills = [s.strip(' .;') for s in re.split(r';|,', joined) if 1 < len(s.strip()) < 90]
    education_match = re.search(r'Education and training\s*(.*?)(?:Interests|$)', text, re.S | re.I)
    education = [x.strip() for x in education_match[1].splitlines() if x.strip()] if education_match else []
    experience = [Experience(organization=organization, role=role, dates=dates, bullets=bullets)]
    projects = re.search(r'Selected technical projects\s*(.*?)Technical skills', text, re.S | re.I)
    if projects:
        project_bullets, current = [], ""
        for line in projects[1].splitlines():
            line = line.strip()
            if line.startswith(("- ", "• ")):
                if current:
                    project_bullets.append(current)
                current = line[2:]
            elif current and line:
                current += " " + line
        if current:
            project_bullets.append(current)
        if project_bullets:
            experience.append(Experience(organization="", role="Selected technical projects", dates="", bullets=project_bullets))
    return Profile(name=name, email=mail[0] if mail else email, phone=phone[0] if phone else "",
        location=location, summary=summary_value, education=education, skills=list(dict.fromkeys(skills)),
        experience=experience, is_example=False)


def search_results(payload: dict) -> list[dict]:
    """Accept structured results or the web connector's documented readable result blocks."""
    results = []
    def walk(value):
        if isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            url = value.get("url") or value.get("link")
            title = value.get("title") or value.get("name")
            if isinstance(url, str) and isinstance(title, str):
                results.append({"title": title, "url": url, "description": value.get("snippet") or value.get("content") or value.get("description") or title})
            for child in value.values():
                if isinstance(child, (list, dict)):
                    walk(child)
    walk(payload)
    text = source_text(payload)
    pattern = re.compile(r'^(.+?)\s*\((https?://[^\s)]+)\)\s*$', re.M)
    matches = list(pattern.finditer(text))
    for i, match in enumerate(matches):
        description = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        description = clean_excerpt(description)
        results.append({"title": match[1].strip(), "url": match[2], "description": description.strip()})
    unique = {}
    for item in results:
        url = item["url"]
        if re.fullmatch(r'Job Title\s*:', item["title"], re.I) or 'job_description_files.php' in url:
            continue
        if re.search(r'^(?:what\b.*\bjobs\b|find a job\b|search jobs\b)', item["title"], re.I):
            continue
        if "linkedin.com" in urlsplit(url).netloc and "/jobs/view/" not in url:
            continue
        if re.search(r'/job/[^/?#]+|/jobs/view/|viewjob\?.*jk=|/jobs/(?!search(?:/|$))[^/?#]+|/careers/[^/?#]+', url):
            unique[url] = item
    return list(unique.values())


class Workspace:
    def __init__(self, root: Path, bridge=None, recover=True):
        self.root = root.resolve()
        self.data = self.root / "data"
        self.artifacts = self.root / "artifacts"
        self.data.mkdir(parents=True, exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.data / "workspace.db", cloud_url="")
        self.bridge = bridge or ConnectorBridge(self.root)
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="job-agent")
        self.write_lock = threading.RLock()
        self.scan_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.accounts = {}
        with self.store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS workspace_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS job_details (job_id TEXT PRIMARY KEY, full_description INTEGER DEFAULT 0, stage TEXT DEFAULT 'saved', notes TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, kind TEXT, status TEXT, created_at TEXT, finished_at TEXT DEFAULT '', result TEXT DEFAULT '{}', error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, job_id TEXT, revision TEXT, kind TEXT, status TEXT, created_at TEXT, result TEXT DEFAULT '{}', error TEXT DEFAULT '', UNIQUE(job_id,revision,kind));
            ''')
            if recover:
                db.execute("UPDATE tasks SET status='interrupted', error='App stopped during this operation' WHERE status='running'")
                db.execute("UPDATE actions SET status='needs_review', error='Interrupted write: inspect Gmail or Drive before resolving' WHERE status='running'")
        self.preferences = Preferences.model_validate(self.get_meta("preferences", {}))
        self.profile = None
        profile_path = self.data / "profile.json"
        if profile_path.exists():
            self.profile = Profile.model_validate_json(profile_path.read_text())
        self.sources = json.loads((self.data / "source-documents.json").read_text()) if (self.data / "source-documents.json").exists() else []
        threading.Thread(target=self._scheduler, daemon=True).start()

    def get_meta(self, key, default=None):
        with self.store.connect() as db:
            row = db.execute("SELECT value FROM workspace_meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        with self.store.connect() as db:
            db.execute("INSERT INTO workspace_meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def save_preferences(self, preferences):
        if ((preferences.morning_enabled and not self.preferences.morning_enabled)
                or (preferences.standout_enabled and not self.preferences.standout_enabled)):
            self.require_style_approval()
        ZoneInfo(preferences.timezone)
        validate_types(preferences.role_types)
        if preferences.use_custom_keywords and (not preferences.keywords or len(preferences.keywords) > 3 or not all(k.strip() for k in preferences.keywords)):
            raise ValueError("Enter one to three extra search phrases, or turn off extra phrases")
        self.preferences = preferences
        self.set_meta("preferences", preferences.model_dump())

    def save_profile(self, profile):
        with self.write_lock:
            if profile.is_example:
                raise ValueError("Use your confirmed profile, rather than an example profile")
            if self.profile and profile != self.profile:
                self.set_meta('document_style_approval', None)
            target = self.data / "profile.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(profile.model_dump_json(indent=2))
            temporary.chmod(0o600)
            temporary.replace(target)
            self.profile = profile

    def document_style(self):
        from .document_style import DocumentStyle
        return DocumentStyle.model_validate(self.get_meta('document_style', {}))

    def save_document_style(self, value):
        from .document_style import DocumentStyle
        with self.write_lock:
            style = DocumentStyle.model_validate(value)
            if style != self.document_style():
                self.set_meta('document_style_approval', None)
            self.set_meta('document_style', style.model_dump())
            return self.document_style_state()

    def _style_fingerprint(self):
        from .document_style import style_fingerprint
        return style_fingerprint(self.profile, self.document_style())

    def _sample_hashes(self, sample):
        directory = Path(sample['directory']).resolve()
        if not directory.is_relative_to((self.artifacts / 'style-samples').resolve()):
            raise ValueError('Sample directory is invalid')
        result = {}
        for name in ('Resume.pdf', 'Cover Letter.pdf'):
            path = (directory / name).resolve()
            if not path.is_relative_to(directory) or not path.is_file():
                raise ValueError('Sample PDF is missing; generate a new sample')
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for kind, count in sample.get('preview_pages', {}).items():
            for number in range(1, count + 1):
                name = f'{kind}-page-{number}.png'
                path = directory / name
                if not path.is_file():
                    raise ValueError('Sample page preview is missing; generate a new sample')
                result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def document_style_state(self):
        fingerprint = self._style_fingerprint()
        sample = self.get_meta('document_style_sample')
        approval = self.get_meta('document_style_approval')
        current = bool(sample and sample.get('fingerprint') == fingerprint)
        approved = bool(current and approval and approval.get('fingerprint') == fingerprint
                        and approval.get('sample_id') == sample.get('id'))
        reason = 'Choose your style, generate a sample and review both PDFs.'
        if not self.profile:
            reason = 'Save your confirmed profile in Profile & sources first.'
        elif sample and not current:
            reason = 'Your profile, style or document rules changed. Generate and approve a new sample.'
        elif current:
            reason = 'Open both sample PDFs, then confirm that you reviewed them.'
        if approved:
            try:
                approved = self._sample_hashes(sample) == approval.get('hashes')
            except (ValueError, OSError):
                approved = False
            reason = ('Sample approved. Automatic emails still require a separate opt-in and schedule.' if approved
                      else 'Approved sample files changed or are missing. Generate and approve a new sample.')
        view = None if not sample else {k: sample.get(k) for k in ('id', 'fingerprint', 'job_id', 'job_title', 'employer', 'created_at', 'quality', 'preview_pages')}
        return {'preferences': self.document_style().model_dump(), 'fingerprint': fingerprint,
                'sample': view, 'sample_current': current, 'approved': approved,
                'approved_at': approval.get('approved_at') if approved else None, 'message': reason}

    def generate_style_sample(self, job_id):
        with self.write_lock:
            sample_id = uuid.uuid4().hex
            result = self.prepare(job_id, sample_id=sample_id)
            _, job = self.job(job_id)
            sample = {'id': sample_id, 'fingerprint': self._style_fingerprint(), 'job_id': job_id,
                      'job_title': job.title, 'employer': job.employer, 'job_revision': job.revision,
                      'directory': result['packet'], 'created_at': utcnow(), 'quality': result['quality']}
            from .document_style import render_sample_pages
            sample['preview_pages'] = render_sample_pages(Path(result['packet']))
            sample['hashes'] = self._sample_hashes(sample)
            self.set_meta('document_style_sample', sample)
            return self.document_style_state()

    def sample_file(self, sample_id, kind):
        sample = self.get_meta('document_style_sample')
        if kind not in {'resume', 'cover'} or not sample or sample.get('id') != sample_id:
            raise ValueError('Sample not found. Generate a current sample.')
        self._sample_hashes(sample)
        return Path(sample['directory']) / ('Resume.pdf' if kind == 'resume' else 'Cover Letter.pdf')

    def sample_preview_file(self, sample_id, kind, number):
        sample = self.get_meta('document_style_sample')
        if (not sample or sample.get('id') != sample_id or kind not in {'resume', 'cover'}
                or not 1 <= number <= sample.get('preview_pages', {}).get(kind, 0)):
            raise ValueError('Sample page not found')
        if self._sample_hashes(sample) != sample.get('hashes'):
            raise ValueError('Sample files changed; generate a new sample')
        return Path(sample['directory']) / f'{kind}-page-{number}.png'

    def approve_document_style(self, sample_id, fingerprint, reviewed_resume=False, reviewed_cover=False):
        with self.write_lock:
            if reviewed_resume is not True or reviewed_cover is not True:
                raise ValueError('Review and confirm both the sample résumé and cover letter first')
            sample = self.get_meta('document_style_sample')
            if not sample or sample.get('id') != sample_id or sample.get('fingerprint') != self._style_fingerprint() or fingerprint != sample['fingerprint']:
                raise ValueError('Sample is outdated. Generate and review a new sample before approval')
            _, job = self.job(sample['job_id'])
            if job.revision != sample['job_revision']:
                raise ValueError('Sample listing changed. Generate a new sample')
            from .packet_checks import require_delivery
            require_delivery(Path(sample['directory']), job, self.profile)
            hashes = self._sample_hashes(sample)
            if hashes != sample['hashes']:
                raise ValueError('Sample PDFs changed. Generate and review a new sample')
            self.set_meta('document_style_approval', {'sample_id': sample_id, 'fingerprint': fingerprint,
                          'hashes': hashes, 'approved_at': utcnow()})
            return self.document_style_state()

    def require_style_approval(self):
        status = self.document_style_state()
        if not status['approved']:
            raise ValueError('Automatic emails are blocked until you approve a current sample résumé and cover letter in Document style. ' + status['message'])
        return status

    def task(self, kind, operation):
        task_id = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute("INSERT INTO tasks(id,kind,status,created_at) VALUES (?,?,?,?)", (task_id, kind, "running", utcnow()))
        def run():
            try:
                result = operation()
                with self.store.connect() as db:
                    db.execute("UPDATE tasks SET status='done',finished_at=?,result=? WHERE id=?", (utcnow(), json.dumps(result, default=str), task_id))
            except Exception as exc:
                with self.store.connect() as db:
                    db.execute("UPDATE tasks SET status='error',finished_at=?,error=? WHERE id=?", (utcnow(), str(exc)[:1200], task_id))
        self.pool.submit(run)
        return {"task_id": task_id}

    def activity(self):
        with self.store.connect() as db:
            db.row_factory = __import__('sqlite3').Row
            tasks = [dict(r) for r in db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 40")]
            actions = [dict(r) for r in db.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT 80")]
        for item in tasks + actions:
            item["result"] = json.loads(item["result"])
        return {"tasks": tasks, "actions": actions}

    def connect(self):
        accounts = {}
        for app in ("gmail", "google_drive"):
            try:
                account = self.bridge.call(f"{app}.get_profile")
                accounts[app] = {"name": account.get("name"), "email": account.get("email"), "id": account.get("id"), "connected": True}
            except Exception as exc:
                accounts[app] = {"connected": False, "error": str(exc)[:500]}
        self.accounts = accounts
        self.set_meta("connections", {"accounts": accounts, "checked_at": utcnow()})
        return accounts

    def require_account(self, app):
        account = self.bridge.call(f"{app}.get_profile")
        expected = self.get_meta("connections", {}).get("accounts", {}).get(app, {})
        if expected.get("id") and account.get("id") != expected["id"]:
            raise ValueError("Connected account changed. Reconnect in Connections before continuing.")
        return account

    def sources_info(self):
        return [{k: v for k, v in source.items() if k != "text"} for source in self.sources]

    def import_source(self, file_id, kind="resume"):
        if kind not in {"resume", "letter", "example"}:
            raise ValueError("Source kind must be resume, letter or example")
        meta = self.bridge.call("google_drive.get_file_metadata", {"fileId": file_id, "fields": "id,name,mimeType,webViewLink,modifiedTime"})
        url = meta.get("webViewLink") or meta.get("url") or meta.get("display_url")
        if not url:
            raise ValueError("Drive did not return a usable source link")
        fetched = self.bridge.call("google_drive.fetch", {"url": url})
        text = source_text(fetched)
        if len(text) < 100:
            raise ValueError("Drive could not read sufficient text from this source")
        source = {"id": meta["id"], "name": meta.get("name") or meta.get("title"), "url": url, "kind": kind, "modified_time": meta.get("modifiedTime") or meta.get("modified_time"), "text": text}
        source["role_types"] = example_types(source["name"], text)
        with self.write_lock:
            sources = [s for s in self.sources if s["id"] != source["id"]] + [source]
            target = self.data / "source-documents.json"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(sources, indent=2))
            temporary.chmod(0o600)
            temporary.replace(target)
            self.sources = sources
        return {k: v for k, v in source.items() if k != "text"}

    def activate_resume(self, file_id):
        source = next((s for s in self.sources if s["id"] == file_id and s["kind"] == "resume"), None)
        if not source:
            raise ValueError("Import this résumé from Drive first")
        account = self.require_account("gmail")
        profile = resume_profile(source["text"], account.get("email", ""))
        if self.profile:
            profile = profile.model_copy(update={"references_mode": self.profile.references_mode, "referees": self.profile.referees})
        self.save_profile(profile)
        self.save_preferences(self.preferences.model_copy(update={"active_resume_id": file_id}))
        return profile.model_dump()

    def match(self, job):
        if not self.profile:
            return {"score": 0, "skills": []}
        target = terms(job["title"] + " " + job["description"])
        matched = [s for s in self.profile.skills if terms(s) and terms(s) <= target]
        return {"score": min(100, len(matched) * 8), "skills": matched[:12]}

    def jobs(self):
        from .listing_info import extract_dates, date_state, clean_summary
        from .locations import location_info
        from .listing_view import listing_view
        from .fit import fit_assessment
        from .applications import application_key
        rows = self.store.jobs()
        style_preferences = self.document_style().model_dump()
        with self.store.connect() as db:
            details = {r[0]: {"full_description": bool(r[1]), "stage": r[2], "notes": r[3]} for r in db.execute("SELECT * FROM job_details")}
            metadata = {r[0]:json.loads(r[1]) for r in db.execute("SELECT key,value FROM workspace_meta WHERE key LIKE 'listing:%' OR key LIKE 'top:%' OR key LIKE 'shortlist:%' OR key LIKE 'location_override:%'")}
        applications = {a['id']:a for a in self.get_meta('applications', [])}
        for row in rows:
            row.update(details.get(row["id"], {}))
            row.update(self.match(row["job"]))
            row["role_types"] = [{"id": item["id"], "label": item["label"]} for item in matched_types(Job.model_validate(row["job"]))]
            row['application'] = applications.get(application_key(row['job']['employer'], row['job']['title']))
            if row['application']:
                row['stage'] = 'applied'
            row["shortlist"] = metadata.get("shortlist:" + row["id"])
            row['listing'] = metadata.get('listing:'+row['id'], extract_dates(row['job']['description']))
            row['listing'] = {**row['listing'], **date_state(row['listing'],self.preferences.timezone)}
            row['source_domain'] = urlsplit(row['job']['url']).netloc.removeprefix('www.')
            row['summary'] = clean_summary(row['job']['description'])
            row['location_info'] = location_info(row['job'], self.preferences.location, metadata.get('location_override:'+row['id']))
            row['reading_view'] = listing_view(row['job']['description'], row['job']['title'], row['job']['employer'])
            # A literal coverage percentage, separate from the existing search rank.
            # Use the primary description, excluding known recommendation sections.
            skill_phrases = [s for s in self.profile.skills if terms(s)] if self.profile else []
            view = row['reading_view']
            listing_words = terms(view['title']+' '+' '.join(
                b['text'] if b['kind']=='paragraph' else ' '.join(b['items'])
                for section in view['sections'] for b in section['blocks']))
            overlaps = [s for s in skill_phrases if terms(s) <= listing_words]
            row['skill_overlap'] = {'percent':round(100*len(overlaps)/len(skill_phrases)) if skill_phrases else None,
                'matched':len(overlaps),'total':len(skill_phrases),'skills':overlaps}
            row['fit'] = fit_assessment(Job.model_validate(row['job']), self.profile, self.preferences,
                row['reading_view'],row['location_info'],full=bool(row.get('full_description')),closed=row['listing']['closed'])
            if row['fit']['status']=='Closed':
                row['listing']['closed']=True
            row['top_saved'] = bool(metadata.get('top:'+row['id'],False))
            row['top_match'] = bool(self.preferences.auto_top_enabled and row.get('full_description')
                and row.get('stage') not in {'applied','archived'} and not row['listing']['closed']
                and row['fit']['status']=='Good match' and not row['fit']['reviews']
                and row['fit']['percent'] is not None and row['fit']['percent']>=self.preferences.auto_top_threshold)
            row['top_listing'] = row['top_saved'] or row['top_match']
            quality_path = Path(row["packet_dir"]) / "quality-report.json" if row.get("packet_dir") else None
            row["quality"] = json.loads(quality_path.read_text()) if quality_path and quality_path.is_relative_to(self.artifacts) and quality_path.is_file() else None
            tailoring_path=Path(row['packet_dir'])/'tailoring.json' if row.get('packet_dir') else None
            row['profile_stale'] = bool(row.get('packet_dir') and row.get('status')=='prepared' and self.profile and (
                not tailoring_path.is_relative_to(self.artifacts) or not tailoring_path.is_file()
                or json.loads(tailoring_path.read_text()).get('profile')!=self.profile.model_dump()))
            row['style_stale'] = bool(tailoring_path and tailoring_path.is_file() and
                (json.loads(tailoring_path.read_text()).get('document_preferences', {}) != style_preferences))
            if row["quality"]:
                if row['style_stale']:
                    row['quality']['delivery_ready'] = False
                    row['quality']['errors'].append('Document style updated; regenerate this packet')
                if row['profile_stale']:
                    row['quality']['delivery_ready']=False
                    row['quality']['errors'].append('Profile updated; regenerate this packet to include the current referee details and facts')
                from .packet_checks import RULESET_VERSION
                if row["quality"].get("ruleset") != RULESET_VERSION:
                    row["quality"]["delivery_ready"] = False
                    row["quality"]["errors"].append("Regenerate this packet to apply the current role-focus rules")
        return sorted(rows, key=lambda row: (-row["score"], row["seen_at"]))

    def add_job(self, job, full=False):
        previous = self.store.get(job.identity)
        if not previous or full:
            self.save_listing_dates(job)
        if previous and previous["revision"] == job.revision:
            if full:
                with self.store.connect() as db:
                    # Employer/location corrections do not change the description hash.
                    # Persist them without resetting stages, packets or delivery records.
                    if previous['payload'] != job.model_dump_json():
                        db.execute('UPDATE jobs SET payload=?,updated_at=? WHERE id=?', (job.model_dump_json(), utcnow(), job.identity))
                    db.execute("INSERT INTO job_details(job_id,full_description) VALUES (?,1) ON CONFLICT(job_id) DO UPDATE SET full_description=1", (job.identity,))
            return False
        # A search snippet must never overwrite a complete, reviewed job description.
        if previous and not full:
            return False
        self.store.save_job(job)
        with self.store.connect() as db:
            db.execute("INSERT INTO job_details(job_id,full_description) VALUES (?,?) ON CONFLICT(job_id) DO UPDATE SET full_description=excluded.full_description", (job.identity, int(full)))
        return previous is None

    def save_listing_dates(self, job, text=None):
        from .listing_info import extract_dates
        found = extract_dates(job.description if text is None else text)
        previous = self.get_meta('listing:'+job.identity,{})
        merged = {**previous, **{k:v for k,v in found.items() if v is not None and k!='date_evidence'}}
        merged['date_evidence'] = {**previous.get('date_evidence',{}),**found['date_evidence']}
        if found.get('closing_hint')=='Open until filled':
            merged['closes_on']=None
        merged.update(source_url=str(job.url),observed_at=utcnow())
        self.set_meta('listing:'+job.identity,merged)

    def set_top_listing(self, job_id, value):
        self.job(job_id)
        if not isinstance(value,bool):
            raise ValueError('Top listing must be true or false')
        self.set_meta('top:'+job_id,value)
        return {'saved':True,'top':value}

    def discover(self, extended=False):
        from .morning import search_queries
        if not self.scan_lock.acquire(blocking=False):
            raise ValueError("A job search is already running")
        try:
            queries = search_queries(self.preferences, extended)
            items, errors = [], []
            for offset in range(0, len(queries), 3):
                batch = queries[offset:offset + 3]
                try:
                    result = self.bridge.call("search_service.web_run", {"system2_search_query": [{"q": q} for q in batch], "response_length": "long"})
                    items.extend(search_results(result))
                except Exception as exc:
                    errors.append(str(exc)[:300])
            items = list({str(item["url"]): item for item in items}.values())
            if errors and not items:
                raise ValueError("Search failed: " + errors[0])
            added = 0
            excluded_closed = 0
            for item in items:
                description = clean_excerpt(str(item["description"]))[:12000]
                closing = stated_closing_date(description)
                if closing and closing < datetime.now(ZoneInfo(self.preferences.timezone)).date():
                    excluded_closed += 1
                    continue
                if len(description) < 20:
                    continue
                original_title = item["title"]
                title = re.sub(r'\s*[-|]\s*SEEK\s*$', '', original_title).split(" | ")[0].strip()[:300]
                employer = re.search(r'\bat\s+(.+?)(?:\s*[—|]\s*.*)?$', original_title)
                hiring = re.match(r'(.+?) hiring (.+?) in .+', title)
                if hiring:
                    title, company = hiring[2], hiring[1]
                else:
                    company = employer[1].strip() if employer else "Employer on job listing"
                    if employer and 'Careers at ' not in title:
                        title = title.split(' at ')[0].strip()
                company = re.split(r'\s+[—|]\s+', company)[0].strip()
                if ' at ' in title and 'Careers at ' not in title:
                    title = title.split(' at ')[0].strip()
                job = Job(source_id="opportunity", title=title, employer=company,
                    url=item["url"], description=description, location=self.preferences.location)
                added += self.add_job(job)
            report = {"at": utcnow(), "mode": "extended" if extended else "daily", "queries": queries,
                "found": len(items), "new": added, "excluded_closed": excluded_closed,
                "domains": sorted({urlsplit(str(i["url"])).netloc for i in items}), "errors": errors}
            self.set_meta("last_search", report)
            return report
        finally:
            self.scan_lock.release()

    def job(self, job_id):
        row = self.store.get(job_id)
        if not row:
            raise ValueError("Job no longer exists")
        return row, Job.model_validate_json(row["payload"])

    def hydrate(self, job_id):
        from .listing_view import confirmed_listing_employer
        row, job = self.job(job_id)
        result = self.bridge.call("search_service.web_run", {"open": [{"ref_id": str(job.url)}], "response_length": "long"})
        text = source_text(result)
        if re.search(r'(?im)^\s*#{1,6}\s*\d[\d,]*[^\n]{0,150}\bjobs?\s+in\b',text):
            raise ValueError('The URL returned job-search results instead of the original listing; verify the employer posting before preparing a packet.')
        if re.search(r'expired_jd_redirect|jobnotfound=true|sorry, we can.t provide additional information about this job', text, re.I):
            raise ValueError('The listing has expired or redirects to a job search page; it cannot be used for a current packet.')
        if len(text) < 300 or any(phrase in text.lower() for phrase in ("just a moment...", "access denied", "failed to fetch", "unable to resolve open call")):
            raise ValueError("The job board blocked readable access. Open the listing and paste its description in Edit job.")
        self.save_listing_dates(job,text)
        closing = stated_closing_date(text)
        if closing and closing < datetime.now(ZoneInfo(self.preferences.timezone)).date():
            raise ValueError(f"This listing states a closing date of {closing.isoformat()}. Verify that the employer has reopened it before preparing a packet.")
        text = readable_listing(text, job.title)
        job = job.model_copy(update={"description": text[:60000], "employer": confirmed_listing_employer(job, text)})
        self.add_job(job, full=True)
        return {"description_chars": len(job.description)}

    def prepare(self, job_id, sample_id=None):
        with self.write_lock:
            if not self.profile or self.profile.is_example:
                raise ValueError("Choose your real résumé in Profile first")
            row, job = self.job(job_id)
            with self.store.connect() as db:
                full = db.execute("SELECT full_description FROM job_details WHERE job_id=?", (job_id,)).fetchone()
            if not full or not full[0]:
                raise ValueError("Read the full listing or paste its description before preparing a packet")
            from .listing_view import confirmed_listing_employer
            employer = confirmed_listing_employer(job, job.description)
            if employer != job.employer:
                job = job.model_copy(update={'employer': employer})
                self.add_job(job, full=True)
            if re.fullmatch(r'(?:Employer on job listing|Employer in job alert|Unknown|TBD)', job.employer, re.I):
                raise ValueError('Employer needs confirmation. Use Edit details & notes to enter the employer shown on the original listing, then prepare again.')
            families = matched_types(job, self.preferences.role_types) or matched_types(job)
            role_type = families[0]["id"] if families else None
            prepared = prepare_text(job, self.profile, "local", role_type_id=role_type)
            prepared['document_preferences'] = self.document_style().model_dump()
            if prepared['document_preferences']['fact_order'] == 'original':
                prepared['skills'] = list(self.profile.skills)
                prepared['experience'] = [item.model_dump() for item in self.profile.experience]
            from .application_review import focus_application
            prepared = focus_application(job, self.profile, prepared,
                                         prepared['document_preferences']['resume_focus'])
            # Keep source facts complete, and use a concise opening consistent with the supplied letters.
            prepared["source_documents"] = self.sources_info()
            prepared["active_resume_id"] = self.preferences.active_resume_id
            prepared["example_documents"] = [{k: v for k, v in source.items() if k != "text"}
                for source in self.sources if source["kind"] == "example" and role_type in source.get("role_types", [])]
            prepared["method"] = "Original résumé facts ranked for the role; grounded cover-letter template"
            from .documents import DOCUMENT_STYLE_VERSION
            from .packet_checks import check_content, validate_packet
            from .tailor import grounded_cover
            prepared["cover_style"] = "supplied_opening" if any(
                'I help colleagues turn unfamiliar technology into practical ways of working.' in source["text"]
                for source in self.sources if source["kind"] == "letter") else "standard"
            prepared["cover_letter"] = grounded_cover(job, self.profile, prepared)
            prepared.update(document_style_version=DOCUMENT_STYLE_VERSION, job_identity=job.identity, job_revision=job.revision)
            content = check_content(job, self.profile, prepared)
            if not content["passed"]:
                raise ValueError("Packet held by quality rules: " + "; ".join(content["errors"]))
            profile_hash = hashlib.sha256((self.profile.model_dump_json() + json.dumps(prepared, sort_keys=True)).encode()).hexdigest()[:12]
            directory = self.artifacts / job.identity[:16] / (job.revision[:12] + "-" + profile_hash)
            if sample_id:
                directory = self.artifacts / 'style-samples' / sample_id
            generate_documents(directory, job, self.profile, prepared, timezone=self.preferences.timezone)
            quality = validate_packet(directory, job, self.profile, prepared)
            if not quality["passed"]:
                raise ValueError("Packet held by quality rules: " + "; ".join(quality["errors"]))
            prepared["artifact_hashes"] = {name: item["sha256"] for name, item in quality["files"].items()}
            (directory / "tailoring.json").write_text(json.dumps(prepared, indent=2))
            message = build_email(job, self.profile, prepared, directory)
            save_preview(message, directory)
            if not sample_id:
                self.store.update(job_id, "prepared", str(directory))
            return {"packet": str(directory), "review_required": True, "quality": quality}

    def check_prepare(self, job_id):
        from .morning import shortlist
        if not self.profile:
            raise ValueError("Choose a confirmed résumé profile first")
        from .applications import application_for_job
        _, stored_job = self.job(job_id)
        applied = application_for_job(self, stored_job)
        if applied:
            return {'held':True,'assessment':{'selected':False,'reasons':['Already applied; Gmail status: '+applied['status']],'source_url':applied['source_url']}}
        self.hydrate(job_id)
        _, job = self.job(job_id)
        assessment = shortlist(job, self.profile, self.preferences)
        self.set_meta("shortlist:" + job_id, assessment)
        if not assessment["selected"]:
            return {"held": True, "assessment": assessment}
        return {**self.prepare(job_id), "assessment": assessment}

    def action(self, job_id, kind, operation):
        with self.write_lock:
            row, job = self.job(job_id)
            if not row["packet_dir"] or row["status"] != "prepared":
                raise ValueError("Prepare and review this packet first")
            from .packet_checks import require_delivery
            if not self.profile:
                raise ValueError("Confirmed profile is missing")
            prepared = json.loads((Path(row['packet_dir']) / 'tailoring.json').read_text())
            if prepared.get('document_preferences', {}) != self.document_style().model_dump():
                raise ValueError('Document style updated; regenerate this packet before delivery')
            require_delivery(Path(row["packet_dir"]), job, self.profile)
            fingerprint = hashlib.sha256(row["packet_dir"].encode()).hexdigest()[:16]
            revision = job.revision + ":" + fingerprint
            with self.store.connect() as db:
                existing = db.execute("SELECT id,status,result,error FROM actions WHERE job_id=? AND revision=? AND kind=?", (job_id, revision, kind)).fetchone()
                if existing:
                    if existing[1] == "done":
                        return {"already_done": True, **json.loads(existing[2])}
                    if existing[1] != "retryable":
                        raise ValueError(f"This action is {existing[1]}. Inspect Activity before resolving or retrying.")
                    action_id = existing[0]
                    db.execute("UPDATE actions SET status='running',error='',created_at=? WHERE id=?", (utcnow(), action_id))
                else:
                    action_id = uuid.uuid4().hex
                    db.execute("INSERT INTO actions(id,job_id,revision,kind,status,created_at) VALUES (?,?,?,?,?,?)", (action_id, job_id, revision, kind, "running", utcnow()))
            try:
                result = operation(row, job)
                with self.store.connect() as db:
                    db.execute("UPDATE actions SET status='done',result=? WHERE id=?", (json.dumps(result), action_id))
                return result
            except Exception as exc:
                with self.store.connect() as db:
                    db.execute("UPDATE actions SET status='needs_review',error=? WHERE id=?", (str(exc)[:1200], action_id))
                raise

    def record_acknowledgement(self, job_id, kind, result):
        # Keep returned provider IDs even when a later verification read fails.
        with self.store.connect() as db:
            db.execute("UPDATE actions SET result=? WHERE job_id=? AND kind=? AND status='running'", (json.dumps(result), job_id, kind))

    def ensure_folder(self):
        if self.preferences.drive_folder_id:
            meta = self.bridge.call("google_drive.get_file_metadata", {"fileId": self.preferences.drive_folder_id, "fields": "id,name,mimeType,webViewLink,trashed"})
            if meta.get("trashed") or (meta.get("mimeType") or meta.get("mime_type")) != "application/vnd.google-apps.folder":
                raise ValueError("The configured Drive destination is no longer a folder")
            return meta["id"]
        existing = self.bridge.call("google_drive.search", {"query": "Job Agent", "item_type": "folder", "special_filter_query_str": "name = 'Job Agent' and trashed = false and 'me' in owners", "topn": 10})
        folders = existing.get("results", [])
        if len(folders) > 1:
            raise ValueError("More than one Job Agent folder exists. Set its exact folder ID in Connections.")
        folder = folders[0] if folders else self.bridge.call("google_drive.create_folder", {"name": "Job Agent", "parent_folder": "root"})
        folder_id = folder.get("id") or folder.get("folder_id")
        if not folder_id:
            raise ValueError("Drive did not confirm a destination folder ID. Check Drive before retrying.")
        self.save_preferences(self.preferences.model_copy(update={"drive_folder_id": folder_id}))
        return folder_id

    def upload(self, job_id, kind):
        if kind not in {"resume", "cover"}:
            raise ValueError("Unknown packet file")
        def write(row, job):
            self.require_account("google_drive")
            folder_id = self.ensure_folder()
            name = "Resume.pdf" if kind == "resume" else "Cover Letter.pdf"
            path = (Path(row["packet_dir"]) / name).resolve()
            if not path.is_relative_to(self.artifacts) or not path.is_file():
                raise ValueError("Packet file is missing")
            safe_title = re.sub(r'[^\w .-]', '', job.title)[:90]
            draft = self.gmail_packet(job_id)
            if not draft.get("message_id"):
                raise ValueError("The packet draft needs a verified message ID before transferring files")
            message = self.bridge.call("gmail.read_email", {"message_id": draft["message_id"], "format": "full"})
            entries = []
            def collect(part):
                if part.get("filename") == name and part.get("read_attachment_supported") is True:
                    entries.append(part)
                for child in part.get("parts") or []:
                    collect(child)
            collect(message.get("message", message).get("payload") or {})
            if len(entries) != 1:
                raise ValueError("Gmail did not confirm one supported packet attachment for this file")
            attachment = entries[0]
            arguments = {"message_id": draft["message_id"]}
            attachment_id = (attachment.get("body") or {}).get("attachment_id")
            if attachment_id:
                arguments["attachment_id"] = attachment_id
            else:
                arguments["filename"] = name
            downloaded = self.bridge.call("gmail.read_attachment", arguments)
            reference = downloaded.get("file_uri")
            if not isinstance(reference, dict) or not reference.get("download_url"):
                raise ValueError("Gmail did not return a managed file reference for the packet")
            result = self.bridge.call("google_drive.upload_file", {"file_uri": reference, "parent_folder_id": folder_id,
                "file_name": f"{safe_title} - {name}", "mime_type": "application/pdf"})
            file_id = result.get("id") or result.get("file_id")
            if not file_id:
                raise ValueError("Drive upload did not return a file ID. Inspect Drive before resolving.")
            self.record_acknowledgement(job_id, "drive_" + kind, {"id": file_id, "folder_id": folder_id})
            meta = self.bridge.call("google_drive.get_file_metadata", {"fileId": file_id, "fields": "id,name,mimeType,webViewLink,size"})
            return {"id": meta["id"], "name": meta.get("name") or meta.get("title"), "url": meta.get("webViewLink") or meta.get("url") or meta.get("display_url"), "folder_id": folder_id}
        return self.action(job_id, "drive_" + kind, write)

    def gmail_packet(self, job_id, send=False, standout=False, automatic=False):
        if automatic:
            self.require_style_approval()
        def write(row, job):
            if automatic:
                self.require_style_approval()
            account = self.require_account("gmail")
            directory = Path(row["packet_dir"])
            parts = [{"mime_type": "text/html", "charset": "utf-8", "body": {"content": (directory / "notification.html").read_text()}}]
            for name in ("Resume.pdf", "Cover Letter.pdf"):
                path = (directory / name).resolve()
                if not path.is_relative_to(self.artifacts) or not path.is_file():
                    raise ValueError("Packet file is missing")
                parts.append({"mime_type": "application/pdf", "filename": name, "content_disposition": "attachment",
                    "body": {"base64_url_content": base64.urlsafe_b64encode(path.read_bytes()).decode()}})
            result = self.bridge.call("gmail.send_email" if send else "gmail.create_draft", {
                "to": account["email"], "subject": f"{'Standout job' if standout else 'Job Agent'}: {job.title} — packet for review",
                "payload": {"mime_type": "multipart/mixed", "parts": parts},
                "response_fields": ["id", "payload"] if send else ["id", "message"]})
            identity = result.get("id") or result.get("draft_id") or result.get("message", {}).get("id")
            if not identity:
                raise ValueError("Gmail did not confirm a message ID. Inspect Gmail before resolving.")
            message_id = result.get("message", {}).get("id") or result.get("message_id") or (identity if send else None)
            self.record_acknowledgement(job_id, "gmail_send_self" if send else "gmail_draft", {"id": identity,
                "message_id": message_id, "recipient": account["email"], "sent": send, "attachment_count": 2, "attachments_verified": False})
            verified = False
            if message_id:
                readback = self.bridge.call("gmail.read_email", {"message_id": message_id, "format": "full"})
                payload = readback.get("message", readback).get("payload", {})
                names = []
                def attachments(part):
                    if part.get("filename"):
                        names.append(part["filename"])
                    for child in part.get("parts") or []:
                        attachments(child)
                attachments(payload)
                if not {"Resume.pdf", "Cover Letter.pdf"} <= set(names):
                    raise ValueError("Gmail accepted the message but attachments need verification. Inspect Gmail before resolving.")
                verified = True
            return {"id": identity, "message_id": message_id, "recipient": account["email"], "sent": send, "attachment_count": 2, "attachments_verified": verified}
        return self.action(job_id, "gmail_send_self" if send else "gmail_draft", write)

    def sync_applications(self):
        from .applications import sync_applications
        return sync_applications(self)

    def alerts(self):
        found = self.bridge.call("gmail.search_email_ids", {"query": self.preferences.email_query, "max_results": 12})
        self.set_meta("job_alert_search", {"at": utcnow(), "result": found})
        return found

    def read_alert(self, message_id):
        allowed = self.get_meta("job_alert_search", {}).get("result", {}).get("message_ids", [])
        if message_id not in allowed:
            raise ValueError("Find job alerts first; only those returned messages can be read here")
        result = self.bridge.call("gmail.read_email", {"message_id": message_id, "format": "full"})
        message = result.get("message", result)
        payload = message.get("payload", {})
        headers = payload.get("headers", [])
        subject = next((h.get("value", "") for h in headers if h.get("name", "").lower() == "subject"), "Job alert") if isinstance(headers, list) else headers.get("Subject", "Job alert")
        plain, markup = [], []
        def body(part):
            content = (part.get("body") or {}).get("content", "")
            if content:
                (markup if part.get("mime_type", part.get("mimeType")) == "text/html" else plain).append(content)
            for child in part.get("parts") or []:
                body(child)
        body(payload)
        soup = BeautifulSoup("\n".join(markup), "html.parser")
        links = []
        seen = set()
        for node in soup.select('a[href]'):
            url = node.get("href", "")
            for _ in range(2):
                query = parse_qs(urlsplit(url).query)
                nested = next((query[k][0] for k in ("url", "u", "redirect", "target", "dest") if query.get(k)), None)
                if not nested:
                    break
                url = unquote(nested)
            title = node.get_text(" ", strip=True)
            if not re.search(r'/job/[^/?#]+|/jobs/view/|viewjob\?', url) or len(title) < 5 or url in seen:
                continue
            if urlsplit(url).scheme not in {"http", "https"}:
                continue
            seen.add(url)
            context = node.parent.get_text(" ", strip=True) if node.parent else title
            job = {"title": title[:300], "employer": "Employer in job alert", "url": url,
                "description": (context + "\nJob-alert lead. Read the original listing before preparing documents.")[:12000], "location": self.preferences.location}
            links.append({"title": title, "job": job})
        return {"subject": subject, "text": "\n".join(plain) or soup.get_text(" ", strip=True) or message.get("snippet", ""), "links": links}

    def _scheduler(self):
        last = 0
        import time
        while not self.stop_event.wait(15):
            prefs = self.preferences
            now = datetime.now(ZoneInfo(prefs.timezone))
            if prefs.schedule_enabled and now.weekday() < 5 and 7 <= now.hour < 21 and time.monotonic() - last >= prefs.interval_minutes * 60:
                last = time.monotonic()
                self.task("Scheduled discovery", self.discover)

    def close(self):
        self.stop_event.set()
        self.bridge.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
