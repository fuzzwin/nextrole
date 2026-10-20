"""Readable listing sections, retaining source wording and the original text."""
import re

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
    if not re.fullmatch(r'(?:Employer on job listing|Employer in job alert|Unknown|TBD)', job.employer, re.I):
        return job.employer
    explicit = re.search(r'(?im)^\s*(?:Employer|Hiring organisation|Hiring organization)\s*:\s*([^\n|<>]{2,100})\s*$', text)
    if explicit:
        return explicit[1].strip()
    # The official careers host and its company section independently establish identity.
    host = (urlsplit(str(job.url)).hostname or '').lower()
    if host in {'openai.com', 'www.openai.com'} and urlsplit(str(job.url)).path.startswith('/careers/'):
        if re.search(r'(?im)^\s*(?:#+\s*)?About OpenAI\s*$', text):
            return 'OpenAI'
    return job.employer


def listing_view(text, title='', employer=''):
    original = text
    role_title = re.split(r'\s+[—|]\s+', title)[0]
    text = re.sub(r'(?m)^L\d+: ?', '', text.replace('\r', ''))
    text = re.sub(r'【\d+†([^】]*)】', r'\1', text)
    text = re.sub(r'[^]*|【[^】]*】|\[wordlim\s*:?\s*\d+\]', '', text)
    text = without_site_footer(text)
    # Stop at explicit board recommendations, rather than folding other roles in.
    text = re.split(r'(?im)^\s*(?:#+\s*)?(?:Similar jobs|Find similar jobs|Recommended jobs|People also viewed|More jobs like this|Explore more jobs|See also|What .+ jobs ask for|Tailor my CV Apply|Show more Show less)\b', text)[0]
    freehire = 'Sign in to see your match' in text and 'Profile match' in text
    if freehire:
        text = re.split(r'(?im)^\s*## Skills\s*$', text)[0]
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
    salary = re.search(r'(?im)^\s*Salary\s*:\s*([^\n]+)', text)
    if not salary:
        salary = re.search(r'(?i)\b(?:Salary range|Salary|Remuneration|Pay range)\s*:\s*(\$[^\n|]{3,100})',text)
    if not salary:
        salary = re.search(r'(\$\d[\d,]*(?:\.\d+)?[kK]?\s*(?:–|—|-|to)\s*\$?\d[\d,]*(?:\.\d+)?[kK]?(?:\s+(?:base|per (?:year|annum|hour)|p\.?a\.?|plus superannuation|plus super|\+ super)){0,3})',text)
    if salary:
        facts.insert(0, {'label':'Salary', 'value':salary[1].strip()})
    employer = re.split(r'\s+[—|]\s+.*(?:LinkedIn Jobs|SEEK|freehire)', employer, flags=re.I)[0]
    if employer=='Employer on job listing':
        employer=''
    if title:
        for line in lines:
            if ' · ' in line and line.split(' · ',1)[1].casefold()==role_title.casefold():
                employer=line.split(' · ',1)[0]
                break
    # Known board header ends before the actual employer-written description.
    marker = next((i for i,line in enumerate(lines) if line=='Description Company'),None)
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
    if any(f['label']=='Work format' and f['value'].casefold()=='hybrid' for f in facts):
        office=re.search(r'[^.!?\n]*\bbased full time in (?:our |the )?[^.!?\n]*\boffice\b[^.!?\n]*[.!?]?',text,re.I)
        if office:
            notices.append({'message':'Confirm the work arrangement: the header says Hybrid, while the description mentions full-time office attendance.', 'quote':office[0].strip()})
    overview=next((s for s in sections if s['title']=='Overview'),None)
    preview=next((b['text'] for s in ([overview] if overview else sections) for b in s['blocks'] if b['kind']=='paragraph'), '')
    return {'title':display_title,'facts':facts,'employer':employer,'sections':sections,'highlights':highlights[:3],
            'notices':notices,'preview':preview,'original_chars':len(original)}
