"""Frozen behavioral acceptance for the 2026-10-28 dashboard revision."""
from campus_agent.models import Job, Profile, Experience
from campus_agent.workspace import Workspace, Preferences
from campus_agent.listing_view import listing_view
from campus_agent.fit import fit_assessment
from campus_agent.locations import location_info


def candidate():
    return Profile(name='Alex Example',email='alex@example.com',summary='Workflow automation and systems support.',education=[],skills=['Python','Power Automate','Microsoft 365'],experience=[Experience(organization='Example',role='Systems Specialist',dates='2021 - Present',bullets=['Built Python workflow automation for payment files.','Delivered Power Automate approval workflows.','Administered Microsoft 365 and Entra ID for IT onboarding.'])])


def role(text, title='Automation Specialist', location='Melbourne, VIC'):
    return Job(source_id='test',employer='Example Employer',title=title,url='https://example.com/job/1',location=location,description=text)


def fit(job, profile=None):
    return fit_assessment(job,profile or candidate(),Preferences(),listing_view(job.description,job.title,job.employer),location_info(job.model_dump(),Preferences().location),full=True)


def test_thin_listing_is_not_a_perfect_match():
    value=fit(role('Location: Melbourne VIC\nRequirements\n- Python workflow automation experience.'))
    assert value['percent']<80
    assert not value['auto_eligible']
    assert value['coverage']['criteria_count']==1


def test_negated_and_prototype_facts_do_not_prove_delivery():
    p=candidate()
    p.skills=['Python','Power Automate']
    p.experience[0].bullets=['No hands-on Python experience.','Proposed Power Automate approval workflows before rollout.']
    value=fit(role('Location: Melbourne VIC\nRequirements\n- Python automation experience.\n- Delivered Power Automate workflows.\n- Production Python development.'),p)
    assert value['percent']<80 and not value['auto_eligible']
    assert not any(r['status']=='Supported' for r in value['requirements'])
    assert next(b for b in value['breakdown'] if b['id']=='skills')['points']<30


def test_fully_supported_role_can_be_an_automatic_strong_match(tmp_path):
    ws=Workspace(tmp_path)
    try:
        ws.save_profile(candidate())
        job=role('Location: Melbourne VIC\nAbout the role\nBuild workflow automations and support business systems.\nRequirements\n- Python workflow automation experience.\n- Power Automate workflow delivery experience.\n- Microsoft 365 systems support experience.')
        ws.add_job(job,full=True)
        row=ws.jobs()[0]
        assert row['fit']['percent']>=80 and row['fit']['auto_eligible'] and row['top_match']
        assert row['top_reason'] and row['reading_view']['overview']
        ws.set_top_listing(job.identity,True)
        ws.save_profile(candidate().model_copy(update={'skills':[], 'experience':[]}))
        row=ws.jobs()[0]
        assert not row['top_match'] and row['top_saved']
    finally:
        ws.close()


def test_out_of_area_role_cannot_be_automatic_top(tmp_path):
    ws=Workspace(tmp_path)
    try:
        ws.save_profile(candidate())
        job=role('Location: Sydney NSW\nRequirements\n- Python workflow automation experience.\n- Power Automate workflow delivery experience.\n- Microsoft 365 systems support experience.',location='Sydney NSW')
        ws.add_job(job,full=True)
        assert not ws.jobs()[0]['top_match']
    finally:
        ws.close()


def test_salary_keeps_units_and_rejects_other_money():
    cases=[('Salary: $110,000 - $130,000 + super', 'year'),('$650–$800 per day + GST','day'),('Pay rate: $55.50 per hour + super','hour'),('Salary\nAUD 120k–140k package','year')]
    for text,period in cases:
        data=listing_view('About the role\nBuild automations.\n'+text,'Automation Specialist','Example')
        assert data['salary']['period']==period
        assert data['salary']['evidence'] and data['salary']['display']
    for text in ['Benefits\n$2,000 learning allowance.','Salary packaging up to $15,900.','About the role\nBuild workflows.\nSimilar jobs\nSalary: $200,000 per year']:
        assert listing_view(text)['salary']['status']=='not_stated'


def test_conflicting_salary_is_flagged():
    data=listing_view('Salary: $100k - $120k per year\nRemuneration: $180k - $200k per year')
    assert data['salary']['status']=='conflicting'
    assert data['salary']['alternatives']
