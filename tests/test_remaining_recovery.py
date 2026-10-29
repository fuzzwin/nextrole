import pytest
from test_workspace import workspace, profile
from campus_agent.models import Job
from campus_agent.listing_view import confirmed_listing_employer, listing_view
from campus_agent.workspace import public_listing_url


def job(url='https://careers.example.com/job/1', title='Systems Specialist Job Details'):
    return Job(source_id='opportunity', employer='Employer on job listing', title=title, url=url, description='Original saved job capture with no full listing.', location='Melbourne')


def test_company_field_and_indeed_alias_require_matching_title():
    advert='# Systems Specialist\nCompany: Example Energy Ltd\n'+('Job description for a systems role. '*15)
    assert confirmed_listing_employer(job(),advert)=='Example Energy Ltd'
    assert confirmed_listing_employer(job(title='Different Specialist'),advert)=='Employer on job listing'
    alias=job('https://au.indeed.com/viewjob?jk=1','ExampleBrand - Automation Engineer - Perth WA - Indeed.com')
    text='# Automation Engineer (ExampleBrand)\n\nExample Group\n\nPerth WA\n## Full job description\nRequirements\n- Python experience.'
    assert confirmed_listing_employer(alias,text)=='Example Group'
    assert confirmed_listing_employer(alias,text.replace('ExampleBrand','OtherBrand'))=='Employer on job listing'


def test_requirement_heading_variants_and_optional_scope(workspace):
    text='# Systems Specialist\nCompany: Example Energy Ltd\nWhat you\'ll need to succeed: Python automation experience and Microsoft 365 support.\nBenefits: Free training allowance.\nKey Requirements: Proven experience delivering enterprise automation.\nSkills Required: Python and PowerShell experience.'
    j=job().model_copy(update={'description':text})
    workspace.add_job(j,full=True)
    fit=workspace.jobs()[0]['fit']
    assert fit['percent'] is not None
    assert any('Python automation' in x['text'] for x in fit['requirements'])
    assert not any('training allowance' in x['text'] for x in fit['requirements'])


def test_linkedin_public_url_drops_secrets_and_rejects_ambiguity():
    assert public_listing_url('https://www.linkedin.com/jobs/view/123456/?trackingId=secret&otp=secret')=='https://www.linkedin.com/jobs/view/123456/'
    assert public_listing_url('https://www.linkedin.com/jobs/view/systems-specialist-123456/?token=secret')=='https://www.linkedin.com/jobs/view/123456/'
    with pytest.raises(ValueError): public_listing_url('https://www.linkedin.com/jobs/search/?currentJobId=123&token=secret')


def test_bonus_bullets_remain_optional(workspace):
    text="# Systems Specialist\nCompany: Example Energy Ltd\nRequirements\n- Python automation experience.\n- Bonus points if you have:\n- Advanced finance experience.\n- Government project experience."
    j=job().model_copy(update={'description':text});workspace.add_job(j,full=True)
    texts=[r['text'] for r in workspace.jobs()[0]['fit']['requirements']]
    assert any('Python automation' in t for t in texts)
    assert not any('finance' in t or 'Government' in t for t in texts)


def test_linkedin_comm_canonical_and_nonpublic_urls_rejected():
    assert public_listing_url('https://www.linkedin.com/comm/jobs/view/12345/?otpToken=secret')=='https://www.linkedin.com/jobs/view/12345/'
    with pytest.raises(ValueError): public_listing_url('https://name:secret@careers.example.com/job/1')
    with pytest.raises(ValueError): public_listing_url('https://careers.example.com/job/1?token=secret')


def test_hydrate_rejects_long_wrapper_short_advert_without_overwrite(workspace):
    j=job().model_copy(update={'description':'# Systems Specialist\nRequirements\n'+('Python and systems support experience. '*30)})
    workspace.add_job(j,full=True)
    workspace.bridge.call=lambda *_:{'content':('metadata wrapper ' * 30)+'\n# Systems Specialist\nShort description.'}
    with pytest.raises(ValueError): workspace.hydrate(j.identity)
    assert workspace.job(j.identity)[1].description==j.description


def test_company_fields_reject_nonentities_but_allow_names():
    for candidate in ['4.8 out of 5','Funding raised AUD 10000000']:
        text='# Systems Specialist\nCompany: '+candidate+'\nRequirements\n- Python experience.'
        assert confirmed_listing_employer(job(),text)=='Employer on job listing'
    for candidate in ['3M','FundingCircle']:
        text='# Systems Specialist\nCompany: '+candidate+'\nRequirements\n- Python experience.'
        assert confirmed_listing_employer(job(),text)==candidate


def test_title_specialization_and_indeed_alias():
    from campus_agent.listing_view import title_matches_source
    for suffix in ['Payroll','Cyber Defence']:
        assert not title_matches_source('Systems Specialist - '+suffix,'# Systems Specialist\n')
    assert title_matches_source('ExampleBrand - Automation Engineer - Perth WA - Indeed.com','# Automation Engineer (ExampleBrand)\n')


def test_company_marketing_scopes_do_not_become_requirements(workspace):
    for i,heading in enumerate(['About Example Helix','Company overview','Our story']):
        text='# Systems Specialist\nCompany: Example Energy Ltd\nRequirements\n- Python automation experience.\n## '+heading+'\nExperience the future of Terraform with our industry-leading products and services.'
        j=job('https://careers.example.com/job/'+str(100+i)).model_copy(update={'description':text});workspace.add_job(j,full=True)
        fit=next(r for r in workspace.jobs() if r['id']==j.identity)['fit']
        assert not any('Terraform' in r['text'] for r in fit['requirements'])


