"""Reopen employer sources and check that each exported answer has evidence."""

import re
from concurrent.futures import TimeoutError
from urllib.parse import urlsplit

from .career_render import RESEARCH_AREAS
from .career_technology import technology_rows
from .evidence_matrix import matrix_requirements, section_kind
from .listing_view import heading_key, listing_view, same_role, source_problem
from .locations import CITIES, STATES


TOPICS = dict(zip(RESEARCH_AREAS, (
    r'\b(?:founded|established|places|specialises|specializes|manufactures|provides|recruits|operates|develops|supplies|offers|delivers|(?:is (?:an?|the)|leading) .{0,55}(?:company|provider|insurer|fund|firm|manufacturer|organisation|organization|platform|software|operating system)|we are active in)\b',
    r'\b(?:serves?|supports?|helps?|provides?|builds?|building|works?|customers|clients|members|patients|healthcare providers|law firms)\b.{0,100}\b(?:customers|clients|members|patients|hospitals|law firms|healthcare providers|organisations|organizations|teams|businesses)\b',
    r'\b(?:member.owned|owned by|subsidiary of|listed on|majority stake|mutual organisation|not.for.profit|owns (?:a |the )?(?:majority|minority|[\d.]+\s*%))\b',
    r'\b(?:revenue|funding round|net profit|net loss|operating profit|cash flow|claims paid|raised)\b',
    r'\b(?:chief executive|ceo|appointed|founder.led|co.founded|leadership team|board of directors|employee survey|employee resource groups|our founders)\b',
    r'\b(?:regulated by|under the .{5,80} act|licen[cs]ed by|accredited by|accreditation|hiring index|(?:roles|vacancies) captured|(?:captured|tracked) .{0,75}(?:openings|vacancies|job ads|advertised .{0,25}roles))\b',
    r'\b(?:support|coordinate|develop|manage|deliver|implement|administer|maintain|analyse|analyze|map|test|monitor|lead|build|design|partner|work with|provide|triage|troubleshoot|resolve|improve)\b',
)))

GAP_QUESTIONS = {
    'Business and history': 'Which part of the business would this team support?',
    'Customers and users': 'Who uses the team’s work, and what problem matters most to them?',
    'Ownership': 'Which entity would employ me, and where does this team report?',
    'Finances and trajectory': 'Which investments or priorities will shape the team’s work this year?',
    'Leadership and culture': 'Who leads the team, and how are decisions and feedback handled?',
    'Market and policy': 'Which regulatory or industry requirements affect this work?',
    'Operating stack and remit': 'Which tools and responsibilities would I own from day one?',
}

_ROLE = RESEARCH_AREAS[-1]
_DUTY_ACTION = re.compile(r'^(?:'+TOPICS[_ROLE][2:-2]+r'|run|scope|work upstream)\b', re.I)
_LINE = re.compile(r'^L(\d+)(?:@P(\d+)(?:-\d+)?)?:\s*(.*)$')
_BAD_LINE = re.compile(r'access denied|unable to resolve|failed to fetch|enable javascript|all rights reserved|cookie policy|similar jobs|search results|sign in to|privacy policy|\b(?:learn more|learn how|find out|explore our|contact us|click here|image:|subscribe)\b', re.I)
_FINITE = re.compile(r'\b(?:is|are|was|were|has|have|had|can|will|serve[sd]?|help[s]?|support[s]?|provides?|offers?|speciali[sz]es?|delivers?|operates?|include[sd]?|work[s]?|report[s]?|appointed|raised|announced|founded|founder.led|co.founded|grown|placed|rolled out|captured|welcomed|generated|places|owns|use[sd]?|announces?|partner(?:s|ed|ing)?|does business)\b', re.I)
_GENERIC = {'group', 'limited', 'ltd', 'pty', 'inc', 'plc', 'corporation', 'company', 'australia', 'global', 'llc', 'holdings', 'employer'}


def _employer_domain(url, employer):
    name = [part for part in re.findall(r'[a-z0-9]+', employer.casefold()) if part not in _GENERIC]
    labels = (urlsplit(url).hostname or '').split('.')
    if labels[-2:-1] in (['co'], ['com'], ['org'], ['net']):
        labels = labels[:-2]
    else:
        labels = labels[:-1]
    # Use the publisher's registered label, never an arbitrary subdomain.
    if len(name) > 1 and name[-1] == 'health' and labels[-1:] == [''.join(name[:-1])]:
        name = name[:-1]
    return bool(name and labels and len(''.join(name)) >= 3
                and re.sub(r'[^a-z0-9]', '', labels[-1]) in {
                    ''.join(name), ''.join(name) + 'au', ''.join(name) + 'bpo',
                })


_AU_LOCATION = re.compile(r'\b(?:Australia(?:n)?|'+'|'.join(map(re.escape, (*CITIES, *STATES.values())))+r')\b', re.I)


def _in_market(url, page, australian):
    """Require local issuer evidence for a same-name company on a foreign domain."""
    return not australian or (urlsplit(url).hostname or '').endswith('.au') or bool(_AU_LOCATION.search(page))


def _sentences(body, minimum=7, require_punctuation=False):
    if require_punctuation:
        # Connected pages commonly put a full navigation menu ahead of the article.
        heading = re.search(r'(?m)^L\d+:\s+# ', body)
        if heading:
            body = body[heading.start():]
    for line in body.splitlines():
        line = re.sub(r'^L\d+:\s*', '', line).strip()
        line = re.sub(r'【\d+†([^】]*)】', r'\1', line).strip()
        if not line or line.startswith(('#', '|', '[')) or _BAD_LINE.search(line):
            continue
        line = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', line)
        line = re.sub(r'^[*•\-\s]+', '', line).replace('**', '')
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])', line):
            sentence = ' '.join(sentence.split())
            if (minimum <= len(sentence.split()) <= 25 and not any(c in sentence for c in '<>[]')
                    and (not require_punctuation or sentence.endswith('.'))):
                yield sentence


def _opened(response, url):
    """Accept readable body fields or the line-numbered output of an actual open."""
    containers = [response, response.get('structuredContent') or {}]
    for container in containers:
        for item in container.get('results', []):
            if isinstance(item, dict) and item.get('url') == url and isinstance(item.get('content'), str):
                return str(item.get('title') or ''), item['content']
    for container in containers:
        body = container.get('content') or container.get('text')
        if not isinstance(body, str):
            continue
        lines = body.splitlines()
        if len(lines) < 3 or not lines[0].strip().endswith('(' + url + ')') or not re.search(r'Source: (?:open|find)\(', lines[1]):
            continue
        paragraphs = []
        page = last_line = None
        for raw in lines[2:]:
            match = _LINE.match(raw)
            if not match:
                continue
            number, source_page, line = match.groups()
            if (source_page and source_page==page and int(number)==last_line+1 and
                    line and not paragraphs[-1].endswith(('.', '!', '?'))):
                paragraphs[-1]+=' '+line
            else:
                paragraphs.append(f'L{number}: {line}')
            page, last_line = source_page, int(number)
        return lines[0].strip()[:-len(url)-3], '\n'.join(paragraphs)
    return '', ''


def _role_listing(text, vacancy):
    text = re.sub(
        r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:what you will deliver|what you['’]ll deliver|what you deliver|what you will own|key deliverables)[ \t]*:?[ \t]*$",
        '## Responsibilities', text,
    )
    return listing_view(text, vacancy['title'], vacancy['employer'])


def role_matrix(text, vacancy):
    # Use the existing scoring matrix without changing its rules.
    return matrix_requirements(_role_listing(text, vacancy))


def technology_passages(text, vacancy):
    # Technical context can appear in longer duty or qualification paragraphs.
    view = _role_listing(text, vacancy)
    for row in matrix_requirements(view):
        if row['kind']=='competency':
            yield row['quote']
    for section in view['sections']:
        heading = section['title']
        if section_kind(heading) not in {'duty','requirement','optional'} and heading_key(heading)!='what you have':
            continue
        for block in section['blocks']:
            if block['kind']=='list':
                yield from block['items']
            elif heading_key(heading) != 'skills':
                yield block['text']


def _stated_duties(advert, vacancy, material):
    listed = [row['quote'] for row in material if row['category']=='duty']
    if listed:
        return listed
    for section in _role_listing(advert, vacancy)['sections']:
        if section_kind(section['title'])!='duty':
            continue
        for block in section['blocks']:
            passages = [block['text']] if block['kind']=='paragraph' else block['items']
            for text in passages:
                sentences = re.split(r"(?<=[.!?]) +(?=[A-Z])", text)
                for sentence in sentences:
                    action = re.sub(r"^(?:You['’]ll|You will) ", '', sentence, flags=re.I)
                    if len(sentence.split())>=8 and _DUTY_ACTION.match(action):
                        listed.append(sentence)
    return list(dict.fromkeys(listed))[:6]


def vacancy_check(url, vacancy, response):
    heading, body = _opened(response, url)
    text = re.sub(r'(?m)^L\d+:\s*', '', body)
    # Both strings may include job-board decorations. Strip only the saved publisher's name.
    def title(value):
        value = re.sub(r'^\[Hiring\]\s*', '', value, flags=re.I)
        return re.sub(r'\s+@\s*'+re.escape(vacancy['employer'])+r'\s*$', '', value, flags=re.I)
    headers = [heading, *re.findall(r'(?m)^#{1,6}\s+([^\n]+)', text[:4000])[:2]]
    matches = any(same_role(title(vacancy['title']), title(h), vacancy['employer']) for h in headers)
    issuer = re.sub(r'\W+', '', vacancy['employer'].casefold())
    if not matches or issuer not in re.sub(r'\W+', '', (heading+' '+text[:4000]).casefold()):
        return 'unconfirmed'
    text = re.split(r'(?im)^#{1,6}\s+More [^\n]{1,90} jobs (?:in|from)\b', text, maxsplit=1)[0]
    problem = source_problem(text, vacancy['title'])
    if problem:
        return 'closed' if problem[0] == 'closed' else 'unconfirmed'
    if not any(row['kind'] == 'competency' for row in role_matrix(text, vacancy)):
        return 'unconfirmed'
    return 'readable'


def research(observed, report, scope, limit, web, discover, progress, technology_links=(), company_links=(), alternate_vacancy_url=None):
    """Discovery supplies URLs. The separate open pass supplies all public answers."""
    vacancy = observed['vacancy']
    employer = vacancy['employer']
    australian = any(_AU_LOCATION.search(place) for place in vacancy['locations'])
    market = ' Australia' if australian else ''
    sources = observed['sources']
    answers = {}
    pages = {}
    candidates_by_topic = {area: [] for area in RESEARCH_AREAS[:-1]}
    employer_key = re.sub(r'[^a-z0-9]', '', employer.casefold())
    name_words = re.findall(r'[a-z0-9]+', employer.casefold())
    acronym = name_words[0] if name_words and len(name_words[0]) in {3,4} and employer.startswith(name_words[0].upper()) else ''
    attempts = 0
    failures = 0
    tried = set()
    company_attempts = []
    company_limit = max(0, limit-min(2,len(technology_links)))

    def call(args, message):
        nonlocal attempts, failures
        progress(message, attempts, limit)
        attempts += 1
        try:
            return web(args)
        except (InterruptedError, TimeoutError):
            raise
        except Exception:
            failures += 1
            return {}

    if 'role' in scope:
        advert = sources['advert']
        rows = role_matrix(advert['excerpt'], vacancy)
        material = [row for row in rows if row['kind'] == 'competency' and row['importance'] != 'optional']
        duties = _stated_duties(advert['excerpt'], vacancy, material)
        report['role_research'] = {
            'duties': duties,
            'requirements': len(material),
            'conditions': [row['quote'] for row in rows if row['kind'] == 'condition'],
            'scope_questions': [row['quote'] for row in rows if row['kind'] == 'review'],
            'source_check': 'unconfirmed',
        }
        url = advert.get('read_url') or advert.get('url')
        if url and ('employer' not in scope or limit >= 4):
            response = call({'open': [{'ref_id': url}], 'response_length': 'long'}, 'Reopening the original vacancy')
            report['role_research']['source_check'] = vacancy_check(url, vacancy, response)
        if (report['role_research']['source_check']=='unconfirmed' and alternate_vacancy_url
                and alternate_vacancy_url!=url and attempts<limit):
            response = call({'open': [{'ref_id': alternate_vacancy_url}], 'response_length': 'long'},
                            'Checking another copy of this vacancy')
            if vacancy_check(alternate_vacancy_url, vacancy, response)=='readable':
                label, _ = _opened(response, alternate_vacancy_url)
                sources['alternate_vacancy'] = {
                    'kind':'employer', 'label':label or 'Matching vacancy copy',
                    'url':alternate_vacancy_url, 'excerpt':'',
                    'locator':f"Matching title, employer and readable criteria checked {observed['checked_on']}.",
                }
                report['role_research']['source_check']='readable_copy'
        state = report['role_research']['source_check']
        if state == 'closed':
            vacancy['status'] = 'closed'
            report['decision'] = 'The original posting says this vacancy has closed.'
            report['next_step'] = 'Use this guide for preparation if the employer posts a new requisition.'
        if len(material) >= 2:
            answers[_ROLE] = {
                'text': f"The saved advert contains {len(duties)} stated duties and {len(material)} material criteria. See the role and fit sections below.",
                'source': 'advert',
            }

    def rank(area, sentence):
        lower = sentence.casefold()
        compact = re.sub(r'[^a-z0-9]', '', lower)
        named = employer_key in compact or bool(acronym and re.search(r'\b'+re.escape(acronym)+r'\b', lower))
        dated = bool(re.search(r'\b(?:20\d{2}|FY\s*\d{2})\b', sentence, re.I))
        metric = bool(re.search(r'[%€£$]|\b(?:million|billion|thousand)\b', lower))
        if area == 'Finances and trajectory':
            if (named and metric and dated and re.search(TOPICS[area],sentence,re.I) and not re.search(r'\b(?:charit(?:y|ies)|donations?|fundrais\w*|run for a reason)\b',lower)):
                return (True, True, True, len(sentence.split()))
            return None
        if area == 'Customers and users' and re.search(r'\b(?:dedicated to your success|our commitment|contact us)\b',lower):
            return None
        if area == 'Customers and users' and (
                re.search(r'\b(?:welcomed|serves?|ended the year with)\b.{0,85}\b(?:members|customers)\b',lower)
                or named and re.search(r'\b(?:is used by|partnering with|firmwide|use[s]? it for|provides .{0,55} support to)\b',lower)):
            return (named, metric, dated, len(sentence.split()))
        if area == 'Market and policy' and dated:
            if named and re.search(TOPICS[area],sentence,re.I):
                return (True, metric, True, len(sentence.split()))
            if re.match(r'^[\d,]+ advertised .{0,40} roles tracked and deduplicated\b',lower):
                return (False, True, True, len(sentence.split()))
        if area == 'Leadership and culture':
            if re.search(r'\b(?:your leadership|our leadership team|meet (?:the|our) team)\b',lower):
                return None
            if re.search(r'^(?:founder.led since|our founders [A-Z])',sentence,re.I):
                return (named, metric, dated, len(sentence.split()))
        if not _FINITE.search(sentence) or not re.search(TOPICS[area], sentence, re.I):
            return None
        if area == 'Business and history':
            if not (named or re.match(r"^(?:founded in|we (?:are|provide|offer|specialise|operate)|we[’']ve (?:grown|built))",lower)):
                return None
            if re.match(r'^(?:more than |over )?[\d,.]+\s',lower):
                return None
            # Prefer what the organisation does over a biographical reference or a quote about its owner.
            description = bool(re.match(r"^(?:we (?:are|provide|offer|specialise|operate)|founded in)",lower)
                               or re.match(r'^[\w –&-]+? (?:is|operates|provides|places)\b',sentence,re.I))
            return (description, named, dated, len(sentence.split()))
        if area == 'Ownership' and not re.search(r'\b(?:owns|owned|subsidiary|majority stake|mutual organisation|listed on)\b',lower):
            return None
        if area == 'Customers and users':
            if not (named or re.search(r'^we (?:serve|support|provide|help|work|build|partner)', lower)):
                return None
        return (named, metric, dated, len(sentence.split()))

    def select_answers():
        # Find the strongest combination that fits the quote allowance on each page.
        # Six topic bits keep the number of combinations bounded.
        combined = {(0, 0): (0, {})}
        topics = list(candidates_by_topic)
        ranked = [sorted(set(candidates_by_topic[area]), reverse=True) for area in topics]
        for ref in pages:
            choices = {(0, 0): (0, {})}
            for index, candidates in enumerate(ranked):
                for position, (_, sentence, source) in enumerate(candidates):
                    if source != ref:
                        continue
                    words = len(sentence.split())
                    for (mask, used), (strength, findings) in list(choices.items()):
                        bit = 1 << index
                        if mask & bit or used+words > 25 or sentence in findings.values():
                            continue
                        key = (mask | bit, used+words)
                        value = strength + len(candidates)-position
                        if key not in choices or value > choices[key][0]:
                            choices[key] = (value, {**findings, topics[index]: sentence})
            for (mask, count), (strength, existing) in list(combined.items()):
                for (added, _), (quality, findings) in choices.items():
                    if not added or mask & added or set(findings.values()) & {x['text'] for x in existing.values()}:
                        continue
                    key = (mask | added, min(count+1, 2))
                    value = strength+quality
                    if key not in combined or value > combined[key][0]:
                        merged = {**existing, **{area:{'text':text,'source':ref} for area,text in findings.items()}}
                        combined[key] = (value, merged)
        def priority(item):
            (mask, pages_used), (strength, _) = item
            has_business = bool(mask & 1)
            coverage = mask.bit_count()
            return (has_business and coverage>=3 and pages_used>=2, has_business, coverage, strength)
        _, (_, selected) = max(combined.items(), key=priority)
        for area in topics:
            answers.pop(area, None)
        answers.update(selected)

    def collect_page(url, focus='', selected=False):
        if attempts >= company_limit or not _employer_domain(url, employer):
            return
        if (url,focus) in tried:
            return
        tried.add((url,focus))
        args = {'find': [{'ref_id': url, 'pattern': focus}]} if focus else {'open': [{'ref_id': url}]}
        label, body = _opened(call({**args,'response_length':'long'}, 'Checking an employer source'), url)
        text = label+' '+body
        identity = re.sub(r'[^a-z0-9]', '', text.casefold())
        named = employer_key in identity or bool(acronym and re.search(r'\b'+re.escape(acronym)+r'\b',text.casefold()))
        global_context = selected and re.search(r'\b(?:global|worldwide|international|countries)\b',text,re.I)
        readable = bool(body and named and (global_context or _in_market(url, text, australian)))
        company_attempts.append({'url':url,'readable':readable})
        if not readable:
            return
        ref=next((key for key,page in pages.items() if page['url']==url),f'employer_{len(tried)}')
        pages[ref]={'kind':'employer','label':label or employer,'url':url,
                    'locator':f"Employer page checked {observed['checked_on']}. Statements apply to the publisher’s stated scope."}
        passages=list(_sentences(body, require_punctuation=True))
        employer_subject = r', (?='+r'[ -]*'.join(map(re.escape,name_words))+r' (?:is|provides|serves)\b)'
        # Extract a complete company statement when a line starts mid-sentence in a preceding clause.
        for sentence in list(passages):
            pieces=re.split(employer_subject, sentence, flags=re.I)
            if len(pieces)>1 and len(pieces[0].split())<10:
                passages.remove(sentence)
                passages.extend(pieces[1:])
        for line in _sentences(body, minimum=4):
            founding = re.match(r'^(Founder.led since 20\d{2})[.,]?(?: |$)', line, re.I)
            if founding:
                passages.append(founding[1])
        # Dated, numeric annual-report highlights can be factual even without a full sentence.
        annual_report=bool(re.search(r'\b20\d{2}\s+annual report\b',label,re.I))
        report_highlights=list(_sentences(body, minimum=8)) if annual_report else []
        for sentence in dict.fromkeys([*passages,*report_highlights]):
            for area in RESEARCH_AREAS[:-1]:
                if sentence not in passages and area not in {'Customers and users','Finances and trajectory'}:
                    continue
                score=rank(area,sentence)
                if (score is None and area=='Finances and trajectory' and annual_report and
                        re.match(r'^[£€$][\d,.]+ (?:million|billion) in (?:group )?(?:insurance )?revenue\b',sentence,re.I) and
                        re.search(r'\bFY\d{2}\b',sentence)):
                    score=(False, True, True, len(sentence.split()))
                    amount=sentence.split(',',1)[0] if ',' in sentence else sentence
                    if amount!=sentence and 'revenue' in amount.casefold():
                        candidates_by_topic[area].append(((False, True, True, len(amount.split())),amount,ref))
                if score is not None:
                    candidates_by_topic[area].append((score,sentence,ref))
        select_answers()

    def discover_pages(queries, reserve=0):
        if attempts>=company_limit:
            return
        leads=discover(call({'system2_search_query':[{'q':q} for q in queries],
                             'response_length':'medium'},'Finding employer sources'))
        urls=list(dict.fromkeys(lead['url'] for lead in leads if _employer_domain(lead['url'],employer)
                                and not any(page['url']==lead['url'] for page in pages.values())))
        urls.sort(key=lambda url: (
            australian and not (urlsplit(url).hostname or '').endswith('.au'),
            not bool(re.search(r'/[^?#]*(?:about|our-story|investor|newsroom|annual-report|customers|case-stud)',urlsplit(url).path,re.I)),
        ))
        for url in urls:
            if attempts>=company_limit-reserve or all(area in answers for area in RESEARCH_AREAS[:-1]):
                break
            collect_page(url)

    def missing_topics():
        return [area for area in RESEARCH_AREAS[:-1] if area not in answers]

    if 'employer' in scope:
        for link in company_links:
            collect_page(link['url'],link['focus'],selected=True)
        if not company_links:
            discover_pages([f'{employer}{market} official about company history',
                            f'{employer}{market} official customer case studies',
                            f'{employer}{market} official annual report ownership leadership'],
                           reserve=2 if company_limit-attempts>=4 else 0)
        missing=missing_topics()
        if missing and attempts+1<company_limit:
            discover_pages([f'"{employer}"{market} official {area.lower()}' for area in missing[:3]])
        if attempts<company_limit and pages and missing_topics():
            focus_by_area=dict(zip(RESEARCH_AREAS[:-1],('founded','customers','owned','revenue','chief executive','regulated')))
            url=next(iter(pages.values()))['url']
            collect_page(url,focus_by_area[missing_topics()[0]],selected=True)

    for area,answer in answers.items():
        ref=answer['source']
        if ref in pages:
            sources.setdefault(ref,{**pages[ref],'excerpt':''})
            sources[ref]['excerpt']+='\n'+answer['text']
    report['company_checks']=company_attempts
    for index, url in enumerate(technology_links, 1):
        if attempts >= limit:
            report.setdefault('technology_notes', []).append('Some technology links remain unread within this run’s search budget.')
            break
        label, body = _opened(call({'open': [{'ref_id': url}], 'response_length': 'long'},
                                   'Checking a technology evidence link'), url)
        text = re.sub(r'(?m)^L\d+:\s*', '', body)
        role_page = bool(re.search(r'/(?:jobs?|careers?)(?:/|$)', urlsplit(url).path, re.I))
        named = employer_key in re.sub(r'[^a-z0-9]', '', (label+' '+text[:2500]).casefold())
        in_market = _in_market(url, label+' '+body, australian)
        ref = f'technology_{index}'
        evidence = []
        if named and in_market and body:
            if role_page and not source_problem(text, label):
                sibling = {'title': label, 'employer': employer}
                passages = technology_passages(text, sibling)
                evidence = technology_rows(passages, 'related', ref, limit=1)
            elif not role_page and _employer_domain(url, employer):
                evidence = technology_rows(_sentences(body), 'company', ref, limit=1)
        if evidence:
            report['technology'].extend(evidence)
            sources[ref] = {'kind': 'related_posting' if role_page else 'company_example', 'url': url,
                            'label': label or 'Public evidence link', 'excerpt': evidence[0]['quote'],
                            'locator': f"Public technology source opened {observed['checked_on']}."}
        else:
            report.setdefault('technology_notes', []).append(f"Link {index} did not provide a readable, attributable technology passage.")

    for claim in report['claims']:
        area = claim['area']
        if area in answers:
            answer = answers[area]
            claim.update(kind='confirmed', text=answer['text'], sources=[answer['source']], question='')
        else:
            claim['question'] = GAP_QUESTIONS[area]
    relevant = [area for area in RESEARCH_AREAS if ('role' in scope if area == _ROLE else 'employer' in scope)]
    gaps = [area for area in relevant if area not in answers]
    blockers = []
    employer_count = sum(area in answers for area in RESEARCH_AREAS[:-1])
    if 'employer' in scope and (RESEARCH_AREAS[0] not in answers or employer_count < 3 or len({a['source'] for k, a in answers.items() if k != _ROLE}) < 2):
        blockers.append('Employer research needs business context and three supported topics from at least two employer pages.')
    if 'role' in scope and _ROLE not in answers:
        blockers.append('The saved advert needs enough material criteria to map the work and its requirements.')
    if 'role' in scope and report['role_research']['source_check'] in {'unconfirmed','readable_copy'}:
        gaps.append('Vacancy availability')
    if 'pay' in scope and not observed['employer_pay']:
        gaps.append('Advertised pay')
        if not relevant:
            blockers.append('The saved advert does not establish an employer pay range.')
    if failures:
        progress(f'{failures} source checks could not be completed', attempts, limit)
    report['research_gaps'] = gaps
    return {'export_ready': not blockers, 'verified_topics': list(answers), 'gaps': gaps, 'blockers': blockers,
            'role_criteria': report.get('role_research', {}).get('requirements', 0)}
