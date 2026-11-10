import pytest
from test_workspace import workspace, profile
from test_assessment_flow import make_job
from campus_agent.workspace import SourceChanged, ReadInProgress
from campus_agent.listing_view import listing_view, normalize_listing, source_problem


def test_research_saves_candidates_without_changing_job_or_scoring(workspace):
    job=make_job(900)
    workspace.add_job(job)
    calls=[]
    def search(tool,args):
        calls.append((tool,args))
        return {'results':[
            {'title':job.title+' at '+job.employer,'url':'https://linkedin.com/jobs/search/', 'snippet':job.employer},
            {'title':job.title+' at '+job.employer,'url':'https://example.org/jobs/900?token=private', 'snippet':job.employer},
            {'title':job.title+' at '+job.employer,'url':'https://example.org/jobs/900',
             'snippet':job.employer+' offers full-time work, salary may be estimated.'},
            {'title':'Unrelated nurse at '+job.employer,'url':'https://example.org/jobs/901','snippet':job.employer},
            {'title':job.title+' at Other Employer','url':'https://example.org/jobs/902','snippet':'Other Employer'},
        ]}
    workspace.bridge.call=search
    before=workspace.job(job.identity)[0]['payload']
    result=workspace.research_listing(job.identity)
    assert result['candidates']==1
    assert workspace.job(job.identity)[0]['payload']==before
    assert workspace.research_listing(job.identity)['cached']
    assert len(calls)==1
    assert workspace.profile.name not in str(calls[0][1])
    report=workspace.jobs()[0]['listing_research']
    assert report['candidates'][0]['url']=='https://example.org/jobs/900'


def test_research_rejects_concurrent_source_change(workspace):
    job=make_job(901)
    workspace.add_job(job)
    def search(*_):
        workspace.add_job(job.model_copy(update={'description':'Changed source description with different information.'}),full=True)
        return {'results':[]}
    workspace.bridge.call=search
    with pytest.raises(SourceChanged):
        workspace.research_listing(job.identity)
    assert workspace.get_meta('listing_research:'+job.identity) is None
    assert job.identity not in workspace.reading_jobs


def test_research_respects_running_source_read(workspace):
    job=make_job(902)
    workspace.add_job(job)
    workspace.reading_jobs.add(job.identity)
    with pytest.raises(ReadInProgress):
        workspace.research_listing(job.identity)


@pytest.mark.parametrize('text',[
    'Employment type\nFull-time', 'Work type: Full Time Salaried', '### Employment type\nFull-time'
])
def test_explicit_employment_type_is_displayed(text):
    facts=listing_view(text+'\nRequirements\nPython experience.', 'Developer','Example')['facts']
    assert any(f['label']=='Work type' and f['value'].lower().startswith('full') for f in facts)


def test_expiry_banner_before_full_description_is_retained_as_closed():
    text='The job you are trying to view has expired. Please perform a new search to find current jobs.\n# AI Adoption Specialist\n## Full Job Description\nRequirements\nPython experience.'
    assert source_problem(text,'AI Adoption Specialist')[0]=='closed'


def test_structured_work_type_and_remote_restrictions_are_retained():
    import json
    posting={'@type':'JobPosting','title':'Developer','description':'Requirements: Python development experience.',
             'employmentType':'FULL_TIME','jobLocationType':'TELECOMMUTE',
             'applicantLocationRequirements':{'@type':'Country','name':'Australia'}}
    text=normalize_listing('<script type="application/ld+json">'+json.dumps(posting)+'</script>','Developer')
    facts=listing_view(text,'Developer','Example')['facts']
    assert {'label':'Work type','value':'FULL_TIME'} in facts
    assert {'label':'Work format','value':'Remote'} in facts
    assert 'Applicants must be based in Australia.' in text
