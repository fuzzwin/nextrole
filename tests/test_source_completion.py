import pytest
from campus_agent.models import Job
from campus_agent.listing_view import confirmed_listing_employer, source_problem, normalize_listing
from test_fit import assess
from test_workspace import workspace, profile
from test_detail_refresh import AD
import hashlib
SOURCE_AD=AD.replace('Example Employer\n','Employer: Example Employer\n',1)


def job(title='Systems Specialist',url='https://www.linkedin.com/jobs/view/123/'):
    return Job(source_id='opportunity',title=title,employer='Employer on job listing',url=url,description='A short unreviewed systems role lead.',location='Melbourne')


@pytest.mark.parametrize('heading',[
    'You might thrive in this role if you:', "You'll thrive here if you", 'Who you are',
    'What you bring', 'What you will need', 'Requirements & Qualifications',
    "What Kind of Things We're Most Interested in You Having",
])
def test_original_applicant_heading_variants_are_assessed(heading):
    f=assess(heading+'\n- Python automation experience.')
    assert f['assessment_state']=='assessed' and f['coverage']['criteria_count']==1


def test_bonus_and_ideal_skills_do_not_become_essential_criteria():
    f=assess("Who you are\n- Python automation experience.\nBonus points for:\n- Kubernetes administration.\nYou will ideally have:\n- Mandarin fluency.\nSimilar roles\nRequirements\nCISSP required.")
    assert len(f['requirements'])==1 and f['requirements'][0]['value']==1


def test_linkedin_identity_needs_matching_role_header_and_platform_corroboration():
    text='# Systems Specialist\nExample Services Melbourne, Victoria, Australia\nSee who Example Services has hired for this role\nRequirements\nPython automation experience.'
    assert confirmed_listing_employer(job('Systems Specialist Example Services · Melbourne, VIC Actively recruiting'),text)=='Example Services'
    assert confirmed_listing_employer(job('Sales Specialist'),text)=='Employer on job listing'
    assert confirmed_listing_employer(job(),text.replace('Example Services Melbourne, Victoria, Australia','Unrelated Company Melbourne'))=='Employer on job listing'


def test_geographic_company_name_is_valid_but_undisclosed_client_is_not_invented():
    text='# Systems Specialist\nCourt Services Victoria Melbourne, VIC\nSee who Court Services Victoria has hired for this role\nAbout Us\nCourt Services Victoria provides services.'
    assert confirmed_listing_employer(job(),text)=='Court Services Victoria'
    agency=text.replace('Court Services Victoria','Talent')+'\nOur client is a well-established organisation.'
    assert confirmed_listing_employer(job(),agency)=='Employer on job listing'


@pytest.mark.parametrize('company',['Microsoft','Airservices Australia','Macquarie Group Limited'])
def test_indeed_role_header_allows_legal_company_and_location_decorations(company):
    j=job('Systems Specialist - Victoria - Indeed.com','https://au.indeed.com/viewjob?jk=123')
    text='# Systems Specialist\n\n'+company+'\n\n·\n3.8\nVictoria\nFull-time\nFull job description\n'+AD
    assert confirmed_listing_employer(j,text)==company
    assert confirmed_listing_employer(j,text.replace('# Systems Specialist','# Sales Specialist',1))==j.employer


def test_indeed_title_alias_does_not_silently_change_role():
    j=job('AI Solution Specialist - Remote - Indeed.com','https://au.indeed.com/viewjob?jk=456')
    assert confirmed_listing_employer(j,'# AI Sales Specialist\nRed Hat\n3.8\nAustralia\nFull job description\nSales role.')==j.employer


def test_official_company_section_still_requires_same_role():
    j=job(url='https://openai.com/careers/example/')
    for title in ['Sales Specialist','']:
        text=('# '+title+'\n' if title else '')+'About OpenAI\nOpenAI is an AI research and deployment company.'
        assert confirmed_listing_employer(j,text)==j.employer


@pytest.mark.parametrize('label',['Melbourne, VIC','Sydney NSW 2000','Full-time','Remote (Australia)','Manila, Philippines'])
def test_work_metadata_never_becomes_company(label):
    j=job('Systems Specialist','https://au.indeed.com/viewjob?jk=456')
    assert confirmed_listing_employer(j,'# Systems Specialist\n'+label+'\n3.8\nAustralia\nFull job description\nSupport systems.')==j.employer


def test_jobstore_and_same_role_mirror_require_body_company_corroboration():
    j=job('Systems Specialist (up to A$13,000) - Example Employer in Sydney','https://www.jobstore.com/au/job/123/role')
    assert confirmed_listing_employer(j,'# Systems Specialist\n### Example Employer\n3.8 reviews\nExample Employer is hiring a specialist.')=='Example Employer'
    j=job('Systems Specialist · Example Employer','https://hirealice.app/en/jobs/123')
    assert confirmed_listing_employer(j,'# Systems Specialist\nExample Employer · Melbourne VIC\nDescription\nExample Employer builds systems.')=='Example Employer'


@pytest.mark.parametrize('text',[
    '# Systems Specialist\nThis job post has expired.',
    '# Systems Specialist\nSorry, this job was removed at 02:00 UTC.',
])
def test_explicit_source_closures_are_not_missing_employer_or_requirements(text):
    assert source_problem(text)[0]=='closed'


@pytest.mark.parametrize('text',[
    '# 1 result for Systems Specialist in Melbourne',
    '# Search jobs at Example Employer\nRequirements\nPython experience.',
    'Redirected to URL: https://example.com/au/careers/jobsearch\nFind work',
    'The job vacancy you tried to view was not found.\n# Job search',
])
def test_directory_and_removed_role_redirects_stay_unscored(text):
    assert source_problem(text)[0]=='search_results'


def test_platform_summary_and_qualifications_are_not_used_as_original_requirements():
    f=assess('# Systems Specialist\n### Job summary\nSummary of work.\n### Qualifications\n- Python automation experience.\n## Job description\nEmployer is hiring to build systems and\nShow more')
    assert f['percent'] is None and f['source_state']=='source_summary'


def test_pdf_transport_line_markers_do_not_hide_explicit_headings():
    text=normalize_listing('L0@P0: Requirements\nL1@P0: - Python automation experience.')
    assert text=='Requirements\n- Python automation experience.'
    assert assess(text)['assessment_state']=='assessed'


def test_closed_notice_below_search_form_survives_reading(workspace):
    j=job();workspace.add_job(j)
    text='Cookie choices\n'+'Cookies make this website work. '*15+'\n[Input: Search]\nSorry, this position has been filled.'
    workspace.bridge.call=lambda *_:{'content':text}
    workspace.hydrate(j.identity)
    row=workspace.jobs()[0]
    assert row['fit']['assessment_state']=='closed'
    assert 'position has been filled' in row['job']['description']


def test_backfill_persists_explicit_employer_without_resetting_tracking(workspace):
    j=job();text='# Systems Specialist\nExample Employer Melbourne, VIC\nSee who Example Employer has hired for this role\nRequirements\n- Python automation experience.'
    workspace.add_job(j.model_copy(update={'description':text}),full=True)
    workspace.set_top_listing(j.identity,True)
    with workspace.store.connect() as db:db.execute("UPDATE job_details SET notes='Keep this note' WHERE job_id=?",(j.identity,))
    assert workspace.recheck_saved_employers()['employers_updated']==1
    row=workspace.jobs()[0]
    assert row['job']['employer']=='Example Employer' and row['notes']=='Keep this note' and row['top_saved']
    assert workspace.get_meta('listing_history:'+j.identity)[0]['job']['employer']=='Employer on job listing'


def test_parsing_an_employer_does_not_clear_latest_blocked_source_check(workspace):
    from campus_agent.fit import SOURCE_VERSION as VERSION
    j=job();text='# Systems Specialist\nExample Employer Melbourne, VIC\nSee who Example Employer has hired for this role\nRequirements\n- Python automation experience.'
    workspace.add_job(j.model_copy(update={'description':text}),full=True)
    row,_=workspace.job(j.identity)
    workspace.set_meta('assessment_source:'+j.identity,{'status':'blocked','revision':row['revision'],'version':VERSION,'message':'Access denied'})
    workspace.recheck_saved_employers();updated=workspace.jobs()[0]
    assert updated['assessment_source']['status']=='blocked'
    assert any('saved advert' in r['label'] for r in updated['fit']['reviews'])
    assert not updated['fit']['auto_eligible']


def test_source_correction_is_guarded_and_original_link_is_preserved(workspace):
    j=job('IT Systems Specialist');workspace.add_job(j)
    raw,_=workspace.job(j.identity);expected=hashlib.sha256(raw['payload'].encode()).hexdigest()
    with pytest.raises(ValueError,match='changed'):
        workspace.correct_saved_source(j.identity,'stale',{'description':SOURCE_AD})
    workspace.correct_saved_source(j.identity,expected,{'description':SOURCE_AD,'employer':'Example Employer'})
    row=workspace.jobs()[0]
    assert row['job']['url']==str(j.url)
    assert row['fit']['assessment_state']=='rating_pending' and row['legacy_fit']['percent'] is not None
    calls=[];workspace.bridge.call=lambda tool,args:(calls.append(args) or {'content':AD})
    workspace.hydrate(j.identity)
    assert calls[0]['open'][0]['ref_id']==str(j.url)


def test_source_correction_rejects_unrelated_role_or_invented_employer(workspace):
    j=job();workspace.add_job(j);raw,_=workspace.job(j.identity);expected=hashlib.sha256(raw['payload'].encode()).hexdigest()
    with pytest.raises(ValueError,match='title'):
        workspace.correct_saved_source(j.identity,expected,{'description':SOURCE_AD,'employer':'Example Employer'})
    with pytest.raises(ValueError,match='employer'):
        workspace.correct_saved_source(j.identity,expected,{'description':SOURCE_AD.replace('IT Systems Specialist','Systems Specialist'),'employer':'Invented Organisation'})
    with pytest.raises(ValueError,match='different role'):
        workspace.correct_saved_source(j.identity,expected,{'title':'IT Systems Specialist','description':SOURCE_AD,'employer':'Example Employer'})
    with pytest.raises(ValueError,match='Alternate source'):
        workspace.correct_saved_source(j.identity,expected,{},'https://unrelated.example.com/job')


@pytest.mark.parametrize('url',['https://au.indeed.com/viewjob?jk=1','https://www.simplyhired.com.au/job/123'])
def test_legacy_company_fallback_cannot_discard_functional_title_suffix(url):
    j=job('Systems Specialist — Security',url)
    text='# Systems Specialist\nAcme Corp\nMelbourne VIC\n- Acme Corp - 3.8\nFull job description\nWe hire.'
    assert confirmed_listing_employer(j,text)==j.employer


def test_structured_metadata_cannot_discard_functional_title_suffix():
    import json
    text='<script type="application/ld+json">'+json.dumps({'@type':'JobPosting','title':'Systems Specialist','hiringOrganization':{'name':'Acme Corp'},'description':'Support systems and automation in Melbourne.'})+'</script>'
    assert normalize_listing(text,'Systems Specialist — Security').startswith('Listing mismatch:')


@pytest.mark.parametrize('suffix',['Security VIC','Operations NSW','Cloud QLD 4000','Senior VIC','Security Sydney VIC'])
def test_state_suffix_does_not_turn_functional_scope_into_a_location(suffix):
    j=job('Systems Specialist - '+suffix,'https://au.indeed.com/viewjob?jk=456')
    assert confirmed_listing_employer(j,'# Systems Specialist\nAcme Corp\nMelbourne VIC\nFull job description\nWe hire.')==j.employer


def test_position_description_carries_vacancy_currency_review():
    f=assess('Position Description\nRequirements\n- Python automation experience.')
    assert any('current vacancy' in r['label'] for r in f['reviews'])
    assert not f['auto_eligible']
