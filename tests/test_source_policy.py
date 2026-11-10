import json
from urllib.parse import quote
import pytest
from test_workspace import workspace, profile
from campus_agent.models import Job
from campus_agent.workspace import search_results, public_listing_url
from campus_agent.source_policy import source_exclusion


def job(url='https://www.jobleads.com/au/job/support--123'):
    return Job(source_id='opportunity',title='IT Systems Specialist',employer='Example Employer',url=url,description='Location: Melbourne VIC\nRequirements\n- Python automation experience.\n- Microsoft 365 support experience.\n- Project coordination experience.',location='Melbourne')


@pytest.mark.parametrize('url',[
    'https://JOBLEADS.COM/au/job/a','https://au.jobleads.com/job/a','https://www.jobleads.com./job/a',
    'https://app.bebee.com/job/a',
    'https://example.com/redirect?url='+quote('https://jobleads.com/au/job/a',safe=''),
    'https://example.com/redirect?target='+quote('https://other.example/go?url='+quote('https://bebee.com/job/a',safe=''),safe=''),
])
def test_excluded_domains_subdomains_and_wrappers(url):
    assert source_exclusion(url)['status']=='excluded'
    with pytest.raises(ValueError,match='Excluded'):public_listing_url(url)


@pytest.mark.parametrize('url',[
    'https://notjobleads.com/job/a','https://jobleads.com.example.org/job/a',
    'https://example.org/jobs/jobleads.com','https://example.org/job/a?note=jobleads.com',
    'https://jobleads.com@example.org/job/a','https://careers.example.com/job/a',
    'https://au.linkedin.com/jobs/view/12345/',
])
def test_no_substring_guilt_by_association(url):
    assert source_exclusion(url) is None


def test_discovery_and_research_results_drop_excluded_sources():
    results=search_results({'results':[
        {'title':'IT Systems Specialist','url':str(job().url),'snippet':'Python and Microsoft 365 systems support experience.'},
        {'title':'IT Systems Specialist','url':'https://bebee.com/job/123','snippet':'Python and Microsoft 365 systems support experience.'},
        {'title':'IT Systems Specialist','url':'https://careers.example.com/job/123','snippet':'Python and Microsoft 365 systems support experience.'}]})
    assert [r['url'] for r in results]==['https://careers.example.com/job/123']


def test_new_manual_job_is_rejected_without_writes(workspace):
    with pytest.raises(ValueError,match='Excluded'): workspace.add_job(job(),full=True)
    assert workspace.store.jobs()==[]


def seed(workspace,stage='saved'):
    j=job();workspace.store.save_job(j)
    with workspace.store.connect() as db:
        db.execute('insert into job_details(job_id,full_description,stage,notes) values (?,1,?,?)',(j.identity,stage,'Keep my notes'))
    workspace.set_meta('top:'+j.identity,True)
    return j


@pytest.mark.parametrize('stage',['saved','archived','applied'])
def test_existing_records_remain_intact_but_unscored_and_not_recommended(workspace,stage):
    j=seed(workspace,stage)
    before=workspace.store.get(j.identity)
    row=workspace.jobs()[0]
    assert row['stage']==stage and row['notes']=='Keep my notes'
    assert row['source_policy']['domain']=='jobleads.com'
    assert row['fit']['assessment_state']=='excluded' and row['fit']['percent'] is None
    assert not row['top_match'] and not row['top_listing']
    assert workspace.get_meta('top:'+j.identity) is True
    assert workspace.store.get(j.identity)==before
    assert workspace.detail_refresh.assessment_overview([row])['active']==0
    assert not workspace.detail_refresh.start()['current']
    assert not workspace.bridge.calls


@pytest.mark.parametrize('operation',['hydrate','prepare','check_prepare','action'])
def test_direct_operation_cannot_bypass_source_filter(workspace,operation):
    j=seed(workspace)
    with pytest.raises(ValueError,match='Excluded'):
        if operation=='action':workspace.action(j.identity,'gmail_send_self',lambda *_:pytest.fail('Must not deliver'))
        else:getattr(workspace,operation)(j.identity)
    assert not workspace.bridge.calls


def test_alert_import_omits_excluded_links(workspace):
    workspace.set_meta('job_alert_search',{'result':{'message_ids':['alert']}})
    html='<a href="https://jobleads.com/au/job/123">IT Systems Specialist</a><a href="https://careers.example.com/job/123">IT Support Specialist</a>'
    workspace.bridge.call=lambda *_:{'payload':{'mimeType':'text/html','body':{'content':html}}}
    result=workspace.read_alert('alert')
    assert len(result['links'])==1
    assert result['links'][0]['job']['url']=='https://careers.example.com/job/123'


def test_excluded_listing_can_search_for_an_original_source(workspace):
    j=seed(workspace)
    workspace.bridge.call=lambda *_:{'results':[
        {'title':'IT Systems Specialist at Example Employer','url':str(j.url),'snippet':'Example Employer advert'},
        {'title':'IT Systems Specialist at Example Employer','url':'https://careers.example.com/job/123','snippet':'Example Employer advert'}]}
    assert workspace.research_listing(j.identity)['candidates']==1
    assert workspace.get_meta('listing_research:'+j.identity)['candidates'][0]['url']=='https://careers.example.com/job/123'


def test_career_sources_never_suggest_an_excluded_destination():
    from campus_agent.career import public_url,research_sources
    assert not public_url(str(job().url))
    assert not research_sources({'results':[{'url':str(job().url),'title':'Example role','snippet':'Example snippet'}]})


def test_career_start_holds_excluded_job_before_any_research(workspace):
    j=seed(workspace)
    with pytest.raises(ValueError,match='Excluded'):
        workspace.career.start(j.identity,'deep_research')
    assert not workspace.bridge.calls
