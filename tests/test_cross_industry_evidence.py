import pytest
from campus_agent.fit import fit_assessment
from campus_agent.listing_view import listing_view
from campus_agent.locations import location_info
from campus_agent.models import Credential, Experience, Job, Profile
from campus_agent.workspace import Preferences
from test_workspace import profile, workspace


CASES = [
    ('Registered Nurse', 'AHPRA registration', 'Australia',
     ['Current AHPRA registration is required.', 'Medication administration experience.', 'Vital signs documentation experience.'],
     ['Administered medicines during ward shifts.', 'Documented vital observations in patient records.']),
    ('Electrician', 'A-Grade electrical licence', 'VIC',
     ['Must hold a current A-Grade electrical licence.', 'Switchboard installation experience.', 'Experience inspecting electrical wiring with a multimeter.'],
     ['Installed switchboards across commercial sites.', 'Inspected electrical wiring with a multimeter.']),
    ('Café Supervisor', 'RSA certificate', 'VIC',
     ['Valid Responsible Service of Alcohol certificate required.', 'Espresso preparation experience.', 'Experience operating a point-of-sale system.'],
     ['Prepared espresso on busy weekend shifts.', 'Operated the POS system at the counter.']),
]


def candidate(title, credential, region, facts, **changes):
    fields = {'name': credential, 'jurisdiction': region, 'status': 'current', 'expires_on': '2099-06-01'}
    fields.update(changes)
    return Profile(name='Alex Example', email='alex@example.com', summary='Practical work experience in the role.',
        education=[], skills=[], credentials=[Credential(**fields)], experience=[
            Experience(organization='Example Workplace', role=title, dates='2022 – present', bullets=facts)
        ])


def listing(title, requirements):
    return Job(source_id='opportunity', employer='Example Employer', title=title,
        url='https://example.com/jobs/123', location='Melbourne VIC',
        description='Location: Melbourne VIC\n## Requirements\n'+'\n'.join('- '+r for r in requirements))


def assessed(job, profile):
    prefs = Preferences(role_search_mode='custom', custom_role_titles=[job.title])
    return fit_assessment(job, profile, prefs, listing_view(job.description, job.title, job.employer),
        location_info(job.model_dump(), prefs.location), full=True)


@pytest.mark.parametrize('title,credential,region,requirements,facts', CASES)
def test_cross_industry_qualified_profiles_show_real_evidence(title,credential,region,requirements,facts):
    fit = assessed(listing(title,requirements), candidate(title,credential,region,facts))
    assert fit['status']=='Good match', fit['reviews']
    assert fit['percent'] >= 80
    assert fit['coverage']['criteria_count']==3 and fit['coverage']['work_examples']==2
    assert fit['requirements'][0]['evidence'][0]['role']=='Saved qualification'
    assert [r['evidence'][0]['text'] for r in fit['requirements'][1:]] == facts
    assert not fit['auto_eligible']


@pytest.mark.parametrize('changes', [
    {'status':'expired'}, {'expires_on':'2000-01-01'}, {'status':'pending'}, {'jurisdiction':'NSW'}, {'name':'Electrical licence'},
])
def test_near_miss_licence_stays_in_review(changes):
    title,credential,region,requirements,facts = CASES[1]
    fit=assessed(listing(title,requirements),candidate(title,credential,region,facts,**changes))
    assert fit['status']=='Needs review'
    assert fit['requirements'][0]['value']==0 and not fit['requirements'][0]['evidence']
    assert not fit['auto_eligible']


def test_licence_does_not_satisfy_a_compound_obligation():
    title,credential,region,requirements,facts=CASES[1]
    requirements = [requirements[0].rstrip('.')+' and independently commission high-voltage switchgear.']+requirements[1:]
    fit = assessed(listing(title,requirements), candidate(title,credential,region,facts))
    assert fit['requirements'][0]['value']==0.5
    assert fit['status']=='Needs review' and not fit['auto_eligible']


@pytest.mark.parametrize('bullet', [
    'I have never installed switchboards.',
    'Planning to install switchboards in the future.',
    'Installed switchboards in a simulated training scenario.',
    'Installed lighting. I have not installed switchboards.',
])
def test_unconfirmed_work_never_gets_full_credit(bullet):
    title,credential,region,requirements,facts = CASES[1]
    fit=assessed(listing(title,requirements),candidate(title,credential,region,[bullet,facts[1]]))
    assert fit['requirements'][1]['value']<1
    assert not fit['auto_eligible']


def test_manual_non_it_packet_preserves_profile_and_plain_letter(workspace, monkeypatch):
    from pypdf import PdfReader
    from pathlib import Path
    title,credential,region,requirements,facts = CASES[0]
    job=listing(title,requirements)
    workspace.save_profile(candidate(title,credential,region,facts))
    workspace.save_preferences(Preferences(role_search_mode='custom',custom_role_titles=[title]))
    workspace.add_job(job,full=True)
    monkeypatch.setattr(workspace,'hydrate',lambda job_id: pytest.fail('A saved full advert should be enough for manual preparation'))
    report=workspace.check_prepare(job.identity)
    assert report['quality']['passed']
    text=''.join(page.extract_text() for page in PdfReader(Path(report['packet'])/'Cover Letter.pdf').pages)
    assert title in text and 'business systems' not in text
    assert workspace.profile.credentials[0].name==credential

@pytest.mark.parametrize('requirement,bullet', [
    ('Medication administration experience.', 'Administering medication is covered in my training program.'),
    ('Medication administration experience.', 'Administered medication during a classroom skills assessment.'),
    ('Vital signs monitoring experience.', 'Monitoring vital signs will be my responsibility starting next week.'),
    ('Operating a point-of-sale terminal.', 'Operated a forklift and repaired the point-of-sale terminal.'),
    ('Operate a point-of-sale terminal independently.', 'Operated a point-of-sale terminal under supervision; independently maintained inventory.'),
    ('Switchboard installation experience.', 'Installed lighting next to a switchboard.'),
])
def test_distinct_work_actions_and_training_are_not_full_matches(requirement,bullet):
    title,credential,region,_,_=CASES[0]
    fit=assessed(listing(title,[requirement]),candidate(title,credential,region,[bullet]))
    assert fit['requirements'][0]['value']<1


def test_credential_does_not_establish_tenure():
    title,credential,region,_,facts=CASES[0]
    fit=assessed(listing(title,['Current AHPRA registration and 2 years experience.']),candidate(title,credential,region,facts))
    assert fit['requirements'][0]['value']<1


def test_legacy_profile_dump_and_style_fingerprint_keep_empty_credentials_out(profile):
    assert profile.credentials == []
    assert 'credentials' not in profile.model_dump() and '"credentials"' not in profile.model_dump_json()


@pytest.mark.parametrize('requirement,bullet', [
    ('Medication administration experience.', 'Administered medication to training mannequins.'),
    ('Monitor patient vital signs.', 'Monitored patient vital signs in a role-play exercise.'),
    ('Operate a point-of-sale terminal.', 'Operated a point-of-sale terminal in a demonstration at the training centre.'),
    ('Experience operating an espresso machine.', 'Operated the counter beside the espresso machine.'),
    ('Operating a point-of-sale terminal for 2 years and an espresso machine for 5 years.', 'Operated a point-of-sale terminal and an espresso machine for 2 years.'),
])
def test_simulated_work_unrelated_objects_and_multiple_tenures_stay_in_review(requirement,bullet):
    title,credential,region,_,_=CASES[0]
    fit=assessed(listing(title,[requirement]),candidate(title,credential,region,[bullet]))
    assert fit['requirements'][0]['value']<1


def test_named_degree_requires_the_recorded_level_and_discipline():
    title,credential,region,_,facts=CASES[0]
    p=candidate(title,credential,region,facts)
    job=listing(title,['Bachelor degree in education is required.'])
    assert assessed(job,p.model_copy(update={'education':['Diploma in education']}))['requirements'][0]['value']==0
    assert assessed(job,p.model_copy(update={'education':['Bachelor of Education (expected 2028)']}))['requirements'][0]['value']==0
    assert assessed(job,p.model_copy(update={'education':['Bachelor of Education (abandoned)']}))['requirements'][0]['value']==0
    assert assessed(job,p.model_copy(update={'education':['Bachelor of Education']}))['requirements'][0]['value']==1


@pytest.mark.parametrize('required,saved,region,value',[
    ('Current AHPRA registration as a Registered Nurse.', 'AHPRA registration as a Registered Nurse', 'Australia', 1),
    ('Current AHPRA registration as a Registered Nurse.', 'AHPRA registration', 'Australia', 0),
    ('Current forklift licence LF is required.', 'LF forklift licence', 'VIC', 1),
    ('Current forklift licence LF is required.', 'LO forklift licence', 'VIC', 0),
    ('Current AHPRA registration is required.', 'AHPRA registration', '', 0),
    ('Current AHPRA registration in VIC.', 'AHPRA registration', 'VIC', 0),
])
def test_credential_class_and_recorded_scope_are_specific(required,saved,region,value):
    title,_,_,_,facts=CASES[0]
    fit=assessed(listing(title,[required]),candidate(title,saved,region,facts))
    assert fit['requirements'][0]['value']==value
