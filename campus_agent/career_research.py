"""Reopen employer sources and check that each exported answer has evidence."""

import re
from concurrent.futures import TimeoutError
from urllib.parse import urlsplit

from .career_render import RESEARCH_AREAS


TOPICS = dict(zip(RESEARCH_AREAS, (
    r'\b(?:founded|established|specialises|specializes|manufactures|provides|operates|develops|supplies|offers|delivers|is an? .{0,55}(?:company|provider|insurer|fund|firm|manufacturer|organisation|organization|platform))\b',
    r'\b(?:serves?|supports?|helps?|provides?|customers|clients|members|patients|healthcare providers|law firms)\b.{0,100}\b(?:customers|clients|members|patients|hospitals|law firms|healthcare providers|organisations|organizations|teams|businesses)\b',
    r'\b(?:member.owned|owned by|subsidiary of|listed on|majority stake|mutual organisation|not.for.profit|owns (?:a |the )?(?:majority|minority|[\d.]+\s*%))\b',
    r'\b(?:revenue|funding round|net profit|net loss|operating profit|cash flow|claims paid|raised)\b',
    r'\b(?:chief executive|ceo|appointed|board of directors|employee survey|employee resource groups)\b',
    r'\b(?:regulated by|under the .{5,80} act|licen[cs]ed by|accredited by|accreditation)\b',
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
_BAD_LINE = re.compile(r'access denied|unable to resolve|failed to fetch|enable javascript|all rights reserved|cookie policy|similar jobs|search results|sign in to|privacy policy|\b(?:learn more|learn how|find out|explore our|contact us|click here|image:|subscribe)\b', re.I)
_FINITE = re.compile(r'\b(?:is|are|was|were|has|have|had|can|will|serve[sd]?|help[s]?|support[s]?|provides?|offers?|speciali[sz]es?|delivers?|operates?|include[sd]?|work[s]?|report[s]?|appointed|raised|announced)\b', re.I)
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
        if len(lines) < 3 or not lines[0].strip().endswith('(' + url + ')') or 'Source: open(' not in lines[1]:
            continue
        return lines[0].strip()[:-len(url)-3], '\n'.join(line for line in lines[2:] if re.match(r'^L\d+:', line))
    return '', ''


def research(observed, report, scope, limit, web, discover, progress):
    """Discovery supplies URLs. The separate open pass supplies all public answers."""
    vacancy = observed['vacancy']
    employer = vacancy['employer']
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
        # The saved advert can establish its stated duties, even if its availability is unconfirmed.
        roles = [s for s in _sentences(sources['advert']['excerpt'], minimum=5)
                 if re.match(TOPICS[_ROLE], s, re.I) or re.search(r'\b(?:you will|responsible for)\b', s, re.I)]
        if roles:
            # Prefer the specific duty when the advert also has a short slogan.
            role = max(roles, key=lambda s: (len(s.split()) >= 8, len(re.findall(r'\b[A-Z0-9]{2,}\b', s)), len(s.split())))
            answers[_ROLE] = {'text': role, 'source': 'advert'}

    def rank(area, sentence):
        lower = sentence.casefold()
        compact = re.sub(r'[^a-z0-9]', '', lower)
        named = employer_key in compact or bool(acronym and re.search(r'\b'+re.escape(acronym)+r'\b', lower))
        if not _FINITE.search(sentence) or not re.search(TOPICS[area], sentence, re.I):
            return None
        metric = bool(re.search(r'[%€£$]|\b(?:million|billion|thousand)\b', lower))
        if area == 'Finances and trajectory' and not metric:
            return None
        if area == 'Business and history' and not named:
            return None
        if area == 'Customers and users' and not (named or re.search(r'^we (?:serve|support|provide|help|work)', lower)):
            return None
        return (named, metric, bool(re.search(r'\b(?:founded|established)\b', lower)), len(sentence.split()))

    def select_answers():
        chosen = set()
        left = dict.fromkeys(pages, 25)
        # Give priority to business context, then more specific topics.
        for area in ('Business and history','Ownership','Finances and trajectory','Customers and users','Leadership and culture','Market and policy'):
            answers.pop(area, None)
            options = sorted(candidates_by_topic[area], key=lambda item: item[0], reverse=True)
            for _, sentence, ref in options:
                words = len(sentence.split())
                if words <= left[ref] and sentence.casefold() not in chosen:
                    answers[area] = {'text': sentence, 'source': ref}
                    chosen.add(sentence.casefold())
                    left[ref] -= words
                    break

    def collect(queries, reserve=0):
        if attempts >= limit:
            return
        leads = discover(call({'system2_search_query': [{'q': q} for q in queries],
                               'response_length': 'medium'}, 'Finding employer sources'))
        candidates = [lead['url'] for lead in leads if lead['url'] not in tried
                      and _employer_domain(lead['url'], employer)]
        for url in candidates:
            if attempts >= limit-reserve or all(area in answers for area in RESEARCH_AREAS[:-1]):
                break
            tried.add(url)
            label, body = _opened(call({'open': [{'ref_id': url}], 'response_length': 'long'},
                                       'Reading and checking employer pages'), url)
            identity = re.sub(r'[^a-z0-9]', '', (label + ' ' + body).casefold())
            if not body or (employer_key not in identity and not (acronym and re.search(r'\b'+re.escape(acronym)+r'\b', (label+' '+body).casefold()))):
                continue
            ref = f'employer_{len(tried)}'
            pages[ref] = {'kind': 'employer', 'label': label or employer, 'url': url,
                          'locator': f"Employer page opened {observed['checked_on']}; published statements."}
            for sentence in _sentences(body, require_punctuation=True):
                for area in RESEARCH_AREAS[:-1]:
                    score = rank(area, sentence)
                    if score is not None:
                        candidates_by_topic[area].append((score, sentence, ref))
            select_answers()

    if 'employer' in scope:
        collect([f'"{employer}" official about business founded',
                 f'"{employer}" official customers case studies',
                 f'"{employer}" official annual report ownership leadership'], reserve=2 if limit >= 4 else 0)
        missing = [area for area in RESEARCH_AREAS[:-1] if area not in answers]
        if missing and attempts+1 < limit:
            collect([f'"{employer}" official {area.lower()}' for area in missing[:4]])

    sources.update({answer['source']: pages[answer['source']] for answer in answers.values() if answer['source'] in pages})
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
        blockers.append('A material responsibility needs evidence from the saved advert.')
    if 'pay' in scope and not observed['employer_pay']:
        gaps.append('Advertised pay')
        if not relevant:
            blockers.append('The saved advert does not establish an employer pay range.')
    if failures:
        progress(f'{failures} source checks could not be completed', attempts, limit)
    report['research_gaps'] = gaps
    return {'export_ready': not blockers, 'verified_topics': list(answers), 'gaps': gaps, 'blockers': blockers}
