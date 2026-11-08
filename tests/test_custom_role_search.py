import pytest
from campus_agent.models import Job
from campus_agent.role_types import query_plan
from campus_agent.tailor import grounded_cover
from campus_agent.workspace import Preferences
from test_workspace import workspace, profile, role


def custom(*titles):
    return Preferences(role_search_mode='custom', custom_role_titles=list(titles))


def test_custom_queries_exclude_it_presets_and_legacy_extra_phrases():
    preferences = custom('Registered Nurse', 'Electrician').model_copy(
        update={'keywords': ['IT support'], 'use_custom_keywords': True})
    for extended in (False, True):
        queries = query_plan(preferences, extended)
        assert all('"Registered Nurse"' in q or '"Electrician"' in q for q in queries)
        assert all('Microsoft' not in q and 'IT support' not in q for q in queries)
    assert any('Microsoft' in query for query in query_plan(Preferences()))


def test_custom_titles_label_saved_jobs_and_keep_search_separate(workspace, role):
    workspace.save_preferences(custom('Registered Nurse'))
    nurse = role.model_copy(update={'title': 'Registered Nurse – Theatre'})
    workspace.add_job(nurse, full=True)
    other = Job.model_validate({**role.model_dump(mode='json'), 'url': 'https://example.com/job/other'})
    workspace.add_job(other, full=True)
    rows = {row['id']: row for row in workspace.jobs()}
    assert rows[nurse.identity]['search_match']
    assert rows[nurse.identity]['role_types'][0]['label'] == 'Registered Nurse'
    assert not rows[other.identity]['search_match']
    assert not rows[other.identity]['top_match']
    assert all('outside' not in r['label'].lower() for r in rows[other.identity]['fit']['reviews'])


@pytest.mark.parametrize('titles', [[], ['Registered nurse', 'REGISTERED NURSE'], ['"nurse"']])
def test_invalid_custom_titles_do_not_fall_back_to_it(titles):
    with pytest.raises(ValueError):
        custom(*titles)


def test_cover_letter_ignores_applications_close_boilerplate(profile, role):
    nurse = role.model_copy(update={'title': 'Registered Nurse',
        'description': 'Provide bedside nursing care. Applications close on Friday.'})
    letter = ' '.join(grounded_cover(nurse, profile, {'experience': []}))
    assert 'Registered Nurse' in letter
    assert 'business systems' not in letter and 'especially relevant' not in letter


def test_automatic_custom_check_stops_before_any_connector(workspace, monkeypatch):
    from campus_agent.morning import run_morning
    workspace.save_preferences(custom('Electrician'))
    monkeypatch.setattr(workspace.bridge, 'call', lambda *_: pytest.fail('Automatic connector called'))
    assert run_morning(workspace)['status'] == 'paused'


def test_switch_to_custom_during_scheduled_read_holds_delivery(workspace, role, monkeypatch):
    from test_workspace import morning_profile
    from campus_agent.morning import run_morning
    morning_profile(workspace)
    workspace.add_job(role, full=True)
    monkeypatch.setattr(workspace,'discover',lambda extended=False:{'found':1,'errors':[]})
    monkeypatch.setattr(workspace,'alerts',lambda:{'message_ids':[]})
    def hydrate(_):
        workspace.save_preferences(workspace.preferences.model_copy(
            update={'role_search_mode':'custom','custom_role_titles':['Systems Specialist']}))
    monkeypatch.setattr(workspace,'hydrate',hydrate)
    monkeypatch.setattr(workspace,'prepare',lambda *_: pytest.fail('Automatic prepare after switching mode'))
    assert run_morning(workspace)['paused']
    assert not any(n in {'gmail.send_email','google_drive.upload_file'} for n,_ in workspace.bridge.calls)
