"""Synthetic regressions for evidence ranking, extraction and conservative tenure."""
from datetime import date
import pytest
from test_fit import assess, profile
from campus_agent.fit import criterion_kind, criterion_parts
from campus_agent.tenure import employment_interval, general_support_duration


def fact(text='Resolved service desk incidents.', dates='June 2021 - Present', role='IT Support Specialist', org='Example'):
    return {'text':text,'dates':dates,'role':role,'organisation':org}


def test_general_support_tenure_uses_dates_and_retains_sources():
    result=general_support_duration('At least five years of experience in IT support.',[fact()],today=date(2026,11,11))
    assert result['tenure']['months_at_least']==64
    assert result['text']==fact()['text']
    assert result['tenure']['roles'][0]['dates']=='June 2021 - Present'


@pytest.mark.parametrize('requirement',[
    '5 years Python automation experience.',
    '5 years IT support with Python.',
    '5 years IT support for external customers.',
    '5 years IT support in healthcare.',
    '5 years senior IT support experience.',
    '5 years IT support and software development.',
])
def test_support_dates_never_establish_specialist_scope(requirement):
    assert general_support_duration(requirement,[fact()],today=date(2026,11,11)) is None


@pytest.mark.parametrize('record',[
    fact(role='Retail Assistant'),fact(dates='2021'),fact(dates='2027 - Present'),
    fact(text='Built prototype support tools.'),fact(text='Never supported users.'),
])
def test_unrelated_future_undated_and_qualified_records_do_not_prove_tenure(record):
    assert general_support_duration('3 years IT support experience.',[record],today=date(2026,11,11)) is None


def test_overlap_duplicate_bullets_and_gaps_are_not_double_counted():
    records=[fact(dates='January 2021 - January 2024'),fact(dates='January 2021 - January 2024',text='Administered accounts.'),fact(dates='January 2022 - January 2024',org='Other')]
    assert general_support_duration('4 years IT support experience.',records,today=date(2026,11,11)) is None
    records.append(fact(dates='January 2025 - January 2026',org='Third'))
    assert general_support_duration('4 years IT support experience.',records,today=date(2026,11,11)) is None
    assert general_support_duration('3 years IT support experience.',records,today=date(2026,11,11))['tenure']['months_at_least']==46


def test_imprecise_year_dates_are_conservative():
    assert employment_interval('2021 - 2026',date(2026,11,11))==(date(2021,12,31),date(2026,1,1))
    assert general_support_duration('5 years IT support experience.',[fact(dates='2021 - 2026')],today=date(2026,11,11)) is None


def test_support_tenure_reaches_assessment_but_tool_tenure_does_not(monkeypatch):
    monkeypatch.setattr('campus_agent.tenure.assessment_day',lambda:date(2026,11,11))
    p=profile(['Resolved service desk incidents.','Built Python automation.'])
    support=assess('Requirements\nAt least 5 years IT support experience.',p)
    assert support['requirements'][0]['value']==1
    assert support['requirements'][0]['evidence'][0]['tenure']['months_at_least']==64
    assert assess('Requirements\nAt least 5 years Python automation experience.',p)['requirements'][0]['value']==0


def test_weak_example_does_not_reduce_strong_evidence():
    strong='Coordinated infrastructure projects and managed change control.'
    text='Requirements\nExperience coordinating infrastructure projects and managing change control.'
    before=assess(text,profile([strong]))
    after=assess(text,profile(['Built prototype infrastructure project dashboards.',strong]))
    assert before['requirements'][0]['value']==after['requirements'][0]['value']==1
    assert after['requirements'][0]['evidence'][0]['original_text']==strong
    assert before['breakdown']==after['breakdown']


def test_tool_example_prefers_actual_matching_task_over_first_tool_mention():
    p=profile(['Built Python websites.','Built Python automation.'])
    result=assess('Requirements\nPython automation experience.',p)
    assert result['requirements'][0]['evidence'][0]['text']=='Built Python automation.'


def test_source_urls_do_not_score_or_introduce_tools():
    result=assess('Requirements\n- Python automation experience.\n- Employer source: https://example.com/java-support\n- [Original advert](https://example.com/sql)')
    assert len(result['requirements'])==1
    assert result['matched_skills']==['Python']
    assert not result['unconfirmed_skills']
    assert criterion_kind('Maintain integrations with https://example.com using Python.')=='competency'


def test_semicolons_split_qualification_and_work_without_losing_original_or_weight():
    text='Degree in Information Technology required; Python automation experience; experience administering Microsoft 365.'
    result=assess('Requirements\n'+text,profile(['Built Python automation.','Administer Microsoft 365 accounts.']))
    assert len(result['requirements'])==3
    assert [r['value'] for r in result['requirements']]==[0,1,1]
    assert all(r['source_texts']==[text] for r in result['requirements'])
    assert all(r['importance_weight']==2 for r in result['requirements'])


def test_split_independent_and_clauses_preserves_tool_alternatives():
    assert len(criterion_parts('Python automation experience and ability to communicate with customers.'))==2
    assert criterion_parts('Python and SQL or Java experience')==['Python and SQL or Java experience']
    assert len(criterion_parts('Degree in IT; or equivalent professional experience.'))==1


def test_scope_shared_after_semicolon_stays_together():
    assert len(criterion_parts('Python automation; SQL administration; both in production.'))==1


def test_source_link_in_same_paragraph_does_not_hide_real_requirement():
    result=assess('Requirements\nEmployer source: https://example.com/advert. Python automation experience.')
    assert len(result['requirements'])==1
    assert result['requirements'][0]['value']==1


@pytest.mark.parametrize('requirement',[
    '3 years of application support experience.',
    '3 years of IT support experience; in healthcare.',
    '3 years of technical support experience; for external customers only.',
    'At least 2.5 years of IT support experience.',
])
def test_review_specialisation_and_qualifier_scope(requirement):
    assert general_support_duration(requirement,[fact()],today=date(2026,11,11)) is None
    if ';' in requirement: assert len(criterion_parts(requirement))==1


def test_review_invalid_year_and_unrelated_deployment():
    assert employment_interval('0000 - Present') is None
    assert general_support_duration('3 years IT support experience.',[fact(text='Developed deployment tooling for external marketing.')],today=date(2026,11,11)) is None


def test_review_inline_source_does_not_create_skill():
    result=assess('Requirements\nBuild a support portal; source: https://example.com/python')
    assert 'Python' not in result['matched_skills']+result['unconfirmed_skills']


def test_review_display_limit_never_reduces_score():
    text='Requirements\nAudit compliance findings for executive leadership.'
    facts=['Documented audit entries.','Developed prototype audit compliance findings.']
    first=assess(text,profile(facts))
    second=assess(text,profile(facts+['Created audit checklist.']))
    assert first['requirements'][0]['value']==second['requirements'][0]['value']==0.5


def test_review_unrelated_action_and_object_do_not_combine():
    result=assess('Requirements\nResolve escalated billing incidents.',profile(['Resolved unrelated incidents.','Documented escalated billing procedures.']))
    assert result['requirements'][0]['value']<1


@pytest.mark.parametrize('requirement,bullet',[
    ('Production Python experience.','Ran a Python deployment in production; simulation only.'),
    ('Document Python deployment.','Documented Python deployment; prototype only.'),
    ('3 years IT support experience.','Documented a support incident; mock exercise only.'),
])
def test_review_evidence_disclaimers_survive_splitting(requirement,bullet):
    result=assess('Requirements\n'+requirement,profile([bullet]))
    assert result['requirements'][0]['value']<1


def test_custom_mode_gets_same_general_tenure(monkeypatch):
    from campus_agent.fit import fit_assessment
    from campus_agent.models import Job
    from campus_agent.workspace import Preferences
    from campus_agent.listing_view import listing_view
    monkeypatch.setattr('campus_agent.tenure.assessment_day',lambda:date(2026,11,11))
    job=Job(source_id='test',employer='Example',title='IT Support Specialist',url='https://example.com/job',location='Melbourne',description='Requirements\n3 years IT support experience.')
    result=fit_assessment(job,profile(['Resolved service desk incidents.']),Preferences(role_search_mode='custom',custom_role_titles=['IT Support Specialist']),listing_view(job.description,job.title,job.employer),{'stated':True},full=True)
    assert result['requirements'][0]['value']==1


@pytest.mark.parametrize('bullet',[
    'Supported marketing campaigns.','Resolved billing disputes.','Administered office payroll.',
    'Resolved IT incidents; personal project only.','Resolved IT incidents; example only.',
])
def test_review_tenure_needs_employment_it_duties(bullet):
    assert general_support_duration('3 years IT support experience.',[fact(text=bullet)],today=date(2026,11,11)) is None


@pytest.mark.parametrize('suffix',['specifically serving external customers.','gained in healthcare.'])
def test_review_dependent_scope_never_detaches(suffix):
    text='3 years IT support experience; '+suffix
    assert len(criterion_parts(text))==1
    assert general_support_duration(text,[fact()],today=date(2026,11,11)) is None


def test_review_test_environment_is_not_confirmed_production():
    result=assess('Requirements\nProduction Python experience.',profile(['Ran a Python deployment in production; only on a test environment.']))
    assert result['requirements'][0]['value']<1


def test_explicit_general_support_alternative_counts_without_assuming_specialist_tenure(monkeypatch):
    monkeypatch.setattr('campus_agent.tenure.assessment_day',lambda:date(2026,11,11))
    requirement='Minimum 2 years of relevant experience in IT support, systems support, or a closely related role.'
    result=assess('Requirements\n'+requirement,profile(['Resolved ServiceNow incidents with vendor escalation.']))
    assert result['requirements'][0]['value']==1


def test_unsupported_degree_does_not_get_lexical_credit():
    result=assess('Requirements\nIT/Computer Science/related diploma or degree; Python automation experience.')
    assert result['requirements'][0]['value']==0


@pytest.mark.parametrize('requirement',[
    'At least 3 years of IT support and 7 years of technical support.',
    '3 years IT support experience; must be in healthcare.',
])
def test_ambiguous_or_multiple_tenures_stay_unconfirmed(requirement):
    assert general_support_duration(requirement,[fact()],today=date(2026,11,11)) is None
    if ';' in requirement: assert len(criterion_parts(requirement))==1


def test_tool_as_means_does_not_establish_it_support_duty():
    assert general_support_duration('3 years IT support experience.',[fact(text='Resolved billing disputes using Microsoft 365.')],today=date(2026,11,11)) is None


def test_sandbox_production_phrase_stays_partial():
    result=assess('Requirements\nProduction Python experience.',profile(['Tested Python production migration in a sandbox.']))
    assert result['requirements'][0]['value']<1


def test_independent_tenure_clause_keeps_its_own_specialist_scope():
    text='IT/Computer Science/related diploma or degree; at least 2 years in technical/application/systems support with a healthcare IT provider supporting external customers; remote support using phone and remote access tools; troubleshooting across software, hardware and networks; competing priorities and customer outcomes; communication and stakeholder management.'
    result=assess('Requirements\n'+text)
    assert len(result['requirements'])==6
    assert result['requirements'][0]['value']==result['requirements'][1]['value']==0


def test_actual_administration_with_uat_is_not_reclassified_as_prototype_work():
    result=assess('Requirements\nNetSuite administration experience.',profile(['Administer NetSuite ERP with sandbox UAT for releases.']))
    assert result['requirements'][0]['value']==1
