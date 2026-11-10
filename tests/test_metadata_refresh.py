import json
import re
import threading
import pytest
from fastapi.testclient import TestClient
from test_workspace import workspace,profile,role
from campus_agent.metadata_refresh import refresh_batch,refresh_one,extract_fields,missing_fields
from campus_agent.workspace import SourceChanged,ReadInProgress
from campus_agent.workspace_web import create_workspace_app

AD='''# Systems Specialist
Employer: Example Employer
Location: Sydney NSW
Work arrangement: Remote
Applicants must be based in NSW only.
Employment type: Full-time
Salary: AUD $110,000 - $130,000 per year
Posted on: 2026-11-10
Applications close: 2027-01-20
## Requirements
- Experience supporting users.
- Experience managing stakeholders.
- Experience coordinating projects.
'''

def setup(workspace,role):
    workspace.add_job(role,full=True)
    return workspace.jobs()[0]


def test_fills_only_missing_metadata_and_preserves_source_tracking(workspace,role):
    row=setup(workspace,role)
    with workspace.store.connect() as db:db.execute("update job_details set notes='Keep my notes' where job_id=?",(role.identity,))
    before=workspace.job(role.identity)[0]['payload']
    workspace.bridge.call=lambda *_:{'content':AD}
    report=refresh_one(workspace,row)
    updated=workspace.jobs()[0]
    assert set(report['filled'])=={'salary','arrangement','employment_type','posted','closes'}
    assert updated['location_info']['display']=='Melbourne'
    assert updated['location_info']['arrangement']=='Remote'
    assert 'NSW only' in updated['location_info']['metadata_restrictions']
    assert updated['reading_view']['salary']['minimum']==110000
    assert updated['listing']['closes_on']=='2027-01-20'
    assert updated['notes']=='Keep my notes'
    assert workspace.job(role.identity)[0]['payload']==before
    assert not updated['top_match']
    assert report['fields']['salary']['url']==str(role.url)
    assert 'AUD $110,000' in report['fields']['salary']['evidence']


def test_owner_edit_invalidates_old_metadata_overlay(workspace,role):
    row=setup(workspace,role);workspace.bridge.call=lambda *_:{'content':AD}
    refresh_one(workspace,row)
    workspace.add_job(role.model_copy(update={'description':role.description+'\nChanged by owner.'}),full=True)
    row=workspace.jobs()[0]
    assert row['metadata_refresh'] is None
    assert row['reading_view']['salary']['status']=='not_stated'


def test_stated_salary_and_work_type_are_not_overwritten(workspace,role):
    role=role.model_copy(update={'description':role.description+'\nSalary: AUD $90,000 per year\nEmployment type: Part-time'})
    row=setup(workspace,role);workspace.bridge.call=lambda *_:{'content':AD}
    report=refresh_one(workspace,row)
    assert 'salary' not in report['requested'] and 'employment_type' not in report['requested']
    after=workspace.jobs()[0]
    assert after['reading_view']['salary']['minimum']==90000
    assert {'label':'Work type','value':'Part-time'} in after['reading_view']['facts']


@pytest.mark.parametrize('body',[
    AD.replace('# Systems Specialist','# Finance Manager'),
    AD.replace('Employer: Example Employer','Employer: Other Company'),
    '# Systems Specialist\nAccess denied.\nSalary: AUD $200,000 per year',
])
def test_wrong_or_blocked_source_cannot_supply_metadata(workspace,role,body):
    row=setup(workspace,role)
    workspace.bridge.call=lambda tool,args: {'content':body} if 'open' in args else {'results':[]}
    report=refresh_one(workspace,row)
    assert not report['filled']
    assert workspace.jobs()[0]['reading_view']['salary']['status']=='not_stated'


def test_alternate_requires_exact_vacancy_link_not_just_same_title(workspace,role):
    row=setup(workspace,role)
    alternate='https://other.example/jobs/copy'
    def bridge(tool,args):
        if 'system2_search_query' in args:return {'results':[{'title':'Systems Specialist at Example Employer','url':alternate,'snippet':'Example Employer salary $200,000.'}]}
        return {'content':'Access denied' if args['open'][0]['ref_id']==str(role.url) else AD}
    workspace.bridge.call=bridge
    report=refresh_one(workspace,row)
    assert report['candidates'] and not report['filled']
    assert report['sources'][-1]['status']=='needs_review'
    assert workspace.jobs()[0]['reading_view']['salary']['status']=='not_stated'


def test_verified_same_vacancy_copy_can_fill_missing_fields(workspace,role):
    # Unknown location lets explicit location be recovered without a contradictory city.
    role=role.model_copy(update={'location':'Melbourne Victoria Australia'})
    row=setup(workspace,role)
    alternate='https://other.example/jobs/copy'
    def bridge(tool,args):
        if 'system2_search_query' in args:return {'results':[{'title':'Systems Specialist at Example Employer','url':alternate,'snippet':'Example Employer full-time.'}]}
        return {'content':'Access denied' if args['open'][0]['ref_id']==str(role.url) else AD+'\nOriginal vacancy: '+str(role.url)}
    workspace.bridge.call=bridge
    report=refresh_one(workspace,row)
    assert 'salary' in report['filled'] and 'location' in report['filled']
    assert report['fields']['salary']['url']==alternate


def test_estimated_salary_not_saved_as_advertised_pay(workspace,role):
    row=setup(workspace,role)
    workspace.bridge.call=lambda tool,args:{'content':AD.replace('Salary:','Estimated salary:')} if 'open' in args else {'results':[]}
    report=refresh_one(workspace,row)
    assert 'salary' not in report['fields']
    assert 'employment_type' in report['filled']


def test_concurrent_source_edit_is_preserved(workspace,role):
    row=setup(workspace,role)
    def bridge(*_):
        workspace.add_job(role.model_copy(update={'description':role.description+' Owner correction.'}),full=True)
        return {'content':AD}
    workspace.bridge.call=bridge
    with pytest.raises(SourceChanged):refresh_one(workspace,row)
    assert workspace.get_meta('metadata_details:'+role.identity) is None
    assert role.identity not in workspace.reading_jobs


def test_batch_checks_only_selected_incomplete_metadata_and_caches_attempts(workspace,role):
    chosen=role
    other=role.model_copy(update={'url':'https://example.com/job/other'})
    for job in [chosen,other]:workspace.add_job(job,full=True)
    calls=[]
    workspace.bridge.call=lambda *args:(calls.append(args) or {'content':AD})
    result=refresh_batch(workspace,[chosen.identity])
    assert result['total']==1 and result['processed']==1 and result['fields_filled']==5
    assert workspace.get_meta('metadata_details:'+other.identity) is None
    refresh_batch(workspace,[chosen.identity]);assert len(calls)==1


def test_closed_and_complete_roles_are_skipped(workspace,role):
    complete=role.model_copy(update={'description':AD})
    closed=role.model_copy(update={'url':'https://example.com/job/closed','description':'# Systems Specialist\nNo longer accepting applications.'})
    for job in [complete,closed]:workspace.add_job(job,full=True)
    workspace.bridge.call=lambda *_:pytest.fail('Unnecessary online lookup')
    assert refresh_batch(workspace,[complete.identity,closed.identity])['total']==0


def test_duplicate_click_reuses_current_task(workspace,role):
    setup(workspace,role);started=threading.Event();release=threading.Event()
    def bridge(*args):started.set();release.wait(10);return {'content':AD}
    workspace.bridge.call=bridge
    first=workspace.start_metadata_refresh([role.identity]);assert started.wait(5)
    try:
        second=workspace.start_metadata_refresh([role.identity])
        assert second['task_id']==first['task_id'] and second['reused']
    finally:release.set()


def test_closed_notice_from_exact_original_source_is_retained(workspace,role):
    row=setup(workspace,role)
    workspace.bridge.call=lambda *_:{'content':'# Systems Specialist\nNo longer accepting applications.'}
    result=refresh_one(workspace,row)
    assert result['outcome']=='closed'
    after=workspace.jobs()[0]
    assert after['listing']['closed'] and after['fit']['assessment_state']=='closed'


def test_api_validates_filtered_selection(workspace):
    with TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as client:
        token=re.search(r'const token="([^"]+)"',client.get('/').text)[1]
        headers={'origin':'http://127.0.0.1:8877','x-workspace-token':token}
        assert client.post('/api/refresh-missing-metadata',json={'job_ids':'all'},headers=headers).status_code==400
        assert client.post('/api/refresh-missing-metadata',json={'job_ids':[]},headers=headers).status_code==200


def test_batch_has_ten_job_limit(workspace,role):
    from pydantic import HttpUrl
    ids=[]
    for i in range(12):
        job=role.model_copy(update={'url':HttpUrl(f'https://example.com/job/{i}')})
        workspace.add_job(job,full=True);ids.append(job.identity)
    workspace.bridge.call=lambda *_:{'content':AD}
    result=refresh_batch(workspace,ids)
    assert result['total']==10 and result['processed']==10 and result['deferred']==2
    assert sum(bool(r['metadata_refresh']) for r in workspace.jobs())==10


def test_unknown_employer_recovered_only_from_original_header(workspace,role):
    role=role.model_copy(update={'employer':'Employer on job listing'})
    row=setup(workspace,role);workspace.bridge.call=lambda *_:{'content':AD}
    report=refresh_one(workspace,row)
    assert report['fields']['employer']['value']=='Example Employer'
    assert workspace.jobs()[0]['reading_view']['employer']=='Example Employer'
    assert workspace.job(role.identity)[1].employer=='Example Employer'
    assert workspace.job(role.identity)[1].description==role.description
    assert workspace.get_meta('listing_history:'+role.identity)[-1]['job']['employer']=='Employer on job listing'


def test_read_in_progress_cannot_be_overwritten(workspace,role):
    row=setup(workspace,role);workspace.reading_jobs.add(role.identity)
    try:
        with pytest.raises(ReadInProgress):refresh_one(workspace,row)
    finally:workspace.reading_jobs.remove(role.identity)


def test_literal_not_stated_fields_are_missing(workspace,role):
    role=role.model_copy(update={'description':role.description+'\nEmployment type: Not stated','location':'Not stated'})
    row=setup(workspace,role)
    assert {'employment_type','location'}<=set(missing_fields(row))
    workspace.bridge.call=lambda *_:{'content':AD}
    refresh_one(workspace,row)
    updated=workspace.jobs()[0]
    assert updated['location_info']['display']=='Sydney NSW'
    assert [f['value'] for f in updated['reading_view']['facts'] if f['label']=='Work type']==['Full-time']


def test_decorated_search_titles_are_opened_but_not_assumed_same_vacancy(workspace,role):
    row=setup(workspace,role);calls=[]
    def bridge(tool,args):
        calls.append(args)
        if 'system2_search_query' in args:
            query=args['system2_search_query'][0]['q']
            assert 'Employment type' not in query and 'Closing date' not in query
            return {'results':[{'title':'Systems Specialist - Example Employer | Job Board','url':'https://board.example/job/copy','snippet':'Example Employer.'}]}
        return {'content':'Access denied' if args['open'][0]['ref_id']==str(role.url) else AD}
    workspace.bridge.call=bridge
    report=refresh_one(workspace,row)
    assert len(report['candidates'])==1 and report['sources'][-1]['status']=='needs_review'
    assert not report['filled']


def test_linkedin_url_alias_must_have_identical_vacancy_id(workspace,role):
    from pydantic import HttpUrl
    role=role.model_copy(update={'url':HttpUrl('https://au.linkedin.com/jobs/view/systems-specialist-at-example-employer-123456/')})
    row=setup(workspace,role)
    alias=str(role.url)
    def bridge(tool,args):
        if 'system2_search_query' in args:return {'results':[{'title':'Systems Specialist at Example Employer — Melbourne | LinkedIn Jobs','url':alias,'snippet':'Example Employer.'}]}
        return {'content':AD if args['open'][0]['ref_id']==alias else 'Access denied'}
    workspace.bridge.call=bridge
    report=refresh_one(workspace,row)
    assert 'salary' in report['filled']
    assert report['fields']['salary']['url']==alias


def test_explicit_in_office_board_header_is_recognised(role):
    values,_=extract_fields(AD.replace('Work arrangement: Remote','In-Office'),role,'Melbourne')
    assert values['arrangement']['value']=='On-site'
