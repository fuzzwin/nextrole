import copy
import pytest
from campus_agent.semantic import extract,AssessmentError,validate_rows,render,fingerprint,assess
from campus_agent.models import Job
from test_workspace import profile,workspace


def view(text='Experience supporting users is required.'):
    return {'sections':[{'heading':'Requirements','blocks':[{'kind':'paragraph','text':text}]}]}


def test_invented_requirement_quote_is_rejected():
    with pytest.raises(AssessmentError,match='source'):
        extract(view(),lambda *_:{'requirements':[{'source_id':'missing','text':'Degree','quote':'A degree is essential','importance':'essential','kind':'competency'}]})


def test_incomplete_or_duplicate_decisions_are_rejected():
    for rows in [[],[{'id':'1'},{'id':'1'}]]:
        with pytest.raises(AssessmentError):validate_rows({'matches':rows},'matches',['1','2'],{'supported'})


def test_fixed_coverage_excludes_optional_and_conditions():
    rows=[dict(id=str(i),text='Example',quote='Example original',importance=imp,kind=kind,status=status,evidence=[],reasons=[]) for i,(imp,kind,status) in enumerate([
        ('essential','competency','supported'),('standard','competency','partial'),('standard','competency','not_documented'),('optional','competency','not_documented'),('essential','condition','not_documented')])]
    report={'requirements':rows,'model':'qwen3.5:4B'}
    result=render(report,{'assessment_state':'assessed'})
    assert result['percent']==62 # 2.5 / 4 weighted evidence units
    assert result['auto_eligible'] is False and len(result['separate_checks'])==1
    assert result['coverage']['unconfirmed']==1
    closed=render(report,{'assessment_state':'closed','status':'Closed'})
    assert closed['percent'] is None and closed['status']=='Closed'


def test_changed_profile_invalidates_cache(profile):
    job=Job(source_id='manual',title='IT Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Experience supporting users is required.')
    modified=profile.model_copy(update={'skills':profile.skills+['New confirmed fact']})
    assert fingerprint(job,profile)!=fingerprint(job,modified)


def test_invalid_evidence_reference_blocks_report(profile):
    def invoke(system,data):
        if 'source_blocks' in data:return {'requirements':[{'source_id':'0','text':'Support users','quote':'Experience supporting users','importance':'standard','kind':'competency'}]}
        return {'matches':[{'id':'0','status':'supported','evidence_ids':['invented'],'reason':'Claim'}]}
    job=Job(source_id='manual',title='Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Experience supporting users is required.')
    with pytest.raises(AssessmentError,match='evidence reference'):assess(job,profile.model_copy(update={'is_example':False}),view(),invoke)


def test_second_pass_cannot_upgrade_first_pass(profile):
    def invoke(system,data):
        if 'source_blocks' in data:return {'requirements':[{'source_id':'0','text':'Support users','quote':'Experience supporting users','importance':'standard','kind':'competency'}]}
        if 'requirements' in data:return {'matches':[{'id':'0','status':'not_documented','evidence_ids':[],'reason':'No evidence'}]}
        return {'checks':[{'id':'0','status':'supported','reason':'Unsupported upgrade'}]}
    job=Job(source_id='manual',title='Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Experience supporting users is required.')
    result=assess(job,profile.model_copy(update={'is_example':False}),view(),invoke)
    assert result['requirements'][0]['status']=='not_documented'


def test_selected_source_text_is_preserved_exactly():
    original="Three years’ experience with AI and automation."
    result=extract(view(original),lambda *_:{'requirements':[{'source_id':'0','text':'AI experience','importance':'standard','kind':'competency'}]})
    assert result[0]['quote']==original


def test_local_client_disables_proxy_and_redirects(monkeypatch):
    import campus_agent.semantic as module
    captured={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'model':module.MODEL,'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
    class Client:
        def __init__(self,**kw):captured.update(kw)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,json):
            assert url.startswith('http://127.0.0.1:')
            assert 'tools' not in json
            return Response()
    monkeypatch.setattr(module.httpx,'Client',Client)
    with pytest.raises(AssessmentError,match='cut short'):module.call_model('test',{'source_blocks':[{'id':'0'}]})
    assert captured['trust_env'] is False and captured['follow_redirects'] is False


def test_verifier_does_not_see_prior_verdict(profile):
    def invoke(system,data):
        if 'source_blocks' in data:return {'requirements':[{'source_id':'0','text':'Support users','importance':'standard','kind':'competency'}]}
        if 'requirements' in data:return {'matches':[{'id':'0','status':'supported','evidence_ids':['work:0:0'],'reason':'Anchoring statement'}]}
        assert 'status' not in data['proposals'][0] and 'reason' not in data['proposals'][0]
        return {'checks':[{'id':'0','status':'not_documented','reason':'No direct evidence'}]}
    job=Job(source_id='manual',title='Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Experience supporting users is required.')
    result=assess(job,profile.model_copy(update={'is_example':False}),view(),invoke)
    assert result['requirements'][0]['status']=='not_documented'


def test_cached_report_is_invalidated_and_render_does_not_call_model(workspace,monkeypatch):
    import campus_agent.semantic as module
    job=Job(source_id='manual',title='IT Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Requirements\nExperience supporting users is required.\nMaintain system documentation and assist colleagues with technical problems.')
    workspace.add_job(job,full=True)
    report={'model':module.MODEL,'fingerprint':fingerprint(job,workspace.profile),'requirements':[{'id':'0','text':'Support users','quote':'Experience supporting users is required.','importance':'standard','kind':'competency','status':'not_documented','evidence':[],'reasons':[]}]}
    workspace.set_meta('semantic:'+job.identity,report)
    monkeypatch.setattr('campus_agent.qwen_harness.qualification_current',lambda receipt:True)
    monkeypatch.setattr(module,'call_model',lambda *a,**k:pytest.fail('Rendering must not run inference'))
    row=workspace.jobs()[0]
    assert row['fit']['model']==module.MODEL and not row['fit']['auto_eligible']
    workspace.save_profile(workspace.profile.model_copy(update={'skills':['Changed profile fact']}))
    row=workspace.jobs()[0]
    assert row['semantic_stale'] and 'model' not in row['fit']


def test_incomplete_and_excluded_sources_never_reach_local_model(workspace,monkeypatch):
    import campus_agent.semantic as module
    job=Job(source_id='manual',title='IT Support',employer='Example',location='Melbourne',url='https://example.com/job',description='Search snippet with some interesting skills.')
    workspace.add_job(job,full=False)
    monkeypatch.setattr(module,'assess',lambda *a,**k:pytest.fail('Incomplete source must not be assessed'))
    report=module.assess_saved(workspace,[job.identity])
    assert not report['completed'] and len(report['failed'])==1


def test_local_route_requires_owner_and_bounds_batch(workspace,monkeypatch):
    import re
    from fastapi.testclient import TestClient
    from campus_agent.workspace_web import create_workspace_app
    import campus_agent.semantic as module
    monkeypatch.setattr(workspace,'task',lambda name,fn:fn())
    monkeypatch.setattr(module,'assess_saved',lambda ws,ids:{'completed':ids})
    with TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as client:
        token=re.search(r'const token="([^"]+)"',client.get('/').text)[1]
        assert client.post('/api/assess-local',json={'job_ids':['job']}).status_code==403
        headers={'origin':'http://127.0.0.1:8877','x-workspace-token':token}
        assert client.post('/api/assess-local',headers=headers,json={'job_ids':[]}).status_code==400
        assert client.post('/api/assess-local',headers=headers,json={'job_ids':['j']*11}).status_code==400
        assert client.post('/api/assess-local',headers=headers,json={'job_ids':['j']}).json()=={'completed':['j']}


def test_schema_requires_unique_decision_keys():
    from campus_agent.semantic import output_schema
    schema=output_schema({'proposals':[{'id':'0'},{'id':'1'}]})
    decisions=schema['properties']['checks']
    assert decisions['type']=='object' and decisions['required']==['0','1']
    assert decisions['additionalProperties'] is False
