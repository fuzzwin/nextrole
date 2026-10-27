from campus_agent.listing_view import listing_view


def test_official_careers_identity_and_footer_are_kept_separate_from_product_mentions():
    from campus_agent.listing_view import confirmed_listing_employer
    from campus_agent.models import Job
    text = '# Enablement Lead\nAbout the Role\nLead enablement.\nAbout OpenAI\nCompany details.\nResearch\n\n  * Research Index\n  * Research Overview\nDevelopers\n  * Apps SDK\n'
    job = Job(source_id='test', title='Enablement Lead', employer='Employer on job listing', url='https://openai.com/careers/example/', description=text)
    assert confirmed_listing_employer(job, text) == 'OpenAI'
    assert confirmed_listing_employer(job.model_copy(update={'url':'https://other.example/careers/example/'}), text) == 'Employer on job listing'
    assert confirmed_listing_employer(job, 'Use OpenAI products.') == 'Employer on job listing'
    view = listing_view(text, job.title)
    assert 'Company details.' in str(view['sections'])
    assert 'Research Index' not in str(view['sections']) and 'Apps SDK' not in str(view['sections'])
    assert view['original_chars'] == len(text)


def test_ordinary_research_requirements_are_not_removed_as_navigation():
    view = listing_view('# Analyst\nResearch\n- Research customer needs.\nRequirements\n- Python.', 'Analyst')
    assert 'Research customer needs.' in str(view['sections'])


def test_reading_view_separates_facts_sections_optional_criteria_and_recommendations():
    text='''# Solutions Consultant
Posted Sep 2, 2026 18 views
Profile match
74% 13 of 17 skills
Sign in to see your match
Work format
    Hybrid
Work type
    Full-time
Grade
    Lead
Digital Armour Corporation · Solutions Consultant
Description Company
Salary: $140,000 – $150,000 per year plus superannuation
Digital Armour is hiring a consultant. This role is based full time in our North Sydney office.

What you will do
  * Build production agents.
  * Document and hand over solutions.
What you need
The criterion that matters most: at least one agent used in production. Proofs of concept and demonstrations do not count.
Beyond that:
  * Eighteen months hands-on experience.
Helpful, not required
  * Australian citizenship for some clients.
Our process
1. Screening call
2. Practical build exercise
To apply
Describe one production agent.
## Skills
  * AI ?
What Lead Solutions Engineering jobs ask for — and how much of it you have →
Unrelated role in another country.
'''
    view=listing_view(text,'Solutions Consultant — Digital Armour Corporation · freehire')
    assert view['title']=='Solutions Consultant'
    assert view['employer']=='Digital Armour Corporation'
    assert view['facts'][0]=={'label':'Salary','value':'$140,000 – $150,000 per year plus superannuation'}
    sections={s['title']:s for s in view['sections']}
    assert set(sections)=={'Overview','What you will do','What you need','Helpful, not required','Our process','To apply'}
    assert sections['What you will do']['blocks'][0]['items']==['Build production agents.','Document and hand over solutions.']
    assert sections['Our process']['blocks'][0]['ordered']
    assert 'demonstrations do not count' in view['highlights'][0]
    assert not any('citizenship' in h for h in view['highlights'])
    assert 'Hybrid' in view['notices'][0]['message']
    assert 'North Sydney office' in view['notices'][0]['quote']
    assert '74%' not in str(sections) and 'Unrelated role' not in str(sections)
    assert 'hiring a consultant' in view['preview']


def test_reading_view_preserves_ordinary_text_and_unusual_headings():
    text='A factual opening paragraph.\n\n## Security and compliance\n- Must hold NV1 clearance.\n- Prototype work is insufficient.\n\n## Benefits\nRemote work is available.\n\nRecommended jobs\nOther role.'
    view=listing_view(text,'Example role')
    assert len(view['sections'])==3
    assert view['sections'][1]['title']=='Security and compliance'
    assert view['sections'][1]['blocks'][0]['items']==['Must hold NV1 clearance.','Prototype work is insufficient.']
    assert 'Other role' not in str(view['sections'])
    assert view['notices']==[]
    assert view['original_chars']==len(text)


def test_reading_view_does_not_drop_long_single_line_snippets():
    text='Posted 1 October 2026. '+('This is the actual role description. '*10)
    view=listing_view(text,'Example role')
    assert view['preview']==text.strip()


def test_reading_view_does_not_turn_source_markup_into_html():
    view=listing_view('## Requirements\n- <script>send private data</script>\n- Use Python for reports.','Example role')
    assert view['sections'][0]['blocks'][0]['items'][0]=='<script>send private data</script>'


def test_display_title_and_company_drop_board_suffix_without_losing_technical_title():
    title='AI Enablement Engineer – Claude Code | .NET & Python at Maltem Australia — Melbourne, Victoria, Australia | LinkedIn Jobs'
    view=listing_view('# AI Enablement Engineer – Claude Code | .NET & Python\n\nBuild useful tools with Python.',title,'Maltem Australia — Melbourne, Victoria, Australia | LinkedIn Jobs')
    assert view['title']=='AI Enablement Engineer – Claude Code | .NET & Python'
    assert view['employer']=='Maltem Australia'


def test_salary_range_is_literal_and_does_not_invent_an_unknown_salary():
    text='What we offer\n- $120,000 to $140,000 base plus superannuation\n- Permanent role.'
    facts=listing_view(text,'Automation Specialist')['facts']
    assert facts[0]['value']=='$120,000 to $140,000 base plus superannuation'
    assert not listing_view('Competitive remuneration and flexible working.','Support Specialist')['facts']


def test_structured_employer_salary_and_html_requirements_are_read():
    import json
    posting={'@type':'JobPosting','title':'Automation Specialist','description':'<h2>About the role</h2><p>Build business workflows.</p><h2>Requirements</h2><ul><li>Python automation experience.</li><li>Power Automate workflow experience.</li><li>Microsoft 365 systems support experience.</li></ul>','baseSalary':{'currency':'AUD','value':{'minValue':110000,'maxValue':130000,'unitText':'YEAR'}},'jobLocation':{'address':{'addressLocality':'Melbourne','addressRegion':'VIC','addressCountry':'Australia'}}}
    text='<html><script type="application/ld+json">'+json.dumps(posting)+'</script><p>Noise from the board</p></html>'
    view=listing_view(text,'Automation Specialist')
    assert view['salary']['currency']=='AUD' and view['salary']['period']=='year'
    assert view['salary']['minimum']==110000 and view['salary']['maximum']==130000
    assert 'Build business workflows.' in view['overview']
    requirements=next(s for s in view['sections'] if s['title']=='Requirements')
    assert len(requirements['blocks'][0]['items'])==3
    assert 'Noise' not in str(view['sections'])


def test_other_structured_job_cannot_supply_salary_for_named_role():
    import json
    jobs=[{'@type':'JobPosting','title':name,'description':'<p>Unrelated employer role.</p>','baseSalary':{'currency':'USD','value':{'value':999999,'unitText':'YEAR'}}} for name in ['Other Role','Third Role']]
    text='<html><script type="application/ld+json">'+json.dumps(jobs)+'</script><main><h2>About the role</h2><p>Build business workflows.</p></main></html>'
    assert listing_view(text,'Automation Specialist')['salary']['status']=='not_stated'
