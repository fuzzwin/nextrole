"""Synthetic source/rubric regressions; no private applicant or saved advert data."""
import pytest
from test_fit import assess, profile
from campus_agent.listing_view import source_problem


def points(fit, name):
    return next(b['points'] for b in fit['breakdown'] if b['id']==name)


def test_specific_work_points_change_with_supported_requirements():
    base='Requirements\n- Python automation experience.\n- SQL database administration experience.\n- Jira project coordination experience.'
    partial=assess(base)
    fuller=assess(base,profile(['Built Python automation.','Administered SQL databases.','Coordinated Jira projects.'],['Python','SQL','Jira']))
    assert points(partial,'experience')<points(fuller,'experience')
    assert fuller['percent']>partial['percent']
    assert partial['percent']!=59


def test_adjective_alone_does_not_lower_support():
    assert assess('Requirements\nPython automation experience.')['requirements']==assess('Requirements\nEffective Python automation experience.')['requirements'] or (
        assess('Requirements\nPython automation experience.')['requirements'][0]['value']==
        assess('Requirements\nEffective Python automation experience.')['requirements'][0]['value']==1)


@pytest.mark.parametrize('fact',[
    'I have never deployed Python automation.',
    'I plan to build Python automation in future.',
    'Built a Python prototype for a training exercise.',
    'Python automation knowledge.',
])
def test_negative_future_and_prototype_do_not_earn_full_experience(fact):
    fit=assess('Requirements\n- Python automation experience.',profile([fact],['Python']))
    assert points(fit,'experience')<40
    assert not fit['auto_eligible']


def test_degree_record_is_used_but_does_not_prove_compound_requirement():
    p=profile();p.education=['Bachelor of Information Systems']
    good=assess('Requirements\nFormal tertiary qualifications in Information Systems or related discipline.',p)
    compound=assess('Requirements\nFormal tertiary qualifications in Information Systems and fluent Japanese.',p)
    assert good['requirements'][0]['value']==1
    assert compound['requirements'][0]['value']<1


@pytest.mark.parametrize('record',['CISSP expired','Studying CISSP','Previously held CISSP'])
def test_expired_or_planned_credentials_do_not_satisfy_current_credential(record):
    p=profile();p.skills.append(record)
    fit=assess('Requirements\nCurrent CISSP certification required.',p)
    assert fit['requirements'][0]['value']==0


def test_specialist_duration_needs_explicit_relevant_duration():
    text='Requirements\n5+ years Python automation experience.'
    assert assess(text)['requirements'][0]['value']==0
    p=profile(['Built Python automation for 6 years.'])
    assert assess(text,p)['requirements'][0]['value']>0


@pytest.mark.parametrize('heading',['Your background:','Required skills and qualifications','What you will bring','To be successful in this role','Your skills and experience'])
def test_heading_variants_are_assessed(heading):
    fit=assess(heading+'\nPython automation experience.')
    assert fit['assessment_state']=='assessed'
    assert fit['coverage']['criteria_count']==1


def test_directory_without_numeric_heading_is_rejected():
    text='\n'.join('### Role '+str(i)+'\n#### Employer '+str(i)+'\nRequirements\nPython experience.' for i in range(8))
    fit=assess(text)
    assert fit['percent'] is None
    assert fit['source_state']=='search_results'


@pytest.mark.parametrize('text,expected',[
    ('L0 is out of bounds\nTotal lines: 0','source_unavailable'),
    ('This summary is not verbatim. Python experience.','source_summary'),
    ('[wordlim 200] Overview ... Job summary ... Python experience.','source_summary'),
])
def test_failed_and_summary_captures_are_pending(text,expected):
    fit=assess(text)
    assert fit['percent'] is None and fit['source_state']==expected


def test_original_closed_notice_is_zero_but_recommendation_does_not_close_role():
    fit=assess('Es tut uns leid. Die Stelle, auf die Sie sich bewerben möchten, wurde besetzt.')
    assert fit['percent']==0 and fit['assessment_state']=='closed'
    text='Requirements\nPython automation experience.\nSimilar jobs\nPosition has been filled.'
    assert source_problem(text) is None
    assert assess(text)['assessment_state']=='assessed'


def test_score_matches_components_unless_explicit_cap():
    fit=assess('Requirements\nPython automation experience.\nSQL database administration.\nJira coordination.')
    total=sum(b['points'] or 0 for b in fit['breakdown'])
    assert fit['percent']==min(total,fit['cap']['limit']) if fit['cap'] else fit['percent']==total


def test_unrelated_retail_duration_does_not_prove_python_tenure():
    p=profile(['Built Python automation; previously worked 6 years in retail.'])
    fit=assess('Requirements\n5+ years Python automation experience.',p)
    assert fit['requirements'][0]['value']==0


@pytest.mark.parametrize('fact',[
    'Built Python automation while working for 6 years in retail.',
    'Built Python automation after working for 6 years.',
    'Built Python automation, previously worked for 6 years.',
])
def test_duration_of_unrelated_employment_is_not_specialist_tenure(fact):
    fit=assess('Requirements\n5+ years Python automation experience.',profile([fact]))
    assert fit['requirements'][0]['value']==0


def test_unrelated_automation_does_not_prove_python_automation():
    p=profile(['Built Python websites, and managed unrelated automation.'])
    fit=assess('Requirements\nPython automation experience.',p)
    assert fit['requirements'][0]['value']<1
    assert points(fit,'experience')<40


@pytest.mark.parametrize('heading',['More jobs like this','Find similar jobs','See also','Explore more jobs'])
def test_recommendation_closure_does_not_close_primary_role(heading):
    fit=assess('Requirements\nPython automation experience.\n'+heading+'\nJob closed.')
    assert fit['assessment_state']=='assessed'
