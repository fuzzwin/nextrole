"""0.10.0 guided fit review: suggestions point, people grade. Synthetic profile only."""
import pytest

from campus_agent.evidence_suggest import credential_like, suggest
from campus_agent.fit import custom_work_value
from campus_agent.models import Experience, Job, Profile
from campus_agent.scoring_comparison import compare
from campus_agent.transfer_fit import reviewed_fit


def nurse():
    return Profile(
        name='Sam Example', email='sam@example.com',
        summary='Registered nurse with acute ward experience.',
        education=['Bachelor of Nursing, Example University, 2018'],
        skills=['Patient assessment', 'Clinical handover', 'Rostering'],
        experience=[Experience(organization='Example Health', role='Registered Nurse, Surgical Ward', dates='2020 - present', bullets=[
            'Led after-hours shifts of six nurses on a 28-bed surgical ward.',
            'Administered medications and completed patient assessments for post-operative patients.',
            'Precepted eight graduate nurses through their first rotation.',
            'Recorded care in the electronic medical record and completed clinical handover each shift.'])])


def rows(*texts, importance='standard'):
    return [dict(id=str(i), text=text, quote=text, importance=importance, kind='competency') for i, text in enumerate(texts)]


def test_suggestions_rank_the_matching_bullet_first_for_a_non_it_profile():
    requirements = rows('Administer medications safely in line with policy',
                        'Support and precept graduate nurses and students',
                        'Take part in clinical handover and document care in the electronic medical record',
                        'Demonstrated experience leading a shift or team')
    found = suggest(requirements, nurse())
    assert found['0'][0]['id'] == 'work:0:1' and 'medications' in found['0'][0]['matched']
    assert found['1'][0]['id'] == 'work:0:2'
    assert found['2'][0]['id'] == 'work:0:3'
    assert found['3'][0]['id'] == 'work:0:0'
    assert all(len(items) <= 3 for items in found.values())


def test_unrelated_and_generic_wording_gives_no_suggestion():
    requirements = rows('Experience with warehouse management systems and inventory control',
                        'Strong knowledge of manual handling and workplace safety',
                        'Forklift licence (LF)')
    found = suggest(requirements, nurse())
    assert found == {'0': [], '1': [], '2': []}


def test_licences_are_not_evidenced_by_work_bullets():
    text = 'Current AHPRA registration as a Registered Nurse'
    assert credential_like(text)
    assert all(fact['kind'] in {'credential', 'education'} for fact in suggest(rows(text), nurse())['0'])


def test_comparison_carries_suggestions_but_never_grades_from_them():
    profile = nurse()
    requirements = rows('Support and precept graduate nurses and students',
                        'At least two years of acute surgical ward experience')
    job = Job(source_id='test', employer='Example Hospital', title='Registered Nurse', url='https://example.invalid/rn',
              description='Requirements\n' + '\n'.join(row['text'] for row in requirements), location='Geelong VIC')
    result = compare(job, profile, requirements)
    assert result['suggestions']['0'][0]['id'] == 'work:0:2'
    assert result['duration_criteria'] == ['1']
    # Suggestions leave every rules-only grade untouched: nothing is rated until a person confirms it.
    assert {row['evidence_state'] for row in result['rules']['requirements']} == {'unknown'}
    assert result['rules']['percent'] is None


def test_past_tense_bullets_from_any_occupation_count_as_delivered_work():
    for text in ['Recorded care in the electronic medical record each shift.',
                 'Precepted eight graduate nurses through their first rotation.',
                 'Welded steel frames to drawings for commercial fit-outs.']:
        assert custom_work_value(text) == 1, text
    for text in ['Experienced nurse with six years on wards.', 'Registered nurse.', 'Learned Python in a short course.',
                 'Observed surgery during placement.', 'Shadowed a senior electrician.', 'Proposed a new roster.',
                 'Would have recorded care.', 'Demonstrated wound care in a classroom skills assessment.']:
        assert custom_work_value(text) < 1, text


def test_reviewer_can_confirm_direct_work_and_guard_errors_name_the_criterion():
    profile = nurse()
    requirements = rows('Support and precept graduate nurses and students',
                        'At least two years of acute surgical ward experience')
    confirmed = reviewed_fit(requirements, profile, [
        {'id': '0', 'status': 'direct', 'evidence_ids': ['work:0:2'], 'reason': 'Reviewed as direct experience.'},
        {'id': '1', 'status': 'unknown', 'evidence_ids': [], 'reason': 'No duration stated.'}])
    assert confirmed['percent'] == 100 and confirmed['evidence_coverage_percent'] == 50
    with pytest.raises(ValueError) as error:
        reviewed_fit(requirements, profile, [
            {'id': '0', 'status': 'direct', 'evidence_ids': ['work:0:2'], 'reason': 'Reviewed as direct experience.'},
            {'id': '1', 'status': 'direct', 'evidence_ids': ['work:0:0'], 'reason': 'Six years on the ward.'}])
    message = str(error.value)
    assert 'At least two years of acute surgical ward experience' in message
    assert 'states the duration' in message and 'tenure' in message
