import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from campus_agent.career import CareerService

class Model:
    def __init__(self,**data): self.data=data
    def model_dump(self,**kwargs): return self.data
class Bridge:
    def __init__(self): self.calls=[]
    def call(self,name,args):
        self.calls.append((name,args)); return employer_pages(args)
def employer_pages(args, employer='Example'):
    pages={
        'https://example.com/about': [
            f'{employer} provides service management and reporting for organisations across Australia.',
        ],
        'https://example.com/customers': [
            f'{employer} serves Australian customers in healthcare and other regulated industries.',
            f'{employer} is owned by an independent member cooperative.',
        ],
    }
    if 'open' not in args:
        return {'results':[{'url':url,'title':employer,'snippet':'A fabricated snippet that claims universal approval.'} for url in pages]}
    url=args['open'][0]['ref_id']
    if url not in pages:
        return {'text': f'Coordinator ({url})\nSource: open(test)\nL0: # Coordinator\nL1: Employer: Example\nL2: ## Responsibilities\n'
                        'L3: - Coordinate service support and documentation across the customer operations team.\n'
                        'L4: - Maintain reports and share changes with service managers.'}
    lines='\n'.join(f'L{i}: {line}' for i,line in enumerate(pages[url]))
    return {'text':f'{employer} ({url})\nCrawled: today; Source: open(test)\n{lines}'}

def service(tmp_path):
    root=tmp_path; (root/'data').mkdir(); (root/'artifacts').mkdir()
    profile=Model(summary='Experienced service delivery professional.',experience=[{'organization':'Real Co','role':'Coordinator','dates':'2020–2024','bullets':['Coordinated support requests.','Documented a service process.']}],skills=['Support'],education=[],is_example=False)
    job=Model(title='Coordinator',employer='Example',url='https://example.com/job',description='What you will deliver\n- Coordinate service support and documentation across the customer operations team.\n- Maintain reports and share changes with service managers.',location='Melbourne')
    w=SimpleNamespace(root=root,data=root/'data',artifacts=root/'artifacts',profile=profile,bridge=Bridge(),job=lambda jid:({'revision':'r1'},job))
    return CareerService(w),w

def wait(s,rid):
    for _ in range(100):
        r=s.get(rid)
        if r['status'] not in {'queued','running'}: return r
        time.sleep(.01)
    raise AssertionError('Timed out')

def test_prep_and_cache_practice(tmp_path):
    s,w=service(tmp_path)
    try:
        rid=s.start('job','interview_prep')['run_id']; r=wait(s,rid)
        assert r['status']=='ready_for_review',r
        assert r['result']['validation']['passed'],r['result']['validation']
        assert not w.bridge.calls
        assert s.start('job','interview_prep')['cached']
        assert r['snapshot']['profile']['experience'][0]['bullets'][0] in r['result']['markdown']
        p=s.create_practice(rid)
        with pytest.raises(ValueError): s.practice_next(p['id'])
        answered=s.practice_answer(p['id'],'I coordinated support requests and documented the process.')
        assert answered['answers'][0]['feedback']['mode']=='heuristic'
        with pytest.raises(ValueError): s.practice_answer(p['id'],'Duplicate answer')
        assert len(s.practice_answer(p['id'],'A revised answer',retry=True)['answers'])==2
        assert s.practice_next(p['id'])['question_index']==1
        assert s.review(rid,'approved',r['output_hash'])['review']['disposition']=='approved'
        with pytest.raises(ValueError): s.review(rid,'approved','stale')
        assert s.artifact(rid,'markdown').exists()
    finally:s.close()

def test_bounded_research_and_private_profile(tmp_path):
    s,w=service(tmp_path)
    try:
        rid=s.start('job','deep_research',{'max_web_calls':2,'scope':['role','pay']})['run_id']; r=wait(s,rid)
        assert r['status']=='ready_for_review',r
        assert w.bridge.calls == [('search_service.web_run', {'open':[{'ref_id':'https://example.com/job'}], 'response_length':'long'})]
        assert 'Coordinated support' not in str(w.bridge.calls)
        assert r['usage']['input_tokens'] is None
        assert r['result']['quality']['verified_topics']==['Operating stack and remit']
        assert r['result']['quality']['gaps']==['Advertised pay']
        assert r['result']['quality']['role_criteria']==2
        assert r['result']['assessment']['role_research']['source_check']=='readable'
        assert len(r['result']['assessment']['role_research']['duties'])==2
    finally:s.close()

def test_unknown_owner_and_invalid_options(tmp_path):
    s,w=service(tmp_path)
    try:
        with pytest.raises(ValueError):s.get('../other')
        with pytest.raises(ValueError):s.start('job','interview_prep',{'max_web_calls':999})
        with pytest.raises(ValueError):s.start('job','interview_prep',{'frameworks':['Made up']})
    finally:s.close()

def test_cancel_prevents_late_ready(tmp_path):
    import threading
    s,w=service(tmp_path); started=threading.Event(); release=threading.Event()
    def blocked(*args): started.set(); release.wait(2); return {'text':'https://example.com/about'}
    w.bridge.call=blocked
    try:
        rid=s.start('job','deep_research')['run_id']; assert started.wait(2)
        assert s.cancel(rid)['status']=='cancelled'
        release.set();time.sleep(.03)
        assert s.get(rid)['status']=='cancelled';assert s.get(rid)['result'] is None
    finally:release.set();s.close()

def test_empty_work_history_fails_structural_prep(tmp_path):
    s,w=service(tmp_path); w.profile.data['experience']=[]
    try:
        r=wait(s,s.start('job','interview_prep')['run_id'])
        assert not r['result']['validation']['passed']
        assert r['result']['guide']['cards']==[]
    finally:s.close()

def test_cancel_during_reservation_never_dispatches(tmp_path):
    s,w=service(tmp_path)
    original=s._update
    def update(rid,**changes):
        result=original(rid,**changes)
        if 'usage' in changes: s.cancel(rid)
        return result
    s._update=update
    try:
        r=wait(s,s.start('job','deep_research')['run_id'])
        assert r['status']=='cancelled';assert not w.bridge.calls
    finally:s.close()

def test_limited_draft_cannot_be_approved(tmp_path):
    s,w=service(tmp_path);w.profile.data['experience']=[]
    try:
        r=wait(s,s.start('job','interview_prep')['run_id'])
        assert r['result']['limited_draft']
        with pytest.raises(ValueError):s.review(r['id'],'approved')
    finally:s.close()

def test_prep_inherits_current_research_and_saved_metadata(tmp_path):
    s,w=service(tmp_path)
    w.jobs=lambda:[{'id':'job','reading_view':{'salary':{'status':'stated','minimum':90000,'maximum':100000,'currency':'AUD','period':'annual','display':'AUD 90,000–100,000 per year'},'facts':[{'label':'Work type','value':'Full time'}]},'location_info':{'arrangement':'Hybrid'},'fit':{'requirements':[{'text':'Coordinate support','value':1,'evidence':[{'text':'Coordinated support requests.'}],'reasons':[]}]},'listing':{'closes_on':'2027-12-01'}}]
    try:
        research=wait(s,s.start('job','deep_research',{'max_web_calls':3})['run_id'])
        prep=wait(s,s.start('job','interview_prep',{'stage':'technical'})['run_id'])
        assert prep['snapshot']['research']['run_id']==research['id']
        result=prep['result']
        assert result['observations']['vacancy']['mode']=='Hybrid'
        assert result['observations']['vacancy']['employment']=='Full time'
        assert result['observations']['vacancy']['deadline']=='2027-12-01'
        assert result['observations']['employer_pay']['low']==90000
        assert result['assessment']['fit'][0]['level']=='Direct'
        assert any(k.startswith('employer_') for k in result['sources'])
        assert 'technical decision' in result['questions'][1]['question']
    finally:s.close()

def test_source_blocks_do_not_mix_and_structured_fields():
    from campus_agent.career import research_sources
    rows=research_sources({'text':'Employer A (https://example.com/a)\nA-only statement.\nEmployer B (https://example.com/b)\nB-only statement.'})
    assert len(rows)==2
    assert 'B-only' not in rows[0]['excerpt'] and 'A-only' not in rows[1]['excerpt']
    rows=research_sources({'results':[{'title':'One','url':'https://example.com/one','snippet':'Only one'},{'title':'Two','url':'https://example.com/two','snippet':'Only two'}]})
    assert rows[0]['excerpt']=='Only one' and rows[1]['excerpt']=='Only two'

def test_default_budget_includes_pay_and_credentials_change_cache(tmp_path):
    s,w=service(tmp_path)
    w.profile.data.update(credentials=[{'name':'Nursing registration','status':'pending','expires_on':'2027-01-01','jurisdiction':'VIC'}],availability='Four weeks',technical_projects=[{'title':'Personal prototype','stage':'prototype','summary':'A private test project, not employer work.'}])
    try:
        r=wait(s,s.start('job','deep_research')['run_id'])
        assert 'Advertised pay' in r['result']['quality']['gaps']
        prep=wait(s,s.start('job','interview_prep',{'stage':'recruiter'})['run_id'])
        assert 'pending' in prep['result']['markdown']
        assert 'Private project — not employer work' in prep['result']['markdown']
        methods={m['name']:m for m in prep['result']['guide']['strategy']['methods']}
        assert 'similar task' in methods['CAR']['question']
        assert 'first month' in methods['Approach']['question']
        assert 'yourself' in methods['ICAN+']['question']
        w.profile.data['credentials'][0]['status']='current'
        next_run=s.start('job','interview_prep',{'stage':'recruiter'})
        assert not next_run['cached'] and next_run['run_id']!=prep['id']
        wait(s,next_run['run_id'])
    finally:s.close()

def test_search_snippets_do_not_clear_the_export_gate(tmp_path):
    s,w=service(tmp_path)
    try:
        r=wait(s,s.start('job','deep_research',{'max_web_calls':1})['run_id'])
        assert r['status']=='ready_for_review'
        assert not r['result']['quality']['export_ready']
        assert 'universal approval' not in r['result']['markdown']
        assert s.artifact(r['id'],'markdown').is_file()
        with pytest.raises(ValueError,match='Employer research needs'):
            s.artifact(r['id'],'guide_pdf')
        prep=wait(s,s.start('job','interview_prep')['run_id'])
        assert 'research' not in prep['snapshot']
    finally:s.close()


def test_reopened_employer_sources_support_findings(tmp_path):
    s,w=service(tmp_path)
    try:
        r=wait(s,s.start('job','deep_research')['run_id'])
        assert r['result']['quality']['export_ready']
        assert len(r['result']['quality']['verified_topics'])==4
        assert 'independent member cooperative' in r['result']['markdown']
        assert 'universal approval' not in r['result']['markdown']
        assert 'has not been verified' not in r['result']['markdown']
        assert s.artifact(r['id'],'guide_pdf').is_file()
    finally:s.close()

def test_navigation_does_not_count_as_employer_evidence(tmp_path):
    s,w=service(tmp_path)
    original=w.bridge.call
    def navigation(name,args):
        if 'open' not in args:
            return original(name,args)
        url=args['open'][0]['ref_id']
        return {'text':f'Example ({url})\nSource: open(test)\n'
                        'L0: About us Our board of directors has announced a new leader.\n'
                        'L1: # About Example\n'
                        'L2: Our partners Learn how our services help our customers.\n'
                        'L3: Reports & presentationsFinancial calendarShare informationAnnual Shareholders’ Meeting\n'}
    w.bridge.call=navigation
    try:
        run=wait(s,s.start('job','deep_research')['run_id'])
        assert not run['result']['quality']['export_ready']
        assert run['result']['quality']['verified_topics']==['Operating stack and remit']
    finally:s.close()

def test_australian_role_rejects_foreign_same_name_employer(tmp_path):
    s,w=service(tmp_path)
    original=w.bridge.call
    foreign='https://example.com/foreign'
    def competing(name,args):
        if 'open' not in args:
            result=original(name,args)
            result['results'].insert(0,{'url':foreign,'title':'Example','snippet':'Exact employer name'})
            return result
        if args['open'][0]['ref_id']==foreign:
            return {'text':f'Example ({foreign})\nSource: open(test)\nL0: Example provides US healthcare staffing for hospitals in Texas.'}
        return original(name,args)
    w.bridge.call=competing
    try:
        run=wait(s,s.start('job','deep_research')['run_id'])
        assert run['result']['quality']['export_ready']
        assert 'Texas' not in run['result']['markdown']
        assert not any(item.get('url')==foreign for item in run['result']['sources'].values())
    finally:s.close()

def test_vacancy_check_accepts_board_title_and_checks_employer():
    from campus_agent.career_research import vacancy_check
    url='https://example.com/job'
    vacancy={'title':'[Hiring] Coordinator @Example','employer':'Example'}
    body='Coordinator ({url})\nSource: open(test)\nL0: # Coordinator\nL1: Employer: {name}\nL2: ## Responsibilities\nL3: - Coordinate a busy customer service team.'
    assert vacancy_check(url,vacancy,{'text':body.format(url=url,name='Example')})=='readable'
    assert vacancy_check(url,vacancy,{'text':body.format(url=url,name='Other company')})=='unconfirmed'

def test_undated_company_revenue_story_is_not_a_financial_finding(tmp_path):
    s,w=service(tmp_path)
    original=w.bridge.call
    def employer_story(name,args):
        if args.get('open',[{}])[0].get('ref_id')=='https://example.com/about':
            result=original(name,args)
            result['text']+='\nL1: When our business took a 70% revenue hit overnight, we had two choices.'
            return result
        return original(name,args)
    w.bridge.call=employer_story
    try:
        run=wait(s,s.start('job','deep_research')['run_id'])
        assert run['result']['quality']['export_ready']
        assert 'Finances and trajectory' in run['result']['quality']['gaps']
        assert '70% revenue hit' not in run['result']['markdown']
    finally:s.close()


def test_technology_sources_keep_their_scope_in_full_and_quick_reports(tmp_path):
    s,w=service(tmp_path)
    row,job=w.job('job')
    job.data['description']+='\n- Provide Microsoft 365 support for the operations team.'
    w.profile.data['experience'][0]['bullets'].append('Administered Microsoft 365 accounts for the support team.')
    related='https://example.com/jobs/technical-engineer'
    company='https://example.com/case-study'
    foreign='https://other.example/jobs/engineering'
    pages={
        related:('Engineer', ['# Engineer','Employer: Example, Australia','## Responsibilities','- Build Python integrations on AWS for existing business applications.']),
        company:('Example case study', ['# Example case study','Example uses Salesforce in one Australian customer project.']),
        foreign:('Other company', ['# Engineer','Employer: Another Employer, Australia','## Responsibilities','- Develop production Snowflake models across the customer estate.']),
    }
    original=w.bridge.call
    def sources(name,args):
        url=args['open'][0]['ref_id']
        if url not in pages:
            return original(name,args)
        title,body=pages[url]
        return {'text': f'{title} ({url})\nSource: open(test)\n'+'\n'.join(f'L{i}: {line}' for i,line in enumerate(body))}
    w.bridge.call=sources
    try:
        options={'scope':['role'],'technology_links':[related,company,foreign]}
        run=wait(s,s.start('job','deep_research',options)['run_id'])
        result=run['result']
        assert result['quality']['export_ready']
        tech=result['assessment']['technology']
        assert [entry['scope'] for entry in tech]==['vacancy','related','company','candidate']
        assert '**Related posting** Build Python integrations on AWS' in result['markdown']
        assert '**Company context** Example uses Salesforce' in result['markdown']
        assert '**Your experience** Administered Microsoft 365' in result['markdown']
        assert '**Named in this vacancy** Provide Microsoft 365' in result['quick_markdown']
        assert related in result['quick_markdown'] and company in result['markdown']
        assert 'Snowflake' not in result['markdown']
        assert '**Ask to confirm**' in result['markdown']
        calls=len(w.bridge.calls)
        prep=wait(s,s.start('job','interview_prep')['run_id'])
        assert prep['result']['quality']['export_ready']
        assert prep['snapshot']['research']['technology_run_id']==run['id']
        assert related in prep['result']['markdown']
        assert len(w.bridge.calls)==calls
        with pytest.raises(ValueError,match='public HTTPS'):
            s.start('job','deep_research',{'technology_links':['https://127.0.0.1/secret']})
    finally:s.close()


def test_technology_preserves_optional_words_and_skips_investors():
    from campus_agent.career_research import technology_passages
    from campus_agent.career_technology import technology_rows

    vacancy={'title':'Systems Coordinator','employer':'Example Employer'}
    advert=("## What you have\n"
            "Experience with Oracle Sales Cloud, SAP, ServiceNow or similar platforms would be beneficial. "
            "We also welcome applications from recent graduates with strong digitalisation skills and practical experience gained through projects or work placements.\n"
            "- Solid understanding of APIs, with the ability to troubleshoot and articulate API-related concepts clearly.\n"
            "## About us\n"
            "Our funding comes from the OpenAI Startup Fund.")
    rows=technology_rows(technology_passages(advert,vacancy),'vacancy','advert')
    assert [row['quote'] for row in rows]==[
        'Experience with Oracle Sales Cloud, SAP, ServiceNow or similar platforms would be beneficial.',
        'Solid understanding of APIs, with the ability to troubleshoot and articulate API-related concepts clearly.',
    ]
    company=technology_rows(['Backed by investors including the OpenAI Startup Fund.',
                             'Our Australian deployment connects the client’s CRM with Microsoft Fabric.'],
                            'company','public_example',limit=1)
    assert company[0]['quote']=='Our Australian deployment connects the client’s CRM with Microsoft Fabric.'


def test_targeted_company_sources_keep_verifiable_passages(tmp_path):
    s, w = service(tmp_path)
    original = w.bridge.call
    links = [
        {'url': 'https://example.com/about', 'focus': 'provides service'},
        {'url': 'https://example.com/customers', 'focus': 'Australian customers'},
    ]

    def focused(name, args):
        if 'find' not in args:
            return original(name, args)
        link = args['find'][0]
        response = original(name, {'open': [{'ref_id': link['ref_id']}]})
        response['text'] = response['text'].replace('Source: open(', 'Source: find(')
        return response

    w.bridge.call = focused
    try:
        run = wait(s, s.start('job', 'deep_research', {'company_links': links})['run_id'])
        result = run['result']
        assert result['validation']['passed']
        assert result['quality']['export_ready']
        assert all(check['readable'] for check in result['assessment']['company_checks'][:2])
        for claim in result['assessment']['claims']:
            if claim['kind'] == 'confirmed' and claim['area'] != 'Operating stack and remit':
                assert claim['text'] in result['sources'][claim['sources'][0]]['excerpt']
        quick = result['quick_markdown']
        assert quick.index('## Pay') < quick.index('## Job') < quick.index('## Company')
    finally:
        s.close()


def test_readable_vacancy_copy_does_not_confirm_availability(tmp_path):
    s, w = service(tmp_path)
    original = w.bridge.call
    copy = 'https://example.com/syndicated-job'

    def archived(name, args):
        url = args.get('open', [{}])[0].get('ref_id')
        if url == 'https://example.com/job':
            return {'text': f'Example ({url})\nSource: open(test)\nL1: Access denied'}
        return original(name, args)

    w.bridge.call = archived
    try:
        run = wait(s, s.start('job', 'deep_research', {'scope': ['role'], 'alternate_vacancy_url': copy})['run_id'])
        result = run['result']
        assert result['assessment']['role_research']['source_check'] == 'readable_copy'
        assert 'Vacancy availability' in result['quality']['gaps']
        assert result['sources']['alternate_vacancy']['url'] == copy
        assert result['assessment']['vacancy']['status'] == 'unknown'
    finally:
        s.close()


def test_role_duties_recover_action_sentences_from_prose():
    from campus_agent.career_research import _stated_duties, role_matrix

    vacancy = {'title': 'Enablement Partner', 'employer': 'Example'}
    advert = """What You'll Do
Get close to the work. Partner with frontline teams to map existing work and find bottlenecks.
Build alongside the team. Develop low-code tools for the agreed process with frontline staff.
About You
- Three years of work in process improvement or business analysis."""
    rows = role_matrix(advert, vacancy)
    assert _stated_duties(advert, vacancy, rows) == [
        'Partner with frontline teams to map existing work and find bottlenecks.',
        'Develop low-code tools for the agreed process with frontline staff.',
    ]


def test_research_does_not_turn_a_job_board_estimate_into_employer_pay(tmp_path):
    s, w = service(tmp_path)
    try:
        w.job('job')[1].data['description'] += '\n\nEst. AUD 85,000 - 115,000'
        run = wait(s, s.start('job', 'deep_research', {'scope': ['role', 'pay']})['run_id'])
        assert run['result']['assessment']['employer_pay'] is None
        assert 'Advertised pay' in run['result']['quality']['gaps']
        assert '85,000' not in run['result']['quick_markdown']
    finally:
        s.close()
