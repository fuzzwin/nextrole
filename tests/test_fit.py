from campus_agent.fit import fit_assessment
from campus_agent.models import Job,Profile,Experience
from campus_agent.workspace import Preferences
from campus_agent.listing_view import listing_view
from campus_agent.locations import location_info


def profile(facts=None,skills=None):
    return Profile(name='Alex',email='alex@example.com',summary='IT systems and workflow automation experience.',education=['Bachelor of Audio Production'],skills=skills or ['Python','Power Automate','Copilot Studio: prototype agents'],experience=[Experience(organization='Example Employer',role='IT Support and Systems Specialist',dates='June 2021 - Present',bullets=facts or ['Built a Python utility used monthly by Finance to convert payment files.','Built prototype agents in Copilot Studio, including a daily news briefing.','Recreated a Power Automate workflow, live since June 2026.'])])


def assess(text,p=None,title='Automation Specialist',full=True):
    j=Job(source_id='opportunity',employer='Example Employer',title=title,url='https://example.com/job',description=text,location='Melbourne, VIC')
    view=listing_view(text,title,j.employer)
    return fit_assessment(j,p or profile(),Preferences(),view,location_info(j.model_dump(),'Melbourne Victoria Australia'),full=full)


def test_match_uses_job_requirements_and_work_evidence_not_all_profile_skills():
    text='Location: Melbourne, VIC\nRequirements\n- Python workflow automation experience.'
    fit=assess(text)
    assert fit['percent']==79 and fit['status']=='Needs review'
    assert not fit['auto_eligible']
    assert fit['breakdown']==[
        {'id':'skills','label':'Relevant skills','weight':30,'points':30,'covered':1,'total':1,'state':'assessed'},
        {'id':'experience','label':'Work experience','weight':40,'points':40,'covered':1,'total':1,'state':'assessed'},
        {'id':'requirements','label':'Stated requirements','weight':30,'points':30,'covered':1,'total':1,'state':'assessed'}]
    assert fit['requirements'][0]['status']=='Supported'
    assert fit['strengths'][0]['evidence'] in profile().experience[0].bullets
    assert 'not a hiring probability' in fit['method'].lower()


def test_prototype_and_unrelated_live_work_do_not_satisfy_production_copilot_requirement():
    fit=assess('Location: Melbourne, VIC\nWhat you need\nAt least one Copilot Studio agent that went into production. Proofs of concept and demonstrations do not count.')
    assert fit['percent']<=59 and fit['status']=='Needs review'
    criterion=fit['requirements'][0]
    assert criterion['status']=='Needs confirmation' and not criterion['evidence']
    assert 'prototypes' in criterion['reasons'][0].lower()
    assert all(s['evidence'] in profile().experience[0].bullets or s['evidence'] in profile().skills for s in fit['strengths'])


def test_direct_deployed_agent_fact_supports_that_specific_production_requirement():
    p=profile(['Deployed a Copilot Studio agent to production, used by real colleagues.'])
    fit=assess('Location: Melbourne, VIC\nRequirements\nA Copilot Studio agent deployed to production.',p)
    assert fit['requirements'][0]['status']=='Supported'
    assert fit['requirements'][0]['evidence'][0]['text']==p.experience[0].bullets[0]


def test_missing_mandatory_technology_and_specialist_duration_limit_score():
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Strong .NET / C# development experience.\n- 5+ years hands-on Power Platform experience.\n- Python automation experience.')
    assert fit['percent']<=59 and fit['status']=='Needs review'
    assert any('.NET' in r['label'] for r in fit['reviews'])
    assert any('specialist tenure' in r['label'] for r in fit['reviews'])


def test_optional_requirements_and_related_roles_do_not_create_false_gaps():
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Python workflow automation experience.\nHelpful, not required\n- Kubernetes and Australian citizenship.\nSimilar jobs\n.NET lead developer requiring ten years experience.')
    assert fit['status']=='Needs review'
    assert fit['percent']==79
    assert fit['matched_skills']==['Python']
    assert all(r['label'].startswith('Limited evidence:') for r in fit['reviews'])


def test_non_it_degree_does_not_satisfy_technical_qualification_heading():
    fit=assess('Location: Melbourne, VIC\nSpecialist/Technical Expertise/Qualifications\n- Formal tertiary qualifications in Information Systems or related discipline.\n- Python automation experience.')
    assert fit['percent']<=59
    assert fit['requirements'][0]['status']=='Needs confirmation'
    assert 'credential' in fit['reviews'][0]['label']


def test_five_years_requirement_in_plain_experience_heading_is_not_missed():
    fit=assess("Location: Melbourne, VIC\nWhat you'll need to succeed:\nTechnical Skills:\n- Python automation experience.\nExperience\n- 5+ years hands-on automation experience.")
    assert fit['percent']<=59
    assert any('5+' in r['text'] for r in fit['requirements'])


def test_closed_and_partial_listings_cannot_appear_as_good_matches():
    text='Location: Melbourne, VIC\nNo longer accepting applications\nRequirements\n- Python workflow automation experience.'
    assert assess(text)['status']=='Closed' and assess(text)['percent']==0
    partial=assess(text.replace('No longer accepting applications',''),full=False)
    assert partial['percent'] is None and partial['status']=='Needs review'
    assert partial['assessment_state']=='incomplete'


def test_referee_titles_are_never_used_as_candidate_work_experience():
    from campus_agent.models import Referee
    p=profile(['Unrelated audio editing work.'],skills=['Python'])
    p.referees=[Referee(name='Casey Example',role='IT Systems and Operations Manager',organization='Example Manufacturing')]
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Microsoft 365 systems support and incident management.',p)
    assert not any(s['kind']=='Experience' for s in fit['strengths'])
    assert fit['percent']<70


def test_qualified_power_apps_concept_is_not_confirmed_development_experience():
    p=profile(['Simplified a proposed Power Apps design into Forms and Power Automate flows ahead of rollout.'],skills=['Power Apps'])
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Strong experience designing and building in Power Apps.',p)
    assert fit['requirements'][0]['status']=='Transferable'
    assert fit['status']=='Needs review'
    assert 'proposed Power Apps' in fit['requirements'][0]['evidence'][0]['text']


def test_supported_skill_without_work_example_does_not_become_delivery_experience():
    p=profile(['Unrelated audio editing work.'],skills=['Python'])
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Professional Python development experience.',p)
    assert fit['requirements'][0]['value']<1
    assert fit['requirements'][0]['evidence'][0]['role']=='Saved skill'


def test_commercial_software_engineering_cannot_be_inferred_from_app_prototypes():
    p=profile(['App prototypes. Build React applications using AI coding tools.'],skills=['React'])
    fit=assess('Location: Melbourne, VIC\nRequired Experience\n- Commercial experience as a software engineer.\n- React development experience.',p)
    assert fit['percent']<=59
    assert any('Commercial software-engineering employment' in r['label'] for r in fit['reviews'])


def test_job_requirements_heading_covers_purview_and_unconfirmed_workshops():
    p=profile(['Created an interactive guide to the governed AI Hub.','Map business processes, translating requirements into workflows.'],skills=['Microsoft 365 Copilot'])
    fit=assess('Location: Melbourne, VIC\nJob Requirements\n- Microsoft 365 Copilot knowledge.\n- Knowledge of Microsoft Purview.\n- Experience facilitating workshops.\nShow more Show less\nExperience Designer jobs',p,title='AI Enablement Specialist')
    assert any('Purview' in r['label'] for r in fit['reviews'])
    assert any('Workshop facilitation' in r['label'] for r in fit['reviews'])
    assert not any('Designer' in r['text'] for r in fit['requirements'])


def test_confirmed_user_guides_are_credited_as_work_evidence():
    p=profile(['Created an interactive guide to the governed AI Hub for users.'],skills=['Microsoft 365'])
    fit=assess('Location: Newcastle NSW\nKey criteria\n- Microsoft 365 knowledge.\n- Experience creating guides and communication materials for users.',p,title='Digital Workplace Specialist')
    assert fit['requirements'][1]['status']=='Supported'
    assert any(s['label']=='User guidance and communication' for s in fit['strengths'])


def test_search_redirect_never_receives_a_fit_score():
    fit=assess('# 262 Senior Business Analyst Contract Jobs in United States\n## Requirements\nPython workflow automation experience.')
    assert fit['percent'] is None and fit['status']=='Needs review'
    assert 'search results page' in fit['reviews'][0]['label']


def test_job_closed_footer_overrides_strong_requirements_match():
    fit=assess('Location: Melbourne, VIC\nRequirements\n- Python workflow automation experience.\nApply on employer website\nJob closed')
    assert fit['percent']==0 and fit['status']=='Closed'
