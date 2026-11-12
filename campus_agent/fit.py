"""Explainable evidence coverage for browsing. Never an eligibility decision."""
from __future__ import annotations

import re
from .models import Job

VERSION = 'criterion-evidence-v7'
# Scoring-only changes do not justify retrying blocked external advert reads.
SOURCE_VERSION = 'criterion-evidence-v6'
# These are deliberate product weights, not a probability of being hired.
WEIGHTS = {'skills':30, 'experience':40, 'requirements':30}
TOOLS = {
    'Copilot Studio': r'\bcopilot studio\b', 'Power Automate': r'\bpower automate\b',
    'Power Apps': r'\bpower apps\b', 'Power Platform': r'\bpower platform\b',
    'SharePoint': r'\bsharepoint\b', 'Microsoft 365 Copilot': r'\b(?:microsoft 365|m365) copilot\b',
    'Microsoft 365': r'\b(?:microsoft 365|m365|office 365)\b',
    'Entra ID': r'\b(?:entra(?: id)?|azure ad)\b', 'Intune': r'\bintune\b',
    'Jamf': r'\bjamf\b', 'Kandji': r'\bkandji\b',
    'Google endpoint management': r'\bgoogle endpoint management\b',
    'Exchange': r'\bexchange(?: online)?\b', 'SCCM': r'\bsccm\b',
    'ServiceNow': r'\bservicenow\b', 'NetSuite': r'\bnetsuite\b',
    'Python': r'\bpython\b', 'JavaScript / TypeScript': r'\b(?:javascript|typescript)\b',
    'React': r'\breact\b', 'Node.js': r'\bnode\.?js\b', 'PowerShell': r'\bpowershell\b',
    'REST APIs': r'\brest(?:ful)?(?: apis?)?\b', 'SQL': r'\bsql\b', 'ODBC': r'\bodbc\b',
    'Docker': r'\bdocker\b', '.NET / C#': r'(?<!\w)(?:\.net|c#)(?!\w)',
    'Java': r'\bjava\b', 'Dataverse': r'\bdataverse\b', 'Dynamics 365': r'\bdynamics(?: 365)?\b',
    'Terraform': r'\bterraform\b', 'Kubernetes': r'\bkubernetes\b',
    'Jira': r'\bjira\b', 'Confluence': r'\bconfluence\b', 'SPFx': r'\bspfx\b',
    'ShareGate': r'\bshare\s?gate\b', 'Azure AI': r'\bazure (?:ai|openai)\b',
    'Azure development': r'\bazure development\b|\bcloud.side development\b',
    'Azure': r'\bazure\b', 'OpenAI': r'\bopenai\b', 'Claude': r'\bclaude\b',
    'MCP': r'\bmcp\b', 'Cisco Meraki': r'\b(?:cisco )?meraki\b',
    'Microsoft Purview': r'\b(?:microsoft )?purview\b',
}
# (label, listing demand, source fact). Facts remain verbatim in every explanation.
DOMAINS = [
    ('Workflow automation',r'automat|workflows?|power platform|power automate',r'Power Automate|approval workflow|Python utility'),
    ('Systems and service support',r'\bsystems?\b|\bsupport\b|\bincidents?\b|\bservice desk\b|microsoft 365',r'administer.{0,50}(?:Microsoft 365|Entra)|ServiceNow incidents|IT onboarding'),
    ('AI enablement and adoption',r'\bAI\b|\bLLMs?\b|\badoption\b|\benablement\b|\bagents\b',r'AI Hub|AI.assisted.{0,80}guidance|governed.{0,40}AI'),
    ('Project delivery and handover',r'\bproject|\bprogramme|\bcoordina|\bstakeholder|\bhandover|\bchange control',r'manage.{0,40}projects|project.{0,80}change control|stakeholder.{0,80}handover'),
    ('Process discovery and requirements',r'\brequirements\b|\bdiscovery|\bprocess(?:es)?\b|\bworkshops?\b|business analysis',r'map (?:business )?processes|process mapping|translating requirements'),
    ('Applications and integrations',r'\bapplications?\b|\bERP\b|\bNetSuite\b|\bintegration|\breleases?\b|\bUAT\b',r'NetSuite|ODBC|sandbox UAT'),
    ('Software development',r'\bsoftware|\bdeveloper|\b(?:AI|software) engineer|\bbuild.{0,30}(?:apps?|agents?)|\bprogramming',r'App prototypes|built.{0,35}(?:Python|Flask)|build.{0,40}(?:React|TypeScript)'),
    ('Security operations',r'\bsecurity\b|\bpermissions?\b|\baccess control\b|\bauthentication\b',r'security incident|Entra ID|phishing|authentication'),
    ('User guidance and communication',r'\bguides?\b|\bcommunication|\btraining|\bcoaching|\benablement|\badoption',r'interactive guide|plain.language user guides|induction guides|awareness training|AI Hub demonstration'),
]
REQUIRED = r'your background|what you will bring|required skills and qualifications|to be successful(?: in this role)?|your skills and experience|essential skills and experience|qualifications and experience|key capabilities|selection requirements|what you[’\x27]ll need to succeed|key requirements|skills required|what you need|(?:job )?requirements|essential(?: requirements| criteria)?|must have|(?:minimum|required)?\s*qualifications|(?:key )?selection criteria|key criteria|what (?:we[’\x27]re|we are) looking for|what you[’\x27]ll bring|what you[’\x27]ll need to succeed|skills (?:and|&) experience|about you|technical skills|(?:required )?experience|key skills|your profile|specialist/technical expertise/qualifications|required skills(?: and experience)?|required experience & skills'
OPTIONAL = r'you will ideally have|^why\b|our benefits|highly regarded|is an advantage|bonus points|helpful|not required|desirable|nice to have|preferred|benefits|what we offer|why join|compensation|where this goes|to apply|how to apply|our process'
QUALIFIED = r'\b(?:prototyp\w*|concept|propos\w*|paused|before rollout|ahead of rollout|not (?:yet )?(?:deployed|live)|proof.of.concept|planned|planning|intended|learning|studying|tutorial|training exercise|not implemented|not yet rolled out|personal project|example only|test environment|test deployment|demo environment|non.production)\b'
NON_PRODUCTION = r'\b(?:sandbox|staging environment|UAT)\b'
PRODUCTION = r'\b(?:production|deployed|live|real (?:people|users)|used monthly)\b'


def positive_evidence(text):
    """A saved sentence about missing/unknown experience supplies no delivery evidence."""
    negative = (r"\b(?:no|without|lack\w*|zero)\b.{0,80}\b(?:experience|knowledge|exposure)\b|"
                r"\b(?:never|did not|didn.t|have not|haven.t|has not|hasn.t|not yet|not)\s+(?:been\s+)?(?:used|built|delivered|administer\w*|implement\w*|deploy\w*|work\w*|manage\w*|support\w*|lead|led|verified|confirmed)\b|"
                r"\b(?:unknown|unconfirmed|unverified|not confirmed|not verified|cannot confirm)\b")
    return not re.search(negative,text,re.I)


def evidence_value(text):
    """Full work credit requires an affirmative action, not just a technology noun."""
    if not positive_evidence(text): return 0
    if re.search(QUALIFIED,text,re.I) or re.search(r"\b(?:not|no|never|nothing|without|would|could|might|may|future|pending|expect|hope|hoping|intend|plan|plans|aspire|simulat\w*|classroom|training.lab|lab.exercise|coursework|mock|synthetic|practice)\b|\b\w+n['’]t\b",text,re.I): return 0.5
    action=(r'(?:built|developed|delivered|created|administer(?:ed)?|support(?:ed)?|manage(?:d)?|'
            r'implement(?:ed)?|maintain(?:ed)?|design(?:ed)?|deploy(?:ed)?|automat(?:ed)?|'
            r'configure(?:d)?|map(?:ped)?|recreated|coordinat(?:ed)?|led|lead|wrote|write|'
            r'run|ran|investigate(?:d)?|document(?:ed)?|tested|integrated|provided|resolve(?:d)?|troubleshoot(?:ed)?|handled|owned|'
            r'established|operat(?:ed)?|facilitated|trained|completed|simplified)')
    lead_in=r'^\s*(?:(?:I|We)\s+)?(?:have\s+)?(?:(?:successfully|independently|personally|currently)\s+)?'
    affirmed=re.match(lead_in+action+r'\b',text,re.I)
    if not affirmed:
        # The list above grew from IT résumés. Any occupation's bullet that opens with a past-tense
        # action ("Recorded care…", "Precepted eight graduates…", "Welded frames…") is delivered work too.
        # Describing words and learning-only verbs that look the same are excluded.
        opener=re.match(lead_in+r"([a-z]{3,}ed|taught|sold|drove|held|gave|made|grew|kept|won|oversaw|undertook|bought|cut|laid|sewed|sewn|dug|fed|flew|rode|drew)\b",text,re.I)
        affirmed=opener and opener[1].lower() not in NOT_ACTIONS
    return 1 if affirmed else 0.5


NOT_ACTIONS = set('''advanced experienced registered skilled qualified certified licensed licenced accredited interested motivated
dedicated detailed talented accomplished seasoned trusted organised organized committed focused related based required
needed wanted learned studied observed shadowed attended enrolled educated trained exposed introduced
proposed planned intended expected hoped simulated practised practiced demonstrated'''.split())


# Explicit inflections keep action and object obligations comparable.
ACTION_WORDS = {
    'administered': 'administer', 'administering': 'administer', 'administration': 'administer',
    'supported': 'support', 'supporting': 'support',
    'deployed': 'deploy', 'deploying': 'deploy', 'deployment': 'deploy',
    'configured': 'configure', 'configuring': 'configure', 'configuration': 'configure',
    'managed': 'manage', 'managing': 'manage', 'management': 'manage',
    'coordinated': 'coordinate', 'coordinating': 'coordinate', 'coordination': 'coordinate',
    'documented': 'document', 'documenting': 'document', 'documentation': 'document',
    'mapped': 'map', 'mapping': 'map',
    'tested': 'test', 'testing': 'test',
    'resolved': 'resolve', 'resolving': 'resolve', 'resolution': 'resolve',
    'translated': 'translate', 'translating': 'translate',
    'troubleshoot': 'resolve', 'troubleshooting': 'resolve', 'troubleshooted': 'resolve',
    'issues':'incident', 'issue':'incident', 'incidents':'incident',
    'escalated':'escalate', 'escalating':'escalate', 'escalation':'escalate',
    'communication': 'communicate', 'communicating': 'communicate',
    'independently': 'independent', 'confidently': 'confident',
}


def select_tool_examples(text, facts, skills):
    """Resolve explicit parenthesised OR examples; retain other obligations verbatim."""
    def select(match):
        options = re.split(r',\s*|\s+or\s+', match['options'], flags=re.I)
        names = []
        for option in options:
            name = next((name for name, pattern in TOOLS.items()
                         if re.fullmatch(pattern, option.strip(), re.I)), None)
            if name is None:
                return match[0]
            names.append(name)
        values = {
            name: max([evidence_value(f['text']) for f in facts
                       if re.search(TOOLS[name], f['text'], re.I)] +
                      [0.5 for skill in skills if positive_evidence(skill)
                       and re.search(TOOLS[name], skill, re.I)] + [0])
            for name in names
        }
        selected = max(names, key=values.get)
        if not values[selected]:
            return match[0]
        category = match['category'] or ''
        if re.search(r'\bMDM\b|mobile device management', category, re.I):
            if selected not in {'Intune', 'Jamf', 'Kandji', 'Google endpoint management'}:
                return match[0]
            category = ''
        return category + selected

    return re.sub(
        r'(?P<category>(?:(?:an? )?(?:MDM|mobile device management) platform\s+)?)'
        r'\((?:such as|e\.g\.)\s+(?P<options>[^()\n]+\bor\b[^()\n]+)\)',
        select, text, flags=re.I)


def requirement_words(text):
    # Conservative literal audit of obligations left after known tools/domains.
    stop=set(('a an the in on of to for with as is are be have has must required essential it '
        'experience professional hands strong proven demonstrated ability skills knowledge working '
        'design designing build building create creating develop developing development deliver delivering delivery '
        'implement implementing expert expertise advanced using use core tool role title and plus '
        'or that which who your our their this relevant including related good excellent solid '
        'effective effectively practical modern complex appropriate clear confident strong highly collaborative scalable successfully excellent material materials user users years year months month least at').split())
    words={ACTION_WORDS.get(word, word) for word in re.findall(r'[a-z][a-z0-9]+',text.lower())}-stop
    return {w[:-1] if len(w)>4 and w.endswith('s') else w for w in words}


def unsupported_clauses(criterion, facts):
    """Audit all residual obligations, including comma lists and tool-bearing clauses."""
    facts=[f for f in facts if evidence_value(f['text'])==1]
    text=re.split(r'(?i)proofs? of concept|demonstrations do not count',criterion)[0]
    for pattern in TOOLS.values(): text=re.sub(pattern,' ',text,flags=re.I)
    for _,demand,source in DOMAINS:
        if any(re.search(source,f['text'],re.I) for f in facts):
            # Domain patterns include stems such as 'automat'; remove the whole token.
            for match in reversed(list(re.finditer(demand,text,re.I))):
                a,b=match.span()
                while a>0 and text[a-1].isalnum(): a-=1
                while b<len(text) and text[b].isalnum(): b+=1
                text=text[:a]+' '+text[b:]
    words=requirement_words(text)
    source_words=set().union(*(requirement_words(f['text']) for f in facts)) if facts else set()
    # Credentials and language proficiency require specific review even if a noun appears elsewhere.
    special=re.search(r'\b(?:fluency|fluent|native speaker|language proficiency|cissp|cism|pmp|certification|certified|licen[cs]e)\b',criterion,re.I)
    missing=sorted(words-source_words)
    return ([special[0]] if special else [])+missing


def mentions(text):
    return [name for name,pattern in TOOLS.items() if re.search(pattern,text,re.I)]


def company_section(heading):
    name=heading.casefold().strip()
    return name in {'company description','company overview','our story'} or name.startswith(('who is ','working at ')) or (name.startswith('about ') and name not in {'about the role','about you'})


def recorded_qualification(criterion, profile):
    """Match explicit records only; an unrelated degree or expired status is not proof."""
    records=[x for x in profile.education+profile.skills if positive_evidence(x) and not re.search(r'\bexpired|lapsed|studying|pursuing|planned|pending|previously held\b',x,re.I)]
    names=re.findall(r'\b(?:CISSP|CISM|PMP|ITIL|PL-\d{3}|AZ-\d{3}|MS-\d{3})\b',criterion,re.I)
    if names:
        found=[r for r in records if all(re.search(r'\b'+re.escape(n)+r'\b',r,re.I) for n in names)]
        if re.search(r'\bactive|current|valid\b',criterion,re.I):
            found=[r for r in found if re.search(r'\bactive|current|valid\b',r,re.I)]
        return found[0] if found else None
    if not re.search(r'\bdegree|tertiary|qualifications?\b',criterion,re.I): return None
    fields=re.findall(r'computer science|information (?:technology|systems)|engineering|business|data science|education',criterion,re.I)
    found=[r for r in records if r in profile.education and re.search(r'\bdegree|bachelor|master|diploma|phd\b',r,re.I)
           and (not fields or any(re.search(re.escape(f),r,re.I) for f in fields))]
    return found[0] if found else None


def qualification_only(criterion):
    """A matching degree never proves an extra language, skill or delivery clause."""
    remainder=re.sub(r'\b(?:CISSP|CISM|PMP|ITIL|PL-\d{3}|AZ-\d{3}|MS-\d{3})\b|computer science|information (?:technology|systems)|data science', '', criterion, flags=re.I)
    allowed=set('a an the in or and of with formal tertiary degree bachelor bachelors master masters diploma phd qualification qualifications related relevant discipline field business engineering education active current valid certification certified required essential must have hold holding'.split())
    return not (set(re.findall(r'[a-z]+',remainder.lower()))-allowed)


def recorded_duration(criterion, facts):
    """Never turn overall employment dates into years of a particular technology."""
    demand=re.search(r'\b(\d+)\+?\s*years?\b',criterion,re.I)
    if not demand: return None
    tools=mentions(criterion)
    for fact in facts:
        duration=re.search(r'\b(\d+)\+?\s*years?\b',fact['text'],re.I)
        linked=bool((re.search(r'\bfor\s+\d+\+?\s*years?\s*[.!]?\s*$',fact['text'],re.I)
            and not re.search(r'\bwhile|previously|before|after|working|worked\b',fact['text'],re.I))
            or re.match(r'^\s*\d+\+?\s*years?\s+(?:of\s+)?(?:hands.on\s+)?(?:experience\s+(?:in|with)\s+)?(?:'+ '|'.join(TOOLS[t] for t in tools) +')',fact['text'],re.I)) if tools else False
        # Accept only a direct tenure statement about the requested activity.
        # Extra subjects (company age, client employment, other duties) need review.
        allowed=requirement_words(criterion)|set('built developed supported administered maintained configured operated programmed used provided worked i'.split())
        linked=linked and not (requirement_words(fact['text'])-allowed)
        if (duration and int(duration[1])>=int(demand[1]) and positive_evidence(fact['text'])
            and linked and not re.search(QUALIFIED,fact['text'],re.I) and tools
            and all(re.search(TOOLS[t],fact['text'],re.I) for t in tools)):
            return fact
    return None


def ranked_evidence(criterion, facts):
    """Prefer demonstrated coverage; evidence order must not change credit."""
    words = requirement_words(criterion)
    def rank(fact):
        overlap = len(words & requirement_words(fact['text']))
        complete = evidence_value(fact['text']) == 1 and not unsupported_clauses(criterion,[fact])
        return (complete, overlap, evidence_value(fact['text']))
    return sorted(facts, key=rank, reverse=True)


def criterion_facts(criterion, facts):
    """Keep tool and delivery obligations in the same evidence clause."""
    tools=mentions(criterion)
    result=[]
    for fact in facts:
        # A later disclaimer can qualify an earlier clause. Keep that source intact.
        if not tools or evidence_value(fact['text'])<1:
            if not tools or all(re.search(TOOLS[t],fact['text'],re.I) for t in tools):
                result.append({**fact,'original_text':fact['text']})
            continue
        for clause in re.split(r';\s*|,\s+(?:and|but)\s+|\s+(?:and|but)\s+(?=(?:built|developed|delivered|created|managed|administered|worked|supported|led|implemented)\b)',fact['text'],flags=re.I):
            if clause.strip() and (not tools or all(re.search(TOOLS[t],clause,re.I) for t in tools)):
                result.append({**fact,'text':clause.strip(),'original_text':fact['text']})
    return result


def sentences(view):
    for section in view.get('sections',[]):
        for block in section['blocks']:
            for value in ([block['text']] if block['kind']=='paragraph' else block['items']):
                yield section['title'],value


# Custom search uses explicit equivalences, never similarity scores for obligations.
CUSTOM_SKILLS = {
    'Xero': r'\bxero\b', 'MYOB': r'\bmyob\b', 'Canva': r'\bcanva\b', 'HubSpot': r'\bhubspot\b',
    'Point of sale': r'\b(?:point[ -]of[ -]sale|POS)\b',
    'Espresso machine': r'\bespresso machines?\b',
    'Multimeter': r'\bmultimeters?\b',
}
CREDENTIAL_NAMES = {
    'ahpra-rn': r'\b(?:AHPRA registration as (?:a )?registered nurse|registered nurse registration with AHPRA)\b',
    'forklift-lf': r'\b(?:forklift licen[cs]e (?:class )?LF|LF forklift licen[cs]e)\b',
    'forklift-lo': r'\b(?:forklift licen[cs]e (?:class )?LO|LO forklift licen[cs]e)\b',
    'ahpra': r'\b(?:AHPRA(?: registration)?|registration with AHPRA|registered with AHPRA)\b',
    'vit': r'\b(?:VIT(?: registration)?|registration with VIT|registered with VIT)\b',
    'electrical-a': r"\b(?:a[ -]grade (?:electrical|electrician(?:['’]s)?) licen[cs]e)\b",
    'white-card': r'\bwhite card\b',
    'rsa': r'\b(?:RSA(?: certificate)?|responsible service of alcohol(?: certificate)?)\b',
    'cpa': r'\b(?:CPA(?: designation)?|certified practising accountant)\b',
    'forklift': r'\bforklift licen[cs]e\b',
}
CREDENTIAL_WORD = r'\b(?:licen[cs]e|registration|credential|certification|certificate|certified|registered|permit|endorsement)\b'
STATE_ALIASES = {
    'ACT': 'ACT|Australian Capital Territory', 'NSW': 'NSW|New South Wales',
    'NT': 'NT|Northern Territory', 'QLD': 'QLD|Queensland', 'SA': 'SA|South Australia',
    'TAS': 'TAS|Tasmania', 'VIC': 'VIC|Victoria', 'WA': 'WA|Western Australia',
}
TASK_FORMS = {
    'install': r'install(?:ed|ation|ing|s)?', 'inspect': r'inspect(?:ed|ion|ing|s)?',
    'administer': r'administ(?:er(?:ed|ing|s)?|ration)', 'prepare': r'prepar(?:e[ds]?|ation|ing)',
    'plan': r'plan(?:ned|ning|s)?', 'supervise': r'supervis(?:e[ds]?|ion|ing)',
    'reconcile': r'reconcil(?:e[ds]?|iation|ing)', 'differentiate': r'differentiat(?:e[ds]?|ion|ing)',
    'pick': r'pick(?:ed|ing|s)?', 'document': r'document(?:ed|ation|ing|s)?',
    'operate': r'operat(?:e[ds]?|ion|ing)', 'dispense': r'dispens(?:e[ds]?|ing)',
    'maintain': r'maint(?:ain(?:ed|ing|s)?|enance)', 'teach': r'teach(?:ing|es)?|taught',
    'serve': r'serv(?:e[ds]?|ing)', 'assess': r'assess(?:ed|ment|ing|es)?',
    'monitor': r'monitor(?:ed|ing|s)?', 'clean': r'clean(?:ed|ing|s)?',
    'repair': r'repair(?:ed|ing|s)?', 'test': r'test(?:ed|ing|s)?',
}
TASK_PAST = {
    'installed', 'inspected', 'administered', 'prepared', 'planned', 'supervised',
    'reconciled', 'differentiated', 'picked', 'documented', 'operated', 'dispensed',
    'maintained', 'taught', 'served', 'assessed', 'monitored', 'cleaned', 'repaired', 'tested',
}
TASK_PREFIX = r'^\s*(?:(?:I|We)\s+)?(?:(?:have|personally|independently|regularly)\s+)*'
UNCONFIRMED_WORK = (
    r"\b(?:no|not|never|without|would|could|might|may|will|future|pending|expect\w*|hop\w*|intend\w*|"
    r"plan(?:s|ned|ning)? to|simulat\w*|mock|synthetic|practice|practi[cs]ed|coursework|"
    r"training (?:exercise|scenario|lab|program|course|assessment|cent[re]+|mannequins?)|classroom skills assessment|"
    r"skills assessment|practice lab|starting next|mannequins?|manikins?|role[ -]?play\w*|demonstrat\w*|hypothetical|sandbox)\b|\b\w+n['’]t\b"
)
TASK_CONTEXT = r'\b(?:with|using|under|in|for|at|on|during|alongside|near|beside|by|around|behind|above|below|next to|after|before|to|which|where|that)\b'
ACTION_BREAK = re.compile(
    r'(?<=[.!?])\s+|;\s*|\b(?:but|whereas|while)\s+|'
    r'\band\s+(?=(?:(?:I|we|independently|personally|then|also)\s+)*(?:\w{3,}ed|built|ran|led|taught)\b)',
    re.I,
)



def custom_work_value(text):
    if not positive_evidence(text):
        return 0
    if re.search(UNCONFIRMED_WORK, text, re.I):
        return 0.5
    # Teaching in a classroom can be work. Training, plans and prototypes still
    # pass through the original evidence gate when the action is not explicit.
    if re.match(TASK_PREFIX + r'(?:' + '|'.join(sorted(TASK_PAST)) + r')\b', text, re.I):
        if re.search(r'\b(?:prototyp\w*|propos\w*|concept|learning|studying|tutorial|before rollout)\b', text, re.I):
            return 0.5
        return 1
    return evidence_value(text)


def task_text(text):
    text = re.sub(r'\b(?:vital signs|vital observations)\b', 'vitals', text, flags=re.I)
    text = re.sub(r'\bmedicines?\b', 'medication', text, flags=re.I)
    text = re.sub(CUSTOM_SKILLS['Point of sale'], 'pointofsale', text, flags=re.I)
    for word, variants in TASK_FORMS.items():
        text = re.sub(r'\b(?:' + variants + r')\b', word, text, flags=re.I)
    return text


def task_words(text):
    return requirement_words(task_text(text)) - {'current', 'valid', 'hold', 'holding', 'demonstrated'}


def custom_facts(facts):
    for fact in facts:
        if custom_work_value(fact['text']) < 1:
            yield fact
            continue
        for clause in ACTION_BREAK.split(fact['text']):
            if clause.strip():
                yield {**fact, 'text': clause.strip(), 'original_text': fact['text']}


def task_supported(criterion, fact):
    text = fact['text']
    if custom_work_value(text) != 1:
        return False
    required = task_words(criterion)
    demands = re.findall(r'\b(\d+)\+?\s*(years?|months?)\b', criterion, re.I)
    if re.search(r'\b(?:years?|months?|yrs?|mos?)\b', criterion, re.I):
        stated = re.search(r'\bfor\s+(\d+)\+?\s*(years?|months?)\s*[.!]?$', text, re.I)
        if len(demands) != 1 or not stated:
            return False
        amount, unit = demands[0]
        if stated[2].lower().rstrip('s') != unit.lower().rstrip('s') or int(stated[1]) < int(amount):
            return False
        required -= {'minimum'}
    numeric_scope = re.sub(r'\b\d+\+?\s*(?:years?|months?)\b', '', criterion, flags=re.I)
    if not set(re.findall(r'\d+(?:\.\d+)?', numeric_scope)) <= set(re.findall(r'\d+(?:\.\d+)?', text)):
        return False
    if len(required) < 2 or not required <= task_words(text):
        return False
    actions = required & TASK_FORMS.keys()
    if not actions:
        return True
    action = re.match(TASK_PREFIX + r'([a-z]+)\b', task_text(text), re.I)
    if not action or actions != {action[1].lower()}:
        return False
    required_object = requirement_words(re.split(TASK_CONTEXT, task_text(criterion), maxsplit=1, flags=re.I)[0]) - actions
    recorded_object = requirement_words(re.split(TASK_CONTEXT, task_text(text), maxsplit=1, flags=re.I)[0]) - actions
    return bool(required_object and required_object <= recorded_object)



def credential_evidence(criterion, profile, location):
    """Return named records and the still-unproved part of a compound condition."""
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    matches = []
    remainder = criterion
    for key, pattern in CREDENTIAL_NAMES.items():
        if re.search(pattern, remainder, re.I):
            matches.append(key)
            remainder = re.sub(pattern, ' ', remainder, flags=re.I)
    if not matches and not re.search(CREDENTIAL_WORD, criterion, re.I):
        return None
    today = datetime.now(ZoneInfo('Australia/Melbourne')).date()
    regions = {code for code, aliases in STATE_ALIASES.items()
               if re.search(r'\b(?:' + aliases + r')\b', criterion, re.I)}
    national = bool(re.search(r'\bAustralia\b', criterion, re.I))
    evidence = []
    for key in matches:
        expected = regions or ({'Australia'} if national else set())
        if key.startswith('ahpra'):
            if regions:
                return [], criterion
            expected = {'Australia'}
        if key in {'electrical-a', 'rsa', 'vit'} and not expected:
            expected = set(location.get('states', []))
            if len(expected) != 1:
                return [], criterion
        names = [pattern for name, pattern in CREDENTIAL_NAMES.items() if name == key or name.startswith(key + '-')]
        candidate = next((record for record in profile.credentials
            if record.status == 'current'
            and (not record.expires_on or date.fromisoformat(record.expires_on) >= today)
            and any(re.fullmatch(pattern, record.name, re.I) for pattern in names)
            and (not expected or expected == {record.jurisdiction})), None)
        if candidate is None:
            return [], criterion
        detail = ' · '.join(part for part in (candidate.name, candidate.jurisdiction, 'Recorded current',
                                             'Expires '+candidate.expires_on if candidate.expires_on else '') if part)
        evidence.append({'text': detail, 'role': 'Saved qualification', 'organisation': 'Confirmed profile', 'dates': ''})
    if not evidence:
        return [], criterion
    for region in regions:
        remainder = re.sub(r'\b(?:' + STATE_ALIASES[region] + r')\b', ' ', remainder, flags=re.I)
    if national:
        remainder = re.sub(r'\bAustralia\b', ' ', remainder, flags=re.I)
    return evidence, remainder


ACADEMIC_LEVELS = {
    'bachelor': r"\bbachelor(?:['’]s|s)?\b", 'master': r"\bmaster(?:['’]s|s)?\b",
    'diploma': r'\bdiploma\b', 'doctorate': r'\b(?:doctorate|phd)\b',
}


def recorded_academic_requirement(criterion, profile):
    levels = {name for name, pattern in ACADEMIC_LEVELS.items() if re.search(pattern, criterion, re.I)}
    if len(levels) != 1:
        return None
    level = next(iter(levels))
    pattern = ACADEMIC_LEVELS[level]
    ignore = {'degree', 'tertiary', 'formal', 'qualification', 'qualifications', 'completed', 'awarded'}
    needed = task_words(re.sub(pattern, ' ', criterion, flags=re.I)) - ignore
    for record in profile.education:
        if not re.search(pattern, record, re.I) or not positive_evidence(record):
            continue
        if re.search(r'\b(?:not|never|studying|pursuing|pending|planned|expected|anticipated|incomplete|withdrawn|abandoned|enrolled|working towards|in progress)\b', record, re.I):
            continue
        subject = task_words(re.sub(pattern, ' ', record, flags=re.I)) - ignore
        if needed <= subject:
            return record
    return None


def custom_requirement(criterion, profile, facts, location):
    from .tenure import general_support_duration
    duration=general_support_duration(criterion,facts)
    if duration:
        return 1, [duration], [], True
    credential = credential_evidence(criterion, profile, location)
    if credential is not None:
        evidence, remaining = credential
        if not evidence:
            return 0, [], ['Confirm the named credential, its current status and any stated jurisdiction.'], False
        # A record never establishes additional scope, work, eligibility or tenure.
        if re.search(r'\b(?:years?|months?|experience)\b|\d', remaining, re.I) or task_words(remaining) - {'applicant', 'candidate', 'mandatory', 'required', 'posses'}:
            return 0.5, evidence, ['Credential recorded. Check the additional requirements in this clause.'], False
        return 1, evidence, [], False
    if re.search(r'\b(?:clearance|citizen(?:ship)?|right to work|working rights|visa)\b', criterion, re.I):
        return 0, [], ['Confirm the specific eligibility requirement.'], False
    if re.search(r'\b(?:degree|tertiary|qualification|bachelor|master|diploma|doctorate|phd)\b', criterion, re.I):
        qualification = recorded_academic_requirement(criterion, profile)
        if qualification:
            return 1, [{'text':qualification,'role':'Saved qualification','organisation':'Confirmed profile','dates':''}], [], False
        return 0, [], ['Confirm the specific qualification or eligibility requirement.'], False
    words = task_words(criterion)
    candidates = list(custom_facts(facts))
    supported = next((fact for fact in candidates if task_supported(criterion, fact)), None)
    if supported:
        return 1, [supported], [], True
    partial = next((fact for fact in candidates if len(words & task_words(fact['text'])) >= 2), None)
    if partial:
        return 0.5, [partial], ['Some related work is recorded. Check the specific task, context and scope.'], True
    return 0, [], ['No specific supporting work evidence found.'], True


def criterion_kind(text):
    """Keep job logistics and boilerplate out of competence evidence."""
    value=text.strip(' ·•-:').strip()
    value=re.sub(r"(?i)^what you(?:['’]ll| will) bring(?: will include)?[: ]*",'',value).strip()
    if not value: return 'heading'
    if re.fullmatch(r'(?i)(?:(?:employer |original |advert |listing )?(?:source|source link|url|link)\s*:\s*)?(?:https?://\S+|\[[^\]]+\]\(https?://[^)]+\))[.!]?',value):
        return 'administrative'
    if re.fullmatch(r'(?i)(?:proofs? of concept|demonstrations?|prototypes?)(?:\s+and\s+(?:proofs? of concept|demonstrations?|prototypes?))*\s+do not count[.!]?',value): return 'administrative'
    if re.fullmatch(r"(?i)(?:what you(?:['’]ll| will) bring(?: will include)?|beyond that|requirements|about you|key skills)[: ]*",value): return 'heading'
    if re.search(r'(?i)^(?:to (?:learn|find out) more|visit (?:our|the)|apply (?:now|before|here)|published |posted |click |all applicants are required to complete.{0,40}screening)',value): return 'administrative'
    # Only explicit logistics markers: leading 'Location' alone may be a duty
    # (location scouting/management), and collaboration prose can contain real work.
    if re.search(r'(?i)^(?:the (?:position|role) is based (?:in|at) |location\s*:\s*|location\s*remote\s+in\b|a note on location\s*(?:this is|remote)\b|located in |remote in |this is a remote role|salary\s*:)',value): return 'logistics'
    return 'competency'


def criterion_parts(text):
    # Semicolons mark independent obligations unless an explicit alternative or
    # shared qualifier joins them. AND/OR noun lists and credentials stay intact.
    if re.search(r';\s*(?:or|and/or)\b', text, re.I):
        return [text.strip()] if criterion_kind(text)=='competency' else []
    parts=re.split(r';\s*',text)
    if any(re.match(r'(?i)^(?:(?:must|should|needs? to) be\b|(?:in|for|with|using|under|within|during|including|only|all|each|both|not|excluding)\b)',p) for p in parts[1:]):
        parts=[text]
    independent = r'(?i)^(?:(?:must|at least|minimum|demonstrated|strong|proven|experience|ability|working knowledge|knowledge|understanding|professional fluency|hands.on|an? active|current|degree|diploma|qualifications?|communication|competing priorities)\b|(?:remote|technical|customer|IT|systems?) support\b|(?:independently )?(?:resolve|communicate|share|troubleshoot|manage|administer|coordinate|deliver|build|develop|maintain|design|implement|test|document)\w*\b|(?:Python|SQL|Java|Microsoft 365|Power Automate)\b)'
    if any(criterion_kind(p)=='competency' and not re.match(independent,p.strip()) for p in parts[1:]):
        parts=[text]
    if len(parts)>1 and any(re.search(r'\b(?:all|each|both)\s+(?:of (?:these|the above)|in|with|using|for)\b', p, re.I) for p in parts):
        parts=[text]
    result=[]
    for part in parts:
        # Split repeated requirement introductions, not "Python and SQL".
        result.extend(re.split(r'\s+and\s+(?=(?:must have|must demonstrate|demonstrated ability|proven experience|experience (?:in|with)|ability to|working knowledge of)\b)',part,flags=re.I))
    return [p.strip() for p in result if criterion_kind(p)=='competency']


def fit_assessment(job, profile, preferences, view, location, *, full=False, closed=False):
    result={'version':VERSION,'percent':None,'status':'Needs profile','strengths':[],
            'reviews':[],'requirements':[],'breakdown':[],'cap':None,
            'assessment_state':'needs_profile','assessment_notice':'Save your confirmed profile to assess this role.','auto_eligible':False,'coverage':{'criteria_count':0,'work_examples':0},
            'method':'Criterion-linked evidence: skills 30%, specific work examples 40%, stated requirements 30%. Unconfirmed requirements earn no full credit; review gates are separate. Not a hiring probability.'}
    from .source_policy import source_exclusion
    exclusion=source_exclusion(str(job.url))
    if exclusion:
        result.update(status='Excluded source',assessment_state='excluded',source_state='excluded_source',
                      assessment_notice=exclusion['reason'],source_policy=exclusion,
                      reviews=[{'label':exclusion['reason'],'requirement':''}])
        return result
    if not profile or profile.is_example:
        result['reviews']=[{'label':'Save your confirmed résumé profile to assess this role.','requirement':''}]
        return result
    from .listing_view import source_problem, requirement_heading
    problem=source_problem(job.description,job.title)
    if problem and problem[0]=='closed': closed=True
    if problem and problem[0]!='closed':
        result.update(assessment_state='incomplete',source_state=problem[0],assessment_notice=problem[1],status='Needs review',reviews=[{'label':problem[1],'requirement':''}])
        result['breakdown']=[{'id':key,'label':label,'weight':WEIGHTS[key],'points':None,'covered':None,'total':0,'state':'pending'} for key,label in [('skills','Relevant skills'),('experience','Work experience'),('requirements','Stated requirements')]]
        return result
    from .role_types import search_role_matches
    custom = preferences.role_search_mode == 'custom'
    if custom:
        result['version'] = 'criterion-evidence-custom-v3'
    work_value = custom_work_value if custom else evidence_value
    skill_patterns = CUSTOM_SKILLS if custom else TOOLS
    rows=list(sentences(view))
    primary=view.get('title',job.title)+'\n'+'\n'.join(text for _,text in rows)
    clean_job=Job.model_validate({**job.model_dump(mode='json'),'title':view.get('title',job.title),'description':primary[:100000]})
    facts=[{'text':b,'role':e.role,'organisation':e.organization,'dates':e.dates}
           for e in profile.experience for b in e.bullets if work_value(b)>0]
    # Referees' titles and example cover letters cannot become candidate experience.
    profile_text='\n'.join([s for s in profile.skills if positive_evidence(s)]+[f['text'] for f in facts])
    scoring_text=view.get('title',job.title)+'\n'+'\n'.join(text for heading,block in rows for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',block) for text in criterion_parts(sentence)
        if not re.search(OPTIONAL,heading,re.I) and not company_section(heading) and criterion_kind(text)=='competency')
    if not custom:
        scoring_text = select_tool_examples(scoring_text, facts, profile.skills)
    tools = [name for name, pattern in skill_patterns.items() if re.search(pattern, scoring_text, re.I)]
    supported_tools = [name for name in tools if re.search(skill_patterns[name], profile_text, re.I)]
    tool_values = {
        name: (1 if any(work_value(fact['text']) == 1 and re.search(skill_patterns[name], fact['text'], re.I) for fact in facts) else 0.5)
        for name in supported_tools
    }
    missing_tools = [name for name in tools if name not in supported_tools]
    strengths = []
    for tool in supported_tools:
        work = [fact for fact in facts if re.search(skill_patterns[tool], fact['text'], re.I)]
        fact = next((f for f in work if work_value(f['text']) == 1), work[0] if work else None)
        skill = next((item for item in profile.skills if positive_evidence(item) and re.search(skill_patterns[tool], item, re.I)), None)
        strengths.append({'label':tool,'kind':'Skill','evidence':fact['text'] if fact else skill or 'Saved profile summary',
                          'source':fact or None})
    experience=[]
    for label,demand,source in DOMAINS:
        listing=re.search(demand,scoring_text,re.I)
        if not listing:
            continue
        eligible=[f for f in facts if re.search(source,f['text'],re.I)]
        fact=next((f for f in eligible if evidence_value(f['text'])==1),eligible[0] if eligible else None)
        partial=bool(fact and evidence_value(fact['text'])<1)
        experience.append({'label':label,'value':0.5 if partial else 1 if fact else 0,
                           'evidence':fact,'listing_term':listing[0]})
        if fact:
            strengths.append({'label':label+(' (partial work evidence)' if partial else ''),
                              'kind':'Experience','evidence':fact['text'],'source':fact})

    criteria=[]
    importance={}
    criterion_sources={}
    separate_checks=[]
    for heading,block_text in rows:
      for text in re.split(r'(?<=[.!?])\s+(?=[A-Z])', block_text):
        optional=bool(re.search(OPTIONAL,heading,re.I)) or company_section(heading) or heading.casefold() in {'benefits','what we offer'} or bool(re.search(r'\b(?:nice to have|helpful.{0,12}not required|desirable|preferred but not required)\b',text,re.I))
        explicit=re.search(r'\b(?:must|required|at least|mandatory|seeking a certified)\b|^(?:Requires|You need|Demonstrated|Strong|Proven|Experience|Commercial experience|Hands.on experience|Working knowledge|Ability to)\b',text,re.I)
        if not optional and (re.fullmatch(REQUIRED,heading,re.I) or requirement_heading(heading) or explicit):
            if len(text.strip())>15 and not re.fullmatch(r'Beyond that:?',text,re.I):
                kind=criterion_kind(text)
                if kind=='competency':
                    for part in criterion_parts(text):
                        criteria.append(part)
                        importance[part]=max(importance.get(part,1),2 if re.search(r'\b(?:essential|mandatory|must have|must demonstrate|required)\b',heading+' '+text,re.I) else 1)
                        criterion_sources.setdefault(part,[]).append(text)
                elif kind=='logistics': separate_checks.append({'text':text,'status':'Check separately','kind':'location_or_schedule'})
    criteria=list(dict.fromkeys(criteria))
    explicit_criteria=len(criteria)
    result['separate_checks']=separate_checks
    # The job title can establish a core technical requirement even in a short lead.
    title_tools=[] if custom else mentions(view.get('title',job.title))
    for tool in title_tools:
        if not any(re.search(TOOLS[tool],c,re.I) for c in criteria):
            criteria.append('Core tool in role title: '+tool)

    reviews=[]
    hard=False
    for criterion in criteria:
        if custom:
            value, evidence, reasons, work = custom_requirement(criterion, profile, facts, location)
            status = 'Supported' if value == 1 else 'Transferable' if value else 'Needs confirmation'
            result['requirements'].append({'text':criterion, 'status':status, 'value':value,
                                           'evidence':evidence, 'reasons':reasons, 'work':work})
            if value < 1:
                reviews.append({'label':reasons[0], 'requirement':criterion})
            continue
        original_criterion = criterion
        criterion = select_tool_examples(criterion, facts, profile.skills)
        linked_facts=ranked_evidence(criterion,criterion_facts(criterion,facts))
        required_tools=mentions(criterion)
        found=[t for t in required_tools if t in supported_tools]
        missing=[t for t in required_tools if t not in supported_tools]
        reasons=[]
        evidence=[]
        value=0
        special=False
        qualification=recorded_qualification(criterion,profile)
        from .tenure import general_support_duration
        duration=recorded_duration(criterion,linked_facts) or general_support_duration(criterion,linked_facts)
        if re.search(r'\bworkshops?\b',criterion,re.I) and not any(re.search(r'\bworkshops?\b',f['text'],re.I) for f in facts):
            reasons.append('Workshop facilitation is not explicitly confirmed; process mapping, guides and demonstrations are transferable evidence.')
            special=True
        if re.search(r'\bcommercial.{0,45}software engineer',criterion,re.I) and not any(
            re.search(r'\bsoftware engineer',e.role,re.I) and e.dates for e in profile.experience):
            reasons.append('Commercial software-engineering employment is not confirmed; IT support and app prototypes do not establish this requirement.')
            special=True
        if re.search(r'\b(?:nv1|nv2|baseline clearance|security clearance|australian citizen(?:ship)?|right to work|working rights|formal tertiary|degree|diploma|qualifications? in|certified|(?:degree|tertiary|qualification|certification|licen[cs]e).{0,55}(?:required|essential)|(?:must|require).{0,55}(?:degree|certification|licen[cs]e))\b',criterion,re.I):
            # Credentials/eligibility need explicit, contextual confirmation, never keyword credit.
            if not qualification:
                reasons.append('Eligibility or credential requirement needs confirmation against your records.')
                special=True
        if re.search(r'\b(?:at least|minimum of)\s+(?:[2-9]\d*|two|three|four|five|six|ten)\s+(?:enterprise|production|commercial)',criterion,re.I):
            reasons.append('The required number and scale of delivered solutions need confirmation from specific source facts.')
            special=True
        if re.search(r'\b(?:\d+\+?|one|two|three|four|five|six|seven|eight|ten|twelve|eighteen|twenty)\s*(?:to\s*\d+\s*)?(?:years?|months?)\b',criterion,re.I):
            if not duration:
                reasons.append('Required duration of relevant experience needs confirmation; total IT tenure does not establish specialist tenure.')
                special=True
        production=bool(re.search(PRODUCTION,criterion,re.I) and not re.search(r'\bor production\b',criterion,re.I)
                        and (required_tools or re.search(r'\bagents?\b|software',criterion,re.I)))
        if production:
            candidates=[f for f in linked_facts if re.search(PRODUCTION,f['text'],re.I) and evidence_value(f['text'])==1
                        and not re.search(NON_PRODUCTION,f.get('original_text',f['text']),re.I)
                        and (all(re.search(TOOLS[t],f['text'],re.I) for t in required_tools)
                             if required_tools else re.search(r'\bagents?\b|software',f['text'],re.I))]
            if candidates:
                evidence=candidates[:2]
                value=1
            else:
                reasons.append('Production delivery of this technology is not confirmed; prototypes, demonstrations and unrelated live workflows do not satisfy it.')
                special=True
        if missing:
            reasons.append('Not confirmed in your profile: '+', '.join(missing)+'.')
            special=True
        # Do not stitch an action from one example to an unrelated object in another.
        extra=min((unsupported_clauses(criterion,[f]) for f in linked_facts),key=len,default=unsupported_clauses(criterion,[]))
        if qualification and qualification_only(criterion) and not required_tools and not duration:
            extra=[]
            value=1
            evidence=[{'text':qualification,'role':'Saved qualification','organisation':'Confirmed profile','dates':''}]
        if duration and not qualification:
            extra=[] if duration.get('tenure') else [w for w in extra if w not in {'10','5','4','3','2','year'}]
            if not extra:
                value=1
                evidence=[duration]
        if extra:
            reasons.append('Some details of this requirement are not confirmed in your saved evidence.')
        if not special and not evidence:
            if required_tools and len(found)==len(required_tools):
                value=1
                for tool in found:
                    pattern=TOOLS[tool] if tool!='Power Platform' else r'\bpower (?:platform|automate|apps)\b'
                    work=[f for f in linked_facts if re.search(pattern,f['text'],re.I)]
                    solid=[f for f in work if evidence_value(f['text'])==1]
                    if solid:
                        evidence.append(solid[0])
                    elif work:
                        evidence.append(work[0])
                        if re.search(r'\bexperience|develop|build|deliver|implement|advanced|expert',criterion,re.I):
                            value=min(value,0.5)
                    else:
                        skill=next((s for s in profile.skills if re.search(pattern,s,re.I)),None)
                        if skill:
                            evidence.append({'text':skill,'role':'Saved skill','organisation':'Confirmed profile','dates':''})
                        if re.search(r'\bexperience|develop|build|deliver|implement|advanced|expert',criterion,re.I):
                            value=min(value,0.5)
                evidence=evidence[:3]
                if value<1:
                    reasons.append('Skills or qualified prototype/concept evidence is present; the required hands-on delivery experience needs confirmation.')
            elif not required_tools:
                matches=[e for e in experience if re.search(next(d for label,d,_ in DOMAINS if label==e['label']),criterion,re.I)]
                direct=[f for f in linked_facts if len(requirement_words(criterion)&requirement_words(f['text']))>=1]
                if direct:
                    criterion_words = requirement_words(criterion)
                    direct=ranked_evidence(criterion,direct)
                    evidence=direct[:2]
                    overlap=max(len(criterion_words & requirement_words(f['text'])) for f in direct)
                    value=(0.25 if overlap==1 else 0.5) if extra else max(evidence_value(f['text']) for f in evidence)
                    if value==0.25: reasons.append('Weak lexical overlap only; this does not establish the specific task or context.')
                if value<1:
                    reasons.append('Transferable evidence only; confirm the specific requirement.' if value else 'No specific supporting evidence found in your saved experience.')
        if extra and value>0:
            value=min(value,0.5)
        if special:
            hard=True
            value=0
        status='Supported' if value==1 else 'Transferable' if value else 'Needs confirmation'
        result['requirements'].append({'text':original_criterion,'status':status,'value':value,'evidence':evidence,'reasons':reasons})
        if value<1:
            reviews.append({'label':reasons[0] if reasons else 'Requirement needs review.','requirement':original_criterion})

    for requirement in result['requirements']:
        requirement['source_texts']=list(dict.fromkeys(criterion_sources.get(requirement['text'],[requirement['text']])))
        requirement['evidence_state']='supported' if requirement['value']==1 else 'partial' if requirement['value'] else 'not_documented'
        requirement['importance_weight']=importance.get(requirement['text'],1)
        requirement['importance']='Essential' if requirement['importance_weight']==2 else 'Standard'
        if re.search(r'(?i)clearance|citizen|right to work|working rights|licen[cs]e|registration|degree|qualification|certification',requirement['text']):
            separate_checks.append({'text':requirement['text'],'status':requirement['status'],'kind':'eligibility'})
    skills_ratio=sum(tool_values.values())/len(tools) if tools else 0
    if custom:
        work_criteria = [r for r in result['requirements'] if r['work']]
    else:
        work_criteria = [r for r in result['requirements'] if not re.search(r'(?i)degree|tertiary|qualification|certification|clearance|citizen|working rights|right to work', r['text'])]
    work_values=[r['value']*max((work_value(e['text']) for e in r['evidence'] if e.get('role') not in {'Saved skill','Saved qualification'}),default=0) for r in work_criteria]
    experience_ratio=sum(v*r['importance_weight'] for v,r in zip(work_values,work_criteria))/sum(r['importance_weight'] for r in work_criteria) if work_values else 0
    requirements_ratio=sum(r['value']*r['importance_weight'] for r in result['requirements'])/sum(r['importance_weight'] for r in result['requirements']) if result['requirements'] else 0
    result['breakdown']=[
        {'id':'skills','label':'Relevant skills','weight':30,'points':round(30*skills_ratio),'covered':sum(tool_values.values()),'total':len(tools)},
        {'id':'experience','label':'Work experience','weight':40,'points':round(40*experience_ratio),'covered':sum(work_values),'total':len(work_values)},
        {'id':'requirements','label':'Stated requirements','weight':30,'points':round(30*requirements_ratio),'covered':sum(r['value'] for r in result['requirements']),'total':len(result['requirements'])},
    ]
    if not tools:
        result['method'] = 'Work examples 57%, stated requirements 43%. The advert has no separately scored tools. Each requirement links to recorded evidence.'
        for component, weight, ratio in zip(result['breakdown'], (0,57,43), (0,experience_ratio,requirements_ratio)):
            component.update(weight=weight, points=round(weight * ratio))
    strengths=[s for s in strengths if s['kind']!='Experience']
    seen_work=set()
    for criterion in result['requirements']:
        for fact in criterion['evidence']:
            if criterion['value']>0 and fact.get('role') not in {'Saved skill','Saved qualification'} and fact['text'] not in seen_work:
                seen_work.add(fact['text'])
                strengths.append({'label':'Work evidence: '+criterion['text'][:85],'kind':'Experience','evidence':fact['text'],'source':fact})
    result['strengths']=sorted(strengths,key=lambda s:s['kind']!='Experience')
    result['matched_skills']=supported_tools
    result['unconfirmed_skills']=missing_tools
    result['experience']=[{'label':r['text'],'value':v,'evidence':next((e for e in r['evidence'] if e.get('role') not in {'Saved skill','Saved qualification'}),None)} for r,v in zip(work_criteria,work_values)]
    score=sum(b['points'] for b in result['breakdown'])
    result['confidence']={'level':'limited' if explicit_criteria<3 else 'needs_review' if any(r['value']<1 for r in result['requirements']) else 'supported', 'criteria_count':explicit_criteria, 'meaning':'Evidence completeness, not hiring probability. Unknown requirements are not demonstrated inability.'}
    result['method'] += ' Explicit essential criteria count twice standard criteria; weak lexical overlap receives quarter credit. Component points use importance weights, while covered/total show unweighted evidence counts.'
    caps=[]
    work_examples={f['text'] for requirement in result['requirements'] for f in requirement['evidence'] if f.get('role') not in {'Saved skill','Saved qualification'}}
    result['coverage']={'criteria_count':explicit_criteria,'work_examples':len(work_examples),
                        'supported':sum(r['value']==1 for r in result['requirements']),
                        'partial':sum(0<r['value']<1 for r in result['requirements']),
                        'unconfirmed':sum(r['value']==0 for r in result['requirements'])}
    if explicit_criteria<3 or len(work_examples)<2:
        reviews.append({'label':'Limited evidence: at least three distinct requirements and two work examples are needed for an automatic strong match.','requirement':''})
        caps.append((79,'Listing or evidence is too sparse for a strong-match judgement.'))
    if not full:
        reviews.insert(0,{'label':'Read the full listing before assessing this role.','requirement':''})
    if not explicit_criteria:
        reviews.append({'label':'No explicit requirements could be assessed from the saved listing.','requirement':''})
    if not location.get('stated'):
        reviews.append({'label':'Listing location needs confirmation.','requirement':''})
    from .listing_view import employer_known
    if not employer_known(view.get('employer') or job.employer):
        reviews.append({'label':'Employer identity needs verification.','requirement':''})
    for notice in view.get('notices',[]):
        reviews.append({'label':notice['message'],'requirement':notice['quote']})
    if re.search(r'\b(?:senior|lead|manager|architect|principal|director|head|graduate|internship|apprentice)\b',view.get('title',job.title),re.I):
        reviews.append({'label':'Seniority and scope need review against your confirmed responsibilities.','requirement':''})
    closed=closed or bool(re.search(r'\b(?:no longer (?:available|accepting applications)|position (?:has been )?(?:filled|closed)|job (?:has )?(?:expired|closed)|applications (?:have )?closed)\b',primary,re.I))
    if closed:
        reviews.insert(0,{'label':'The saved closing date has passed. Verify reopening before applying.','requirement':''})
        caps.append((0,'Listing is closed.'))
    if caps:
        limit,reason=min(caps,key=lambda x:x[0])
        result['cap']={'limit':limit,'reason':reason}
        score=min(score,limit)
    if score<70 and not reviews:
        reviews.append({'label':'The available evidence does not yet establish a strong fit across skills, experience and requirements.','requirement':''})
    result['auto_eligible']=bool(preferences.role_search_mode=='presets' and search_role_matches(clean_job,preferences)
        and full and not closed and not reviews and explicit_criteria>=3 and len(work_examples)>=2 and score>=70)
    result.update(percent=score,status='Closed' if closed else 'Good match' if score>=70 and not reviews else 'Needs review',reviews=reviews)
    notice=('Read the full listing before assessing this role.' if not full else
            'The saved listing has no assessable requirements. Paste the complete employer advert.' if not explicit_criteria else
            'Confirm the employer before assessing this role.' if not employer_known(view.get('employer') or job.employer) else '')
    incomplete=bool(not closed and (notice or any('different role' in n['message'] for n in view.get('notices',[]))))
    result['assessment_state']='closed' if closed else 'incomplete' if incomplete else 'assessed'
    result['assessment_notice']=notice if incomplete else ''
    result['source_state']='closed' if closed else 'unread' if not full else 'missing_requirements' if not explicit_criteria else 'employer_missing' if incomplete else 'ready'
    if incomplete:
        result.update(percent=None,cap=None,auto_eligible=False)
    for component in result['breakdown']:
        component['state']='pending' if incomplete else 'not_stated' if not component['total'] else 'assessed'
        if component['state']!='assessed': component.update(points=None,covered=None)
    return result
