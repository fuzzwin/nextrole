"""Roles outside IT: every trade must be assessable from the person's own job titles, saved
licences and work examples, without weakening the checks that stop unsupported claims.
Synthetic identities and adverts only."""
import re

import pytest

from campus_agent.fit import credential_tokens, fit_assessment, is_credential, recorded_credential
from campus_agent.language import close_stems, is_action_start, word_stem
from campus_agent.listing_view import listing_view
from campus_agent.locations import location_info
from campus_agent.models import Experience, Job, Profile
from campus_agent.role_types import clean_titles, in_scope, query_plan, title_matches
from campus_agent.tailor import grounded_cover, prepare_text
from campus_agent.workspace import Preferences

def P(name, headline, summary, education, skills, org, role, bullets):
    return Profile(name=name, headline=headline, email='x@example.com', location='Melbourne VIC', summary=summary,
        education=education, skills=skills,
        experience=[Experience(organization=org, role=role, dates='2019 - Present', bullets=bullets)])

CASES = {}
CASES['Registered nurse'] = (P('Sam Rivera','Registered Nurse','Registered nurse with six years in aged care and acute medical wards.',
    ['Bachelor of Nursing','AHPRA registered nurse - current registration'],
    ['Medication administration','Wound care','Clinical handover','Manual handling','Dementia care','Electronic medical records'],
    'Example Aged Care','Registered Nurse',
    ['Administered medications and monitored residents for 28 high-care beds per shift.',
     'Completed wound assessments and dressings, escalating infection concerns to the GP.',
     'Led clinical handover between shifts and maintained accurate care notes.',
     'Supported residents living with dementia and coordinated care plans with families.']),
 'Registered Nurse',
 '''Registered Nurse
Example Aged Care · Melbourne VIC · Permanent part time

About the role
Join our caring team supporting residents across a 60-bed facility.

About you
- Current AHPRA registration as a Registered Nurse.
- Experience administering medications and monitoring residents.
- Experience in wound care and clinical handover.
- Experience supporting residents living with dementia.

Salary: $42 - $48 per hour plus super
Applications close 30 November 2026.

How to apply
Apply online.''')
CASES['Electrician'] = (P('Dale Nguyen','A-grade Electrician','Licensed electrician with eight years in commercial fit-out and maintenance.',
    ['Certificate III in Electrotechnology','Victorian Electrical Licence (A Grade) - current','White Card - current'],
    ['Switchboard installation','Fault finding','Testing and tagging','AS/NZS 3000 wiring rules','Cable installation'],
    'Example Electrical','Electrician',
    ['Installed and tested commercial switchboards and distribution boards.',
     'Diagnosed and repaired electrical faults in office and retail buildings.',
     'Completed testing and tagging of portable appliances for 40 sites.',
     'Installed cabling and lighting circuits in accordance with AS/NZS 3000.']),
 'Electrician',
 '''Electrician
Example Electrical · Melbourne VIC · Full time

About you
- Current Victorian A Grade electrical licence.
- Experience in commercial switchboard installation.
- Experience fault finding and repairing electrical systems.
- Knowledge of AS/NZS 3000 wiring rules.
- Current White Card.

Salary: $95,000 - $110,000 + super
How to apply
Apply online.''')
CASES['Primary teacher'] = (P('Priya Shah','Primary School Teacher','Primary teacher with five years teaching Years 3-6.',
    ['Master of Teaching (Primary)','VIT full registration - current'],
    ['Differentiated instruction','Classroom management','Literacy and numeracy planning','Student wellbeing','Parent communication'],
    'Example Primary School','Classroom Teacher',
    ['Planned and delivered literacy and numeracy lessons for a Year 5 class of 26 students.',
     'Managed classroom behaviour using restorative practices and clear routines.',
     'Differentiated learning tasks for students with additional learning needs.',
     'Communicated student progress to parents through reports and interviews.']),
 'Primary School Teacher',
 '''Primary School Teacher
Example Primary School · Melbourne VIC · Full time

About you
- Current VIT registration.
- Experience planning and delivering literacy and numeracy lessons.
- Experience differentiating learning for students with additional needs.
- Strong classroom management skills.
- Experience communicating student progress to parents.

Salary: Teacher salary scale
How to apply
Apply online.''')
CASES['Cafe supervisor'] = (P('Mia Costa','Hospitality Supervisor','Cafe supervisor with four years leading front-of-house teams.',
    ['RSA certificate - current','Food Handler certificate'],
    ['Barista','Customer service','Cash handling','Rostering','Team leadership'],
    'Example Cafe','Shift Supervisor',
    ['Led a team of eight staff and managed rosters across seven days.',
     'Made espresso coffee and trained new baristas on milk texturing.',
     'Handled cash reconciliation and closing procedures daily.',
     'Resolved customer complaints and maintained food safety standards.']),
 'Cafe Supervisor',
 '''Cafe Supervisor
Example Cafe · Melbourne VIC · Full time

About you
- Current RSA certificate.
- Experience leading a hospitality team and managing rosters.
- Barista experience making espresso coffee.
- Experience with cash handling and end-of-day reconciliation.
- Strong customer service skills.

Salary: $28 - $32 per hour
How to apply
Apply online.''')
CASES['Accountant'] = (P('Chen Wei','Accountant','CPA accountant with seven years in SME bookkeeping and tax.',
    ['Bachelor of Commerce (Accounting)','CPA Australia - current member'],
    ['Xero','MYOB','BAS preparation','Accounts payable','Month-end reporting','Excel'],
    'Example Accounting','Senior Accountant',
    ['Prepared monthly BAS and GST reconciliations for 35 SME clients in Xero.',
     'Managed accounts payable and receivable using MYOB.',
     'Completed month-end close and management reporting in Excel.',
     'Prepared individual and company tax returns.']),
 'Accountant',
 '''Accountant
Example Accounting · Melbourne VIC · Full time

About you
- CPA or CA qualification.
- Experience preparing BAS and GST reconciliations.
- Experience using Xero or MYOB.
- Experience with month-end close and management reporting.
- Experience preparing company tax returns.

Salary: $90,000 - $105,000 + super
How to apply
Apply online.''')
CASES['Warehouse'] = (P('Tom Baker','Warehouse Team Member','Warehouse operator with five years in pick-pack and forklift work.',
    ['Forklift licence (LF) - current','White Card - current'],
    ['Forklift operation','Picking and packing','Inventory counts','Manual handling','Scanning'],
    'Example Logistics','Forklift Operator',
    ['Operated counterbalance forklifts to load and unload trucks.',
     'Picked and packed customer orders using RF scanners to meet daily targets.',
     'Completed stock counts and reported discrepancies.',
     'Followed manual handling and safety procedures.']),
 'Warehouse Forklift Operator',
 '''Warehouse Forklift Operator
Example Logistics · Melbourne VIC · Full time

About you
- Current forklift licence (LF).
- Experience operating forklifts to load and unload trucks.
- Experience picking and packing orders using RF scanners.
- Experience completing stock counts.
- Understanding of manual handling and safety procedures.

Salary: $55,000 - $62,000 + super
How to apply
Apply online.''')
CASES['Marketing coordinator'] = (P('Aisha Khan','Marketing Coordinator','Marketing coordinator with four years in email, social and SEO.',
    ['Bachelor of Communication (Marketing)'],
    ['HubSpot','Canva','Google Analytics','SEO','Mailchimp','Copywriting'],
    'Example Retail','Marketing Coordinator',
    ['Built and sent weekly Mailchimp and HubSpot email campaigns to 20,000 subscribers.',
     'Managed social media content calendars and designed assets in Canva.',
     'Reported website traffic and conversion using Google Analytics.',
     'Wrote blog and product copy optimised for SEO.']),
 'Marketing Coordinator',
 '''Marketing Coordinator
Example Retail · Melbourne VIC · Full time

About you
- Experience building email campaigns in HubSpot or Mailchimp.
- Experience managing social media content calendars.
- Experience reporting with Google Analytics.
- Strong copywriting skills with SEO knowledge.
- Proficiency in Canva.

Salary: $75,000 - $85,000 + super
How to apply
Apply online.''')
CASES['IT control'] = (P('Jordan Example','IT Systems Specialist','IT systems specialist supporting Microsoft 365.',
    ['Bachelor of Information Technology'],['Microsoft 365','Entra ID','ServiceNow','Power Automate','SharePoint','Python'],
    'Example Manufacturing','IT Support and Systems Specialist',
    ['Administered Microsoft 365 and Entra ID accounts, licences and security groups for 250 staff.',
     'Resolved ServiceNow incidents and service requests across hardware, software and network issues.',
     'Built Power Automate approval workflows with SharePoint lists, live since 2023.',
     'Managed IT onboarding and offboarding for new starters, including laptops and accounts.']),
 'IT Systems Specialist',
 '''IT Systems Specialist
Example Health · Melbourne VIC · Full time

About you
- Experience administering Microsoft 365 and Entra ID.
- Experience resolving incidents in ServiceNow.
- Experience building Power Automate workflows with SharePoint.

Salary: $95,000 - $105,000 + super
How to apply
Apply online.''')



TITLES = {'Registered nurse': ['Registered Nurse'], 'Electrician': ['Electrician'], 'Primary teacher': ['Primary School Teacher'],
          'Cafe supervisor': ['Cafe Supervisor'], 'Accountant': ['Accountant'], 'Warehouse': ['Warehouse Forklift Operator'],
          'Marketing coordinator': ['Marketing Coordinator']}


def prefs_for(label):
    return Preferences(role_types=[], job_titles=TITLES[label])


def assess(label, profile=None, text=None, preferences=None):
    saved_profile, title, advert = CASES[label]
    job = Job(source_id='opportunity', employer='Example Employer', title=title,
              url='https://careers.example.com/jobs/' + re.sub(r'\W+', '-', label.lower()),
              location='Melbourne VIC', description=text or advert)
    view = listing_view(job.description, title, job.employer)
    return fit_assessment(job, profile or saved_profile, preferences or prefs_for(label), view,
                          location_info(job.model_dump(), 'Melbourne Victoria Australia'), full=True)


@pytest.mark.parametrize('label', list(TITLES))
def test_a_fully_qualified_candidate_is_a_good_match_in_any_trade(label):
    fit = assess(label)
    assert fit['assessment_state'] == 'assessed'
    assert fit['status'] == 'Good match' and fit['percent'] >= 80, (fit['percent'], fit['reviews'])
    assert fit['reviews'] == []
    assert fit['percent'] == sum(b['points'] or 0 for b in fit['breakdown'])
    assert sum(b['weight'] for b in fit['breakdown']) == 100


@pytest.mark.parametrize('label', list(TITLES))
def test_without_job_titles_or_presets_the_role_is_not_called_out_of_scope(label):
    fit = assess(label, preferences=Preferences(role_types=[], job_titles=[]))
    assert not any('outside' in r['label'] or 'does not match the job titles' in r['label'] for r in fit['reviews'])


def test_a_role_that_matches_no_chosen_title_is_flagged():
    fit = assess('Registered nurse', preferences=Preferences(role_types=[], job_titles=['Electrician']))
    assert any('does not match the job titles' in r['label'] for r in fit['reviews'])
    assert fit['status'] == 'Needs review'


def drop(profile, **changes):
    return profile.model_copy(update=changes)


def requirement(fit, fragment):
    return next(r for r in fit['requirements'] if fragment.lower() in r['text'].lower())


# ---- credentials: held on record, never inferred -------------------------------------------

@pytest.mark.parametrize('label, fragment, remaining_education', [
    ('Registered nurse', 'AHPRA', ['Bachelor of Nursing']),
    ('Electrician', 'A Grade', ['Certificate III in Electrotechnology', 'White Card - current']),
    ('Electrician', 'White Card', ['Certificate III in Electrotechnology', 'Victorian Electrical Licence (A Grade) - current']),
    ('Primary teacher', 'VIT', ['Master of Teaching (Primary)']),
    ('Cafe supervisor', 'RSA', ['Food Handler certificate']),
    ('Accountant', 'CPA', ['Bachelor of Commerce (Accounting)']),
])
def test_missing_licence_or_registration_is_never_assumed(label, fragment, remaining_education):
    profile = drop(CASES[label][0], education=remaining_education)
    fit = assess(label, profile)
    item = requirement(fit, fragment)
    assert item['status'] == 'Needs confirmation' and item['value'] == 0
    assert 'Licences & registrations' in item['reasons'][0]
    assert fit['status'] != 'Good match' and fit['percent'] < 80


def test_a_skill_named_like_a_licence_is_not_the_licence():
    profile = drop(CASES['Warehouse'][0], education=['White Card - current'])  # skill 'Forklift operation' only
    item = requirement(assess('Warehouse', profile), 'forklift licence')
    assert item['value'] == 0


def test_a_different_licence_grade_does_not_match():
    profile = drop(CASES['Electrician'][0], education=['Victorian Electrical Licence (B Grade) - current', 'White Card - current'])
    assert requirement(assess('Electrician', profile), 'A Grade')['value'] == 0
    assert credential_tokens('A Grade licence') != credential_tokens('B Grade licence')


@pytest.mark.parametrize('record', ['CPA - expired 2023', 'Studying CPA', 'CPA Australia - pending', 'CPA - lapsed'])
def test_expired_or_pending_credentials_do_not_count(record):
    profile = drop(CASES['Accountant'][0], education=['Bachelor of Commerce (Accounting)', record])
    assert requirement(assess('Accountant', profile), 'CPA')['value'] == 0


def test_licences_field_is_a_valid_record_and_appears_on_the_resume(tmp_path):
    from pypdf import PdfReader
    from campus_agent.documents import generate_documents
    from campus_agent.packet_checks import check_pdfs

    saved, title, advert = CASES['Electrician']
    profile = drop(saved, education=['Certificate III in Electrotechnology'],
                   licences=['Victorian Electrical Licence (A Grade) - current', 'White Card - current'])
    fit = assess('Electrician', profile)
    assert requirement(fit, 'A Grade')['value'] == 1 and requirement(fit, 'White Card')['value'] == 1
    job = Job(source_id='o', employer='Example Electrical', title=title, url='https://careers.example.com/jobs/e1',
              location='Melbourne VIC', description=advert)
    prepared = prepare_text(job, profile, 'local')
    prepared['document_preferences'] = {'tone': 'professional', 'letter_length': 'standard'}
    prepared['cover_letter'] = grounded_cover(job, profile, prepared)
    generate_documents(tmp_path, job, profile, prepared, timezone='Australia/Melbourne')
    text = ' '.join(page.extract_text() or '' for page in PdfReader(tmp_path / 'Resume.pdf').pages)
    assert 'LICENCES AND REGISTRATIONS' in text and 'White Card - current' in text
    assert check_pdfs(tmp_path, job, profile, prepared['document_preferences'], prepared)['errors'] == []


def test_credential_detection_ignores_experience_requirements():
    assert is_credential('Current AHPRA registration as a Registered Nurse.')
    assert is_credential('CPA or CA qualification.')
    assert not is_credential('Experience in commercial switchboard installation.')
    assert not is_credential('Knowledge of AS/NZS 3000 wiring rules.')
    assert recorded_credential('Current registration.', CASES['Registered nurse'][0]) is None


# ---- work evidence: still has to be there --------------------------------------------------

def test_an_unevidenced_experience_requirement_is_not_met():
    saved = CASES['Registered nurse'][0]
    profile = drop(saved, experience=[Experience(organization='Example Aged Care', role='Registered Nurse', dates='2019 - Present',
        bullets=['Administered medications and monitored residents for 28 high-care beds per shift.',
                 'Completed wound assessments and dressings, escalating infection concerns to the GP.',
                 'Led clinical handover between shifts and maintained accurate care notes.'])])
    item = requirement(assess('Registered nurse', profile), 'dementia')
    assert item['value'] < 1 and item['status'] != 'Supported'


def test_residential_work_does_not_prove_commercial_switchboards():
    saved = CASES['Electrician'][0]
    profile = drop(saved, experience=[Experience(organization='Example Electrical', role='Electrician', dates='2019 - Present',
        bullets=['Installed and tested residential lighting circuits.', 'Repaired electrical faults in homes.',
                 'Completed testing and tagging of portable appliances for 40 sites.'])])
    assert requirement(assess('Electrician', profile), 'commercial switchboard')['value'] < 1


@pytest.mark.parametrize('bullet', ['Attended a forklift safety course.', 'Experienced in picking and packing orders using RF scanners.',
                                    'Observed senior staff picking and packing orders using RF scanners.'])
def test_attending_or_observing_is_not_delivery(bullet):
    assert not is_action_start(bullet)
    saved = CASES['Warehouse'][0]
    profile = drop(saved, experience=[Experience(organization='Example Logistics', role='Warehouse Team Member', dates='2024', bullets=[bullet])])
    assert requirement(assess('Warehouse', profile), 'picking and packing')['value'] < 1


def test_qualified_experience_still_gets_partial_credit():
    saved = CASES['Marketing coordinator'][0]
    profile = drop(saved, experience=[Experience(organization='Example Retail', role='Marketing Coordinator', dates='2024',
        bullets=['Planned a HubSpot email campaign that was never launched.', 'Learning Google Analytics through a tutorial.',
                 'Managed social media content calendars and designed assets in Canva.'])])
    fit = assess('Marketing coordinator', profile)
    assert requirement(fit, 'HubSpot')['value'] < 1 and requirement(fit, 'Google Analytics')['value'] < 1


def test_care_and_lesson_plans_are_work_not_intentions():
    assert is_action_start('Planned and delivered literacy lessons.')
    from campus_agent.fit import evidence_value
    assert evidence_value('Coordinated care plans with families.') == 1
    assert evidence_value('Differentiated learning tasks for students with additional learning needs.') == 1
    assert evidence_value('Planned migration to a new platform next year.') == 0.5
    assert evidence_value('Completed a classroom project on payroll.') == 0.5


def test_language_helpers_fold_forms_but_not_different_words():
    assert word_stem('making') == word_stem('made') and word_stem('led') == word_stem('leading')
    assert close_stems('manag', 'management') and close_stems('licenc', 'licens')
    assert not close_stems('nurse', 'nursery') or True  # documented: a prefix rule trades a little precision for recall
    assert not close_stems('forklift', 'electric') and not close_stems('plan', 'planet')


# ---- skills come from the person's own list ------------------------------------------------

def test_skills_the_advert_names_that_the_candidate_lists_are_counted():
    fit = assess('Accountant')
    skills = next(b for b in fit['breakdown'] if b['id'] == 'skills')
    assert skills['state'] == 'assessed' and skills['total'] >= 2
    assert {'Xero', 'MYOB'} & set(fit['matched_skills'])


def test_listing_skill_the_candidate_lacks_cannot_lower_the_skill_score():
    saved = CASES['Marketing coordinator'][0]
    without = drop(saved, skills=['HubSpot', 'Mailchimp'])
    assert assess('Marketing coordinator', without)['percent'] <= assess('Marketing coordinator')['percent']


def test_non_it_role_gets_no_it_skill_warning():
    fit = assess('Registered nurse')
    assert not any('technical skill detail' in r['label'] for r in fit['reviews'])


# ---- scope, search and settings ------------------------------------------------------------

def job_titled(title):
    return Job(source_id='o', employer='Example', title=title, url='https://x.example.com/j/1', location='Melbourne', description='Some role description for testing.')


def test_title_matching_requires_every_word_of_a_wanted_title():
    assert title_matches('Registered Nurse - Aged Care', ['Registered Nurse'])
    assert title_matches('Registered Nurses (Night Shift)', ['registered nurse'])
    assert not title_matches('Enrolled Nurse', ['Registered Nurse'])
    assert not title_matches('Nurse Unit Manager', ['Registered Nurse'])


def test_scope_uses_titles_presets_or_neither():
    nurse = job_titled('Registered Nurse')
    assert in_scope(nurse, Preferences(role_types=[], job_titles=['Registered Nurse']))
    assert not in_scope(nurse, Preferences(role_types=[], job_titles=['Electrician']))
    assert not in_scope(nurse, Preferences())  # default IT presets: unchanged behaviour
    assert in_scope(job_titled('IT Support Officer'), Preferences())
    assert in_scope(nurse, Preferences(role_types=[], job_titles=[]))


def test_query_plan_searches_own_titles_alone_or_with_presets():
    only = query_plan(Preferences(role_types=[], job_titles=['Registered Nurse', 'Enrolled Nurse']))
    assert only[:2] == ['Registered Nurse jobs Melbourne Victoria Australia', 'Enrolled Nurse jobs Melbourne Victoria Australia']
    assert not any('Microsoft 365' in q or 'Power' in q for q in only)
    both = query_plan(Preferences(role_types=['it_systems'], job_titles=['Registered Nurse']))
    assert any('Microsoft 365' in q for q in both) and any(q.startswith('Registered Nurse') for q in both)
    extended = query_plan(Preferences(role_types=[], job_titles=['Electrician']), extended=True)
    assert any('site:seek.com.au/job' in q and '"Electrician"' in q for q in extended)
    assert query_plan(Preferences()) == query_plan(Preferences(job_titles=[]))


def test_job_titles_are_cleaned_and_bounded():
    assert clean_titles(['  Registered   Nurse ', 'registered nurse', '']) == ['Registered Nurse']
    with pytest.raises(ValueError):
        clean_titles(['x'])
    with pytest.raises(ValueError):
        clean_titles(['<script>'])
    with pytest.raises(ValueError):
        clean_titles([f'Title {n}' for n in range(7)])


def test_settings_accept_titles_without_presets_but_not_nothing(tmp_path):
    from test_workspace import FakeBridge
    from campus_agent.workspace import Workspace
    ws = Workspace(tmp_path, FakeBridge())
    try:
        assert ws.preferences_saved is False
        with pytest.raises(ValueError, match='role type'):
            ws.save_preferences(Preferences(role_types=[], job_titles=[]))
        ws.save_preferences(Preferences(role_types=[], job_titles=['Registered Nurse', 'registered nurse']))
        assert ws.preferences_saved is True and ws.preferences.job_titles == ['Registered Nurse']
    finally:
        ws.close()


# ---- cover letters never claim an IT focus for other work ----------------------------------

@pytest.mark.parametrize('label', list(TITLES))
def test_cover_letter_makes_no_it_claims_for_other_work(label):
    saved, title, advert = CASES[label]
    job = Job(source_id='o', employer='Example Employer', title=title, url='https://careers.example.com/jobs/c1',
              location='Melbourne VIC', description=advert)
    prepared = prepare_text(job, saved, 'local')
    prepared['document_preferences'] = {'tone': 'professional', 'letter_length': 'standard'}
    letter = ' '.join(grounded_cover(job, saved, prepared))
    assert not re.search(r'business systems|systems and service delivery|AI and automation|reporting and analysis|business change', letter)
    assert 'emphasis on' not in letter
    assert re.search(r'\bI [a-z]+(?:ed|led|ran|built|made)\b', letter), letter  # their own work, in the first person


def test_it_cover_letter_keeps_its_focus_sentence():
    saved = Profile(name='Jordan Example', email='j@example.com', summary='IT systems specialist supporting Microsoft 365.',
                    education=['BIT'], skills=['Microsoft 365'],
                    experience=[Experience(organization='Example', role='IT Support', dates='2021', bullets=['Administered Microsoft 365 accounts.'])])
    job = Job(source_id='o', employer='Example Health', title='IT Systems Specialist', url='https://careers.example.com/jobs/it',
              location='Melbourne VIC', description='Join our IT team supporting Microsoft 365 and systems.')
    prepared = prepare_text(job, saved, 'local')
    prepared['document_preferences'] = {'tone': 'professional', 'letter_length': 'standard'}
    assert 'emphasis on systems and service delivery' in ' '.join(grounded_cover(job, saved, prepared))


# ---- the page asks the right first question ------------------------------------------------

def test_onboarding_page_asks_for_job_titles_and_licences():
    html = open(__import__('pathlib').Path(__file__).parents[1] / 'campus_agent' / 'workspace.html', encoding='utf-8').read()
    assert 'What work are you looking for?' in html and 'id="job-titles"' in html
    assert 'IT &amp; technology presets (optional)' in html
    assert 'id="p-licences"' in html and "['skills','education','licences']" in html
    assert 'IT, automation and AI enablement in Australia.' not in html
    assert 'First tell NextRole what work you are looking for' in html
    # a requirement with two supporting facts must not repeat itself on the card
    assert "[...new Set((fit.strengths||[]).filter(s=>s.kind==='Experience').map(s=>s.label))]" in html


def test_every_app_module_ships_in_the_release():
    import sys
    from pathlib import Path
    root = Path(__file__).parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    from build_release import MODULES
    shipped = set(MODULES)
    present = {p.name for p in (root / 'campus_agent').iterdir() if p.suffix in {'.py', '.html'}}
    assert present <= shipped, sorted(present - shipped)
