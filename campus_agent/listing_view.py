"""Readable listing sections, retaining source wording and the original text."""
import re
import json


HEADINGS = {
    'about the team', 'in this role, you will', 'you might thrive in this role if you',
    'about us', 'about the company', 'about the role', 'the role', 'your role',
    'what you will do', 'what you’ll do', "what you'll do", 'responsibilities',
    'key responsibilities', 'your responsibilities', 'duties', 'key duties',
    'what you need', 'what we’re looking for', "what we're looking for",
    'what we are looking for', 'requirements', 'essential requirements',
    'qualifications', 'about you', 'skills and experience', 'selection criteria',
    'helpful, not required', 'desirable', 'desirable criteria', 'nice to have',
    'where this goes', 'what we offer', 'benefits', 'why join us',
    'our process', 'recruitment process', 'how to apply', 'to apply',
    'compensation & benefits', 'the opportunity', 'what you’ll bring',
    "what you'll bring", 'what you bring', 'your experience',
    "what you'll need to succeed", 'what you’ll need to succeed',
    'technical skills', 'experience', 'key skills', 'minimum qualifications',
    'specialist/technical expertise/qualifications', 'key selection criteria',
    'essential', 'must have', 'your profile', 'what you will own',
    'what you need to do now', 'other relevant information',
    'required experience', 'required skills', 'required skills and experience',
    'required experience & skills', 'required qualifications',
    'job requirements', 'key criteria', 'company description',
}


def without_site_footer(text):
    # Recognize a navigation cluster, not the ordinary word "Research" in a role.
    return re.split(r'(?im)^\s*Research\s*\n+\s*[*•-]\s+Research Index\b', text, maxsplit=1)[0].rstrip()


def confirmed_listing_employer(job, text):
    """Resolve placeholders from explicit employer evidence, never a product mention."""
    from urllib.parse import urlsplit
    host = (urlsplit(str(job.url)).hostname or '').lower()
    if not re.fullmatch(r'(?:Employer on job listing|Employer in job alert|Unknown|TBD)', job.employer, re.I):
        return job.employer
    explicit = re.search(r'(?im)^\s*(?:Employer|Hiring organisation|Hiring organization)\s*:\s*([^\n|<>]{2,100})\s*$', text)
    if explicit:
        return explicit[1].strip()
    if host in {'simplyhired.com.au','www.simplyhired.com.au'} and urlsplit(str(job.url)).path.startswith('/job/'):
        header=re.split(r'(?im)^\s*(?:#+\s*)?(?:Full Job Description|Job Details|Qualifications|Benefits)\s*$',restore_flat_markdown(text),maxsplit=1)[0]
        company=re.search(r'(?m)^\s*[-*]\s+([^\n|<>]{2,100}?)\s+-\s+[0-5](?:\.\d)?\s*$',header)
        if company:
            name=company[1].strip()
            title_found=any(role_key(job.title) in {role_key(re.sub(r'^#+\s*','',line)),role_key(re.sub(r'^#+\s*','',line))+' - '+name.casefold()} for line in header.splitlines() if line.startswith('#'))
            if title_found: return name
    if (host == 'indeed.com' or host.endswith('.indeed.com')) and urlsplit(str(job.url)).path == '/viewjob':
        header=re.split(r'(?im)^\s*(?:#+\s*)?Full job description\s*$', text, maxsplit=1)[0]
        match=re.search(r'(?m)^\s*#+\s+([^\n]+)\s*\n+\s*([^\n]+)',header)
        if match:
            title=match[1].strip()
            saved=re.split(r'\s+-\s+',job.title)[0].strip()
            name=re.sub(r'\s+\.css-[^\n]*$', '',match[2]).strip()
            from .locations import CITIES, STATES
            location_words = list(CITIES) + list(STATES.values()) + ['Australia']
            is_location = any(re.search(r'\b'+re.escape(place)+r'\b', name, re.I) for place in location_words) or bool(re.search(r'\b(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b',name))
            invalid = re.search(r'\b(?:indeed|job description|location|remote|hybrid|on.site|stars?|rating|apply|employer not|company not|not disclosed|not stated|unknown|confidential|anonymous|undisclosed|recruiter|sign in|save job|view job)\b', name, re.I)
            # A genuine board company header is followed by a parent, rating or location line.
            following=header[match.end():]
            context=re.search(r'(?im)^\s*(?:\(part of .+\)|[0-5](?:\.\d)?(?:\s+[0-5](?:\.\d)?)?\s+out of\s+5\s+stars|[^\n]{0,70}\b(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b)\s*$',following)
            if role_key(title)==role_key(saved) and re.fullmatch(r'[\w][\w &.,\'’()/-]{1,98}',name) and not is_location and not invalid and context:
                return name
    # The official careers host and its company section independently establish identity.
    host = (urlsplit(str(job.url)).hostname or '').lower()
    if host in {'openai.com', 'www.openai.com'} and urlsplit(str(job.url)).path.startswith('/careers/'):
        if re.search(r'(?im)^\s*(?:#+\s*)?About OpenAI\s*$', text):
            return 'OpenAI'
    return job.employer


def listing_view(text, title='', employer=''):
    original = text
    text = normalize_listing(text, title)
    role_title = re.split(r'\s+[—|]\s+', title)[0]
    text = re.sub(r'(?m)^L\d+: ?', '', text.replace('\r', ''))
    text = re.sub(r'【\d+†([^】]*)】', r'\1', text)
    text = re.sub(r'[^]*|【[^】]*】|\[wordlim\s*:?\s*\d+\]', '', text)
    text = without_site_footer(text)
    # Stop at explicit board recommendations, rather than folding other roles in.
    text = re.split(r'(?im)^\s*(?:#+\s*)?(?:Similar jobs|Related jobs|Find similar jobs|Recommended jobs|People also viewed|More jobs like this|Explore more jobs|See also|What .+ jobs ask for|Tailor my CV Apply|Show more Show less)\b', text)[0]
    freehire = 'Sign in to see your match' in text and 'Profile match' in text
    if freehire:
        text = re.split(r'(?im)^\s*## Skills\s*$', text)[0]
    # Split explicit inline headings at paragraph or sentence boundaries only.
    text = re.sub(r'(?im)(^|(?<=[.!?])\s+)(Job Requirements|Requirements|Essential requirements|What you need|About the role|About us|About the company|Company description|Benefits|What we offer|Desirable|Nice to have):\s*', lambda m:m.group(1)+'\n'+m.group(2)+'\n', text)
    lines = [line.strip() for line in text.splitlines()]
    display_title = next((re.sub(r'^#+\s*','',line) for line in lines
                          if line.startswith('#') and len(re.sub(r'^#+\s*','',line))>8
                          and title.casefold().startswith(re.sub(r'^#+\s*','',line).casefold())),title)
    facts = []
    for label in ['Work format', 'Work type', 'Grade']:
        for i,line in enumerate(lines):
            if line.casefold() == label.casefold():
                value = next((v for v in lines[i+1:] if v), '')
                if value and len(value)<=80:
                    facts.append({'label': 'Listed level' if label=='Grade' else label, 'value':value})
                break
    salary = salary_info(text)
    if salary['status'] != 'not_stated':
        facts.insert(0, {'label':'Salary', 'value':salary['display']})
    employer = re.split(r'\s+[—|]\s+.*(?:LinkedIn Jobs|SEEK|freehire)', employer, flags=re.I)[0]
    if not employer_known(employer):
        employer=''
    if title:
        for line in lines:
            if ' · ' in line and line.split(' · ',1)[1].casefold()==role_title.casefold():
                employer=line.split(' · ',1)[0]
                break
    # Known board header ends before the actual employer-written description.
    marker = next((i for i,line in enumerate(lines) if line=='Description Company' or re.fullmatch(r'(?:#+\s*)?Full Job Description',line,re.I)),None)
    if marker is not None:
        lines=lines[marker+1:]
    sections=[{'title':'Overview','blocks':[]}]
    pending=[]
    def flush():
        if pending:
            sections[-1]['blocks'].append({'kind':'paragraph','text':' '.join(pending)})
            pending.clear()
    for line in lines:
        if not line:
            flush()
            continue
        stripped = re.sub(r'^#{1,6}\s*', '', line).strip().strip('*').strip()
        if stripped.casefold() in {title.casefold(),role_title.casefold(),display_title.casefold()} or re.match(r'^(?:Salary\s*:|Image[†:])',stripped,re.I):
            continue
        if re.match(r'^(?:Posted\s+|Published:|Crawled:)',stripped,re.I) and len(stripped)<100:
            continue
        if stripped.rstrip(':').casefold() in HEADINGS or (line.startswith('#') and 0<len(stripped)<100):
            flush()
            sections.append({'title':stripped.rstrip(':'),'blocks':[]})
            continue
        if re.fullmatch(r'[-_=]{3,}',line) or line in {'Discussion Report Save','Description Company','Save to board','Sign in','Seek'}:
            continue
        bullet = re.match(r'^(?:[*•-]\s+|\d+[.)]\s+)(.+)',line)
        if bullet:
            flush()
            ordered=bool(re.match(r'^\d+[.)]',line))
            blocks=sections[-1]['blocks']
            if not blocks or blocks[-1]['kind']!='list' or blocks[-1]['ordered']!=ordered:
                blocks.append({'kind':'list','ordered':ordered,'items':[]})
            blocks[-1]['items'].append(bullet[1])
        else:
            pending.append(line)
    flush()
    sections=[section for section in sections if section['blocks']]
    highlights=[]
    for section in sections:
        if section['title'].casefold() not in {'what you need','requirements','essential requirements','selection criteria','what we’re looking for',"what we're looking for"}:
            continue
        for block in section['blocks']:
            if block['kind']=='paragraph' and re.search(r'\b(?:criterion|must|required|at least|do not count)\b',block['text'],re.I):
                highlights.append(block['text'])
    notices=[]
    if text.startswith('Listing mismatch:'):
        notices.append({'message':'The page metadata describes a different role. Verify the original posting.','quote':text.splitlines()[0]})
    if any(f['label']=='Work format' and f['value'].casefold()=='hybrid' for f in facts):
        office=re.search(r'[^.!?\n]*\bbased full time in (?:our |the )?[^.!?\n]*\boffice\b[^.!?\n]*[.!?]?',text,re.I)
        if office:
            notices.append({'message':'Confirm the work arrangement: the header says Hybrid, while the description mentions full-time office attendance.', 'quote':office[0].strip()})
    overview=next((s for s in sections if s['title']=='Overview'),None)
    preview=next((b['text'] for s in ([overview] if overview else sections) for b in s['blocks'] if b['kind']=='paragraph'), '')
    overview_text = next((b['text'] if b['kind']=='paragraph' else b['items'][0]
        for section in sections if re.search(r'^(?:about the role|the role|your role|the opportunity|what you will do|responsibilities|key responsibilities)$',section['title'],re.I)
        for b in section['blocks']), preview)
    overview_text = re.sub(r'(?<!\w)#{1,6}\s*', '', overview_text)
    if len(overview_text) > 500:
        excerpt = overview_text[:500]
        boundary = max((m.end() for m in re.finditer(r'[.!?](?=\s)', excerpt)), default=0)
        overview_text = (excerpt[:boundary] if boundary >= 250 else excerpt.rsplit(' ', 1)[0] if ' ' in excerpt else '').rstrip() + '…'
    return {'overview':overview_text, 'salary':salary, 'title':display_title,'facts':facts,'employer':employer,'sections':sections,'highlights':highlights[:3],
            'notices':notices,'preview':preview,'original_chars':len(original)}


def normalize_listing(text, title=''):
    """Read employer JobPosting metadata where present, without borrowing other roles."""
    if not re.match(r'\s*(?:<!doctype|<(?:html|p|div|article|main|section)\b|<script[^>]+application/ld\+json)', text, re.I):
        return restore_flat_markdown(text)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')
    postings = []
    def walk(value):
        if isinstance(value, list):
            for item in value: walk(item)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            if 'JobPosting' in ([kinds] if isinstance(kinds,str) else kinds): postings.append(value)
            if '@graph' in value: walk(value['@graph'])
    for script in soup.find_all('script', type='application/ld+json'):
        try: walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): pass
    matches = [p for p in postings if posting_matches(p,title)]
    posting = matches[0] if len(matches)==1 else postings[0] if len(postings)==1 and not title else None
    mismatch=bool(postings and title and not matches)
    if posting and isinstance(posting.get('description'),str):
        body = html_text(posting['description'])
        fields=['# '+posting['title']] if isinstance(posting.get('title'),str) else []
        organisation=posting.get('hiringOrganization',{})
        if isinstance(organisation,dict) and isinstance(organisation.get('name'),str): fields.append('Employer: '+organisation['name'])
        pay=posting.get('baseSalary',{})
        if isinstance(pay,dict):
            amount=pay.get('value',{})
            if isinstance(amount,dict):
                lo,hi=amount.get('minValue',amount.get('value')),amount.get('maxValue')
                if isinstance(lo,(int,float)) and lo>0 and (hi is None or isinstance(hi,(int,float))):
                    period=str(amount.get('unitText','')).lower()
                    fields.append('Salary: '+str(pay.get('currency',''))+' '+str(lo)+((' - '+str(hi)) if hi is not None else '')+(' per '+period if period else ''))
        places=posting.get('jobLocation',[])
        if isinstance(places,dict): places=[places]
        labels=[]
        for place in places if isinstance(places,list) else []:
            address=place.get('address',{}) if isinstance(place,dict) else {}
            if isinstance(address,dict): labels.append(', '.join(str(address[k]) for k in ['addressLocality','addressRegion','addressCountry'] if address.get(k)))
        if labels: fields.append('Location: '+' / '.join(labels))
        for field,label in [('datePosted','Posted on'),('validThrough','Applications close'),('employmentType','Work type')]:
            if isinstance(posting.get(field),str): fields.append(label+': '+posting[field])
        return '\n'.join(fields)+ '\n'+body
    for tag in soup(['script','style','nav','footer']): tag.decompose()
    return ('Listing mismatch: structured data describes a different role. Verify the original posting.\n' if mismatch else '')+html_text(str(soup))


def employer_known(name):
    return bool(name and not re.fullmatch(r'\s*(?:unknown|tbd|n/?a|employer (?:on job listing|in job alert)|not (?:stated|known|verified))\s*',name,re.I))


def role_key(title):
    return re.split(r'\s+[—|]\s+|\s+at\s+',str(title),maxsplit=1,flags=re.I)[0].casefold().strip()


def salary_info(text):
    """Listed pay with its original quote; no currency or annual-pay conversion."""
    unknown={'status':'not_stated','display':'Not stated','currency':None,'period':None,'evidence':'','alternatives':[]}
    symbol=r'(?:AUD\s*\$?|USD\s*\$?|NZD\s*\$?|GBP|EUR|AU\$|US\$|A\$|[$£€])'
    number=r'\d[\d,]*(?:\.\d+)?[kK]?'
    pattern=re.compile(symbol+r'\s*'+number+r'(?:\s*(?:–|—|-|to)\s*(?:'+symbol+r')?\s*'+number+r')?',re.I)
    candidates=[]
    lines=text.splitlines()
    for i,raw in enumerate(lines):
        line=re.sub(r'^\s*(?:[*•-]\s+|#+\s*)','',raw).strip()
        labelled=bool(re.match(r'^(?:salary(?: range)?|remuneration|pay(?: range| rate)?|base salary|rate|compensation)\s*(?::|$)',line,re.I))
        if labelled and not pattern.search(line) and i+1<len(lines): line+=' '+lines[i+1].strip()
        evidence=line
        # An explicitly suffixed currency is just another source spelling.
        line=re.sub(r'('+number+r'(?:\s*(?:–|—|-|to)\s*'+number+r')?)\s+(AUD|USD|NZD|GBP|EUR)\b',r'\2 \1',line,flags=re.I)
        for match in pattern.finditer(line):
            value=match[0].strip();tail=line[match.end():]
            # Classify each money figure, rather than dropping a salary line that mentions benefits.
            prefix=line[:match.start()]
            nearby_before=re.split(r'[;+]|\b(?:plus|and)\b',prefix,flags=re.I)[-1]
            nearby_after=re.split(r'[;+]|\b(?:plus|and)\b',tail,flags=re.I)[0]
            other=r'learning|training|budget|allowance|salary packaging|sign.on|bonus|revenue|turnover|relocation|equity|project value|projects range'
            benefit_before=re.search(other,nearby_before,re.I)
            benefit_after=re.search(other,nearby_after,re.I)
            explicit_basis=re.search(r'per\s+(?:year|annum|hour|day|week|month)|/\s*(?:hr?|day|week|month)|\b(?:annual|hourly|daily|weekly|monthly)\b',nearby_after,re.I)
            # A declared base range can be followed by extra benefits without ceasing to be salary.
            declared_base=bool(re.search(r'base salary\s*:',prefix,re.I) or (re.search(r'(?:–|—|-|to)',value) and re.search(r'\bsalary(?: range)?\s*:',prefix,re.I)))
            if benefit_before: continue
            if benefit_after and not (declared_base or (labelled and explicit_basis and explicit_basis.start()<benefit_after.start())): continue
            if re.search(r'not (?:disclosed|stated)|negotiable|salary packaging',prefix,re.I): continue
            before=line[:match.start()].strip()
            period_context=tail+' '+before
            pm=re.search(r'(?:per\s+|/\s*|\bp\s*/\s*|\bp\.?)(annum|year|hour|day|week|month|hr|a|h|d)\b|\b(hourly|daily|weekly|monthly|annually|annual)\b',period_context,re.I)
            period=next((g.lower() for g in pm.groups() if g),None) if pm else None
            period={'annum':'year','hr':'hour','h':'hour','d':'day','a':'year','hourly':'hour','daily':'day','weekly':'week','monthly':'month','annually':'year','annual':'year'}.get(period,period)
            before=line[:match.start()].strip()
            pay_context=bool(re.search(r'base|super|package|salary|remuneration|pay\b',line,re.I))
            standalone=not before and not re.search(r'[a-z]',tail,re.I)
            if not labelled and not pm and not (pay_context or standalone): continue
            numbers=re.findall(number,value)
            parsed=[float(n.rstrip('kK').replace(',',''))*(1000 if n.lower().endswith('k') else 1) for n in numbers]
            if len(parsed)==2 and numbers[-1].lower().endswith('k') and not numbers[0].lower().endswith('k') and parsed[0]<1000: parsed[0]*=1000
            if not parsed or min(parsed)<=0 or (len(parsed)>1 and parsed[0]>parsed[1]): continue
            inferred=not period and (min(parsed)>=10000 or any(n.lower().endswith('k') for n in numbers))
            if inferred: period='year'
            currencies=[c for c,rx in [('USD',r'USD|US\$'),('NZD',r'NZD'),('AUD',r'AUD|AU\$|(?<![A-Z])A\$'),('GBP',r'GBP|£'),('EUR',r'EUR|€')] if re.search(rx,value,re.I)]
            currency=currencies[0] if len(currencies)==1 else None
            display=evidence.split(':',1)[1].strip() if labelled and ':' in evidence else evidence
            if len(display)>160: display=value+tail[:60]
            record={'status':'conflicting' if len(currencies)>1 else 'stated','display':display,'currency':currency,'period':period,'period_inferred':bool(inferred),'minimum':parsed[0],'maximum':parsed[-1],'evidence':evidence,'alternatives':[]}
            same=next((r for r in candidates if r['minimum']==parsed[0] and r['maximum']==parsed[-1] and r['period']==period and (r['currency']==currency or r['currency'] is None or currency is None)),None)
            if same is None: candidates.append(record)
    if not candidates: return unknown
    result=candidates[0]
    if len(candidates)>1 or result['status']=='conflicting':
        result={**result,'status':'conflicting','display':'Conflicting pay figures — check listing','alternatives':candidates}
    return result


def html_text(markup):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(markup,'html.parser')
    for item in soup.find_all('li'): item.insert_before('\n- '); item.append('\n')
    for heading in soup.find_all(re.compile(r'^h[1-6]$')): heading.insert_before('\n## '); heading.append('\n')
    for paragraph in soup.find_all(['p','div','br']): paragraph.append('\n')
    for tag in soup(['script','style','nav','footer']): tag.decompose()
    # Prefixes remain on the same line as their source text.
    text=soup.get_text(' ',strip=False)
    text=re.sub(r'\s*\n\s*', '\n', text)
    return text


def posting_matches(posting,title):
    actual=role_key(posting.get('title',''))
    expected=role_key(title)
    if actual==expected: return True
    organisation=posting.get('hiringOrganization',{})
    name=organisation.get('name','') if isinstance(organisation,dict) else ''
    return bool(name and expected==actual+' - '+str(name).casefold().strip())


def restore_flat_markdown(text):
    """Recover headings/lists lost when a search excerpt collapses Markdown lines."""
    if text.count('\n')>=2 or not re.search(r'\s#{1,6}\s',text): return text
    text=re.sub(r'\s+(#{1,6}\s+)',r'\n\1',text)
    text=re.sub(r'(?<!\*)\s+\*\s+(?!\*)','\n- ',text)
    names=sorted(HEADINGS|{'full job description','job details'},key=len,reverse=True)
    headings='|'.join(re.escape(name) for name in names)
    lines=[]
    for line in text.splitlines():
        match=re.match(r'^(#{1,6}\s+(?:'+headings+r'))(?:\s+(.+))?$',line,re.I)
        if match:
            lines.append(match[1])
            if match[2]: lines.append(match[2])
        else: lines.append(line)
    return '\n'.join(lines)
