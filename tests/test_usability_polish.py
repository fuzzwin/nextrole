from campus_agent.listing_view import listing_view
from campus_agent.listing_info import clean_summary
from campus_agent.locations import location_info


def test_summary_markup_and_truncation_preserve_words():
    source = 'About the role\n' + ('Build useful systems for people. ' * 30) + '【1†source】'
    view = listing_view(source)
    assert len(view['overview']) <= 501
    assert view['overview'].endswith('…')
    assert view['overview'][:-1].endswith('.')
    assert '【' not in view['overview']
    assert '####' not in clean_summary('#### About the role 【2†source】')


def test_location_removes_only_exact_employer_prefix_and_keeps_evidence():
    info = location_info({'description':'Location: Example Corp Sydney NSW', 'employer':'Example Corp', 'location':''}, '')
    assert info['display'] == 'Sydney NSW'
    assert 'Example Corp' in info['evidence']
    suburb = location_info({'description':'Location: North Sydney, Sydney NSW', 'employer':'Example Corp', 'location':''}, '')
    assert suburb['display'] == 'North Sydney, Sydney NSW'


def test_remote_label_does_not_repeat():
    result = location_info({'description':'', 'location':''}, '', override='Remote - Remote')
    assert result['display'] == 'Remote'
    assert result['arrangement'] == 'Remote'
    assert result['evidence'] == 'Saved by you'


def test_indivisible_long_summary_is_omitted_without_changing_source():
    source = 'About the role\n' + 'x' * 600
    assert listing_view(source)['overview'] == '…'
    assert 'x' * 600 in source
