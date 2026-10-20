import asyncio
import json
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient
from campus_agent.models import Job, Profile, Source, Settings, canonical_url
from campus_agent.pipeline import Agent, process_lock
from campus_agent.sources import structured_jobs, listing_links, checked_url, SourceError
from campus_agent.web import create_app
from campus_agent.tailor import prepare_text

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def profile():
    return Profile.model_validate_json((ROOT/"profile.example.json").read_text())

@pytest.fixture
def job():
    return Job(source_id="asi",employer="ASI",title="Student Events Assistant",
               url="https://example.com/jobs?jobId=123&utm_source=test",
               description="Customer service and teamwork supporting event attendees. Help set up events and coordinate student volunteers.")

@pytest.fixture
def settings():
    return Settings(first_run="notify",sources=[Source(id="asi",name="ASI",url="https://example.com/jobs",kind="html",allowed_hosts=["example.com"])])

def scan(agent,jobs,send=False):
    return asyncio.run(agent.scan(send=send,supplied={"asi":jobs}))

def test_packet_contents_and_dedup(tmp_path,settings,profile,job):
    agent=Agent(settings,profile,tmp_path)
    first=scan(agent,[job])
    second=scan(agent,[job])
    assert first["prepared"]==1 and first["new"]==1
    assert second["prepared"]==0 and second["new"]==0
    row=agent.store.get(job.identity)
    packet=Path(row["packet_dir"])
    resume="\n".join(p.extract_text() for p in PdfReader(packet/"Resume.pdf").pages)
    cover="\n".join(p.extract_text() for p in PdfReader(packet/"Cover Letter.pdf").pages)
    assert profile.name in resume and profile.experience[0].bullets[0] in resume
    assert job.title in cover and job.employer in cover
    msg=BytesParser(policy=policy.default).parsebytes((packet/"notification.eml").read_bytes())
    assert len(list(msg.iter_attachments()))==2
    assert all(part.get_content_type()=="application/pdf" for part in msg.iter_attachments())
    assert "not a submitted application" in msg.get_body(preferencelist=("plain",)).get_content()

def test_first_run_baselines_existing_posts(tmp_path,settings,profile,job):
    agent=Agent(settings.model_copy(update={"first_run":"baseline"}),profile,tmp_path)
    report=scan(agent,[job])
    assert report["baseline"]==1 and report["prepared"]==0
    assert agent.store.get(job.identity)["status"]=="baseline"
    added=Job.model_validate({**job.model_dump(),"url":"https://example.com/jobs?jobId=124"})
    assert scan(agent,[job,added])["prepared"]==1

def test_description_update_creates_new_revision(tmp_path,settings,profile,job):
    agent=Agent(settings,profile,tmp_path)
    scan(agent,[job])
    changed=job.model_copy(update={"description":job.description+" New weekend shifts available."})
    result=scan(agent,[changed])
    assert result["updated"]==1 and result["prepared"]==1
    assert len(agent.store.jobs())==1

def test_queue_budget_does_not_drop_jobs(tmp_path,settings,profile,job):
    agent=Agent(settings.model_copy(update={"max_jobs_per_scan":1}),profile,tmp_path)
    second=Job.model_validate({**job.model_dump(),"url":"https://example.com/jobs?jobId=2"})
    assert scan(agent,[job,second])["prepared"]==1
    assert len(agent.store.jobs())==2
    assert scan(agent,[job,second])["prepared"]==1

def test_prepare_failure_is_retryable(tmp_path,settings,profile,job,monkeypatch):
    agent=Agent(settings,profile,tmp_path)
    original=agent.prepare
    monkeypatch.setattr(agent,"prepare",lambda j: (_ for _ in ()).throw(RuntimeError("failure")))
    assert scan(agent,[job])["errors"]
    assert agent.store.get(job.identity)["status"]=="error"
    monkeypatch.setattr(agent,"prepare",original)
    assert scan(agent,[job])["prepared"]==1

def test_uncertain_smtp_not_retried(tmp_path,settings,profile,job,monkeypatch):
    agent=Agent(settings,profile,tmp_path)
    monkeypatch.setattr("campus_agent.pipeline.check_mail_settings",lambda p:None)
    monkeypatch.setenv("MAIL_FROM","me@example.com")
    monkeypatch.setenv("MAIL_TO","me@example.com")
    calls=[]
    def fail(message):
        calls.append(message)
        raise TimeoutError()
    monkeypatch.setattr("campus_agent.pipeline.send_email",fail)
    scan(agent,[job],send=True)
    assert agent.store.get(job.identity)["status"]=="needs_review"
    scan(agent,[job],send=True)
    assert len(calls)==1

def test_confirmed_send_not_repeated(tmp_path,settings,profile,job,monkeypatch):
    agent=Agent(settings,profile,tmp_path)
    monkeypatch.setattr("campus_agent.pipeline.check_mail_settings",lambda p:None)
    monkeypatch.setenv("MAIL_FROM","me@example.com")
    monkeypatch.setenv("MAIL_TO","me@example.com")
    calls=[]
    monkeypatch.setattr("campus_agent.pipeline.send_email",calls.append)
    assert scan(agent,[job],send=True)["sent"]==1
    assert scan(agent,[job],send=True)["sent"]==0
    assert len(calls)==1

def test_schedule_and_dst(settings):
    # 15:00 UTC = 08:00 PDT; winter 15:00 UTC = 07:00 PST.
    assert settings.in_window(datetime(2026,7,6,15,tzinfo=timezone.utc))
    assert settings.in_window(datetime(2026,1,5,15,tzinfo=timezone.utc))
    assert not settings.in_window(datetime(2026,7,5,15,tzinfo=timezone.utc))
    assert not settings.in_window(datetime(2026,7,7,4,tzinfo=timezone.utc)) # Monday 21:00

def test_canonical_identity(job):
    assert canonical_url("https://EXAMPLE.com/jobs?utm_campaign=x&jobId=123#top")=="https://example.com/jobs?jobId=123"
    alternate=Job.model_validate({**job.model_dump(),"url":"https://example.com/jobs?jobId=123&utm_source=other"})
    assert alternate.identity==job.identity

def test_jsonld_and_html_discovery(settings):
    source=settings.sources[0]
    payload={"@context":"https://schema.org","@type":"JobPosting","title":"Student Assistant","url":"/jobs?jobId=42","description":"<p>Customer service and event support.</p>","hiringOrganization":{"name":"ASI"}}
    html='<script type="application/ld+json">'+json.dumps(payload)+'</script>'
    jobs=structured_jobs(html,source)
    assert jobs[0].employer=="ASI" and jobs[0].url.host=="example.com"
    assert len(listing_links('<a href="/jobs?jobId=42">Student Assistant</a>',source,str(source.url)))==1
    with pytest.raises(SourceError):
        checked_url("https://evil.example/job",source)

def test_untrusted_markup_escaped_and_facts_grounded(tmp_path,settings,profile,job):
    job=job.model_copy(update={"title":"Student <script>alert(1)</script> Assistant"})
    packet=prepare_text(job,profile,"local")
    assert {b for exp in packet["experience"] for b in exp["bullets"]}=={b for exp in profile.experience for b in exp.bullets}
    agent=Agent(settings,profile,tmp_path)
    scan(agent,[job])
    html=(Path(agent.store.get(job.identity)["packet_dir"])/"notification.html").read_text()
    assert "<script>" not in html and "&lt;script&gt;" in html

def test_invalid_settings(settings):
    with pytest.raises(ValueError):
        Settings.model_validate({**settings.model_dump(),"start_hour":22,"end_hour":7})
    with pytest.raises(ValueError):
        Source(id="a",name="a",url="https://example.com/jobs",allowed_hosts=["other.example"])

def test_scan_lock_excludes_second_worker(tmp_path):
    with process_lock(tmp_path):
        with pytest.raises(RuntimeError):
            with process_lock(tmp_path):
                pass
    assert not (tmp_path/".scan.lock").exists()

def test_dashboard_csrf_and_file_boundary(tmp_path,settings,profile):
    app=create_app(Agent(settings,profile,tmp_path))
    client=TestClient(app,base_url="http://127.0.0.1:8765")
    assert client.get("/").status_code==200
    assert client.get("/api/status").json()["total"]==0
    assert client.post("/api/scan").status_code==403
    assert client.get("/files/missing/resume").status_code==404
    assert client.get("/",headers={"host":"attacker.example"}).status_code==400

def test_mcp_tools_never_expose_send(tmp_path,settings,profile):
    from campus_agent.mcp_server import make_server
    server=make_server(Agent(settings,profile,tmp_path))
    tools=asyncio.run(server.list_tools())
    assert {t.name for t in tools}=={"agent_status","list_jobs","scan_jobs","prepare_packet"}


def test_offline_mode_blocks_network_paths_and_cloud(tmp_path,settings,profile,monkeypatch):
    monkeypatch.setenv("SQLITECLOUD_URL","sqlitecloud://not-a-real-server")
    agent=Agent(settings.model_copy(update={"offline":True}),profile,tmp_path)
    assert not agent.store.cloud_url
    with pytest.raises(RuntimeError,match="Offline demo"):
        asyncio.run(agent.scan())
    with pytest.raises(RuntimeError,match="Offline demo"):
        asyncio.run(agent.scan(send=True,supplied={"asi":[]}))
