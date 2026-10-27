"""Incomplete listing acceptance: never turn snippets and board tags into full gauges."""
from test_dashboard_acceptance import candidate,role,fit
from campus_agent.fit import fit_assessment
from campus_agent.workspace import Preferences
from campus_agent.listing_view import listing_view,confirmed_listing_employer,normalize_listing
from campus_agent.locations import location_info

TEXT='Location: Melbourne VIC\nRequirements\n- Python workflow automation experience.\n- Power Automate workflow experience.\n- Microsoft 365 systems support experience.'


def assess(text,full=True,employer='Example Employer'):
 j=role(text).model_copy(update={'employer':employer})
 return fit_assessment(j,candidate(),Preferences(),listing_view(text,j.title,j.employer),location_info(j.model_dump(),Preferences().location),full=full)


def test_unread_listing_has_no_percentage_or_full_component_bars():
 value=assess(TEXT,full=False)
 assert value['percent'] is None and not value['auto_eligible']
 assert value['assessment_state']=='incomplete'
 assert value['assessment_notice']
 assert all(b['state']=='pending' and b['points'] is None and b['covered'] is None for b in value['breakdown'])


def test_full_intro_without_requirements_stays_unassessed():
 value=assess('Location: Melbourne VIC\nAbout the role\nBuild Python workflow automation and help teams use their systems.')
 assert value['percent'] is None and not value['auto_eligible']
 assert 'requirements' in value['assessment_notice'].lower()


def test_missing_employer_has_no_overall_percentage():
 value=assess(TEXT,employer='Unknown')
 assert value['percent'] is None and not value['auto_eligible']
 assert 'employer' in value['assessment_notice'].lower()


def test_complete_identified_role_can_still_be_assessed():
 value=assess(TEXT)
 assert value['assessment_state']=='assessed'
 assert value['percent']>=80 and value['auto_eligible']
 assert all(b['state']=='assessed' for b in value['breakdown'])


def test_closed_unread_listing_remains_closed():
 value=assess(TEXT+'\nJob closed',full=False)
 assert value['percent']==0 and value['status']=='Closed'
 assert not value['auto_eligible']


def test_flat_board_tags_do_not_become_employer_requirements():
 text='# Automation Specialist * Example Employer - 4.2 * Melbourne VIC ## Qualifications * Kubernetes * Python ## Full Job Description #### About the role Build Python workflow automation. #### Requirements * Python workflow automation experience. * Power Automate workflow experience. * Microsoft 365 systems support experience.'
 view=listing_view(text,'Automation Specialist','Example Employer')
 assert 'Kubernetes' not in str(view['sections'])
 assert 'Requirements' in [s['title'] for s in view['sections']]
 assert len(next(s for s in view['sections'] if s['title']=='Requirements')['blocks'][0]['items'])==3


def test_short_board_intro_does_not_invent_mandatory_criteria():
 text='# Automation Specialist * Example Employer - 4.2 * Melbourne VIC ## Qualifications * Kubernetes * Python ## Full Job Description #### About the role Build Python workflow automation for business teams.'
 value=assess(text)
 assert value['coverage']['criteria_count']==0 and value['percent'] is None
 assert 'Kubernetes' not in value.get('unconfirmed_skills',[])


def test_source_employer_uses_board_header_not_title_suffix():
 j=role(TEXT).model_copy(update={'url':'https://www.simplyhired.com.au/job/example','employer':'Employer on job listing'})
 text='# Automation Specialist\n- Example Employer - 4.2\n- Melbourne VIC\n## Full Job Description\nBuild workflow automations.'
 assert confirmed_listing_employer(j,text)=='Example Employer'
 assert confirmed_listing_employer(j.model_copy(update={'url':'https://unrelated.example/job/1'}),text)=='Employer on job listing'


def test_matching_structured_title_can_have_verified_employer_suffix():
 import json
 data={'@type':'JobPosting','title':'Automation Specialist','hiringOrganization':{'name':'Example Employer'},'description':'<h2>Requirements</h2><ul><li>Python workflow automation experience.</li></ul>'}
 text='<html><script type="application/ld+json">'+json.dumps(data)+'</script></html>'
 cleaned=normalize_listing(text,'Automation Specialist - Example Employer')
 assert not cleaned.startswith('Listing mismatch:')
 assert 'Employer: Example Employer' in cleaned
 wrong=normalize_listing(text,'Automation Specialist - Unrelated Employer')
 assert wrong.startswith('Listing mismatch:')
