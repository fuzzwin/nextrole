import pytest
from test_fit import assess, profile


def test_no_tool_advert_uses_the_existing_work_and_requirements_weights():
    fit = assess('Requirements\n- Experience coordinating projects.',
                 profile(['Coordinated projects.']), title='Project Coordinator')
    assert [c['weight'] for c in fit['breakdown']] == [0, 57, 43]
    assert fit['requirements'][0]['value'] == 1
    assert fit['percent'] == 79  # Sparse evidence still needs review.
    assert not fit['auto_eligible']


def test_explicit_mdm_alternatives_credit_intune_and_keep_the_original_requirement():
    text = 'Have experience with an MDM platform (such as Jamf, Kandji, Intune or Google endpoint management)'
    fit = assess('Requirements\n- '+text, profile(
        ['Deploy PCs and applications through Intune, SCCM and Group Policy.'], skills=['Intune']))
    assert fit['requirements'][0]['value'] == 1
    assert fit['requirements'][0]['text'] == text
    assert fit['matched_skills'] == ['Intune']
    assert fit['unconfirmed_skills'] == []


@pytest.mark.parametrize('clause', [
    'Experience with Intune and Jamf.',
    'Experience with an MDM platform (such as Jamf, Kandji, Intune or Google endpoint management) and fluency in German.',
])
def test_alternative_does_not_erase_other_mandatory_requirements(clause):
    fit = assess('Requirements\n- '+clause, profile(
        ['Deploy PCs through Intune.'], skills=['Intune']))
    assert fit['requirements'][0]['value'] < 1
    assert not fit['auto_eligible']


@pytest.mark.parametrize('fact,expected', [
    ('Administer Microsoft 365 accounts and licensing.', 1),
    ('Never administered Microsoft 365 accounts.', 0.5),
    ('Plan to administer Microsoft 365 accounts.', 0.5),
])
def test_administration_inflection_preserves_work_maturity(fact, expected):
    fit = assess('Requirements\n- Experience administering Microsoft 365.',
                 profile([fact], skills=['Microsoft 365']))
    assert fit['requirements'][0]['value'] == expected
    if fact.startswith('Never'):
        assert all(e['role'] == 'Saved skill' for e in fit['requirements'][0]['evidence'])


def test_best_matching_work_example_precedes_incidental_overlap():
    p = profile(['Built prototype project dashboards.',
                 'Coordinated infrastructure projects and managed change control.'])
    fit = assess('Requirements\n- Experience coordinating infrastructure projects and managing change control.',
                 p, title='Project Coordinator')
    assert fit['requirements'][0]['evidence'][0]['original_text'] == p.experience[0].bullets[1]
