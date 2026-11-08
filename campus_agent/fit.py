"""Explainable evidence coverage for browsing. Never an eligibility decision."""
from __future__ import annotations

import re
from .language import close_stems, is_action_start, word_stem
from .models import Job

VERSION = 'criterion-evidence-v6'
# These are deliberate product weights, not a probability of being hired.
WEIGHTS = {'skills':30, 'experience':40, 'requirements':30}
TOOLS = {
    'Copilot Studio': r'\bcopilot studio\b', 'Power Automate': r'\bpower automate\b',
    'Power Apps': r'\bpower apps\b', 'Power Platform': r'\bpower platform\b',
    'SharePoint': r'\bsharepoint\b', 'Microsoft 365 Copilot': r'\b(?:microsoft 365|m365) copilot\b',
    'Microsoft 365': r'\b(?:microsoft 365|m365|office 365)\b',
    'Entra ID': r'\b(?:entra(?: id)?|azure ad)\b', 'Intune': r'\bintune\b',
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
# Advert logistics often sit inside a requirements section; they are never candidate criteria.
LOGISTICS = (r'^\s*(?:applications?\s+(?:close|closing|are\s+due|due|open\s+until)\b|(?:closing|close)\s+date\b|'
             r'(?:salary|remuneration|pay|package|compensation|rate)(?:\s+(?:range|band|package|rate))?\s*(?::|[-–]\s)|'
             r'(?:start\s+date|job\s+ref(?:erence)?|reference\s+(?:no|number))\b|'
             r'(?:to apply|how to apply|apply\s+(?:now|online|today|via|through|by|with))\b)')
QUALIFIED = (r'\b(?:prototyp\w*|concept|propos\w*|paused|before rollout|ahead of rollout|not (?:yet )?(?:deployed|live)|proof.of.concept|'
             r'(?:planned|planning)(?!\s+(?:and|lessons?|units?|events?|rosters?|menus?|shifts?|care|curricul\w+|activit\w+|sessions?|routes?|schedules?|budgets?)\b)|'
             r'intended|learning(?!\s+(?:tasks?|needs?|goals?|outcomes?|activit\w+|plans?|programs?|programmes?|environments?|support|difficulties|styles?|materials?|resources?|experiences?|objectives?|sequences?|intentions?|spaces?|areas?|centres?|abilities)\b)|'
             r'studying|tutorial|training exercise|not implemented|not yet rolled out)\b')
PRODUCTION = r'\b(?:production|deployed|live|real (?:people|users)|used monthly)\b'


# Listing-side mentions stay literal; on the candidate side a product family is
# evidenced by its members (Power Automate/Power Apps work is Power Platform work).
EVIDENCE_ALIASES = {'Power Platform': r'\bpower (?:platform|automate|apps)\b'}


def evidence_pattern(tool):
    return EVIDENCE_ALIASES.get(tool, TOOLS[tool])


def positive_evidence(text):
    """A saved sentence about missing/unknown experience supplies no delivery evidence."""
    negative = (r"\b(?:no|without|lack\w*|zero)\b.{0,80}\b(?:experience|knowledge|exposure)\b|"
                r"\b(?:never|did not|didn.t|have not|haven.t|has not|hasn.t|not yet|not)\s+(?:been\s+)?(?:used|built|delivered|administer\w*|implement\w*|deploy\w*|work\w*|manage\w*|support\w*|lead|led|verified|confirmed)\b|"
                r"\b(?:unknown|unconfirmed|unverified|not confirmed|not verified|cannot confirm)\b")
    return not re.search(negative,text,re.I)


def evidence_value(text):
    """Full work credit requires an affirmative action, not just a technology noun."""
    if not positive_evidence(text): return 0
    if re.search(QUALIFIED,text,re.I) or re.search(r"\b(?:not|no|never|nothing|without|would|could|might|may|future|pending|expect|hope|hoping|intend|aspire|simulat\w*|training.lab|lab.exercise|coursework|mock|synthetic|practice)\b|\bclassroom\s+(?:exercises?|projects?|assignments?|courses?|simulations?|training)\b|\b(?:i|we|they|to|will)\s+plans?\b|\bplans?\s+to\b|\b\w+n['’]t\b",text,re.I): return 0.5
    affirmed=is_action_start(text)
    return 1 if affirmed else 0.5


STOP_WORDS=set(('a an the in on of to for with as is are be have has must required essential '
    'experience professional hands strong proven demonstrated ability skills knowledge working '
    'design designing build building create creating develop developing development deliver delivering delivery '
    'implement implementing expert expertise advanced using use core tool role title and plus '
    'or that which who your our their this relevant including related good excellent solid '
    'effective effectively practical modern complex appropriate clear confident strong highly collaborative scalable successfully excellent material materials user users years year months month least at '
    'understanding proficiency proficient competent demonstrable sound genuine basic general current valid prior previous minimum other various range variety '
    'end day daily additional needs need ensure ensuring able capable well within across between towards').split())
STOP_STEMS={word_stem(w) for w in STOP_WORDS}


def requirement_words(text):
    # Conservative literal audit of obligations left after known tools/domains.
    words=set(re.findall(r'[a-z][a-z0-9]+',text.lower()))-STOP_WORDS
    return {word_stem(w) for w in words}-STOP_STEMS


def unsupported_clauses(criterion, facts, confirmed=()):
    """Audit all residual obligations, including comma lists and tool-bearing clauses.

    `confirmed` carries words from the candidate's own saved skills, headline and role
    titles, so a requirement naming their trade is not flagged for lacking it in a bullet.
    """
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
    if facts:
        source_words|=requirement_words(' '.join(confirmed))
    # Credentials and language proficiency require specific review even if a noun appears elsewhere.
    special=re.search(r'\b(?:fluency|fluent|native speaker|language proficiency|cissp|cism|pmp|certification|certified|licen[cs]e)\b',criterion,re.I)
    missing=sorted(w for w in words if not any(close_stems(w,s) for s in source_words))
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


CREDENTIAL = (r'\b(?:registration|registered|licen[cs]e[ds]?|certificate|certification|certified|accredit\w*|white card|blue card|'
              r'working with children|police check|first aid|ticket|membership|member of|clearance)\b')
EXPERIENCE_LIKE = r'\b(?:experience|knowledge|understanding|skills?|ability|proven|demonstrated|years?)\b'
GENERIC_CREDENTIAL_WORDS = set(('current valid active holds hold holding required essential must have has a an the in of or and with to as be for '
    'your relevant appropriate full open minimum registration registered licence licences license licensed licenced certificate certification '
    'certified accreditation accredited membership member qualification qualifications ticket clearance evidence proof').split())


def is_credential(criterion):
    """A requirement that is a licence, registration, certificate or membership held on record,
    rather than experience that can be shown by a work example."""
    if re.search(EXPERIENCE_LIKE,criterion,re.I): return False
    if re.search(CREDENTIAL,criterion,re.I): return True
    return bool(re.search(r'\bqualifications?\b',criterion,re.I) and re.search(r'\b[A-Z]{2,6}\b',criterion))


def credential_tokens(text):
    tokens={word_stem(w) for w in re.findall(r'[A-Za-z][A-Za-z0-9]+',text) if w.lower() not in GENERIC_CREDENTIAL_WORDS}
    # "A Grade" and "B Grade", "Class C" and "Class R" are different licences: keep the letter or number.
    for letter in re.findall(r'\b([A-Za-z0-9])\s+(?:grade|class|level)\b',text,re.I)+re.findall(r'\b(?:grade|class|level)\s+([A-Za-z0-9])\b',text,re.I):
        tokens.add('grade-'+letter.lower())
    return tokens


def recorded_credential(criterion, profile):
    """A credential is supported only by an explicit saved record naming it (licence, registration,
    card, membership); an unrelated degree, an expired or pending record, or a nearby word is not proof."""
    records=[x for x in list(profile.education)+list(profile.skills)+list(getattr(profile,'licences',[]))
             if positive_evidence(x) and not re.search(r'\bexpired|lapsed|studying|pursuing|planned|pending|previously held|working towards|in progress\b',x,re.I)]
    for alternative in re.split(r'\s+or\s+|\s*/\s*',criterion):
        needed=credential_tokens(alternative)
        if not needed: continue
        for record in records:
            have=credential_tokens(record)
            if all(any(close_stems(n,h) for h in have) for n in needed):
                return record
    return None


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
            or re.match(r'^\s*\d+\+?\s*years?\s+(?:of\s+)?(?:hands.on\s+)?(?:experience\s+(?:in|with)\s+)?(?:'+ '|'.join(evidence_pattern(t) for t in tools) +')',fact['text'],re.I)) if tools else False
        # Accept only a direct tenure statement about the requested activity.
        # Extra subjects (company age, client employment, other duties) need review.
        allowed=requirement_words(criterion)|requirement_words('built developed supported administered maintained configured operated programmed used provided worked i')
        linked=linked and not (requirement_words(fact['text'])-allowed)
        if (duration and int(duration[1])>=int(demand[1]) and positive_evidence(fact['text'])
            and linked and not re.search(QUALIFIED,fact['text'],re.I) and tools
            and all(re.search(evidence_pattern(t),fact['text'],re.I) for t in tools)):
            return fact
    return None


def criterion_facts(criterion, facts):
    """Keep tool and delivery obligations in the same evidence clause."""
    tools=mentions(criterion)
    result=[]
    for fact in facts:
        parts=re.split(r';\s*|,\s+(?:and|but)\s+|\s+(?:and|but)\s+(?=(?:built|developed|delivered|created|managed|administered|worked|supported|led|implemented)\b)',fact['text'],flags=re.I)
        clauses=[]
        for index,part in enumerate(parts):
            # "Planned and delivered lessons": a lone leading verb belongs with what follows it.
            if index<len(parts)-1 and part.strip() and len(part.split())<3:
                parts[index+1]=part.strip()+' and '+parts[index+1]
                continue
            clauses.append(part)
        for clause in clauses:
            if clause.strip() and (not tools or all(re.search(evidence_pattern(t),clause,re.I) for t in tools)):
                result.append({**fact,'text':clause.strip(),'original_text':fact['text']})
    return result


def stated_weights(totals):
    """A component the listing never states (e.g. it names no recognised tools) is
    shown as 'Not stated'; its weight is shared by the stated components instead of
    silently scoring zero. Integer weights always sum to 100."""
    stated=[key for key in WEIGHTS if totals.get(key)]
    if not stated or len(stated)==len(WEIGHTS):
        return dict(WEIGHTS)
    base=sum(WEIGHTS[key] for key in stated)
    exact={key:100*WEIGHTS[key]/base for key in stated}
    weights={key:int(exact[key]) for key in WEIGHTS if key in exact}
    for key in sorted(stated,key=lambda k:exact[k]-weights[k],reverse=True)[:100-sum(weights.values())]:
        weights[key]+=1
    return {key:weights.get(key,0) for key in WEIGHTS}


def sentences(view):
    for section in view.get('sections',[]):
        for block in section['blocks']:
            for value in ([block['text']] if block['kind']=='paragraph' else block['items']):
                yield section['title'],value


def fit_assessment(job, profile, preferences, view, location, *, full=False, closed=False):
    result={'version':VERSION,'percent':None,'status':'Needs profile','strengths':[],
            'reviews':[],'requirements':[],'breakdown':[],'cap':None,
            'assessment_state':'needs_profile','assessment_notice':'Save your confirmed profile to assess this role.','auto_eligible':False,'coverage':{'criteria_count':0,'work_examples':0},
            'method':'Criterion-linked evidence: skills 30%, specific work examples 40%, stated requirements 30%; a component the listing does not state shares its weight with the others. Unconfirmed requirements earn no full credit; review gates are separate. Not a hiring probability.'}
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
    from .role_types import in_scope, matched_types
    rows=list(sentences(view))
    primary=view.get('title',job.title)+'\n'+'\n'.join(text for _,text in rows)
    clean_job=Job.model_validate({**job.model_dump(mode='json'),'title':view.get('title',job.title),'description':primary[:100000]})
    facts=[{'text':b,'role':e.role,'organisation':e.organization,'dates':e.dates}
           for e in profile.experience for b in e.bullets if evidence_value(b)>0]
    # Referees' titles and example cover letters cannot become candidate experience.
    profile_text='\n'.join([s for s in profile.skills if positive_evidence(s)]+[f['text'] for f in facts])
    scoring_text=view.get('title',job.title)+'\n'+'\n'.join(text for heading,text in rows
        if not re.search(OPTIONAL,heading,re.I) and not company_section(heading))
    tools=mentions(scoring_text)
    supported_tools=[t for t in tools if re.search(evidence_pattern(t),profile_text,re.I)]
    tool_values={t:(1 if any(re.search(evidence_pattern(t),f['text'],re.I) and evidence_value(f['text'])==1 for f in facts) else 0.5) for t in supported_tools}
    missing_tools=[t for t in tools if t not in supported_tools]
    # The candidate's own saved skills are also demands when the advert names them (Xero, Barista,
    # Forklift, Canva…). They can only add supported skills, never create an unconfirmed gate.
    own_hits=[]
    for skill in profile.skills:
        name=skill.strip()
        if not 3<=len(name)<=40 or not positive_evidence(name) or any(re.search(pattern,name,re.I) for pattern in TOOLS.values()): continue
        if re.search(r'(?<![\w+#])'+re.escape(name)+r'(?![\w+#])',scoring_text,re.I) and name.lower() not in {h.lower() for h in own_hits}:
            own_hits.append(name)
    own_values={name:(1 if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',f['text'],re.I) and evidence_value(f['text'])==1 for f in facts) else 0.5) for name in own_hits}
    # Words naming the person's trade (headline, role titles) may support a requirement's trade noun;
    # a saved skill only vouches for a requirement that repeats that skill word for word.
    trade_words=[x for x in [profile.headline,*[e.role for e in profile.experience]] if x and positive_evidence(x)]
    strengths=[]
    for name in own_hits:
        work=next((f for f in facts if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',f['text'],re.I)),None)
        strengths.append({'label':name,'kind':'Skill','evidence':work['text'] if work else name,'source':work or None})
    for tool in supported_tools:
        work=[f for f in facts if re.search(evidence_pattern(tool),f['text'],re.I)]
        fact=next((f for f in work if evidence_value(f['text'])==1),work[0] if work else None)
        skill=next((s for s in profile.skills if positive_evidence(s) and re.search(evidence_pattern(tool),s,re.I)),None)
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
    for heading,block_text in rows:
      for text in re.split(r'(?<=[.!?])\s+(?=[A-Z])', block_text):
        optional=bool(re.search(OPTIONAL,heading,re.I)) or company_section(heading) or heading.casefold() in {'benefits','what we offer'} or bool(re.search(r'\b(?:nice to have|helpful.{0,12}not required|desirable|preferred but not required)\b',text,re.I))
        explicit=re.search(r'\b(?:must|required|at least|mandatory|seeking a certified)\b|^(?:Requires|You need|Demonstrated|Strong|Proven|Experience|Commercial experience|Hands.on experience|Working knowledge|Ability to)\b',text,re.I)
        if not optional and (re.fullmatch(REQUIRED,heading,re.I) or requirement_heading(heading) or explicit):
            if len(text.strip())>15 and not re.fullmatch(r'Beyond that:?',text,re.I) and not re.search(LOGISTICS,text,re.I):
                criteria.append(text)
    criteria=list(dict.fromkeys(criteria))
    explicit_criteria=len(criteria)
    # The job title can establish a core technical requirement even in a short lead.
    title_tools=mentions(view.get('title',job.title))
    for tool in title_tools:
        if not any(re.search(TOOLS[tool],c,re.I) for c in criteria):
            criteria.append('Core tool in role title: '+tool)

    reviews=[]
    hard=False
    for criterion in criteria:
        linked_facts=criterion_facts(criterion,facts)
        required_tools=mentions(criterion)
        found=[t for t in required_tools if t in supported_tools]
        missing=[t for t in required_tools if t not in supported_tools]
        reasons=[]
        evidence=[]
        value=0
        special=False
        credential=is_credential(criterion)
        named=bool(re.search(r'\b(?:CISSP|CISM|PMP|ITIL|PL-\d{3}|AZ-\d{3}|MS-\d{3})\b',criterion,re.I))
        credential_record=recorded_credential(criterion,profile) if credential and not named else None
        qualification=credential_record if credential and not named else recorded_qualification(criterion,profile)
        duration=recorded_duration(criterion,linked_facts)
        if re.search(r'\bworkshops?\b',criterion,re.I) and not any(re.search(r'\bworkshops?\b',f['text'],re.I) for f in facts):
            reasons.append('Workshop facilitation is not explicitly confirmed; process mapping, guides and demonstrations are transferable evidence.')
            special=True
        if re.search(r'\bcommercial.{0,45}software engineer',criterion,re.I) and not any(
            re.search(r'\bsoftware engineer',e.role,re.I) and e.dates for e in profile.experience):
            reasons.append('Commercial software-engineering employment is not confirmed; IT support and app prototypes do not establish this requirement.')
            special=True
        if re.search(r'\b(?:nv1|nv2|baseline clearance|security clearance|australian citizen(?:ship)?|right to work|working rights|formal tertiary|degree in|qualifications? in|certified|(?:degree|tertiary|qualification|certification|licen[cs]e).{0,55}(?:required|essential)|(?:must|require).{0,55}(?:degree|certification|licen[cs]e))\b',criterion,re.I):
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
                        and (all(re.search(evidence_pattern(t),f['text'],re.I) for t in required_tools)
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
        stated_skills=[s for s in profile.skills if s.strip() and positive_evidence(s) and re.search(r'(?<![\w+#])'+re.escape(s.strip())+r'(?![\w+#])',criterion,re.I)]
        extra=unsupported_clauses(criterion,linked_facts,trade_words+stated_skills)
        if credential and not named:
            extra=[]
            if credential_record:
                value=1
                evidence=[{'text':credential_record,'role':'Saved qualification','organisation':'Confirmed profile','dates':''}]
            elif not special:
                reasons.append('Registration, licence or certificate is not in your saved records. Add it under Licences & registrations if you hold it.')
                special=True
        elif (extra and not required_tools and not duration and len(extra)==1 and extra[0] in requirement_words(criterion)
              and len(requirement_words(criterion))>=4 and not re.search(r'\d',criterion)):
            # One everyday word the bullets do not repeat (finding vs diagnosed, systems) is not a missing obligation
            # when the rest of a four-word requirement is evidenced.
            extra=[]
        if qualification and qualification_only(criterion) and not required_tools and not duration:
            extra=[]
            value=1
            evidence=[{'text':qualification,'role':'Saved qualification','organisation':'Confirmed profile','dates':''}]
        if duration and not qualification:
            extra=[w for w in extra if w not in {'10','5','4','3','2','year'}]
            if not extra:
                value=1
                evidence=[duration]
        if extra:
            reasons.append('Some details of this requirement are not confirmed in your saved evidence.')
        if not special and not evidence:
            if required_tools and len(found)==len(required_tools):
                value=1
                for tool in found:
                    pattern=evidence_pattern(tool)
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
                    evidence=direct[:2]
                    value=0.5 if extra else min(evidence_value(f['text']) for f in evidence)
                if value<1:
                    reasons.append('Transferable evidence only; confirm the specific requirement.' if value else 'No specific supporting evidence found in your saved experience.')
        if extra and value>0:
            value=min(value,0.5)
        if special:
            hard=True
            value=0
        status='Supported' if value==1 else 'Transferable' if value else 'Needs confirmation'
        result['requirements'].append({'text':criterion,'status':status,'value':value,'evidence':evidence,'reasons':reasons,'credential':credential})
        if value<1:
            reviews.append({'label':reasons[0] if reasons else 'Requirement needs review.','requirement':criterion})

    skill_total=len(tools)+len(own_hits)
    skills_ratio=(sum(tool_values.values())+sum(own_values.values()))/skill_total if skill_total else 0
    work_criteria=[r for r in result['requirements'] if not r.get('credential') and not re.search(r'(?i)degree|tertiary|qualification|certification|clearance|citizen|working rights|right to work',r['text'])]
    work_values=[r['value']*max((evidence_value(e['text']) for e in r['evidence'] if e.get('role') not in {'Saved skill','Saved qualification'}),default=0) for r in work_criteria]
    experience_ratio=sum(work_values)/len(work_values) if work_values else 0
    requirements_ratio=sum(r['value'] for r in result['requirements'])/len(result['requirements']) if result['requirements'] else 0
    totals={'skills':skill_total,'experience':len(work_values),'requirements':len(result['requirements'])}
    weights=stated_weights(totals)
    result['breakdown']=[
        {'id':'skills','label':'Relevant skills','weight':weights['skills'],'points':round(weights['skills']*skills_ratio),'covered':sum(tool_values.values())+sum(own_values.values()),'total':skill_total},
        {'id':'experience','label':'Work experience','weight':weights['experience'],'points':round(weights['experience']*experience_ratio),'covered':sum(work_values),'total':len(work_values)},
        {'id':'requirements','label':'Stated requirements','weight':weights['requirements'],'points':round(weights['requirements']*requirements_ratio),'covered':sum(r['value'] for r in result['requirements']),'total':len(result['requirements'])},
    ]
    strengths=[s for s in strengths if s['kind']!='Experience']
    seen_work=set()
    for criterion in result['requirements']:
        for fact in criterion['evidence']:
            if criterion['value']>0 and fact.get('role') not in {'Saved skill','Saved qualification'} and fact['text'] not in seen_work:
                seen_work.add(fact['text'])
                strengths.append({'label':'Work evidence: '+criterion['text'][:85],'kind':'Experience','evidence':fact['text'],'source':fact})
    result['strengths']=sorted(strengths,key=lambda s:s['kind']!='Experience')
    result['matched_skills']=supported_tools+own_hits
    result['unconfirmed_skills']=missing_tools
    result['experience']=[{'label':r['text'],'value':v,'evidence':next((e for e in r['evidence'] if e.get('role') not in {'Saved skill','Saved qualification'}),None)} for r,v in zip(work_criteria,work_values)]
    score=sum(b['points'] for b in result['breakdown'])
    caps=[]
    work_examples={f['text'] for requirement in result['requirements'] for f in requirement['evidence'] if f.get('role') not in {'Saved skill','Saved qualification'}}
    result['coverage']={'criteria_count':explicit_criteria,'work_examples':len(work_examples),
                        'supported':sum(r['value']==1 for r in result['requirements']),
                        'partial':sum(0<r['value']<1 for r in result['requirements']),
                        'unconfirmed':sum(r['value']==0 for r in result['requirements'])}
    # A mandatory licence, registration or card that is not on record is a gate, not one more point lost.
    missing_credentials=[r for r in result['requirements'] if r.get('credential') and r['value']==0 and r['reasons'] and 'Licences & registrations' in r['reasons'][0]]
    if missing_credentials:
        caps.append((69,'A required licence, registration or certificate is not in your saved records.'))
    if explicit_criteria<3 or len(work_examples)<2:
        reviews.append({'label':'Limited evidence: at least three distinct requirements and two work examples are needed for an automatic strong match.','requirement':''})
        caps.append((79,'Listing or evidence is too sparse for a strong-match judgement.'))
    if not tools and not own_hits and matched_types(clean_job):
        reviews.append({'label':'Not enough explicit technical skill detail to assess the skills component.','requirement':''})
    if not full:
        reviews.insert(0,{'label':'Read the full listing before assessing this role.','requirement':''})
    if not explicit_criteria:
        reviews.append({'label':'No explicit requirements could be assessed from the saved listing.','requirement':''})
    if not in_scope(clean_job,preferences):
        reviews.append({'label':('Role title does not match the job titles you are looking for.' if getattr(preferences,'job_titles',None) else 'Role falls outside your selected role types.'),'requirement':''})
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
    result['auto_eligible']=bool(full and not closed and not reviews and explicit_criteria>=3 and len(work_examples)>=2 and score>=75)
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
