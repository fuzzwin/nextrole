"""Explainable evidence coverage for browsing. Never an eligibility decision."""
from __future__ import annotations

import re
from .models import Job

VERSION = 'experience-fit-v1'
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
    ('Project delivery and handover',r'\bproject|\bdelivery|\bcoordina|\bstakeholder|\bhandover|\bchange control',r'manage.{0,40}projects|project.{0,80}change control|stakeholder.{0,80}handover'),
    ('Process discovery and requirements',r'\brequirements\b|\bdiscovery|\bprocess(?:es)?\b|\bworkshops?\b|business analysis',r'map (?:business )?processes|process mapping|translating requirements'),
    ('Applications and integrations',r'\bapplications?\b|\bERP\b|\bNetSuite\b|\bintegration|\breleases?\b|\bUAT\b',r'NetSuite|ODBC|sandbox UAT'),
    ('Software development',r'\bsoftware|\bdeveloper|\b(?:AI|software) engineer|\bbuild.{0,30}(?:apps?|agents?)|\bprogramming',r'App prototypes|built.{0,35}(?:Python|Flask)|build.{0,40}(?:React|TypeScript)'),
    ('Security operations',r'\bsecurity\b|\bpermissions?\b|\baccess control\b|\bauthentication\b',r'security incident|Entra ID|phishing|authentication'),
    ('User guidance and communication',r'\bguides?\b|\bcommunication|\btraining|\bcoaching|\benablement|\badoption',r'interactive guide|plain.language user guides|induction guides|awareness training|AI Hub demonstration'),
]
REQUIRED = r'what you need|(?:job )?requirements|essential(?: requirements| criteria)?|must have|(?:minimum|required)?\s*qualifications|(?:key )?selection criteria|key criteria|what (?:we[’\x27]re|we are) looking for|what you[’\x27]ll bring|what you[’\x27]ll need to succeed|skills (?:and|&) experience|about you|technical skills|(?:required )?experience|key skills|your profile|specialist/technical expertise/qualifications|required skills(?: and experience)?|required experience & skills'
OPTIONAL = r'helpful|not required|desirable|nice to have|preferred|benefits|what we offer|why join|compensation|where this goes|to apply|how to apply|our process'
QUALIFIED = r'\b(?:prototyp\w*|concept|propos\w*|paused|before rollout|ahead of rollout|not (?:yet )?(?:deployed|live)|proof.of.concept)\b'
PRODUCTION = r'\b(?:production|deployed|live|real (?:people|users)|used monthly)\b'


def mentions(text):
    return [name for name,pattern in TOOLS.items() if re.search(pattern,text,re.I)]


def sentences(view):
    for section in view.get('sections',[]):
        for block in section['blocks']:
            for value in ([block['text']] if block['kind']=='paragraph' else block['items']):
                yield section['title'],value


def fit_assessment(job, profile, preferences, view, location, *, full=False, closed=False):
    result={'version':VERSION,'percent':None,'status':'Needs profile','strengths':[],
            'reviews':[],'requirements':[],'breakdown':[],'cap':None,
            'method':'Evidence coverage: skills 30%, work experience 40%, stated requirements 30%. Unknown criteria earn no points. Not a hiring probability.'}
    if not profile or profile.is_example:
        result['reviews']=[{'label':'Save your confirmed résumé profile to assess this role.','requirement':''}]
        return result
    if re.search(r'(?im)^\s*#{1,6}\s*\d[\d,]*[^\n]{0,150}\bjobs?\s+in\b',job.description):
        result.update(status='Needs review',reviews=[{'label':'The source returned a job-search results page instead of this role. Verify the original posting.','requirement':''}])
        return result
    from .role_types import matched_types
    rows=list(sentences(view))
    primary=view.get('title',job.title)+'\n'+'\n'.join(text for _,text in rows)
    clean_job=Job.model_validate({**job.model_dump(mode='json'),'title':view.get('title',job.title),'description':primary[:100000]})
    facts=[{'text':b,'role':e.role,'organisation':e.organization,'dates':e.dates}
           for e in profile.experience for b in e.bullets]
    # Referees' titles and example cover letters cannot become candidate experience.
    profile_text='\n'.join(profile.skills+[profile.summary]+[f['text'] for f in facts])
    scoring_text=view.get('title',job.title)+'\n'+'\n'.join(text for heading,text in rows
        if not re.search(OPTIONAL,heading,re.I) and heading.casefold() not in {'about us','about the company','company description'})
    tools=mentions(scoring_text)
    supported_tools=[t for t in tools if re.search(TOOLS[t],profile_text,re.I)]
    missing_tools=[t for t in tools if t not in supported_tools]
    strengths=[]
    for tool in supported_tools:
        fact=next((f for f in facts if re.search(TOOLS[tool],f['text'],re.I)),None)
        skill=next((s for s in profile.skills if re.search(TOOLS[tool],s,re.I)),None)
        strengths.append({'label':tool,'kind':'Skill','evidence':fact['text'] if fact else skill or 'Saved profile summary',
                          'source':fact or None})
    experience=[]
    for label,demand,source in DOMAINS:
        listing=re.search(demand,scoring_text,re.I)
        if not listing:
            continue
        fact=next((f for f in facts if re.search(source,f['text'],re.I)),None)
        partial=bool(fact and re.search(QUALIFIED,fact['text'],re.I))
        experience.append({'label':label,'value':0.5 if partial else 1 if fact else 0,
                           'evidence':fact,'listing_term':listing[0]})
        if fact:
            strengths.append({'label':label+(' (transferable prototype work)' if partial else ''),
                              'kind':'Experience','evidence':fact['text'],'source':fact})

    criteria=[]
    for heading,text in rows:
        optional=bool(re.search(OPTIONAL,heading,re.I)) or bool(re.search(r'\b(?:nice to have|helpful.{0,12}not required|desirable|preferred but not required)\b',text,re.I))
        explicit=re.search(r'\b(?:must|required|at least|mandatory|seeking a certified)\b|^(?:Demonstrated|Strong|Proven|Experience|Commercial experience|Hands.on experience|Working knowledge|Ability to)\b',text,re.I)
        if not optional and (re.fullmatch(REQUIRED,heading,re.I) or explicit):
            if len(text.strip())>15 and not re.fullmatch(r'Beyond that:?',text,re.I):
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
        required_tools=mentions(criterion)
        found=[t for t in required_tools if t in supported_tools]
        missing=[t for t in required_tools if t not in supported_tools]
        reasons=[]
        evidence=[]
        value=0
        special=False
        if re.search(r'\bworkshops?\b',criterion,re.I) and not any(re.search(r'\bworkshops?\b',f['text'],re.I) for f in facts):
            reasons.append('Workshop facilitation is not explicitly confirmed; process mapping, guides and demonstrations are transferable evidence.')
            special=True
        if re.search(r'\bcommercial.{0,45}software engineer',criterion,re.I) and not any(
            re.search(r'\bsoftware engineer',e.role,re.I) and e.dates for e in profile.experience):
            reasons.append('Commercial software-engineering employment is not confirmed; IT support and app prototypes do not establish this requirement.')
            special=True
        if re.search(r'\b(?:nv1|nv2|baseline clearance|security clearance|australian citizen(?:ship)?|right to work|working rights|formal tertiary|degree in|qualifications? in|certified|(?:degree|tertiary|qualification|certification|licen[cs]e).{0,55}(?:required|essential)|(?:must|require).{0,55}(?:degree|certification|licen[cs]e))\b',criterion,re.I):
            # Credentials/eligibility need explicit, contextual confirmation, never keyword credit.
            reasons.append('Eligibility or credential requirement needs confirmation against your records.')
            special=True
        if re.search(r'\b(?:at least|minimum of)\s+(?:[2-9]\d*|two|three|four|five|six|ten)\s+(?:enterprise|production|commercial)',criterion,re.I):
            reasons.append('The required number and scale of delivered solutions need confirmation from specific source facts.')
            special=True
        if re.search(r'\b(?:\d+\+?|one|two|three|four|five|six|seven|eight|ten|twelve|eighteen|twenty)\s*(?:to\s*\d+\s*)?(?:years?|months?)\b',criterion,re.I):
            reasons.append('Required duration of relevant experience needs confirmation; total IT tenure does not establish specialist tenure.')
            special=True
        production=bool(re.search(PRODUCTION,criterion,re.I) and not re.search(r'\bor production\b',criterion,re.I)
                        and (required_tools or re.search(r'\bagents?\b|software',criterion,re.I)))
        if production:
            candidates=[f for f in facts if re.search(PRODUCTION,f['text'],re.I) and not re.search(QUALIFIED,f['text'],re.I)
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
        if not special and not evidence:
            if required_tools and len(found)==len(required_tools):
                value=1
                for tool in found:
                    pattern=TOOLS[tool] if tool!='Power Platform' else r'\bpower (?:platform|automate|apps)\b'
                    work=[f for f in facts if re.search(pattern,f['text'],re.I)]
                    solid=[f for f in work if not re.search(QUALIFIED,f['text'],re.I)]
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
                if matches and all(e['value'] for e in matches):
                    value=min(e['value'] for e in matches)
                    evidence=[e['evidence'] for e in matches if e['evidence']][:2]
                if value<1:
                    reasons.append('Transferable evidence only; confirm the specific requirement.' if value else 'No specific supporting evidence found in your saved experience.')
        if special:
            hard=True
            value=0
        status='Supported' if value==1 else 'Transferable' if value else 'Needs confirmation'
        result['requirements'].append({'text':criterion,'status':status,'value':value,'evidence':evidence,'reasons':reasons})
        if value<1:
            reviews.append({'label':reasons[0] if reasons else 'Requirement needs review.','requirement':criterion})

    skills_ratio=len(supported_tools)/len(tools) if tools else 0
    experience_ratio=sum(e['value'] for e in experience)/len(experience) if experience else 0
    requirements_ratio=sum(r['value'] for r in result['requirements'])/len(result['requirements']) if result['requirements'] else 0
    result['breakdown']=[
        {'id':'skills','label':'Relevant skills','weight':30,'points':round(30*skills_ratio),'covered':len(supported_tools),'total':len(tools)},
        {'id':'experience','label':'Work experience','weight':40,'points':round(40*experience_ratio),'covered':sum(e['value'] for e in experience),'total':len(experience)},
        {'id':'requirements','label':'Stated requirements','weight':30,'points':round(30*requirements_ratio),'covered':sum(r['value'] for r in result['requirements']),'total':len(result['requirements'])},
    ]
    result['strengths']=sorted(strengths,key=lambda s:s['kind']!='Experience')
    result['matched_skills']=supported_tools
    result['unconfirmed_skills']=missing_tools
    result['experience']=experience
    score=sum(b['points'] for b in result['breakdown'])
    caps=[]
    limited=[e['label'] for e in experience if e['value']<1]
    if limited:
        reviews.append({'label':'Work evidence is partial or unconfirmed for: '+', '.join(limited)+'.','requirement':''})
        caps.append((69,'Some relevant work experience needs review.'))
    if not tools:
        reviews.append({'label':'Not enough explicit technical skill detail to assess the skills component.','requirement':''})
        caps.append((69,'Skill detail is incomplete.'))
    if hard:
        caps.append((59,'Essential requirements need confirmation.'))
    if reviews:
        caps.append((69,'Some stated requirements have partial or no supporting evidence.'))
    if not full:
        reviews.insert(0,{'label':'Preliminary assessment: read the full listing before relying on this score.','requirement':''})
        caps.append((49,'Full listing not yet read.'))
    if not explicit_criteria:
        reviews.append({'label':'No explicit requirements could be assessed from the saved listing.','requirement':''})
        caps.append((69,'Requirements are incomplete.'))
    if not matched_types(clean_job,preferences.role_types):
        reviews.append({'label':'Role falls outside your selected role types.','requirement':''})
        caps.append((49,'Outside your selected role types.'))
    if not location.get('stated'):
        reviews.append({'label':'Listing location needs confirmation.','requirement':''})
        caps.append((69,'Location is unconfirmed.'))
    if not (view.get('employer') or job.employer not in {'','Employer on job listing','Employer in job alert'}):
        reviews.append({'label':'Employer identity needs verification.','requirement':''})
        caps.append((69,'Employer identity is unconfirmed.'))
    for notice in view.get('notices',[]):
        reviews.append({'label':notice['message'],'requirement':notice['quote']})
        caps.append((69,'Listing contains conflicting work details.'))
    if re.search(r'\b(?:senior|lead|manager|architect|principal|director|head|graduate|internship|apprentice)\b',view.get('title',job.title),re.I):
        reviews.append({'label':'Seniority and scope need review against your confirmed responsibilities.','requirement':''})
        caps.append((69,'Seniority needs review.'))
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
    result.update(percent=score,status='Closed' if closed else 'Good match' if score>=70 and not reviews else 'Needs review',reviews=reviews)
    return result
