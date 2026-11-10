from test_workspace import application_mail, workspace, profile
from campus_agent.applications import parse_application, rebuild_applications, candidate_metadata, sync_applications
import pytest

def test_joining_team_company_is_clean_and_body_is_not_job_title():
    event=parse_application(application_mail(subject='Thank you for applying',sender='example@myworkday.com',body='Thanks for submitting your application for Example Health. Now that we have received your application, we will review your resume. If your experience is a match, we will invite you to an interview. Thanks again for your interest in joining the team at Example Health!'))
    assert event['company']=='Example Health'
    assert event['title']=='' and event['needs_review'] and event['status']=='received'

def test_recruiter_role_with_company_beats_generic_interest_phrase():
    e=parse_application(application_mail(subject='We have received your application for Senior Business Analyst - AI',body='Thank you for your recent application for the Senior Business Analyst - AI role with Example & Partners. Thank you for your interest in working with us.'))
    assert (e['company'],e['title'])==('Example & Partners','Senior Business Analyst - AI')
    assert not e['needs_review'] and 'receipt' in e['summary']

def known_roles():
    return [dict(company='Example Health',title=t,thread_ids=[str(i)]) for i,t in enumerate(['Registered Nurse','Care Coordinator'])]

def test_company_sender_identifies_employer_but_not_which_previous_application():
    e=parse_application(application_mail(subject='Interview invitation',sender='Example Health Recruitment <talent@examplehealth.com>',thread='new',body='We invite you to an interview with our team.'),known_roles())
    assert e['company']=='Example Health' and not e['title'] and e['needs_review']

def test_exact_title_and_company_can_link_new_thread():
    e=parse_application(application_mail(subject='Registered Nurse - interview invitation',sender='Example Health Recruitment <talent@examplehealth.com>',thread='new',body='We invite you to an interview.'),known_roles())
    assert e['title']=='Registered Nurse' and not e['needs_review']

def test_nontech_application_and_future_interview_not_confirmed_invite():
    e=parse_application(application_mail(subject='Application for Registered Nurse',sender='careers@hospital.example',body='Thank you for applying. If successful, we invite you to an interview. We are thrilled you would like to work with us at Example Hospital!'))
    assert e['status']=='received' and e['title']=='Registered Nurse'
    assert not candidate_metadata(application_mail(subject='New jobs: Registered Nurse application advice',sender='newsletter@example.com'))

def test_rescan_legacy_receipt_is_bounded_and_preserves_seen(workspace,monkeypatch):
    old=parse_application(application_mail());old.pop('parser_version')
    workspace.set_meta('application_events',[old]);workspace.set_meta('applications',rebuild_applications([old]));workspace.set_meta('application_mail_seen',[old['message_id'],'unrelated'])
    calls=[]
    def call(name,args):
        calls.append(name)
        if name=='gmail.search_email_ids':return {'message_ids':[]}
        if name=='gmail.read_email':return application_mail()
        if name=='gmail.batch_read_email':return {'responses':[application_mail()]}
        pytest.fail(name)
    monkeypatch.setattr(workspace.bridge,'call',call)
    assert sync_applications(workspace)['bodies_read']==1
    assert sync_applications(workspace)['bodies_read']==0
    assert 'unrelated' in workspace.get_meta('application_mail_seen',[])
    assert not any('send' in name for name in calls)

def test_duplicate_sync_is_rejected_without_dispatch(workspace):
    import threading
    workspace._application_sync_lock=threading.Lock();workspace._application_sync_lock.acquire()
    try:
        with pytest.raises(ValueError,match='already running'):sync_applications(workspace)
        assert not workspace.bridge.calls
    finally:workspace._application_sync_lock.release()

def test_status_negation_and_conditional_scope():
    assert parse_application(application_mail(subject='Application update',body='This is not an offer of employment.')) is None
    assert parse_application(application_mail(subject='Application update',body='Your interview is cancelled.')) is None
    e=parse_application(application_mail(body='We are pleased to invite you for an interview; if you need adjustments let us know.'))
    assert e['status']=='interview'

def test_vacancy_cancellation_is_not_candidate_rejection():
    e=parse_application(application_mail(subject='Example Health Application Update for Nurse Lead',body='We have made the decision to cancel this position and are not moving forward with filling the role.'))
    assert e['status']=='vacancy_cancelled' and e['company']=='Example Health' and e['title']=='Nurse Lead'

def test_interview_role_and_employer_from_explicit_subject():
    e=parse_application(application_mail(subject='Interview Invitation | Nurse Lead Role at Example Health!',body='We reviewed your application and invite you to an interview.'))
    assert e['company']=='Example Health' and e['title']=='Nurse Lead' and e['status']=='interview'

def test_interest_in_role_never_becomes_employer():
    e=parse_application(application_mail(subject='Application for Senior Business Analyst',body='Thank you for your application and your interest in the Senior Business Analyst position.'))
    assert e['needs_review'] and not e['company']

@pytest.mark.parametrize('body',['Your position is not cancelled.','We have not decided to cancel this position.','Your application has not been unsuccessful.'])
def test_negated_outcome_is_not_recorded(body):
    assert parse_application(application_mail(subject="Application update",body=body)) is None

def test_metadata_rejected_legacy_event_is_retained_for_review_once(workspace,monkeypatch):
    old=parse_application(application_mail());old.pop('parser_version')
    workspace.set_meta('application_events',[old]);workspace.set_meta('application_mail_seen',[old['message_id']])
    def call(name,args):
        if name=='gmail.search_email_ids':return {'message_ids':[]}
        if name=='gmail.read_email':return application_mail(subject='Credit limit application',sender='bank@example.com')
        pytest.fail(name)
    monkeypatch.setattr(workspace.bridge,'call',call)
    first=sync_applications(workspace)
    assert not first['applications'] and first['needs_review'][0]['evidence']==old['evidence']
    assert sync_applications(workspace)['headers_checked']==0


def test_cancelled_update_preserves_work_arrangement_to_avoid_conflating_roles():
    e=parse_application(application_mail(subject='Example Health Application Update for Nurse Lead (Remote - Australia)',body='We have made the decision to cancel this position.'))
    assert e['company']=='Example Health' and e['title']=='Nurse Lead (Remote - Australia)' and e['status']=='vacancy_cancelled'

def test_different_arrangements_keep_independent_application_histories():
    received=parse_application(application_mail(subject='Example Health Application Update for Nurse Lead (Remote - Canada)',body='We received your application.',thread='canada'))
    cancelled=parse_application(application_mail(message_id='other',subject='Example Health Application Update for Nurse Lead (Remote - Australia)',body='We have made the decision to cancel this position.',thread='australia'))
    applications=rebuild_applications([received,cancelled])
    assert len(applications)==2
    assert {a['title']:a['status'] for a in applications}=={'Nurse Lead (Remote - Canada)':'received','Nurse Lead (Remote - Australia)':'vacancy_cancelled'}
