import threading
import pytest
from test_workspace import workspace, profile
from test_assessment_flow import make_job
from campus_agent.detail_refresh import DetailRefreshQueue, KEY, RETRY_SECONDS, HOST_DELAY, source_context, source_host
from campus_agent.workspace import SourceChanged


AD = ('# IT Systems Specialist\nExample Employer\nLocation: Melbourne VIC\n'
      'Salary: $120,000 - $140,000 per year + super\nAbout the role\n'
      + 'Support systems and business automation. '*9+
      '\nRequirements\n- Python automation experience.\n- Microsoft 365 support experience.\n- SQL database administration experience.')


def setup_queue(workspace, count=2, text=None):
    jobs=[make_job(700+i,text) if text else make_job(700+i) for i in range(count)]
    for job in jobs: workspace.add_job(job)
    clock=[1800000000.0]
    queue=DetailRefreshQueue(workspace,clock=lambda:clock[0])
    workspace.detail_refresh=queue
    workspace.bridge.call=lambda *_:{'content':AD}
    return queue,jobs,clock


def test_old_pending_roles_get_real_details_and_scores_with_history(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    row=workspace.jobs()[0]
    with workspace.store.connect() as db:
        db.execute("UPDATE job_details SET notes='keep my note' WHERE job_id=?",(row['id'],))
    workspace.set_top_listing(row['id'],True)
    preferences=workspace.preferences.model_dump();profile=workspace.profile.model_dump()
    queue.start();result=queue.run_batch()
    after=workspace.jobs()[0]
    assert result['assessed']==1 and result['waiting']==0
    assert after['fit']['percent'] is not None
    assert after['reading_view']['salary']['status']!='not_stated'
    assert after['id']==row['id'] and after['job']['url']==row['job']['url']
    assert after['notes']=='keep my note' and after['top_saved']
    assert workspace.preferences.model_dump()==preferences and workspace.profile.model_dump()==profile
    assert workspace.get_meta('listing_history:'+row['id'])[-1]['job']['description']==jobs[0].description
    assert not workspace.activity()['actions']


def test_host_pacing_and_restart_resume_without_repeating_assessed_job(workspace):
    queue,jobs,clock=setup_queue(workspace)
    queue.start();first=queue.run_batch()
    assert first['checked']==1 and first['waiting']==1
    queue=DetailRefreshQueue(workspace,clock=lambda:clock[0])
    assert queue.run_batch()['checked']==1
    clock[0]+=HOST_DELAY+1
    assert queue.run_batch()['assessed']==2


def test_pause_during_read_stops_after_current_job(workspace):
    queue,jobs,clock=setup_queue(workspace)
    entered=threading.Event();release=threading.Event()
    def read(*_):
        entered.set();assert release.wait(3);return {'content':AD}
    workspace.bridge.call=read
    queue.start();thread=threading.Thread(target=queue.run_batch);thread.start()
    assert entered.wait(3)
    assert queue.pause()['phase']=='pausing'
    release.set();thread.join(3);assert not thread.is_alive()
    assert queue.summary()['checked']==1 and not queue.summary()['enabled']
    clock[0]+=HOST_DELAY+1;queue.start();queue.run_batch()
    assert queue.summary()['assessed']==2


def test_failures_retry_once_after_day_then_hold_even_after_restart(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    calls=[]
    workspace.bridge.call=lambda *args:(calls.append(args) or {'content':'Access denied'})
    queue.start();queue.run_batch();queue.run_batch()
    assert len(calls)==1 and queue.summary()['needs_source']==1
    clock[0]+=RETRY_SECONDS+1;queue.run_batch();assert len(calls)==2
    clock[0]+=RETRY_SECONDS+1
    queue=DetailRefreshQueue(workspace,clock=lambda:clock[0]);queue.start();queue.run_batch()
    assert len(calls)==2 and queue.summary()['waiting']==0
    assert workspace.jobs()[0]['job']['description']==jobs[0].description


def test_successful_partial_read_changes_revision_without_resetting_retry_budget(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    calls=[]
    partial='# IT Systems Specialist\nAbout the role\n'+'Support business systems. '*20
    workspace.bridge.call=lambda *args:(calls.append(args) or {'content':partial})
    queue.start();queue.run_batch()
    assert workspace.job(jobs[0].identity)[0]['revision']!=jobs[0].revision
    clock[0]+=HOST_DELAY+1;queue.run_batch();assert len(calls)==1
    clock[0]+=RETRY_SECONDS;queue.run_batch();assert len(calls)==2
    clock[0]+=RETRY_SECONDS;queue.run_batch();assert len(calls)==2


def test_manual_source_edit_reopens_exhausted_record(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    workspace.bridge.call=lambda *_:{'content':'Access denied'}
    queue.start();queue.run_batch();clock[0]+=RETRY_SECONDS+1;queue.run_batch()
    updated=jobs[0].model_copy(update={'description':'An updated excerpt with a new source revision requiring a full read.'})
    workspace.add_job(updated,full=True)
    workspace.bridge.call=lambda *_:{'content':AD}
    clock[0]+=HOST_DELAY+1;queue.run_batch()
    assert queue.summary()['assessed']==1


def test_excluded_and_directory_records_never_fetched(workspace):
    queue,jobs,clock=setup_queue(workspace,3)
    with workspace.store.connect() as db:
        db.execute("UPDATE job_details SET stage='archived' WHERE job_id=?",(jobs[0].identity,))
        db.execute("UPDATE job_details SET stage='applied' WHERE job_id=?",(jobs[1].identity,))
    directory=jobs[2].model_copy(update={'description':'# 200 jobs in Melbourne\nRequirements\nPython automation experience.'})
    workspace.add_job(directory,full=True)
    workspace.bridge.call=lambda *_:pytest.fail('Excluded source was fetched')
    before=workspace.get_meta(KEY)
    overview=queue.assessment_overview(workspace.jobs())
    assert overview['active']==1 and overview['manual']==1 and overview['remaining']==0
    assert overview['reasons']=={'search_results':1}
    assert workspace.get_meta(KEY)==before
    queue.start();result=queue.run_batch()
    assert result['total']==1 and result['needs_source']==1 and result['waiting']==0


def test_coverage_separates_saved_scores_retry_work_and_manual_review(workspace):
    queue, jobs, clock = setup_queue(workspace, 8)
    scored, reading, ready, waiting, manual, profile_job, closed, inactive = [job.identity for job in jobs]
    queue.start()
    snapshot = workspace.get_meta(KEY)
    snapshot['current'] = {'id': reading, 'title': 'Currently reading'}
    snapshot['items'][reading].update(attempts=2)
    snapshot['items'][waiting].update(status='needs_source', attempts=1, next_attempt=clock[0]+300)
    snapshot['items'][manual].update(status='needs_source', attempts=2, next_attempt=clock[0]+300)
    workspace.set_meta(KEY, snapshot)
    rows = {row['id']:row for row in workspace.jobs()}
    rows[scored]['fit'].update(assessment_state='assessed', percent=0)
    rows[profile_job]['fit'].update(assessment_state='needs_profile', source_state=None)
    rows[closed]['fit'].update(assessment_state='closed', percent=0)
    rows[inactive]['stage'] = 'applied'
    result = queue.assessment_overview(list(rows.values()))
    assert result['by_job'] == dict(zip(
        (scored, reading, ready, waiting, manual, profile_job, closed, inactive),
        ('scored', 'reading', 'ready', 'waiting', 'manual', 'profile', 'closed', 'inactive'),
    ))
    assert (result['active'], result['scored'], result['unrated'], result['remaining']) == (6, 1, 5, 3)
    assert result['next_check_at']==clock[0]+300
    assert sum(result['reasons'].values())==result['unrated']
    assert workspace.get_meta(KEY)==snapshot


def test_connector_failure_pauses_queue_without_exhausting_sources(workspace):
    queue,jobs,clock=setup_queue(workspace)
    def unavailable(*_):raise RuntimeError('Codex connector process has stopped. Reconnect in Connections.')
    workspace.bridge.call=unavailable
    queue.start();queue.run_batch()
    assert queue.summary()['phase']=='needs_connection'
    assert sum(i['attempts'] for i in workspace.get_meta(KEY)['items'].values())==0
    assert all(r['job']['description']==jobs[0].description for r in workspace.jobs())


def test_closed_original_is_classified_closed_not_scored(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    workspace.bridge.call=lambda *_:{'content':'# IT Systems Specialist\nThis position has been filled.\n'+('Visit our careers page for other opportunities. '*9)}
    queue.start();assert queue.run_batch()['closed']==1
    assert workspace.jobs()[0]['fit']['assessment_state']=='closed'


def test_background_queue_does_not_overlap_itself_or_explicit_batches(workspace):
    queue,jobs,clock=setup_queue(workspace)
    queue.start();workspace.batch_lock.acquire()
    try:assert queue.run_batch()['checked']==0
    finally:workspace.batch_lock.release()
    queue.worker_lock.acquire()
    try:assert queue.run_batch()['checked']==0
    finally:queue.worker_lock.release()


def test_duplicate_search_requests_reuse_one_task_before_worker_starts(workspace,monkeypatch):
    submitted=[]
    monkeypatch.setattr(workspace.pool,'submit',lambda operation:submitted.append(operation))
    first=workspace.start_discovery()
    second=workspace.start_discovery(extended=True)
    assert second['task_id']==first['task_id'] and second['reused']
    assert len(submitted)==1
    assert len(workspace.activity()['tasks'])==1


def test_restoring_archived_job_requeues_without_resetting_attempts(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    queue.start()
    with workspace.store.connect() as db:db.execute("UPDATE job_details SET stage='archived' WHERE job_id=?",(jobs[0].identity,))
    queue.run_batch();assert queue.summary()['checked']==1
    with workspace.store.connect() as db:db.execute("UPDATE job_details SET stage='saved' WHERE job_id=?",(jobs[0].identity,))
    queue.run_batch();assert queue.summary()['assessed']==1


def test_interrupted_reads_do_not_reset_attempt_budget(workspace):
    queue,jobs,clock=setup_queue(workspace,1);queue.start()
    for attempt in (1,2):
        state=workspace.get_meta(KEY);item=state['items'][jobs[0].identity]
        item.update(attempts=attempt,next_attempt=clock[0]+RETRY_SECONDS)
        state['current']={'id':jobs[0].identity,'title':jobs[0].title}
        workspace.set_meta(KEY,state)
        queue=DetailRefreshQueue(workspace,clock=lambda:clock[0])
        assert workspace.get_meta(KEY)['items'][jobs[0].identity]['attempts']==attempt
    workspace.bridge.call=lambda *_:pytest.fail('Exhausted crashed source was read again')
    clock[0]+=RETRY_SECONDS+1;queue.run_batch()
    assert queue.summary()['waiting']==0


def test_user_edit_after_read_before_finalization_is_not_marked_attempted(workspace,monkeypatch):
    queue,jobs,clock=setup_queue(workspace,1)
    original_get=workspace.job;original_hydrate=workspace.hydrate;read_done=[False]
    def hydrate(job_id):
        result=original_hydrate(job_id);read_done[0]=True;return result
    def get(job_id):
        if read_done[0]:
            read_done[0]=False
            workspace.add_job(jobs[0].model_copy(update={'description':'A manually corrected short advert needing a new read.'}),full=True)
        return original_get(job_id)
    monkeypatch.setattr(workspace,'hydrate',hydrate);monkeypatch.setattr(workspace,'job',get)
    queue.start();queue.run_batch(limit=1)
    row=workspace.jobs()[0];item=workspace.get_meta(KEY)['items'][row['id']]
    assert item['context']!=source_context(row)
    assert row['job']['description'].startswith('A manually corrected')


def test_prior_source_revisions_are_all_retained(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    for n in range(5):
        workspace.bridge.call=lambda *_,n=n:{'content':AD+'\nSource revision '+str(n)}
        workspace.hydrate(jobs[0].identity)
    history=workspace.get_meta('listing_history:'+jobs[0].identity)
    assert len(history)==5 and history[0]['job']['description']==jobs[0].description


def test_linkedin_subdomains_share_one_pacing_key():
    assert source_host('https://au.linkedin.com/jobs/view/123')==source_host('https://www.linkedin.com/jobs/view/456')=='linkedin.com'


def test_source_edit_during_failed_read_is_not_charged_to_new_source(workspace):
    queue,jobs,clock=setup_queue(workspace,1)
    def failed(*_):
        workspace.add_job(jobs[0].model_copy(update={'description':'A manually corrected short advert needing a new read.'}),full=True)
        raise RuntimeError('Access denied')
    workspace.bridge.call=failed
    queue.start();queue.run_batch(limit=1)
    row=workspace.jobs()[0];item=workspace.get_meta(KEY)['items'][row['id']]
    assert item['context']!=source_context(row)
    assert row['assessment_source'] is None
    workspace.bridge.call=lambda *_:{'content':AD}
    clock[0]+=HOST_DELAY+1;queue.run_batch()
    assert queue.summary()['assessed']==1
