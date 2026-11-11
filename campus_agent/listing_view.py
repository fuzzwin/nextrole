"""Readable listing sections, retaining source wording and the original text."""
import re
import json
import html

REQUIREMENT_HEADINGS = {
    'you might thrive in this role if you', "you'll thrive here if you", 'who you are',
    'what you bring', 'what you will need', "what you'll bring", 'requirements & qualifications',
    'requirements and qualifications', "what kind of things we're most interested in you having",
    'your qualifications', 'your skills & experience',
}


def heading_key(value):
    return re.sub(r'\s+',' ',html.unescape(value).replace('’',"'")).strip().rstrip(':?').casefold()


def requirement_heading(value):
    return heading_key(value) in REQUIREMENT_HEADINGS


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
    'your background', 'what you will bring', 'required skills and qualifications', 'to be successful', 'to be successful in this role', 'your skills and experience', 'essential skills and experience', 'qualifications and experience', 'key capabilities', 'selection requirements', 'job requirements', 'key requirements', 'skills required', 'key criteria', 'company description', 'company overview', 'our story',
}
HEADINGS |= REQUIREMENT_HEADINGS | {'bonus points for', 'highly regarded', "what you'll own",
    "how you'll spend your time", "what's life like at plenti", 'hear more from the team', 'you will ideally have'}


def without_site_footer(text):
    # Recognize a navigation cluster, not the ordinary word "Research" in a role.
    return re.split(r'(?im)^\s*Research\s*\n+\s*[*•-]\s+Research Index\b', text, maxsplit=1)[0].rstrip()


RECOMMENDATIONS = r'(?im)^\s*(?:#+\s*)?(?:Similar jobs|Similar roles|More roles at|Related jobs|Find similar jobs|Recommended jobs|People also viewed|Jobs with similar titles|Search similar titles|More jobs like this|Explore more jobs|Hear More from the Team|See also|What .+ jobs ask for|Tailor my CV Apply|Show more Show less|Show more\s*\n\s*Show less)\b'


def source_problem(text, title=''):
    """Classify unavailable or misdirected captures before reading criteria."""
    clean = re.sub(r'(?m)^L\d+(?:@P[\d-]+)?: ?', '', text)
    if re.search(r'(?i)L0 is out of bounds|Total lines:\s*0|Failed to fetch https?://|^\s*Access denied|^\s*Just a moment',clean):
        return ('source_unavailable','The source returned an unavailable or blocked page, not a readable advert.')
    if re.search(r'(?i)\b(?:summary|synopsis|excerpt)\b[^\n]{0,100}\bnot\s+(?:a\s+)?verbatim|\bnot\s+(?:a\s+)?verbatim\b[^\n]{0,100}\b(?:summary|synopsis|excerpt)',clean):
        return ('source_summary','Only a non-verbatim summary is saved. Original employer requirements are needed.')
    if re.search(r'(?i)\bjobs?\s+(?:in|near me)\b',title) or re.search(r'(?im)^\s*#{1,6}\s*\d[\d,]*[^\n]{0,150}\bjobs?\s+in\b',clean):
        return ('search_results','This source is a job-search directory, not the original individual advert.')
    if re.search(r'(?im)^\s*#{1,6}\s*(?:Current openings at\b|\d+ results? for\b|\d+ jobs\s*$|Search jobs at\b)',clean) or re.search(r'(?i)Redirected to URL:[^\n]*(?:job_not_found|[?&]error=true|/jobsearch\b|/careers/[^/]+/jobs(?:\s|$))|job vacancy you tried to view was not found',clean):
        return ('search_results','This source redirects to a list of vacancies instead of this individual advert.')
    if re.search(r'(?im)^\s*#{1,6}\s*Job summary\s*$',clean) and not re.search(r'(?im)^\s*#{1,6}\s*(?:Full )?Job description\s*$',clean):
        return ('source_summary','This board saved a job summary, not the complete original employer advert.')
    primary = re.split(RECOMMENDATIONS,clean)[0]
    if len(re.findall(r'(?m)^\s*####\s+[^\n]+',primary))>=6 and len(re.findall(r'(?m)^\s*###\s+[^\n]+',primary))>=6:
        return ('search_results','The saved capture contains unrelated roles/employers. Verify the individual advert.')
    if re.search(r'(?i)wurde besetzt|position (?:has been )?(?:filled|closed)|no longer accepting applications|job (?:has )?(?:expired|closed)|this job post has expired|the job you are trying to view has expired|sorry, this job was removed', primary):
        return ('closed','The original source says this listing is closed or filled.')
    if re.search(r'(?im)^\s*#{1,6}\s*Job summary\s*$',primary):
        body=re.split(r'(?im)^\s*#{1,6}\s*(?:Full )?Job description\s*$',primary,maxsplit=1)
        if len(body)==2 and re.search(r'(?im)^\s*Show more\s*$',body[1]):
            return ('source_summary','The original advert is truncated behind Show more; board-generated qualifications are not the employer requirements.')
    if '[wordlim' in clean and clean.count('...')>=2 and len(clean)<1200:
        return ('source_summary','Only an indexed excerpt is saved. Read or paste the complete original advert.')
    return None

def title_matches_source(saved_title, text):
    """Require a role title in the captured single-role heading, not body mentions."""
    if re.search(r'(?im)^\s*#{1,6}\s*\d[\d,]*[^\n]{0,120}\bjobs?\s+in\b',text): return False
    headings=re.findall(r'(?m)^\s*#{1,6}\s+([^\n]{3,200})',text[:4000])
    saved=re.sub(r'\s+-\s+Indeed\.com\s*$', '', saved_title,flags=re.I)
    saved=re.sub(r'\s+-\s+(?:[A-Za-z][A-Za-z .\']*\s+)?(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)(?:\s+\d{4})?\s*$', '', saved,flags=re.I)
    saved=re.sub(r'\s+Job Details\s*$', '',saved,flags=re.I).strip().casefold()
    for heading in headings[:1]:
        candidate=heading.strip().casefold()
        if candidate == saved: return True
        alias=re.search(r'\s*\(([^()]{2,60})\)\s*$',heading)
        if alias and saved == (alias[1]+' - '+heading[:alias.start()].strip()).casefold(): return True
    return False


def same_role(saved, actual, company=''):
    """Allow listing decorations, never a different functional title or seniority."""
    clean=lambda s:re.sub(r'\s+',' ',re.sub('(?i)managerment','management',html.unescape(s)).replace('’',"'").replace('–','-').replace('—','-')).strip().casefold()
    expected=clean(saved)
    actual=clean(re.sub(r'^\[Hiring\]\s*','',actual,flags=re.I))
    if company:actual=re.sub(r'\s+(?:[-·|]|at)\s*'+re.escape(clean(company))+r'\s*$','',actual)
    actual=re.split(r'\s*\|\s*(?:up\s*to|from)\s*\$',actual,maxsplit=1,flags=re.I)[0]
    expected=re.sub(r'\s+(?:-\s*(?:indeed\.com|seek(?: \(seek\.com\))?)|job details)\s*$','',expected)
    if expected==actual:return True
    if re.search(r'(?:…|\.{3})$',expected):
        prefix=re.sub(r'(?:…|\.{3})$','',expected)
        if len(prefix)>=30 and len(prefix.split())>=4 and actual.startswith(prefix):return True
    if not expected.startswith(actual):return False
    tail=expected[len(actual):]
    if tail and tail[0].isalnum():return False
    if company:tail=tail.replace(clean(company),'',1)
    tail=re.sub(r'\b\d+\s+(?:school alumni|company alum|connections?|alumni)\b|\b(?:school alumni|company alum|connections?|alumni)\b',' ',tail,flags=re.I)
    from .locations import CITIES, STATES
    for place in sorted([*CITIES,*STATES.values(),'alice springs','barangaroo','australia','remote','hybrid','location','actively recruiting','easy apply','company alum','in','at','up to'],key=len,reverse=True):
        tail=re.sub(r'\b'+re.escape(place)+r'\b',' ',tail,flags=re.I)
    tail=re.sub(r'\b(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\b|\b\d+\b|A\$[\d,]+',' ',tail,flags=re.I)
    return not re.search(r'[a-z]',tail,re.I)


def valid_company(name):
    name=re.sub(r'^[#*\s]+|[#*\s]+$','',name)
    from .locations import CITIES, STATES
    places={str(p).casefold() for p in [*CITIES,*STATES.values(),'Alice Springs','Barangaroo','Australia','Remote','Hybrid']}
    residue=name.casefold()
    for place in sorted(places|{'vic','nsw','qld','wa','sa','tas','act','nt'},key=len,reverse=True):
        residue=re.sub(r'\b'+re.escape(place)+r'\b',' ',residue)
    geographic=not re.search(r'[a-z]',residue) or re.search(r',\s*(?:Australia|United States|United Kingdom|New Zealand|Philippines)\s*$|\s+(?:VIC|NSW|QLD|WA|SA|TAS|ACT|NT)\s*\d{4}\s*$',name,re.I)
    return bool(2<=len(name)<=100 and not geographic and not re.search(
        r'(?i)^(?:apply|save job|job details|full job|full.time\b|part.time\b|permanent\b|casual\b|salary\b|sign in|unknown|not disclosed|not stated|undisclosed|anonymous|confidential|employer (?:on|not)|company not|vacancy from)|[<>{}]|\d.*out of.*5',name))


def header_employer(job, text):
    """Explicit same-role platform evidence; no product, title-only or logo guesses."""
    from urllib.parse import urlsplit
    host=(urlsplit(str(job.url)).hostname or '').lower().removeprefix('www.')
    primary=re.split(RECOMMENDATIONS,re.sub(r'(?m)^L\d+(?:@P[\d-]+)?:\s?','',html.unescape(text)))[0]
    headings=re.findall(r'(?m)^\s*#{1,6}\s+([^\n]+)',primary[:4000])
    if host in {'rmit.edu.au','www.rmit.edu.au'} and urlsplit(str(job.url)).path.lower().endswith('.pdf'):
        if re.search(r'\bRMIT is a global university\b',primary) and any(same_role(job.title,l.strip(),'RMIT University') for l in primary.splitlines()[:30]):return 'RMIT University'
    if host=='healthsharevic.org.au' and urlsplit(str(job.url)).path.lower().endswith('.pdf'):
        if re.search(r'HealthShare Victoria \(HSV\) is a Victorian public sector entity',primary) and re.search(r'(?im)^\s*Position\s+'+re.escape(job.title)+r'\s*$',primary):return 'HealthShare Victoria'
    if not headings:return None
    title=headings[0].strip()
    if host=='linkedin.com' or host.endswith('.linkedin.com'):
        match=re.search(r'(?im)^\s*See who ([^\n†]+?) has hired for this role',primary)
        if match:
            name=match[1].strip()
            header=primary[:match.start()]
            corroborated=re.search(r'(?m)^\s*'+re.escape(name)+r'(?:\s|†|$)',header)
            agency=name.casefold() in {'talent','peoplebank','hays','randstad','galileo search','robert half','sharp & carter','mercor'}
            client=re.search(r'(?i)our client\b|on behalf of|partner(?:ing|ed) with|well.established organi[sz]ation|client(?:\x27s)? team',primary)
            if corroborated and same_role(job.title,title,name) and valid_company(name) and not (agency and client):return name
    if host=='indeed.com' or host.endswith('.indeed.com'):
        header=re.split(r'(?im)^\s*(?:#+\s*)?Full job description\s*$',primary,maxsplit=1)[0]
        match=re.search(r'(?m)^\s*#{1,6}\s+[^\n]+\n+\s*([^\n]+)',header)
        if match:
            name=re.sub(r'\s+\.css-[^\n]*$', '',match[1]).strip()
            metadata=header[match.end():]
            if valid_company(name) and same_role(job.title,title,name) and re.search(r'(?m)^\s*[0-5](?:\.\d)?\s*$|\b(?:VIC|NSW|QLD|Victoria|Australia)\b',metadata):return name
    if host=='jobstore.com' and len(headings)>1:
        name=headings[1].strip()
        if name.casefold()=='mercor' and re.search(r'(?i)AI research labs|leading AI companies',primary):return None
        if same_role(job.title,title,name) and valid_company(name) and re.search(re.escape(name),primary[primary.find(name)+len(name):],re.I):return name
    if host in {'hirealice.app','victra.careers'}:
        header=re.search(r'(?m)^\s*#{1,6}\s+[^\n]+\n+([^\n]+)',primary)
        if header:
            name=header[1].split(' · ')[0].strip()
            saved=re.sub(r'\s+[·|—-]\s*(?:Victra|HireAlice)\s*$','',job.title,flags=re.I)
            if valid_company(name) and same_role(saved,title,name) and re.search(r'\b'+re.escape(name)+r'\b',primary[header.end():],re.I):return name
    if host in {'builtin.com','builtinmelbourne.com','builtinsydney.au'}:
        match=re.search(r'(?im)^\s*(?:#+\s*)?About ([^\n:]{2,80})\s*$',primary)
        if match:
            name=match[1].strip()
            if valid_company(name) and name.casefold() not in {'us','the role','the team','you','this role'} and same_role(job.title,title,name) and len(re.findall(re.escape(name),primary,re.I))>=2:return name
        match=re.search(r'(?i)\bWorking at ([\w &.]+?) (?:will|means|is)\b',primary)
        if match:
            name=match[1].strip()
            office=re.search(r'(?im)^\s*#+\s*'+re.escape(name)+r'\b[^\n]*Office\s*$',primary)
            if office and valid_company(name) and same_role(job.title,title,name):return name
        match=re.search(r'(?im)^\s*(?:#+\s*)?Working at ([^\n:]{2,80})\s*$',primary)
        if match:
            name=match[1].strip()
            claim=re.search(r'(?i)core member of '+re.escape(name)+r'[’\x27]s [^.\n]{0,60}team',primary)
            if claim and valid_company(name) and same_role(job.title,title,name):return name
    if host=='jobs.lever.co':
        match=re.search(r'(?im)^\s*(?:#+\s*)?Who is ([^\n?]{2,80})\??\s*$',primary)
        if match:
            name=match[1].strip();tenant=urlsplit(str(job.url)).path.strip('/').split('/')[0]
            if re.sub(r'\W','',name).casefold()==tenant.casefold() and same_role(job.title,title,name) and re.search(r'(?im)^'+re.escape(name)+r' is a\b',primary):return name
    if host=='swiftcruit.ai':
        match=re.search(r'(?im)^\s*(?:#+\s*)?Employer\s*\n+([^\n]+)',primary)
        if match:
            name=match[1].strip()
            if valid_company(name) and same_role(job.title,title,name) and re.search(r'(?im)^\s*(?:#+\s*)?Why '+re.escape(name)+r'\s*$',primary):return name
    if host=='deliverycentric.com' and same_role(job.title,title,'Delivery Centric') and re.search(r'(?im)^Delivery Centric is seeking\b',primary):return 'Delivery Centric'
    if host=='careers.rldatix.com' and same_role(job.title,title,'RLDatix') and re.search(r'(?im)^RLDatix (?:\(RLD\) )?is on a mission\b',primary):return 'RLDatix'
    return None


def confirmed_listing_employer(job, text):
    """Resolve placeholders from explicit employer evidence, never a product mention."""
    from urllib.parse import urlsplit
    host = (urlsplit(str(job.url)).hostname or '').lower()
    if not re.fullmatch(r'(?:Employer on job listing|Employer in job alert|Unknown|TBD)', job.employer, re.I):
        return job.employer
    found=header_employer(job,text)
    if found:return found
    explicit = re.search(r'(?im)^\s*(?:Employer|Company|Hiring organisation|Hiring organization)\s*:\s*([^\n|<>]{2,100})\s*$', text)
    first_heading=re.search(r'(?m)^\s*#{1,6}\s+[^\n]+',text)
    next_heading=re.search(r'(?m)^\s*#{1,6}\s+[^\n]+',text[first_heading.end():]) if first_heading else None
    header_end=first_heading.end()+next_heading.start() if next_heading else len(text)
    if explicit and first_heading and first_heading.end() < explicit.start() < header_end and title_matches_source(job.title,text):
        name=explicit[1].strip()
        if valid_company(name) and not re.search(r'\b(?:indeed|remote|hybrid|apply|rating|stars?|unknown|not disclosed|not stated|undisclosed|confidential)\b|\b[0-5](?:\.\d)?\s+out of\s+5\b|\b(?:funding|valuation|revenue)\s+(?:raised|of|is|was)\b',name,re.I):
            return name
    if host in {'simplyhired.com.au','www.simplyhired.com.au'} and urlsplit(str(job.url)).path.startswith('/job/'):
        header=re.split(r'(?im)^\s*(?:#+\s*)?(?:Full Job Description|Job Details|Qualifications|Benefits)\s*$',restore_flat_markdown(text),maxsplit=1)[0]
        company=re.search(r'(?m)^\s*[-*]\s+([^\n|<>]{2,100}?)\s+-\s+[0-5](?:\.\d)?\s*$',header)
        if company:
            name=company[1].strip()
            title_found=any(same_role(job.title,re.sub(r'^#+\s*','',line),name) for line in header.splitlines() if line.startswith('#'))
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
            alias=re.search(r'\s*\(([^()]{2,60})\)\s*$',title)
            alias_match=bool(alias and job.title.casefold().startswith((alias[1]+' - '+title[:alias.start()].strip()+' - ').casefold()))
            if (same_role(job.title,title,name) or alias_match) and re.fullmatch(r'[\w][\w &.,\'’()/-]{1,98}',name) and not is_location and not invalid and context:
                return name
    # The official careers host and its company section independently establish identity.
    host = (urlsplit(str(job.url)).hostname or '').lower()
    if host in {'openai.com', 'www.openai.com'} and urlsplit(str(job.url)).path.startswith('/careers/'):
        if title_matches_source(job.title,text) and re.search(r'(?im)^\s*(?:#+\s*)?About OpenAI\s*$', text):
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
    text = re.split(RECOMMENDATIONS, text)[0]
    freehire = 'Sign in to see your match' in text and 'Profile match' in text
    if freehire:
        text = re.split(r'(?im)^\s*## Skills\s*$', text)[0]
    # Split explicit inline headings at paragraph or sentence boundaries only.
    text = re.sub(r'(?im)(^|(?<=[.!?])\s+)(Job Requirements|Key Requirements|Requirements|Skills Required|Your Profile|What you[\x27’]ll need to succeed|What you need|Essential requirements|About the role|About us|About the company|Company description|Benefits|What we offer|Desirable|Nice to have):\s*', lambda m:m.group(1)+'\n'+m.group(2)+'\n', text)
    lines = [line.strip() for line in text.splitlines()]
    display_title = next((re.sub(r'^#+\s*','',line) for line in lines
                          if line.startswith('#') and len(re.sub(r'^#+\s*','',line))>8
                          and title.casefold().startswith(re.sub(r'^#+\s*','',line).casefold())),title)
    facts = []
    for label, aliases in [('Work format', ['Work format']), ('Work type', ['Work type','Employment type','Job type']), ('Listed level', ['Grade'])]:
        for i, line in enumerate(lines):
            match = re.fullmatch(r'(?:'+ '|'.join(aliases) + r')\s*(?::\s*(.*))?', re.sub(r'^(?:[*•-]\s+)?#+\s*','',line), re.I)
            if not match:
                continue
            value = (match[1] or '').strip() or next((v for v in lines[i+1:] if v), '')
            if value and len(value) <= 80:
                facts.append({'label':label, 'value':value})
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
    board_summary=any(re.fullmatch(r'(?:#+\s*)?Job summary',line,re.I) for line in lines)
    marker = next((i for i,line in enumerate(lines) if line=='Description Company' or re.fullmatch(r'(?:#+\s*)?Full Job Description',line,re.I) or (board_summary and re.fullmatch(r'(?:#+\s*)?Job Description',line,re.I))),None)
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
        if heading_key(stripped) in HEADINGS or (len(stripped)<80 and re.match(r'(?i)^(?:about [A-Za-z]|why [A-Za-z]|our benefits)',stripped)) or (line.startswith('#') and 0<len(stripped)<100):
            flush()
            sections.append({'title':stripped.rstrip(':'),'blocks':[]})
            continue
        if re.fullmatch(r'[-_=]{3,}',line) or line in {'Discussion Report Save','Description Company','Save to board','Sign in','Seek'}:
            continue
        bullet = re.match(r'^(?:[*•-]\s+|\d+[.)]\s+)(.+)',line)
        if bullet and re.match(r'(?i)^bonus points\b',bullet[1]):
            flush()
            sections.append({'title':'Bonus points','blocks':[]})
            continue
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
    if re.search(r'(?im)^\s*(?:#+\s*)?Position Description\s*$',text):
        notices.append({'message':'This is a position description; confirm the current vacancy and closing date.','quote':'Position Description'})
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
        return restore_flat_markdown(re.sub(r'(?m)^L\d+(?:@P[\d-]+)?:\s?','',text))
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
        if posting.get('jobLocationType') == 'TELECOMMUTE':
            fields.append('Work format: Remote')
            eligibility = posting.get('applicantLocationRequirements', [])
            if isinstance(eligibility, dict):
                eligibility = [eligibility]
            names = [place['name'] for place in eligibility if isinstance(place,dict)
                     and isinstance(place.get('name'),str)] if isinstance(eligibility,list) else []
            if names:
                fields.append('Applicants must be based in '+ ' or '.join(names)+'.')
        employment = posting.get('employmentType')
        if isinstance(employment,list) and employment and all(isinstance(value,str) for value in employment):
            fields.append('Work type: '+ ' / '.join(employment))
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
        # A repeated identical unit belongs to one range, e.g. A$93/hr – A$112/hr.
        unit = r'(?:hour|hr|day|week|month|year|annum)'
        line = re.sub(r'(' + symbol + r'\s*' + number + r')(/\s*' + unit + r')'
                      r'(\s*(?:–|—|-|to)\s*(?:' + symbol + r')?\s*' + number + r')\2\b',
                      r'\1\3\2', line, flags=re.I)
        # An explicitly suffixed currency is just another source spelling.
        line=re.sub(r'('+number+r'(?:\s*(?:–|—|-|to)\s*'+number+r')?)\s+(AUD|USD|NZD|GBP|EUR)\b',r'\2 \1',line,flags=re.I)
        matches=list(pattern.finditer(line))
        for index,match in enumerate(matches):
            sentence_start=max((m.end() for m in re.finditer(r'[.!?]\s+',line[:match.start()])),default=0)
            sentence_end=next((match.end()+m.start() for m in re.finditer(r'[.!?]\s+',line[match.end():])),len(line))
            start=max(sentence_start,matches[index-1].end() if index else 0)
            end=min(sentence_end,matches[index+1].start() if index+1<len(matches) else len(line))
            context=line[start:end]
            offset=match.start()-start
            value=match[0].strip();tail=context[offset+len(match[0]):]
            prefix=context[:offset]
            pay_marker=list(re.finditer(r'\b(?:base salary|salary(?: range)?|remuneration|compensation|pay(?: rate| range)?)\s*:',prefix,re.I))
            if pay_marker: prefix=prefix[pay_marker[-1].start():]
            funding=r'\b(?:funding|funded|fundraise|fundraising|raised|raising|series\s+[a-f]\b|valuation|valued|revenue|turnover|investment round)\b'
            if re.search(funding,prefix,re.I) or re.search(r'^(?:\s*[mMbB])?\s*(?:in\s+)?(?:series\s+[a-f]\b|funding|valuation|revenue|raised)',tail,re.I):
                continue
            # Classify each money figure, rather than dropping a salary line that mentions benefits.
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
            before=prefix.strip()
            period_context=tail+' '+before
            pm=re.search(r'(?:per\s+|/\s*|\bp\s*/\s*|\bp\.?)(annum|year|hour|day|week|month|hr|a|h|d)\b|\b(hourly|daily|weekly|monthly|annually|annual)\b',period_context,re.I)
            period=next((g.lower() for g in pm.groups() if g),None) if pm else None
            period={'annum':'year','hr':'hour','h':'hour','d':'day','a':'year','hourly':'hour','daily':'day','weekly':'week','monthly':'month','annually':'year','annual':'year'}.get(period,period)
            before=prefix.strip()
            pay_context=bool(re.search(r'\b(?:base|super|package|salary|remuneration|compensation|pay)\b',prefix+' '+tail,re.I))
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
            if len(matches)>1 or start>0 or end<len(line):
                display=(prefix+value+tail).strip(' ,;')
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
    organisation=posting.get('hiringOrganization',{})
    name=organisation.get('name','') if isinstance(organisation,dict) else ''
    return same_role(title,str(posting.get('title','')),str(name))


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
