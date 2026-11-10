from test_workspace import workspace, profile
from test_assessment_flow import make_job
from campus_agent.detail_refresh import DetailRefreshQueue, KEY, source_context

AD='About the role: Support systems. Requirements: Requires hands-on Python automation experience. You need experience supporting Microsoft 365 systems.'

def test_unvalidated_score_is_withheld_and_never_auto_top(workspace):
    job=make_job(901,AD);workspace.add_job(job,full=True)
    workspace.set_top_listing(job.identity,True)
    row=workspace.jobs()[0]
    assert row['legacy_fit']['percent'] is not None
    assert row['fit']['percent'] is None
    assert row['fit']['assessment_state']=='rating_pending'
    assert not row['fit']['auto_eligible'] and not row['top_match']
    assert row['top_saved'] and row['top_listing']
    assert row['job']['description']==AD and row['full_description']
    assert workspace.jobs()[0]['fit']['percent'] is None # cached path too

def test_model_wait_is_not_missing_advert_or_user_input(workspace):
    job=make_job(902,AD);workspace.add_job(job,full=True)
    row=workspace.jobs()[0];queue=DetailRefreshQueue(workspace)
    state=queue._state();state['items'][job.identity]={'context':source_context(row),'status':'queued','attempts':0,'next_attempt':0,'host':'example.com'}
    workspace.set_meta(KEY,state)
    queue.start();summary=queue.assessment_overview(workspace.jobs())
    assert summary['model']==1 and summary['manual']==0 and summary['remaining']==0 and summary['scored']==0
    assert summary['by_job'][job.identity]=='model'
    assert queue.summary()['waiting']==0

def test_incomplete_source_still_uses_advert_queue(workspace):
    workspace.add_job(make_job(903))
    queue=DetailRefreshQueue(workspace);queue.start()
    row=workspace.jobs()[0]
    assert row['fit']['assessment_state']=='incomplete'
    assert queue.assessment_overview([row])['model']==0
    assert queue.summary()['waiting']==1


def test_closed_adverts_remain_closed(workspace):
    job=make_job(904,AD+'\nNo longer accepting applications.');workspace.add_job(job,full=True)
    row=workspace.jobs()[0]
    assert row['listing']['closed']
    assert row['fit']['status']=='Closed'
    assert row['fit']['assessment_state']!='rating_pending'
