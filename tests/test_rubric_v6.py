from test_fit import assess,profile
from campus_agent.fit import criterion_parts


def test_location_training_only_has_no_skill_score():
    result=assess('Requirements\nLOCATION Remote in Australia (required) AEST Saturday Wednesday TRAINING 4 weeks Monday Friday',title='Technical Support Specialist')
    assert result['percent'] is None
    assert not result['requirements']
    assert result['separate_checks'][0]['kind']=='location_or_schedule'


def test_headings_adverts_and_apply_dates_do_not_score():
    result=assess("Requirements\nWhat you'll bring will include\nPublished 14 Oct 2026\nApply before 13 Nov 2026\nTo learn more about Davidson, visit davidsonwp.com.\nPython workflow automation experience.")
    assert len(result['requirements'])==1
    assert result['requirements'][0]['value']==1


def test_split_only_independent_clauses_preserve_and_or():
    parts=criterion_parts('Python automation experience; Strong customer communication skills')
    assert len(parts)==2
    assert len(criterion_parts('Python and SQL or Java experience'))==1


def test_essential_gap_weighs_more_than_standard_gap():
    first=assess('Requirements\nPython workflow automation experience.\nMust have Kubernetes production experience.')
    second=assess('Requirements\nPython workflow automation experience.\nKubernetes production experience.')
    assert first['percent']<second['percent']
    assert first['requirements'][1]['importance_weight']==2
    assert first['confidence']['level']=='limited'


def test_weak_word_overlap_is_not_same_as_transferable_task():
    result=assess('Requirements\nExperience with customer relationships and payroll reconciliation.',profile(['Created payroll reports.']))
    assert result['requirements'][0]['value']<=.25
    assert result['confidence']['level']=='limited'


def test_boilerplate_prefixes_preserve_real_duties_and_eligibility():
    from campus_agent.fit import criterion_kind
    for text in ['You will work alongside nurses to administer medication safely.',
                 'Location management experience is required.',
                 'We provide clinical care; you must have current AHPRA registration.',
                 'Training 4 weeks of new staff is required.']:
        assert criterion_kind(text)=='competency'


def test_exclusion_note_does_not_earn_independent_credit():
    result=assess('Requirements\nA Copilot Studio agent deployed to production. Proofs of concept and demonstrations do not count.')
    assert len(result['requirements'])==1
    assert result['requirements'][0]['value']==0


def test_collaboration_and_location_duties_are_retained_without_action_whitelist():
    for text in ['You will work alongside nurses to assess patients and coordinate discharge.',
                 'Location scouting and site inspections are required.']:
        result=assess('Requirements\n'+text,title='Coordinator')
        assert result['requirements']
        assert result['requirements'][0]['text']==text
