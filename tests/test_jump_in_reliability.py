"""Regression checks for a new user pasting roles and using every card action,
with or without Codex connections. Synthetic identities and adverts only."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from campus_agent.connectors import ConnectorBridge, ConnectorError, ConnectorUnavailable
from campus_agent.fit import fit_assessment, stated_weights, word_stem
from campus_agent.listing_view import listing_view
from campus_agent.locations import location_info
from campus_agent.models import Experience, Job, Profile
from campus_agent.workspace import Preferences, Workspace
from campus_agent.workspace_web import create_workspace_app
from test_workspace import FakeBridge, profile, workspace  # noqa: F401 (fixtures)

FACTS = [
    'Administered Microsoft 365 and Entra ID accounts, licences and security groups for 250 staff.',
    'Resolved ServiceNow incidents and service requests across hardware, software and network issues.',
    'Built Power Automate approval workflows with SharePoint lists, live since 2023.',
    'Built a Python utility used monthly by Finance to convert payment files.',
    'Managed IT onboarding and offboarding for new starters, including laptops and accounts.',
]

STRONG_ADVERT = '''IT Systems Specialist
Example Health · Melbourne VIC · Full time · Hybrid

About the role
Join our small IT team supporting 300 staff across Melbourne.

About you
- Experience administering Microsoft 365 and Entra ID.
- Experience resolving incidents in ServiceNow.
- Experience building Power Automate workflows with SharePoint.

Salary: $95,000 - $105,000 + super
Applications close 30 November 2026.

How to apply
Apply online with your résumé and cover letter.'''

SUPPORT_ADVERT = '''IT Support Officer
Example Logistics · Melbourne VIC · Full time

About you
- Experience resolving hardware, software and network incidents.
- Experience managing onboarding and offboarding for staff.
- Experience supporting Windows laptops, printers and mobile devices.

How to apply
Apply online.'''


def it_profile():
    return Profile(name='Jordan Example', email='jordan@example.com', location='Melbourne VIC',
                   summary='IT systems specialist supporting Microsoft 365 and workflow automation.',
                   education=['Bachelor of Information Technology'],
                   skills=['Microsoft 365', 'Entra ID', 'ServiceNow', 'Power Automate', 'SharePoint', 'Python'],
                   experience=[Experience(organization='Example Manufacturing', role='IT Support and Systems Specialist',
                                          dates='June 2021 - Present', bullets=FACTS)])


def role(text, title='IT Systems Specialist', url='https://careers.example.com/jobs/it-1'):
    return Job(source_id='opportunity', employer='Example Health', title=title, url=url,
               location='Melbourne VIC', description=text)


def assess(text, title='IT Systems Specialist'):
    job = role(text, title)
    view = listing_view(text, title, job.employer)
    return fit_assessment(job, it_profile(), Preferences(), view,
                          location_info(job.model_dump(), 'Melbourne Victoria Australia'), full=True)


def test_word_stem_folds_tenses_of_one_word_only():
    assert {word_stem(w) for w in ['administering', 'administered', 'administer']} == {'administer'}
    assert {word_stem(w) for w in ['resolving', 'resolved', 'resolve']} == {'resolv'}
    assert word_stem('process') == word_stem('processes') == 'process'
    assert word_stem('printers') != word_stem('python')


def test_another_tense_of_the_requirements_verb_is_not_an_unconfirmed_detail():
    fit = assess(STRONG_ADVERT)
    by_text = {r['text']: r for r in fit['requirements']}
    assert by_text['Experience administering Microsoft 365 and Entra ID.']['status'] == 'Supported'
    assert by_text['Experience resolving incidents in ServiceNow.']['status'] == 'Supported'


def test_salary_and_closing_lines_are_not_scored_as_requirements():
    fit = assess(STRONG_ADVERT)
    assert not any(re.search(r'(?i)applications close|salary', r['text']) for r in fit['requirements'])
    assert fit['coverage']['criteria_count'] == 3


def test_strong_pasted_match_scores_as_a_strong_match():
    fit = assess(STRONG_ADVERT)
    assert fit['assessment_state'] == 'assessed'
    assert fit['percent'] >= 90 and fit['status'] == 'Good match'


def test_unstated_component_shares_its_weight_and_score_still_equals_points():
    fit = assess(SUPPORT_ADVERT, 'IT Support Officer')
    skills = next(b for b in fit['breakdown'] if b['id'] == 'skills')
    assert skills['state'] == 'not_stated' and skills['weight'] == 0
    assert sum(b['weight'] for b in fit['breakdown']) == 100
    assert fit['percent'] == sum(b['points'] or 0 for b in fit['breakdown'])
    # Real gaps (Windows, printers) still keep it below a strong match and under review.
    assert 60 <= fit['percent'] < 90 and fit['status'] == 'Needs review'
    assert any('Windows' in r['requirement'] for r in fit['reviews'])


def test_stated_weights_sum_to_one_hundred():
    assert stated_weights({'skills': 3, 'experience': 2, 'requirements': 2}) == {'skills': 30, 'experience': 40, 'requirements': 30}
    assert stated_weights({'skills': 0, 'experience': 2, 'requirements': 2}) == {'skills': 0, 'experience': 57, 'requirements': 43}
    assert stated_weights({'skills': 2, 'experience': 0, 'requirements': 2}) == {'skills': 50, 'experience': 0, 'requirements': 50}
    assert stated_weights({'skills': 0, 'experience': 0, 'requirements': 0}) == {'skills': 30, 'experience': 40, 'requirements': 30}


class NoCodexBridge(FakeBridge):
    def call(self, tool, arguments=None):
        self.calls.append((tool, arguments or {}))
        raise ConnectorUnavailable('Install Codex CLI and sign in with the same ChatGPT account, then reconnect.')


@pytest.fixture
def offline(tmp_path):
    ws = Workspace(tmp_path, NoCodexBridge())
    ws.save_profile(it_profile())
    yield ws
    ws.close()


def test_missing_codex_never_marks_a_pasted_role_as_blocked(offline):
    job = role(STRONG_ADVERT)
    offline.add_job(job, full=True)
    before = offline.jobs()[0]['fit']
    with pytest.raises(ConnectorUnavailable):
        offline.hydrate(job.identity)
    row = offline.jobs()[0]
    assert row['assessment_source'] is None
    assert row['fit']['status'] == before['status'] == 'Good match'
    assert not any('source check was blocked' in r['label'] for r in row['fit']['reviews'])


def test_real_source_failures_are_still_recorded_as_blocked(workspace):
    job = role(STRONG_ADVERT)
    workspace.add_job(job, full=True)
    workspace.bridge.call = lambda tool, args=None: {'content': 'access denied'}
    with pytest.raises(ValueError):
        workspace.hydrate(job.identity)
    assert workspace.jobs()[0]['assessment_source']['status'] == 'blocked'


def test_check_and_prepare_uses_the_saved_advert_when_codex_is_missing(offline):
    job = role(STRONG_ADVERT)
    offline.add_job(job, full=True)
    result = offline.check_prepare(job.identity)
    assert 'not re-checked' in result['notice']
    if not result.get('held'):
        assert Path(result['packet'], 'Resume.pdf').is_file()
    assert offline.jobs()[0]['assessment_source'] is None


def test_check_and_prepare_on_an_unread_lead_explains_how_to_continue(offline):
    lead = role('Brief search snippet for an IT systems role in Melbourne.', url='https://careers.example.com/jobs/lead-2')
    offline.add_job(lead)
    with pytest.raises(ValueError, match='paste the full advert'):
        offline.check_prepare(lead.identity)


def test_batch_stops_without_marking_every_role_blocked(offline):
    jobs = [role('Brief search snippet for an IT systems specialist role.', url=f'https://careers.example.com/jobs/{n}') for n in range(3)]
    for job in jobs:
        offline.add_job(job)
    with pytest.raises(ConnectorUnavailable):
        offline.assess_batch([j.identity for j in jobs])
    assert all(r['assessment_source'] is None for r in offline.jobs())
    assert offline.get_meta('assessment_progress')['remaining'] == 3


def test_bridge_reports_missing_codex_as_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr('campus_agent.connectors.shutil.which', lambda name: None)
    monkeypatch.setattr('campus_agent.connectors.Path.home', lambda: tmp_path)
    bridge = ConnectorBridge(tmp_path)
    with pytest.raises(ConnectorUnavailable, match='Install Codex CLI'):
        bridge.call('search_service.web_run', {})
    assert issubclass(ConnectorUnavailable, ConnectorError)


@pytest.fixture
def client(workspace):
    app = TestClient(create_workspace_app(workspace), base_url='http://127.0.0.1:8877')
    token = re.search(r'const token="([^"]+)"', app.get('/').text)[1]
    app.headers.update({'origin': 'http://127.0.0.1:8877', 'x-workspace-token': token})
    return app


def test_each_new_paste_saves_once_and_updates_in_place(client, workspace):
    first = {'title': 'IT Support Officer', 'employer': 'Example Logistics', 'location': 'Melbourne VIC',
             'url': 'https://jobs.example.com/job/it-support-77', 'description': SUPPORT_ADVERT}
    ids = {client.post('/api/jobs', json=first).json()['id']}
    ids.add(client.post('/api/jobs', json={**first, 'url': first['url'] + '?utm_source=seek&utm_medium=email'}).json()['id'])
    edited = client.post('/api/jobs', json={**first, 'description': SUPPORT_ADVERT + '\nFlexible start times.'})
    ids.add(edited.json()['id'])
    second = client.post('/api/jobs', json={**first, 'title': 'Service Desk Analyst', 'url': 'https://jobs.example.com/job/desk-9'})
    assert len(ids) == 1 and second.status_code == 200
    rows = workspace.jobs()
    assert len(rows) == 2
    support = next(r for r in rows if r['id'] in ids)
    assert 'Flexible start times' in support['job']['description'] and support['full_description']
    assert all(r['fit']['percent'] is not None for r in rows)


def test_form_errors_are_plain_language(client):
    bad = client.post('/api/jobs', json={'title': 'Role', 'employer': 'E', 'location': 'Melbourne',
                                         'url': 'not a url', 'description': 'short'})
    assert bad.status_code == 400
    detail = bad.json()['detail']
    assert detail.startswith('Please check:') and 'Original job URL' in detail and 'Job description' in detail
    assert 'pydantic' not in detail


def test_ui_confirms_saves_closes_panels_and_offers_the_right_fix():
    html = (Path(__file__).parents[1] / 'campus_agent' / 'workspace.html').read_text()
    for text in ('Profile saved.', 'Settings saved.', 'Style choices saved.', 'Role saved.', 'Role changes saved.', 'Drive destination saved.'):
        assert text in html
    assert "const POPOVERS=['search-preferences','list-actions','role-type-picker','work-arrangement-picker','more-job-filters']" in html
    assert "e.key!=='Escape'" in html
    assert "button('Add employer'" in html and "button('Paste full advert'" in html
    assert 'function taskMessage' in html and 'not connected:' in html
    assert '<link rel="icon" href="data:,">' in html


def test_job_alert_button_is_in_a_visible_view_not_the_hidden_sidebar():
    html = (Path(__file__).parents[1] / 'campus_agent' / 'workspace.html').read_text()
    activity = html[html.index('<section id="activity"'):]
    activity = activity[:activity.index('</section>')]
    assert 'id="check-alerts"' in activity
    side = html[html.index('<div class="side">'):html.index('<section id="profile"')]
    assert 'id="check-alerts"' not in side


def test_read_reports_what_still_blocks_scoring(client, workspace):
    import time
    lead = Job(source_id='opportunity', employer='Employer on job listing', title='Systems Analyst',
               url='https://careers.example.com/jobs/analyst-3', location='Melbourne VIC',
               description='Search snippet for a systems analyst role in Melbourne.')
    workspace.add_job(lead)
    page = ('# Systems Analyst\nMelbourne VIC · Full time\n\nAbout the role\n' + 'Support business systems for staff. ' * 12 +
            '\n\nAbout you\n- Experience resolving ServiceNow incidents.\n- Experience administering Microsoft 365.\n')
    workspace.bridge.call = lambda tool, args=None: {'content': page}
    task = client.post('/api/jobs/' + lead.identity + '/read', json={}).json()['task_id']
    for _ in range(100):
        done = next(t for t in workspace.activity()['tasks'] if t['id'] == task)
        if done['status'] != 'running':
            break
        time.sleep(0.05)
    assert done['status'] == 'done'
    assert 'employer' in done['result']['notice'].lower()


def test_power_automate_work_evidences_a_power_platform_role_title():
    text = ('Power Platform Specialist\nExample Water · Melbourne VIC\n\nAbout you\n'
            '- Experience building Power Automate approval workflows with SharePoint.\n'
            '- Experience administering Microsoft 365 and Entra ID.\n'
            '- Experience resolving incidents in ServiceNow.')
    fit = assess(text, 'Power Platform Specialist')
    title_tool = next(r for r in fit['requirements'] if r['text'] == 'Core tool in role title: Power Platform')
    assert title_tool['status'] == 'Supported'
    assert 'Power Platform' in fit['matched_skills']
    # A profile without any Power Platform family work is still not credited.
    other = it_profile().model_copy(update={'skills': ['Python'], 'experience': [Experience(
        organization='Example', role='Analyst', dates='2020 - Present', bullets=['Built a Python utility used monthly by Finance.'])]})
    job = role(text, 'Power Platform Specialist')
    view = listing_view(text, job.title, job.employer)
    bare = fit_assessment(job, other, Preferences(), view, location_info(job.model_dump(), 'Melbourne Victoria Australia'), full=True)
    assert 'Power Platform' in bare['unconfirmed_skills']
