import base64
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from campus_agent.connectors import ConnectorBridge, ConnectorError, unpack
from campus_agent.models import Job, Profile
from campus_agent.workspace import Workspace, resume_profile, search_results, readable_listing, stated_closing_date
from campus_agent.tailor import local_selection
from campus_agent.workspace_web import create_workspace_app


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.fail_upload = False

    def call(self, tool, arguments=None):
        args = arguments or {}
        self.calls.append((tool, args))
        if tool.endswith("get_profile"):
            return {"id": "owner", "name": "Test Person", "email": "owner@example.com"}
        if tool == "google_drive.search":
            return {"results": []}
        if tool == "google_drive.create_folder":
            return {"id": "folder"}
        if tool == "google_drive.get_file_metadata":
            return {"id": args["fileId"], "name": "Packet", "mimeType": "application/vnd.google-apps.folder" if args["fileId"] == "folder" else "application/pdf", "webViewLink": "https://drive.google.com/observed-file"}
        if tool == "google_drive.upload_file":
            if self.fail_upload:
                raise TimeoutError("Uncertain upload")
            assert args["file_uri"]["file_id"] == "managed-packet-reference"
            return {"id": "uploaded-file"}
        if tool == "gmail.read_email":
            return {"payload": {"parts": [{"filename": "Resume.pdf", "read_attachment_supported": True, "body": {"attachment_id": "resume-attachment"}, "parts": None}, {"filename": "Cover Letter.pdf", "read_attachment_supported": True, "body": {"attachment_id": "cover-attachment"}, "parts": None}]}}
        if tool == "gmail.read_attachment":
            return {"file_uri": {"file_id": "managed-packet-reference", "download_url": "https://example.com/managed-reference"}}
        if tool == "gmail.create_draft":
            return {"id": "draft-id", "message": {"id": "draft-message"}}
        if tool.startswith("gmail."):
            return {"id": "gmail-id"}
        return {}

    def pending_approvals(self):
        return []

    def close(self):
        pass


@pytest.fixture
def workspace(tmp_path, profile):
    bridge = FakeBridge()
    ws = Workspace(tmp_path, bridge)
    ws.save_profile(profile.model_copy(update={"is_example": False, "email": "profile-address@example.com"}))
    yield ws
    ws.close()


@pytest.fixture
def profile():
    return Profile.model_validate_json((Path(__file__).parents[1] / "profile.example.json").read_text())


@pytest.fixture
def role():
    return Job(source_id="opportunity", title="Systems Specialist", employer="Example Employer",
               url="https://example.com/job/123", location="Melbourne", description="Customer service and teamwork with Python and Microsoft Excel support.")


def test_resume_continuation_preserves_qualifiers():
    text = '''Test Person
IT specialist
Melbourne, Victoria | 0448 111 222 | person@example.com
Professional summary
IT specialist with confirmed systems and automation experience.
Core capabilities: Automation
Professional experience
IT Systems Specialist June 2021 - Present
Example Organisation, Melbourne
- Built and tested a workflow ahead of rollout.
Test Person | Page 1 of 2
Professional experience (continued)
IT systems, network and support
- Built prototype agents; outcomes remain unmeasured.
Technical skills
Development and integration: Python; PowerShell
Education and training
ITIL Foundation - 2021
Interests
Music
'''
    profile = resume_profile(text)
    assert profile.experience[0].bullets == ["Built and tested a workflow ahead of rollout.", "Built prototype agents; outcomes remain unmeasured."]
    assert profile.email == "person@example.com"
    assert profile.education == ["ITIL Foundation - 2021"]


def test_search_filters_aggregate_boards_and_accepts_employer_roles():
    result = search_results({"text": '''AI Consultant | Careers at Company (https://company.example/jobs/ai-consultant/)
Job description for an AI consulting role.
--------------------------------
Systems Specialist Jobs (https://au.linkedin.com/jobs/systems-specialist-jobs-melbourne)
Many jobs.
--------------------------------
Systems Engineer (https://au.linkedin.com/jobs/view/systems-engineer-123)
A specific role description.
'''})
    assert len(result) == 2
    assert all("jobs/systems-specialist-jobs" not in r["url"] for r in result)


def test_readable_listing_removes_navigation_and_success_form():
    text = '''Menu and unrelated corporate navigation
【0†Home】
# AI Enablement Consultant
Location Melbourne, AU
## The role
Lead workflow discovery and responsible AI enablement.
## Apply for this position
Send a short note on a business problem you diagnosed.
[Input]
Full name
Application received
Thanks for your application.
'''
    readable = readable_listing(text, "AI Enablement Consultant")
    assert readable.startswith("# AI Enablement Consultant")
    assert "short note" in readable
    assert "Application received" not in readable and "Menu" not in readable
    assert stated_closing_date("Applications close 10 June 2026").isoformat() == "2026-06-10"


def test_ai_title_prioritises_ai_facts_without_changing_them(profile, role):
    first = profile.experience[0].model_copy(update={"bullets": [
        "Worked with the team and the users across the business with other people.",
        "Created an AI enablement guide and delivered a live demonstration."]})
    profile = profile.model_copy(update={"experience": [first]})
    selection = local_selection(role.model_copy(update={"title": "AI Enablement Consultant", "description": "Help teams with AI enablement and practical demonstrations across the business."}), profile)
    assert selection.bullet_ids[0] == "0:1"


def test_prepare_requires_full_listing(workspace, role):
    workspace.add_job(role)
    with pytest.raises(ValueError, match="full listing"):
        workspace.prepare(role.identity)
    workspace.add_job(role.model_copy(update={"description": role.description + " Full listing."}), full=True)
    result = workspace.prepare(role.identity)
    assert Path(result["packet"]).is_relative_to(workspace.artifacts)
    assert (Path(result["packet"]) / "Resume.pdf").read_bytes().startswith(b"%PDF-")


def test_search_snippet_cannot_replace_full_description(workspace, role):
    workspace.add_job(role, full=True)
    workspace.add_job(role.model_copy(update={"description": "A short, stale snippet from a later search."}))
    _, saved = workspace.job(role.identity)
    assert saved.description == role.description


def test_drive_upload_readback_and_duplicate_protection(workspace, role):
    workspace.add_job(role, full=True)
    workspace.prepare(role.identity)
    first = workspace.upload(role.identity, "resume")
    second = workspace.upload(role.identity, "resume")
    assert first["id"] == "uploaded-file" and second["already_done"]
    assert len([c for c in workspace.bridge.calls if c[0] == "google_drive.upload_file"]) == 1
    assert 'download_url' not in json.dumps(workspace.activity()["actions"])


def test_normalized_drive_metadata_and_source_import(workspace, role):
    original = workspace.bridge.call
    def normalized(tool, args=None):
        if tool == "google_drive.get_file_metadata":
            return {"id": args["fileId"], "title": "Source or packet", "mime_type": "application/vnd.google-apps.folder" if args["fileId"] == "folder" else "application/pdf", "url": "https://drive.google.com/observed-file"}
        if tool == "google_drive.fetch":
            return {"content": "Confirmed source text. " * 20}
        return original(tool, args)
    workspace.bridge.call = normalized
    source = workspace.import_source("source-id")
    assert source["name"] == "Source or packet" and source["url"] == "https://drive.google.com/observed-file"
    workspace.add_job(role, full=True)
    workspace.prepare(role.identity)
    assert workspace.upload(role.identity, "resume")["url"] == "https://drive.google.com/observed-file"
    assert workspace.upload(role.identity, "cover")["name"] == "Source or packet"


def test_ambiguous_write_never_retries_without_resolution(workspace, role):
    workspace.add_job(role, full=True)
    workspace.prepare(role.identity)
    workspace.bridge.fail_upload = True
    with pytest.raises(TimeoutError):
        workspace.upload(role.identity, "resume")
    with pytest.raises(ValueError, match="needs_review"):
        workspace.upload(role.identity, "resume")
    assert len([c for c in workspace.bridge.calls if c[0] == "google_drive.upload_file"]) == 1
    assert next(a for a in workspace.activity()["actions"] if a["kind"] == "drive_resume")["status"] == "needs_review"


def test_gmail_only_uses_connected_owners_inbox_and_real_attachments(workspace, role):
    workspace.add_job(role, full=True)
    workspace.prepare(role.identity)
    workspace.gmail_packet(role.identity, send=True)
    workspace.gmail_packet(role.identity, send=True)
    sends = [args for name, args in workspace.bridge.calls if name == "gmail.send_email"]
    assert len(sends) == 1 and sends[0]["to"] == "owner@example.com"
    attachments = sends[0]["payload"]["parts"][1:]
    assert [part["filename"] for part in attachments] == ["Resume.pdf", "Cover Letter.pdf"]
    assert all(base64.urlsafe_b64decode(part["body"]["base64_url_content"]).startswith(b"%PDF-") for part in attachments)


def test_profile_changes_create_new_packet_and_cloud_action(workspace, role):
    workspace.add_job(role, full=True)
    first = workspace.prepare(role.identity)["packet"]
    workspace.upload(role.identity, "resume")
    workspace.save_profile(workspace.profile.model_copy(update={"summary": "Updated but confirmed professional background and relevant support experience."}))
    second = workspace.prepare(role.identity)["packet"]
    workspace.upload(role.identity, "resume")
    assert first != second
    assert len([c for c in workspace.bridge.calls if c[0] == "google_drive.upload_file"]) == 2


def test_unselected_mail_cannot_be_read(workspace):
    with pytest.raises(ValueError, match="Find job alerts first"):
        workspace.read_alert("unrelated-email")
    assert not workspace.bridge.calls


def test_api_csrf_review_gate_and_file_boundary(workspace, role, tmp_path):
    workspace.add_job(role, full=True)
    client = TestClient(create_workspace_app(workspace), base_url="http://127.0.0.1:8877")
    index = client.get("/")
    token = re.search(r'const token="([^"]+)"', index.text)[1]
    headers = {"origin": "http://127.0.0.1:8877", "x-workspace-token": token}
    assert client.post("/api/connect").status_code == 403
    assert client.post("/api/jobs/" + role.identity + "/email-self", headers=headers, json={}).status_code == 400
    assert client.get("/", headers={"host": "attacker.example"}).status_code == 400
    workspace.store.update(role.identity, "prepared", str(tmp_path.parent))
    assert client.get("/files/" + role.identity + "/resume").status_code == 404
    assert client.get("/api/state").json()["kind"] == "job-workspace"


def test_bridge_refuses_unexposed_tools_and_provider_errors(tmp_path):
    bridge = ConnectorBridge(tmp_path)
    with pytest.raises(ConnectorError, match="does not permit"):
        bridge.call("gmail.delete_email", {})
    with pytest.raises(ConnectorError, match="denied"):
        unpack({"isError": True, "content": [{"type": "text", "text": "denied"}]})
    assert bridge.proc is None
    assert 'sensitive-signature' not in str(ConnectorError('Download failed: https://example.com/file?sig=sensitive-signature'))



def approve_sample_style(workspace):
    """Exercise the real review/approval path with synthetic, archived sample data."""
    sample_job = Job(source_id='opportunity', title='IT Support Specialist', employer='Example Employer',
        url='https://example.com/job/style-sample', location='Melbourne',
        description='Apply in Melbourne Australia. Python automation, Microsoft Excel reporting and SharePoint support.')
    workspace.add_job(sample_job, full=True)
    state = workspace.generate_style_sample(sample_job.identity)
    workspace.approve_document_style(state['sample']['id'], state['fingerprint'], True, True)
    with workspace.store.connect() as db:
        db.execute("UPDATE job_details SET stage='archived' WHERE job_id=?", (sample_job.identity,))


def morning_profile(workspace):
    from campus_agent.models import Experience
    profile = workspace.profile.model_copy(update={
        'skills': ['Python', 'Microsoft Excel', 'SharePoint'],
        'experience': [Experience(organization='Confirmed Employer', role='IT Specialist', dates='2021-present', bullets=[
            'Built Python automation for monthly Microsoft Excel reporting.',
            'Supported SharePoint systems and process automation for colleagues.'])]})
    workspace.save_profile(profile)
    approve_sample_style(workspace)
    workspace.save_preferences(workspace.preferences.model_copy(update={
        'morning_enabled': True, 'morning_recipient': 'owner@example.com', 'morning_save_drive': False}))
    return profile


def test_shortlist_uses_listing_location_and_confirmed_facts(workspace, role):
    from campus_agent.morning import shortlist
    profile = morning_profile(workspace)
    text = 'Apply for this Melbourne Australia role. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.'
    good = role.model_copy(update={'description': text})
    assert shortlist(good, profile)['selected']
    overseas = good.model_copy(update={'description': text.replace('Melbourne Australia', 'Boston USA')})
    assert not shortlist(overseas, profile)['selected']  # Search hint is still Melbourne.
    for extra in ['Australian citizenship required', 'Applications have closed', 'NV1 clearance required']:
        assert not shortlist(good.model_copy(update={'description': text + extra}), profile)['selected']
    assert not shortlist(good.model_copy(update={'title': 'Head of IT'}), profile)['selected']


def test_extended_discovery_is_bounded_and_reports_coverage(workspace):
    from campus_agent.morning import search_queries
    assert len(search_queries(workspace.preferences)) == 10
    assert len(search_queries(workspace.preferences, True)) == 24
    result = workspace.discover(extended=True)
    queries = [args for name, args in workspace.bridge.calls if name == 'search_service.web_run']
    assert len(queries) == 8
    assert all(len(q['system2_search_query']) <= 3 for q in queries)
    assert result['mode'] == 'extended' and result['found'] == 0


def test_morning_delivers_once_and_refreshes_listing(workspace, role, monkeypatch):
    from campus_agent.morning import run_morning
    from datetime import datetime
    from zoneinfo import ZoneInfo
    morning_profile(workspace)
    workspace.add_job(role)
    monkeypatch.setattr(workspace, 'discover', lambda extended=False: {'found': 1, 'errors': []})
    monkeypatch.setattr(workspace, 'alerts', lambda: {'message_ids': []})
    refreshed = []
    def hydrate(job_id):
        refreshed.append(job_id)
        workspace.add_job(role.model_copy(update={'description': 'Apply in Melbourne Australia. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.'}), full=True)
    monkeypatch.setattr(workspace, 'hydrate', hydrate)
    now = datetime(2026, 10, 16, 8, tzinfo=ZoneInfo('Australia/Melbourne'))
    result = run_morning(workspace, now=now)
    assert result['status'] == 'done' and len(result['packets']) == 1
    sends = [args for name, args in workspace.bridge.calls if name == 'gmail.send_email']
    assert len(sends) == 2 and all(s['to'] == 'owner@example.com' for s in sends)
    assert len(sends[0]['payload']['parts']) == 3
    assert refreshed == [role.identity]
    assert run_morning(workspace, now=now)['already_done']
    tomorrow = now.replace(day=17)
    assert not run_morning(workspace, now=tomorrow)['packets']
    assert len([name for name, _ in workspace.bridge.calls if name == 'gmail.send_email']) == 3


def test_morning_recipient_change_and_pause_stop_sending(workspace):
    from campus_agent.morning import run_morning
    with pytest.raises(ValueError, match='paused'):
        run_morning(workspace)
    morning_profile(workspace)
    workspace.preferences.morning_recipient = 'another@example.com'
    with pytest.raises(ValueError, match='differs'):
        run_morning(workspace)
    assert not any(name == 'gmail.send_email' for name, _ in workspace.bridge.calls)


def test_uncertain_morning_receipt_is_not_retried(workspace, monkeypatch):
    from campus_agent.morning import run_morning
    morning_profile(workspace)
    monkeypatch.setattr(workspace, 'discover', lambda extended=False: {'found': 0, 'errors': []})
    monkeypatch.setattr(workspace, 'alerts', lambda: {'message_ids': []})
    original = workspace.bridge.call
    def call(name, args=None):
        if name == 'gmail.send_email':
            raise TimeoutError('Unknown provider outcome')
        return original(name, args)
    monkeypatch.setattr(workspace.bridge, 'call', call)
    with pytest.raises(TimeoutError):
        run_morning(workspace)
    assert workspace.get_meta('last_morning')['status'] == 'needs_review'
    with pytest.raises(ValueError, match='will not automatically repeat'):
        run_morning(workspace)


def test_cross_process_morning_lock(workspace):
    import fcntl
    from campus_agent.morning import run_morning
    morning_profile(workspace)
    with (workspace.data / 'morning.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='already active'):
            run_morning(workspace)


def test_explicit_required_experience_is_separate_from_keyword_overlap(workspace, role):
    from campus_agent.morning import shortlist
    profile = morning_profile(workspace)
    description = 'Apply in Melbourne Australia. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.\nEssential\nStrong commercial experience as a Software Engineer\nStrong development experience with .NET / C#\nDesirable\nKubernetes\n'
    assessment = shortlist(role.model_copy(update={'description': description}), profile)
    assert not assessment['selected']
    assert any('.NET' in r for r in assessment['reasons'])
    assert any('software-engineering' in r for r in assessment['reasons'])
    assert not any('Kubernetes' in r for r in assessment['reasons'])
    study = description.split('\nEssential')[0] + '\nSpecialist/Technical Expertise/Qualifications\nFormal tertiary qualifications in Information Systems or related discipline\n'
    assert any('tertiary' in r for r in shortlist(role.model_copy(update={'description': study}), profile)['reasons'])


def test_listing_reader_removes_numbered_navigation_before_heading():
    text = 'L1: Login navigation\nL2: # Systems Specialist\nL3: Apply in Australia. Job details here.\nL4: ## Similar jobs\nL5: Unsupported skills from another job'
    result = readable_listing(text, 'Systems Specialist')
    assert result.startswith('# Systems Specialist')
    assert 'Login navigation' not in result and 'Unsupported skills' not in result


def test_packet_rules_preserve_facts_and_hold_missing_referees(workspace, role):
    workspace.save_profile(workspace.profile.model_copy(update={'references_mode': 'named'}))
    workspace.add_job(role, full=True)
    result = workspace.prepare(role.identity)
    assert result['quality']['passed'] and not result['quality']['delivery_ready']
    with pytest.raises(ValueError, match='Named referee details'):
        workspace.gmail_packet(role.identity, send=True)
    assert not any(name == 'gmail.send_email' for name, _ in workspace.bridge.calls)


def test_named_referees_render_only_after_sharing_confirmation(workspace, role):
    from campus_agent.models import Referee
    from pypdf import PdfReader
    ref = Referee(name='Confirmed Referee', role='IT Manager', organization='Example Company',
                  relationship='Former manager', email='referee@example.com', phone='0400 111 222')
    workspace.save_profile(workspace.profile.model_copy(update={'references_mode': 'named', 'referees': [ref]}))
    workspace.add_job(role, full=True)
    first = workspace.prepare(role.identity)
    text = '\n'.join(p.extract_text() for p in PdfReader(Path(first['packet']) / 'Resume.pdf').pages)
    assert ref.email not in text and not first['quality']['delivery_ready']
    ref.sharing_confirmed = True
    workspace.save_profile(workspace.profile.model_copy(update={'referees': [ref]}))
    result = workspace.prepare(role.identity)
    assert result['quality']['delivery_ready']
    reader = PdfReader(Path(result['packet']) / 'Resume.pdf')
    text = '\n'.join(p.extract_text() for p in reader.pages)
    assert 'REFERENCES' in text and ref.name in text and ref.email in text and ref.phone in text
    assert all(abs(float(p.mediabox.width) - 595.276) < 1 for p in reader.pages)
    workspace.gmail_packet(role.identity, send=True)


@pytest.mark.parametrize('change', ['fact', 'cover', 'profile', 'pdf', 'focus'])
def test_delivery_harness_holds_tampered_or_stale_packets(workspace, role, change):
    workspace.add_job(role, full=True)
    directory = Path(workspace.prepare(role.identity)['packet'])
    if change in {'fact', 'cover', 'focus'}:
        p = directory / 'tailoring.json'
        prepared = json.loads(p.read_text())
        if change == 'fact':
            prepared['experience'][0]['bullets'][0] += ' Saved 99% of annual costs.'
        elif change == 'cover':
            prepared['cover_letter'][1] = 'I am applying to an unrelated employer.'
        else:
            prepared['role_type_id'] = 'applications'
        p.write_text(json.dumps(prepared))
    elif change == 'profile':
        workspace.save_profile(workspace.profile.model_copy(update={'phone': '0412 345 678'}))
    else:
        p = directory / 'Resume.pdf'
        p.write_bytes(p.read_bytes() + b'\nChanged after preparation\n')
    with pytest.raises(ValueError, match='quality rules|changed after preparation'):
        workspace.gmail_packet(role.identity, send=True)
    assert not any(name == 'gmail.send_email' for name, _ in workspace.bridge.calls)


def test_pdf_rule_catches_coloured_text(workspace, role):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    from campus_agent.packet_checks import check_pdfs
    workspace.add_job(role, full=True)
    directory = Path(workspace.prepare(role.identity)['packet'])
    path = directory / 'Resume.pdf'
    writer = PdfWriter(clone_from=path)
    page = writer.pages[0]
    stream = DecodedStreamObject()
    original = page.get_contents().get_data()
    assert b'0 0 0 rg' in original
    stream.set_data(original.replace(b'0 0 0 rg', b'1 0 0 rg'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    with path.open('wb') as output:
        writer.write(output)
    assert any('text must be black' in e for e in check_pdfs(directory, role, workspace.profile)['errors'])


def test_board_metadata_is_held_before_packet_generation(workspace, role):
    bad = role.model_copy(update={'employer': 'Example Employer | LinkedIn Jobs'})
    workspace.add_job(bad, full=True)
    with pytest.raises(ValueError, match='job-board metadata'):
        workspace.prepare(bad.identity)


@pytest.mark.parametrize('title,expected', [
    ('IT Systems Specialist','it_systems'), ('Power Platform Consultant','automation'),
    ('AI Enablement Specialist','ai_enablement'), ('AI Operations Analyst','ai_operations'),
    ('Business Analyst','business_analysis'), ('Technology Applications Specialist','applications'),
    ('IT Project Coordinator','project_delivery'),
    ('IT Portfolio and Delivery Coordinator','project_delivery'),
    ('IT Service Delivery Coordinator','service_delivery'),
    ('Implementation Specialist','service_delivery'),
    ('Release Coordinator','service_delivery')])
def test_role_families_cover_the_application_examples(role, title, expected):
    from campus_agent.role_types import matched_types
    assert expected in [r['id'] for r in matched_types(role.model_copy(update={'title':title}))]


def test_selected_roles_control_search_and_shortlist(workspace, role):
    from campus_agent.role_types import ROLE_TYPES,query_plan
    from campus_agent.morning import shortlist
    queries=query_plan(workspace.preferences)
    assert all(any(item['queries'][0] in q for q in queries) for item in ROLE_TYPES)
    extended=query_plan(workspace.preferences,extended=True)
    assert len(extended)==24
    assert all(any('site:'+domain in q for q in extended) for domain in ['seek.com.au/job','au.linkedin.com/jobs/view','au.indeed.com/viewjob'])
    preferences=workspace.preferences.model_copy(update={'role_types':['project_delivery']})
    workspace.save_preferences(preferences)
    assert all('project' in q.lower() or 'delivery' in q.lower() for q in query_plan(preferences))
    profile=morning_profile(workspace)
    job=role.model_copy(update={'title':'IT Project Coordinator','description':'Apply in Melbourne Australia. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.'})
    assert shortlist(job,profile,preferences)['selected']
    other=preferences.model_copy(update={'role_types':['applications']})
    assert not shortlist(job,profile,other)['selected']
    with pytest.raises(ValueError,match='role type'):
        workspace.save_preferences(preferences.model_copy(update={'role_types':[]}))


def test_delivery_focus_uses_technology_experience_and_selected_search(workspace, role):
    from campus_agent.role_types import matched_types, query_plan
    from campus_agent.morning import shortlist
    preferences=workspace.preferences.model_copy(update={'role_types':['service_delivery']})
    assert all('delivery' in q.lower() or 'implementation' in q.lower() for q in query_plan(preferences))
    job=role.model_copy(update={'title':'IT Service Delivery Coordinator','description':'Apply in Melbourne Australia. Coordinate Python automation and Microsoft Excel reporting, SharePoint support and process automation for colleagues.'})
    assert shortlist(job,morning_profile(workspace),preferences)['selected']
    for title in ['Delivery Driver','Courier Driver','Food Delivery Partner']:
        assert not matched_types(job.model_copy(update={'title':title}),preferences.role_types)
    unsupported=job.model_copy(update={'description':job.description+'\nRequirements:\n5+ years of service delivery management experience.'})
    assert any('years' in reason for reason in shortlist(unsupported,workspace.profile,preferences)['reasons'])


def test_application_focus_ranks_original_facts_without_new_claims(workspace, role):
    from campus_agent.models import Experience
    from campus_agent.tailor import local_selection,prepare_text
    p=workspace.profile.model_copy(update={'experience':[Experience(role='IT Specialist',organization='Employer',dates='2021-present',bullets=[
        'Created AI Hub guidance and gave a demonstration for colleagues.',
        'Administer NetSuite ERP applications and test vendor releases with sandbox UAT.'])]})
    job=role.model_copy(update={'title':'Applications Specialist','description':'Support business platforms and work with users and vendors.'})
    result=prepare_text(job,p,'local',role_type_id='applications')
    assert result['experience'][0]['bullets'][0]==p.experience[0].bullets[1]
    assert set(result['experience'][0]['bullets'])==set(p.experience[0].bullets)


def test_role_example_import_preserves_confirmed_profile(workspace,monkeypatch):
    before=workspace.profile.model_dump()
    original=workspace.bridge.call
    def call(name,args=None):
        if name=='google_drive.get_file_metadata':
            return {'id':args['fileId'],'title':'Alex_Example_Cover_Letter_Davidson.pdf','url':'https://drive.google.com/observed-example'}
        if name=='google_drive.fetch':
            return {'content':'Confirmed application example. ' * 20}
        return original(name,args)
    monkeypatch.setattr(workspace.bridge,'call',call)
    source=workspace.import_source('real-provider-id','example')
    assert source['role_types']==['business_analysis','project_delivery']
    assert workspace.profile.model_dump()==before
    assert json.loads((workspace.data/'source-documents.json').read_text())[0]['id']=='real-provider-id'


@pytest.mark.parametrize('suitable',[True,False])
def test_check_and_prepare_holds_unmatched_roles_before_any_cloud_write(workspace,role,monkeypatch,suitable):
    morning_profile(workspace)
    title='IT Systems Specialist' if suitable else 'Head of IT'
    job=role.model_copy(update={'title':title,'description':'Apply in Melbourne Australia. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.'})
    workspace.add_job(job)
    monkeypatch.setattr(workspace,'hydrate',lambda job_id:workspace.add_job(job,full=True))
    result=workspace.check_prepare(job.identity)
    if suitable:
        assert result['quality']['delivery_ready']
    else:
        assert result['held'] and not workspace.store.get(job.identity)['packet_dir']
    assert not any(name in {'gmail.send_email','gmail.create_draft','google_drive.upload_file'} for name,_ in workspace.bridge.calls)


def test_listing_budget_is_shared_across_selected_role_types():
    from campus_agent.role_types import spread_candidates
    rows=[{'id':str(n),'role_types':[{'id':'it_systems'}]} for n in range(10)]
    rows += [{'id':'project','role_types':[{'id':'project_delivery'}]}, {'id':'outside','role_types':[{'id':'applications'}]}]
    result=spread_candidates(rows,['it_systems','project_delivery'])
    assert [r['id'] for r in result[:2]]==['0','project']
    assert 'outside' not in [r['id'] for r in result]


def test_transferable_business_experience_can_match_without_named_software(workspace,role):
    from campus_agent.models import Experience
    from campus_agent.morning import shortlist
    p=workspace.profile.model_copy(update={'skills':['Python','Microsoft Excel'],'experience':[
        Experience(role='IT Specialist',organization='Employer',dates='2021-present',bullets=[
            'Map processes with stakeholders, translating requirements into workflows and user guides.',
            'Created a guide to the governed AI Hub and gave a live demonstration.'])]})
    job=role.model_copy(update={'title':'AI Business Analyst','description':'Apply in Melbourne Australia. Lead discovery and workflow reviews, gather business requirements and help teams with AI adoption.'})
    result=shortlist(job,p)
    assert result['selected'] and not result['skills']
    assert len(result['capabilities'])>=2 and len(result['supporting_facts'])==2
    assert all(e['fact'] in p.experience[0].bullets for e in result['capabilities'])
    constrained=job.model_copy(update={'description':job.description+'\nWhat we’re looking for\n3+ years in consulting, business analysis or operations improvement.\nWhy join\nBenefits and flexibility.'})
    assert not shortlist(constrained,p)['selected']
    assert any('years' in r for r in shortlist(constrained,p)['reasons'])


def test_aggregate_question_pages_are_not_individual_jobs():
    result=search_results({'text':'What AI Enablement Jobs Are Near Me? (https://jobs.example/jobs/ai-enablement)\nAn aggregate of many roles across Australia.'})
    assert result==[]


def test_extra_search_phrases_are_optional(workspace):
    workspace.save_preferences(workspace.preferences.model_copy(update={'keywords':[],'use_custom_keywords':False}))
    from campus_agent.role_types import query_plan
    assert len(query_plan(workspace.preferences))==10
    with pytest.raises(ValueError,match='extra search phrases'):
        workspace.save_preferences(workspace.preferences.model_copy(update={'use_custom_keywords':True}))


def test_succeed_requirements_hold_unsupported_platform_specialism(workspace,role):
    from campus_agent.morning import shortlist
    job=role.model_copy(update={'title':'Power Platform Specialist','description':"Apply in Melbourne Australia. Power Automate and Microsoft Excel workflows.\nWhat you'll need to succeed:\n5+ years hands-on Power Platform experience. Experience with Microsoft Dataverse.\nWhat we offer\nBenefits."})
    result=shortlist(job,morning_profile(workspace))
    assert not result['selected']
    assert any('Dataverse' in r for r in result['reasons'])
    assert any('years' in r for r in result['reasons'])


@pytest.mark.parametrize('signal',['expired_jd_redirect','jobnotfound=true'])
def test_expired_redirect_does_not_replace_original_listing(workspace,role,monkeypatch,signal):
    workspace.add_job(role)
    monkeypatch.setattr(workspace.bridge,'call',lambda *args,**kwargs:{'content':signal+'\n'+'Unrelated search result '*30})
    with pytest.raises(ValueError,match='expired or redirects'):
        workspace.hydrate(role.identity)
    assert workspace.job(role.identity)[1].description==role.description


def test_resume_bullets_stay_complete_on_one_page(workspace,role,tmp_path):
    from campus_agent.models import Experience
    from campus_agent.tailor import prepare_text
    from campus_agent.documents import generate_documents
    from pypdf import PdfReader
    facts=[f'Coordinated delivery item {n}, gathering stakeholder requirements, supporting testing and documenting handover. Maintained accurate records for the business and resolved issues with internal teams and external vendors before the agreed release date.' for n in range(18)]
    p=workspace.profile.model_copy(update={'experience':[Experience(role='IT Specialist',organization='Example',dates='2021-present',bullets=facts)]})
    generate_documents(tmp_path,role,p,prepare_text(role,p,'local'))
    pages=[re.sub(r'\s+',' ',page.extract_text()) for page in PdfReader(tmp_path/'Resume.pdf').pages]
    assert len(pages)>1
    assert all(any(fact in page for page in pages) for fact in facts)


def test_morning_and_afternoon_are_independent_but_never_repeat_jobs(workspace,role,monkeypatch):
    from campus_agent.morning import run_morning
    from datetime import datetime
    from zoneinfo import ZoneInfo
    morning_profile(workspace)
    text='Apply in Melbourne Australia. Python automation for monthly Microsoft Excel reporting. Supported SharePoint systems and process automation for colleagues.'
    first=role.model_copy(update={'description':text})
    second=first.model_copy(update={'url':'https://example.com/job/new-afternoon-role','title':'IT Systems Support Specialist'})
    workspace.add_job(first,full=True)
    monkeypatch.setattr(workspace,'discover',lambda extended=False:{'found':1,'errors':[]})
    monkeypatch.setattr(workspace,'alerts',lambda:{'message_ids':[]})
    monkeypatch.setattr(workspace,'hydrate',lambda job_id:None)
    now=datetime(2026,10,16,8,tzinfo=ZoneInfo('Australia/Melbourne'))
    am=run_morning(workspace,now=now)
    workspace.add_job(second,full=True)
    pm=run_morning(workspace,now=now.replace(hour=16),session='afternoon')
    assert [p['job_id'] for p in am['packets']]==[first.identity]
    assert [p['job_id'] for p in pm['packets']]==[second.identity]
    assert run_morning(workspace,now=now.replace(hour=16),session='afternoon')['already_done']
    assert workspace.get_meta('morning:2026-10-16')['status']=='done'
    assert workspace.get_meta('afternoon:2026-10-16')['status']=='done'
    assert len([n for n,_ in workspace.bridge.calls if n=='gmail.send_email'])==4


def strong_alert_profile(workspace):
    from campus_agent.models import Experience
    p=workspace.profile.model_copy(update={'skills':['Python','Power Automate','SharePoint','Microsoft 365'], 'experience':[
        Experience(role='IT Specialist',organization='Confirmed Employer',dates='2021-present',bullets=[
            'Built a Power Automate workflow using SharePoint for business teams.',
            'Map processes with stakeholders, translating requirements into practical workflows.',
            'Manage IT projects with stakeholder coordination, testing and handover.',
            'Administer Microsoft 365 accounts and resolve ServiceNow incidents.',
            'Created an AI Hub guide and supported AI adoption for colleagues.'])]})
    workspace.save_profile(p)
    approve_sample_style(workspace)
    workspace.save_preferences(workspace.preferences.model_copy(update={'morning_enabled':True,'standout_enabled':True,'morning_recipient':'owner@example.com','morning_save_drive':False}))
    return p


def test_standout_requires_strong_local_confirmed_fit(workspace,role):
    from campus_agent.morning import standout_assessment
    p=strong_alert_profile(workspace)
    j=role.model_copy(update={'title':'AI Enablement Specialist','description':'Apply in Melbourne Australia. Python, Power Automate, SharePoint and Microsoft 365. Gather business requirements, coordinate projects and handover, support systems and AI adoption with practical workflows.'})
    assert standout_assessment(j,p,workspace.preferences)['selected']
    assert standout_assessment(j.model_copy(update={'description':j.description.replace('Melbourne Australia','Scoresby VIC')}),p,workspace.preferences)['selected']
    for change in [
        {'title':'AI Enablement Lead'},
        {'description':j.description.replace('Melbourne','Sydney')},
        {'description':j.description+'\nAbout you\nJira and Confluence experience required.'},
        {'description':j.description+'\nAustralian citizenship required.'}]:
        assert not standout_assessment(j.model_copy(update=change),p,workspace.preferences)['selected']
    assert standout_assessment(j.model_copy(update={'description':j.description.replace('Melbourne','Sydney')+' Fully remote in Australia.'}),p,workspace.preferences)['selected']


def test_standout_sends_one_packet_without_empty_receipts_or_digest_duplicates(workspace,role,monkeypatch):
    from campus_agent.morning import run_morning
    from datetime import datetime
    from zoneinfo import ZoneInfo
    strong_alert_profile(workspace)
    j=role.model_copy(update={'title':'AI Enablement Specialist','description':'Apply in Melbourne Australia. Python, Power Automate, SharePoint and Microsoft 365. Gather business requirements, coordinate projects and handover, support systems and AI adoption with practical workflows.'})
    workspace.add_job(j,full=True)
    monkeypatch.setattr(workspace,'discover',lambda extended=False:{'found':1,'errors':[]})
    monkeypatch.setattr(workspace,'alerts',lambda:{'message_ids':[]})
    monkeypatch.setattr(workspace,'hydrate',lambda job_id:None)
    now=datetime(2026,10,16,2,15,tzinfo=ZoneInfo('Australia/Melbourne'))
    result=run_morning(workspace,now=now,session='standout')
    assert len(result['packets'])==1
    sends=[a for n,a in workspace.bridge.calls if n=='gmail.send_email']
    assert len(sends)==1 and sends[0]['subject'].startswith('Standout job:')
    assert run_morning(workspace,now=now,session='standout')['already_done']
    assert run_morning(workspace,now=now.replace(hour=3),session='standout')['quiet']
    assert not run_morning(workspace,now=now.replace(hour=8))['packets']
    assert len([n for n,_ in workspace.bridge.calls if n=='gmail.send_email'])==2 # Alert plus morning receipt.


def test_standout_pause_is_independent_and_invalid_sessions_do_nothing(workspace):
    from campus_agent.morning import run_morning
    morning_profile(workspace)
    with pytest.raises(ValueError,match='Standout alerts are paused'):
        run_morning(workspace,session='standout')
    with pytest.raises(ValueError,match='Unknown email check session'):
        run_morning(workspace,session='anything')
    assert not workspace.bridge.calls


def application_mail(message_id='a123456789',subject='Thanks for your application for Systems Specialist',body='Thank you for your application. We are thrilled you would like to work with us at Example Employer!',date='Mon, 12 Oct 2026 00:00:00 +0000',sender='no-reply@us.greenhouse-mail.io',thread='thread-one'):
    return {'id':message_id,'thread_id':thread,'payload':{'headers':[{'name':'Subject','value':subject},{'name':'From','value':sender},{'name':'Date','value':date}], 'mime_type':'text/plain','body':{'content':body}}}


def test_application_history_keeps_later_rejection_when_receipt_arrives_last():
    from campus_agent.applications import parse_application,rebuild_applications
    received=parse_application(application_mail())
    rejected=parse_application(application_mail(message_id='a234567890',subject='An update on your application with Example Employer',body='Thank you for your application for our Systems Specialist role. We have decided not to move forward with your application.',date='Wed, 14 Oct 2026 00:00:00 +0000'))
    rows=rebuild_applications([rejected,received])
    assert len(rows)==1 and rows[0]['status']=='rejected'
    assert rows[0]['applied_at'].startswith('2026-10-12')
    assert rows[0]['last_update_at'].startswith('2026-10-14')
    assert len(rows[0]['events'])==2


def test_application_tracking_requires_identity_and_never_counts_packet_or_rebate():
    from campus_agent.applications import parse_application,candidate_metadata
    assert parse_application(application_mail(subject='Your application',body='Thank you for your application.'))['needs_review']
    assert candidate_metadata(application_mail(subject='Interview invitation',sender='Jane <jane@employer.example>'))
    for subject,sender in [('Job Agent: Systems Specialist — packet for review','owner@example.com'),('Application outcome - registration rebate','no-reply@service.vic.gov.au'),('Alex, your credit limit increase application','bank@example.com'),('Interview advice - new jobs','newsletter@example.com')]:
        assert not candidate_metadata(application_mail(subject=subject,sender=sender))


def test_application_status_reply_can_inherit_only_the_observed_thread():
    from campus_agent.applications import parse_application,rebuild_applications
    known=rebuild_applications([parse_application(application_mail())])
    reply=application_mail(message_id='a345678901',subject='Interview invitation',body='We invite you to an interview with our team.',date='Thu, 15 Oct 2026 00:00:00 +0000')
    result=parse_application(reply,known)
    assert result['status']=='interview' and result['company']=='Example Employer' and not result['needs_review']
    reply['thread_id']='unrelated-thread'
    assert parse_application(reply,known)['needs_review']


def test_application_receipt_marks_only_matching_company_role_and_preserves_notes(workspace,role,monkeypatch):
    from campus_agent.applications import parse_application,ingest_events
    workspace.add_job(role,full=True)
    with workspace.store.connect() as db:db.execute('UPDATE job_details SET notes=? WHERE job_id=?',('User note to preserve',role.identity))
    other=Job.model_validate({**role.model_dump(mode='json'),'employer':'Different Employer','url':'https://example.com/job/other-company'})
    workspace.add_job(other,full=True)
    first=ingest_events(workspace,[parse_application(application_mail())])
    assert first['new_events']==1 and first['linked_jobs']==1
    assert ingest_events(workspace,[parse_application(application_mail())])['new_events']==0
    rows={r['id']:r for r in workspace.jobs()}
    assert rows[role.identity]['stage']=='applied' and rows[role.identity]['notes']=='User note to preserve'
    assert rows[other.identity]['stage']=='saved'
    monkeypatch.setattr(workspace,'hydrate',lambda *_:pytest.fail('Already applied role must not be refreshed or prepared'))
    assert workspace.check_prepare(role.identity)['held']


def test_application_sync_filters_metadata_before_body_reads_and_is_incremental(workspace,monkeypatch):
    messages={'good':application_mail(message_id='good'),'bank':application_mail(message_id='bank',subject='Credit limit application',sender='bank@example.com')}
    calls=[]
    def call(name,args):
        calls.append((name,args))
        if name=='gmail.search_email_ids':return {'message_ids':['good','bank']}
        if name=='gmail.read_email':
            assert args['format']=='metadata'
            return {'id':args['message_id'],'payload':{'headers':messages[args['message_id']]['payload']['headers']}}
        if name=='gmail.batch_read_email':
            assert args['message_ids']==['good']
            return {'responses':[messages['good']]}
        pytest.fail('Unexpected connector operation: '+name)
    monkeypatch.setattr(workspace.bridge,'call',call)
    first=workspace.sync_applications()
    assert first['bodies_read']==1 and first['new_events']==1 and not first['more_available']
    second=workspace.sync_applications()
    assert second['headers_checked']==second['bodies_read']==second['new_events']==0
    assert len([n for n,_ in calls if n=='gmail.batch_read_email'])==1


def test_scheduled_check_syncs_applications_before_selecting_candidates(workspace,role,monkeypatch):
    from campus_agent.morning import run_morning
    from campus_agent.applications import parse_application,ingest_events
    morning_profile(workspace)
    workspace.save_preferences(workspace.preferences.model_copy(update={'application_sync_enabled':True}))
    workspace.add_job(role,full=True)
    monkeypatch.setattr(workspace,'sync_applications',lambda:ingest_events(workspace,[parse_application(application_mail())]))
    monkeypatch.setattr(workspace,'discover',lambda extended=False:{'found':1,'errors':[]})
    monkeypatch.setattr(workspace,'alerts',lambda:{'message_ids':[]})
    monkeypatch.setattr(workspace,'hydrate',lambda *_:pytest.fail('Applied role must not be considered'))
    report=run_morning(workspace)
    assert report['applications']['applications'][0]['status']=='received'
    assert report['packets']==[] and report['listings_checked']==0
    sends=[a for n,a in workspace.bridge.calls if n=='gmail.send_email']
    assert len(sends)==1 and 'Application tracker: 1 recorded' in sends[0]['payload']['body']['content']


def test_application_sync_resolves_interview_returned_before_same_batch_receipt(workspace,monkeypatch):
    messages=[application_mail(message_id='interview',subject='Interview invitation',body='We invite you to an interview with our team.',date='Thu, 15 Oct 2026 00:00:00 +0000'),application_mail(message_id='receipt')]
    def call(name,args):
        if name=='gmail.search_email_ids':return {'message_ids':['interview','receipt']}
        if name=='gmail.read_email':return next(m for m in messages if m['id']==args['message_id'])
        if name=='gmail.batch_read_email':return {'responses':messages}
        pytest.fail(name)
    monkeypatch.setattr(workspace.bridge,'call',call)
    result=workspace.sync_applications()
    assert len(result['applications'])==1 and not result['needs_review']
    assert result['applications'][0]['status']=='interview'
    assert len(result['applications'][0]['events'])==2


@pytest.mark.parametrize('text,posted,closes',[
    ('Posted August 18, 2026\nApplications close: 11:59pm 25 October 2026.','2026-08-18','2026-10-25'),
    ('Date posted: 16/10/2026\nEnd Date: 31/10/2026','2026-10-16','2026-10-31'),
    ('"datePosted": "2026-10-16T23:59:00Z", "validThrough": "2026-11-01T23:59:00+11:00"','2026-10-17','2026-11-01'),
    ('Crawled: 2 days ago; Published: 2 months ago;',None,None),
    ('Posted 31 February 2026\nCloses 35/10/2026',None,None),
])
def test_listing_dates_use_explicit_valid_source_dates(text,posted,closes):
    from campus_agent.listing_info import extract_dates
    result=extract_dates(text)
    assert result['posted_on']==posted and result['closes_on']==closes


def test_listing_dates_keep_relative_wording_without_inventing_absolute_date():
    from campus_agent.listing_info import extract_dates,clean_summary
    info=extract_dates('Posted 2 weeks ago. Open until filled.\nRecommended Jobs\nPosted 1 October 2026. Closes 31 October 2026.')
    assert info['posted_on'] is None and info['closes_on'] is None
    assert info['posted_hint']=='2 weeks ago (source wording)' and info['closing_hint']=='Open until filled'
    assert clean_summary('[wordlim: 200] Published: 2 months ago; Crawled: yesterday; Real role details.')=='Real role details.'


def test_top_listing_and_dates_do_not_change_packet_or_tracking(workspace,role):
    job=role.model_copy(update={'description':role.description+' Posted 1 October 2026. Applications close 31 October 2026.'})
    workspace.add_job(job,full=True)
    packet=workspace.prepare(job.identity)['packet']
    with workspace.store.connect() as db:db.execute('UPDATE job_details SET notes=? WHERE job_id=?',('Existing note',job.identity))
    original=workspace.store.get(job.identity)
    workspace.set_top_listing(job.identity,True)
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['top_listing'] and row['top_saved'] and row['listing']['posted_on']=='2026-10-01'
    assert row['listing']['closes_on']=='2026-10-31' and row['notes']=='Existing note'
    assert row['packet_dir']==packet and row['revision']==original['revision']
    workspace.set_top_listing(job.identity,False)
    assert not next(r for r in workspace.jobs() if r['id']==job.identity)['top_saved']
    with pytest.raises(ValueError,match='true or false'):workspace.set_top_listing(job.identity,'true')


def test_closed_listing_metadata_is_retained_even_when_read_is_held(workspace,role,monkeypatch):
    workspace.add_job(role)
    monkeypatch.setattr(workspace.bridge,'call',lambda *_args,**_kwargs:{'content':'Posted 1 January 2020. Applications close 31 January 2020. '+'Original role responsibilities and requirements. '*10})
    with pytest.raises(ValueError,match='closing date'):workspace.hydrate(role.identity)
    row=next(r for r in workspace.jobs() if r['id']==role.identity)
    assert row['listing']['closes_on']=='2020-01-31' and row['listing']['closed']
    assert not row['top_match']


@pytest.mark.parametrize('description,location,cities,states,mode',[
    ('Location: Scoresby VIC, Australia\nPosted today','Scoresby VIC, Australia',[],['VIC'],''),
    ('Work format Hybrid Location North Sydney, Sydney NSW Region APAC','North Sydney, Sydney NSW',['Sydney'],['NSW'],'Hybrid'),
    ('Location: Sydney, NSW (Hybrid)\nOur Melbourne headquarters supports this team.','Sydney, NSW (Hybrid)',['Sydney'],['NSW'],'Hybrid'),
    ('Location: Remote (Australia)\nWork with our local team.','Remote (Australia)',[],[],'Remote'),
    ('Location: Boston, USA\nFull time role.','Boston, USA',[],[],''),
    ('Support remote users in many countries.','Location not stated',[],[],''),
    ('Location: `` `` ``\nRead our company story.','Location not stated',[],[],''),
    ('Location: Regional VIC (Northwest) 3 days in-office, with future flexibility','Regional VIC (Northwest)',[],['VIC'],''),
    ('Melbourne, VIC\n# Role\nRecommended Jobs\nLocation: Perth, WA','Melbourne, VIC',['Melbourne'],['VIC'],''),
])
def test_location_is_listing_evidence_not_search_area(description,location,cities,states,mode):
    from campus_agent.locations import location_info
    result=location_info({'description':description,'location':'Melbourne Victoria Australia'},'Melbourne Victoria Australia')
    assert result['display']==location and result['cities']==cities and result['states']==states
    assert result['arrangement']==mode


def test_location_display_preserves_packet_and_explicit_manual_location(workspace,role):
    job=role.model_copy(update={'description':'Location: Sydney, NSW (Hybrid)\n'+role.description})
    workspace.add_job(job,full=True)
    previous=workspace.store.get(job.identity)
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['location_info']['cities']==['Sydney']
    assert workspace.store.get(job.identity)['revision']==previous['revision']
    workspace.set_meta('location_override:'+job.identity,'Geelong, VIC')
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['location_info']['display']=='Geelong, VIC'
    assert row['location_info']['states']==['VIC']


def test_skill_overlap_is_profile_phrase_coverage_not_arbitrary_search_score(workspace,role):
    workspace.save_profile(workspace.profile.model_copy(update={'skills':['Python','SQL','TypeScript','Java']}))
    job=role.model_copy(update={'description':'## The role\nUse Python for reporting.\n## Similar jobs\nSQL, TypeScript and Java roles elsewhere.'})
    workspace.add_job(job,full=True)
    original=workspace.store.get(job.identity)
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['skill_overlap']=={'percent':25,'matched':1,'total':4,'skills':['Python']}
    assert workspace.store.get(job.identity)['revision']==original['revision']
    workspace.profile=None
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['skill_overlap']['percent'] is None


def test_corrected_referee_marks_existing_packet_stale_until_regenerated(workspace,role):
    from campus_agent.models import Referee
    p=workspace.profile.model_copy(update={'references_mode':'named','referees':[Referee(name='Casey Example',role='IT Location Manager',organization='Example Manufacturing',phone='0400000000',sharing_confirmed=True)]})
    workspace.save_profile(p)
    workspace.add_job(role,full=True)
    packet=workspace.prepare(role.identity)['packet']
    workspace.save_profile(p.model_copy(update={'referees':[p.referees[0].model_copy(update={'role':'IT Systems and Operations Manager'})]}))
    row=next(r for r in workspace.jobs() if r['id']==role.identity)
    assert row['profile_stale'] and not row['quality']['delivery_ready']
    assert row['packet_dir']==packet
    assert any('regenerate' in error.lower() for error in row['quality']['errors'])


def setup_automatic_top_role(workspace,role):
    from campus_agent.models import Experience
    workspace.save_profile(workspace.profile.model_copy(update={'skills':['Python'], 'experience':[Experience(organization='Example Employer',role='IT Support Specialist',dates='2021 - Present',bullets=['Built a Python utility used monthly by Finance to convert payment files.'])]}))
    job=role.model_copy(update={'title':'Automation Specialist','location':'Melbourne, VIC','description':'Location: Melbourne, VIC\nRequirements\n- Python workflow automation experience.'})
    workspace.add_job(job,full=True)
    return job


def test_automatic_top_includes_threshold_boundary_and_preserves_manual_pins(workspace,role):
    job=setup_automatic_top_role(workspace,role)
    workspace.save_preferences(workspace.preferences.model_copy(update={'auto_top_enabled':True,'auto_top_threshold':100}))
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['fit']['percent']==100 and row['top_match'] and row['top_listing'] and not row['top_saved']
    workspace.set_top_listing(job.identity,True)
    workspace.save_preferences(workspace.preferences.model_copy(update={'auto_top_enabled':False}))
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert not row['top_match'] and row['top_saved'] and row['top_listing']
    assert workspace.preferences.auto_top_threshold==100


def test_requirement_gap_removes_automatic_top_but_keeps_manual_pin(workspace,role):
    job=setup_automatic_top_role(workspace,role)
    assert next(r for r in workspace.jobs() if r['id']==job.identity)['top_match']
    workspace.set_top_listing(job.identity,True)
    workspace.save_preferences(workspace.preferences.model_copy(update={'auto_top_threshold':0}))
    changed=job.model_copy(update={'description':job.description+'\n- Kubernetes development experience required.'})
    workspace.add_job(changed,full=True)
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['fit']['status']=='Needs review' and not row['top_match']
    assert row['top_saved'] and row['top_listing']


@pytest.mark.parametrize('stage',['applied','archived'])
def test_automatic_top_excludes_applied_and_archived_roles(workspace,role,stage):
    job=setup_automatic_top_role(workspace,role)
    with workspace.store.connect() as db:db.execute('UPDATE job_details SET stage=? WHERE job_id=?',(stage,job.identity))
    row=next(r for r in workspace.jobs() if r['id']==job.identity)
    assert row['fit']['status']=='Good match' and not row['top_match']


def test_automatic_top_excludes_unread_and_closed_roles_and_validates_threshold(workspace,role):
    from pydantic import ValidationError
    from campus_agent.workspace import Preferences
    job=setup_automatic_top_role(workspace,role)
    with workspace.store.connect() as db:db.execute('UPDATE job_details SET full_description=0 WHERE job_id=?',(job.identity,))
    assert not next(r for r in workspace.jobs() if r['id']==job.identity)['top_match']
    workspace.add_job(job.model_copy(update={'description':job.description+'\nApplications close 1 January 2020.'}),full=True)
    assert not next(r for r in workspace.jobs() if r['id']==job.identity)['top_match']
    for threshold in [-1,101]:
        with pytest.raises(ValidationError):Preferences(auto_top_threshold=threshold)


def test_location_reads_full_state_names_and_compact_board_headers():
    from campus_agent.locations import location_info
    job={'description':'SoftwareOne North Sydney, New South Wales, Australia','location':'Melbourne Victoria Australia'}
    assert location_info(job,'Melbourne Victoria Australia')['states']==['NSW']
    job['description']='Mid levelFull-timeHybridNewcastle NSW, AustraliaPosted 7 months ago'
    assert location_info(job,'Melbourne Victoria Australia')['display']=='Newcastle NSW'


def test_prepare_resolves_official_employer_and_persists_identity_only_correction(workspace,role):
    job=role.model_copy(update={'employer':'Employer on job listing','url':'https://openai.com/careers/example/','description':role.description+'\nAbout OpenAI\nOpenAI is an AI research and deployment company.'})
    workspace.add_job(job,full=True)
    revision=workspace.store.get(job.identity)['revision']
    result=workspace.prepare(job.identity)
    saved=workspace.job(job.identity)[1]
    assert saved.employer=='OpenAI'
    assert workspace.store.get(job.identity)['revision']==revision
    assert result['quality']['passed']
    from pypdf import PdfReader
    assert 'OpenAI' in ''.join(p.extract_text() for p in PdfReader(Path(result['packet'])/'Cover Letter.pdf').pages)


def test_unverified_product_mention_is_held_with_edit_instructions(workspace,role):
    job=role.model_copy(update={'employer':'Employer on job listing','description':role.description+'\nUse OpenAI and Microsoft tools.'})
    workspace.add_job(job,full=True)
    with pytest.raises(ValueError,match='Edit details & notes'):
        workspace.prepare(job.identity)
    assert workspace.store.get(job.identity)['packet_dir']==''


@pytest.mark.parametrize('session', ['morning', 'afternoon', 'standout'])
def test_style_approval_blocks_all_automatic_sessions_before_any_connector_or_ledger(workspace, session):
    from campus_agent.morning import run_morning
    workspace.preferences = workspace.preferences.model_copy(update={
        'morning_enabled': True, 'standout_enabled': True, 'morning_recipient': 'owner@example.com'})
    workspace.bridge.calls.clear()
    with pytest.raises(ValueError, match='approve a current sample'):
        run_morning(workspace, session=session)
    assert workspace.bridge.calls == []
    assert workspace.get_meta('last_morning') is None


def test_document_style_sample_is_local_and_does_not_replace_real_packet(workspace, role):
    workspace.add_job(role, full=True)
    workspace.prepare(role.identity)
    before = workspace.store.get(role.identity)
    workspace.bridge.calls.clear()
    state = workspace.generate_style_sample(role.identity)
    assert state['sample_current'] and not state['approved']
    assert workspace.store.get(role.identity)['packet_dir'] == before['packet_dir']
    assert workspace.bridge.calls == []
    assert workspace.sample_file(state['sample']['id'], 'resume').is_file()
    assert 'directory' not in state['sample']
    with pytest.raises(ValueError, match='both'):
        workspace.approve_document_style(state['sample']['id'], state['fingerprint'], True, False)
    with pytest.raises(ValueError, match='outdated'):
        workspace.approve_document_style('old-sample', state['fingerprint'], True, True)
    result = workspace.approve_document_style(state['sample']['id'], state['fingerprint'], True, True)
    assert result['approved'] and workspace.require_style_approval()['approved']
    assert workspace.bridge.calls == []


@pytest.mark.parametrize('change', ['profile', 'style', 'sample', 'pdf'])
def test_style_approval_cannot_survive_changed_inputs_or_sample_files(workspace, role, change):
    workspace.add_job(role, full=True)
    state = workspace.generate_style_sample(role.identity)
    workspace.approve_document_style(state['sample']['id'], state['fingerprint'], True, True)
    if change == 'profile':
        workspace.save_profile(workspace.profile.model_copy(update={'phone':'0400 000 001'}))
    elif change == 'style':
        workspace.save_document_style({'tone':'warm'})
    elif change == 'sample':
        workspace.generate_style_sample(role.identity)
    else:
        with workspace.sample_file(state['sample']['id'], 'cover').open('ab') as stream:
            stream.write(b'\n%modified sample')
    assert not workspace.document_style_state()['approved']
    workspace.bridge.calls.clear()
    with pytest.raises(ValueError, match='Automatic emails are blocked'):
        workspace.gmail_packet(role.identity, send=True, automatic=True)
    assert workspace.bridge.calls == []


def test_style_choices_change_pdf_rendering_and_letter_without_changing_facts(workspace, role):
    from pypdf import PdfReader
    workspace.add_job(role, full=True)
    workspace.save_document_style({'layout':'comfortable','tone':'warm','letter_length':'brief','fact_order':'original','resume_pages':2})
    sample = workspace.generate_style_sample(role.identity)['sample']
    directory = workspace.sample_file(sample['id'], 'resume').parent
    prepared = json.loads((directory/'tailoring.json').read_text())
    assert prepared['experience'] == [e.model_dump() for e in workspace.profile.experience]
    assert prepared['skills'] == workspace.profile.skills
    text=' '.join(p.extract_text() for p in PdfReader(directory/'Cover Letter.pdf').pages)
    assert 'I would welcome the opportunity to join' in text
    assert len(PdfReader(directory/'Resume.pdf').pages) <= 2
    assert sample['quality']['delivery_ready']


def test_unapproved_style_cannot_enable_delivery_and_schema_rejects_unconstrained_instructions(workspace):
    with pytest.raises(ValueError, match='Automatic emails are blocked'):
        workspace.save_preferences(workspace.preferences.model_copy(update={'morning_enabled':True}))
    with pytest.raises(ValueError):
        workspace.save_document_style({'tone':'invent achievements'})
    with pytest.raises(ValueError):
        workspace.save_document_style({'custom_prompt':'claim a qualification'})


def test_style_approval_refuses_wrong_fingerprint_and_modified_pdf(workspace, role):
    workspace.add_job(role, full=True)
    state=workspace.generate_style_sample(role.identity)
    with pytest.raises(ValueError, match='outdated'):
        workspace.approve_document_style(state['sample']['id'], 'wrong', True, True)
    with workspace.sample_file(state['sample']['id'],'resume').open('ab') as f:
        f.write(b'\n%changed')
    with pytest.raises(ValueError, match='changed'):
        workspace.approve_document_style(state['sample']['id'], state['fingerprint'], True, True)
    assert not workspace.document_style_state()['approved']


def test_style_api_csrf_review_flags_and_inline_pdf_boundaries(workspace, role):
    workspace.add_job(role, full=True)
    client = TestClient(create_workspace_app(workspace), base_url='http://127.0.0.1:8877')
    page=client.get('/')
    token=re.search(r'const token="([^"]+)"',page.text)[1]
    headers={'origin':'http://127.0.0.1:8877','x-workspace-token':token}
    assert client.post('/api/document-style',json={'tone':'warm'}).status_code==403
    assert client.post('/api/document-style',headers=headers,json={'tone':'warm'}).status_code==200
    sample=workspace.generate_style_sample(role.identity)
    url='/api/document-style/samples/'+sample['sample']['id']+'/resume'
    response=client.get(url)
    assert response.status_code==200 and response.content.startswith(b'%PDF-')
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert "frame-ancestors 'none'" in page.headers['content-security-policy']
    assert client.get(url.replace('/resume','/unknown')).status_code==400
    preview=client.get(url+'/pages/1')
    assert preview.status_code==200 and preview.content.startswith(b'\x89PNG')
    assert preview.headers['cache-control']=='no-store'
    assert client.get(url+'/pages/0').status_code==400
    assert client.get(url+'/pages/100').status_code==400
    body={'sample_id':sample['sample']['id'],'fingerprint':sample['fingerprint'],'reviewed_resume':True,'reviewed_cover':False}
    assert client.post('/api/document-style/approve',headers=headers,json=body).status_code==400
    body['reviewed_cover']=True
    assert client.post('/api/document-style/approve',headers=headers,json=body).json()['approved']
    assert client.get('/api/state').json()['document_style']['approved']


def test_style_page_limit_holds_sample_without_discarding_source_facts(workspace, role):
    from campus_agent.models import Experience
    bullets=['Confirmed support responsibility '+str(i)+' with Microsoft Excel, Python and many colleagues across local operations. '*4 for i in range(45)]
    workspace.save_profile(workspace.profile.model_copy(update={'experience':[Experience(organization='Example Employer',role='IT Support',dates='2020-2026',bullets=bullets)]}))
    workspace.add_job(role, full=True)
    workspace.save_document_style({'layout':'comfortable','resume_pages':2})
    with pytest.raises(ValueError,match='page review limit'):
        workspace.generate_style_sample(role.identity)
    assert workspace.profile.experience[0].bullets==bullets
    assert workspace.get_meta('document_style_sample') is None
    assert not workspace.document_style_state()['approved']


def test_style_change_during_automatic_run_blocks_the_receipt(workspace, monkeypatch):
    from campus_agent.morning import run_morning
    morning_profile(workspace)
    monkeypatch.setattr(workspace,'discover',lambda extended=False:{'found':0,'errors':[]})
    def alerts():
        workspace.save_document_style({'tone':'direct'})
        return {'message_ids':[]}
    monkeypatch.setattr(workspace,'alerts',alerts)
    workspace.bridge.calls.clear()
    with pytest.raises(ValueError, match='Automatic emails are blocked'):
        run_morning(workspace)
    assert not any(name=='gmail.send_email' for name,_ in workspace.bridge.calls)
    assert workspace.get_meta('last_morning')['status']=='needs_review'


def test_style_preview_image_changes_invalidate_approval(workspace, role):
    workspace.add_job(role,full=True)
    state=workspace.generate_style_sample(role.identity)
    workspace.approve_document_style(state['sample']['id'],state['fingerprint'],True,True)
    image=workspace.sample_preview_file(state['sample']['id'],'resume',1)
    image.write_bytes(image.read_bytes()+b'modified')
    assert not workspace.document_style_state()['approved']
    with pytest.raises(ValueError, match='changed'):
        workspace.sample_preview_file(state['sample']['id'],'resume',1)


def test_legacy_style_sample_is_stale_and_can_be_reported_without_crashing(workspace):
    workspace.set_meta('document_style_sample',{'id':'legacy','fingerprint':'old','job_id':'old','job_title':'Old role','employer':'Example','created_at':'2026-10-01','quality':{'passed':True}})
    state=workspace.document_style_state()
    assert not state['sample_current'] and not state['approved']
    assert state['sample']['preview_pages'] is None
