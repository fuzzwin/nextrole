"""Role families grounded in the user's application examples, not new credentials."""
from __future__ import annotations
import re
from collections import deque

DAILY_QUERY_LIMIT = 10
EXTENDED_QUERY_LIMIT = 24
DAILY_LISTING_LIMIT = 12
EXTENDED_LISTING_LIMIT = 32
ROLE_TYPES = [
    {'id':'it_systems','label':'IT support & systems','description':'Systems administration, Microsoft 365, workplace IT and service support.',
     'titles':r'\b(?:it|systems? administrator|systems? specialist|systems? support|desktop|service desk|digital workplace)\b',
     'queries':['IT systems specialist Microsoft 365 support','systems administrator IT support specialist'],
     'focus':'Microsoft 365 Exchange Entra Intune SCCM Group Policy ServiceNow support incidents network onboarding licensing'},
    {'id':'automation','label':'Power Platform & automation','description':'Power Automate, SharePoint, Copilot Studio and practical workflow delivery.',
     'titles':r'\b(?:automation|power platform|power automate|sharepoint|copilot studio)\b',
     'queries':['Power Platform Power Automate automation specialist','SharePoint Copilot Studio process automation consultant'],
     'focus':'Power Automate SharePoint workflow Forms approvals Python automation process testing rollout'},
    {'id':'ai_enablement','label':'AI enablement & adoption','description':'Helping people use AI through guidance, practical coaching and adoption.',
     'titles':r'\b(?:ai enablement|ai adoption|ai training|digital productivity|ai specialist|ai consultant)\b',
     'queries':['AI enablement adoption specialist','digital productivity AI adoption consultant'],
     'focus':'AI Hub guide demonstration adoption colleagues model prompts enablement designer responsible'},
    {'id':'ai_operations','label':'AI platform operations','description':'Platform support, access, incidents, vendor changes and responsible use.',
     'titles':r'\b(?:ai operations|ai platform|ai service|enterprise ai)\b',
     'queries':['AI operations platform support specialist','enterprise AI platform operations analyst'],
     'focus':'platform support incidents vendor releases licensing ServiceNow governance AI Hub responsible'},
    {'id':'business_analysis','label':'Business analysis & consulting','description':'Requirements, business processes, discovery and AI/automation advisory.',
     'titles':r'\b(?:business analyst|business analysis|business systems analyst|business process|ai business|transformation analyst|automation consultant|ai consultant|ai enablement consultant)\b',
     'queries':['business analyst AI automation process improvement','business systems analyst technology consultant'],
     'focus':'requirements stakeholders mapping business value intake process business case project charter Quality Finance HR'},
    {'id':'applications','label':'Business applications & ERP','description':'NetSuite, application support, integrations, releases and vendor coordination.',
     'titles':r'\b(?:applications?|netsuite|erp|business systems)\b',
     'queries':['business applications ERP NetSuite support specialist','technology applications specialist systems support'],
     'focus':'NetSuite ERP applications integration ODBC vendor authentication releases sandbox UAT PDM Box'},
    {'id':'project_delivery','label':'IT project delivery','description':'Technology project coordination, change, stakeholder work and handover.',
     'titles':r'\b(?:project|pmo|it portfolio and delivery|it delivery|technology delivery|digital delivery|technology change|digital transformation)\b',
     'queries':['IT project coordinator technology delivery','technology project delivery business change coordinator'],
     'focus':'project delivery stakeholder waterfall agile hybrid coordination testing change control handover requirements'},
    {'id':'service_delivery','label':'Service delivery & implementation','description':'IT service delivery, implementation, release coordination and transition into support.',
     'titles':r'\b(?:it service delivery|service delivery|technical delivery|implementation (?:coordinator|consultant|specialist|analyst|manager)|(?:release|service transition|technology rollout) (?:coordinator|analyst|specialist|manager))\b',
     'queries':['IT service delivery implementation coordinator','technology implementation specialist release service transition coordinator'],
     'focus':'service delivery stakeholder vendor support incidents coordination implementation rollout testing UAT release change control handover'},
]
BY_ID = {item['id']: item for item in ROLE_TYPES}
DEFAULT_ROLE_TYPES = list(BY_ID)


def matched_types(job, selected=None):
    allowed = set(DEFAULT_ROLE_TYPES if selected is None else selected)
    matches = [item for item in ROLE_TYPES if item['id'] in allowed and re.search(item['titles'], job.title, re.I)]
    # A generic IT token should not displace a more specific application or project title.
    return sorted(matches, key=lambda item: (item['id']=='it_systems', ROLE_TYPES.index(item)))


def validate_types(ids):
    if not ids or any(item not in BY_ID for item in ids) or len(ids) != len(set(ids)):
        raise ValueError('Select at least one known role type without duplicates')
    return ids


def example_types(name, text=''):
    known = {'bellroy':['ai_enablement'], 'businessai':['business_analysis'], 'cleanaway':['ai_operations'],
             'jemena':['ai_enablement','automation'], 'avanade':['automation'],
             'integral_diagnostics':['applications'], 'davidson':['business_analysis','project_delivery'],
             'casey':['automation','it_systems']}
    normalized = name.lower().replace(' ', '_')
    for keyword, ids in known.items():
        if keyword in normalized:
            return ids
    class Title:
        title = ' '.join(re.findall(r'(?im)^(?:Re:|APPLICATION:)\s*(.+)', text))
    return [item['id'] for item in matched_types(Title())]


def query_plan(preferences, extended=False):
    ids = getattr(preferences, 'role_types', DEFAULT_ROLE_TYPES)
    chosen = [BY_ID[item] for item in validate_types(ids)]
    local = preferences.location
    primary = [f"{item['queries'][0]} jobs {local}" for item in chosen]
    secondary = [f"{item['queries'][1]} jobs Australia" for item in chosen]
    custom = [f'{keyword} jobs {local}' for keyword in preferences.keywords[:3]] if getattr(preferences,'use_custom_keywords',False) else []
    queries = primary + custom + secondary
    if extended:
        focus = ' OR '.join(f'"{item["queries"][1]}"' for item in chosen)
        queries += [f'site:{domain} ({focus}) Australia' for domain in ['seek.com.au/job','au.linkedin.com/jobs/view','au.indeed.com/viewjob']]
        queries += [f'{item["queries"][0]} remote Australia' for item in chosen]
    return list(dict.fromkeys(queries))[:EXTENDED_QUERY_LIMIT if extended else DAILY_QUERY_LIMIT]


def spread_candidates(rows, selected):
    """Give each selected role family listing-read time within the shared budget."""
    queues = {item: deque() for item in selected}
    for row in rows:
        family = next((item['id'] for item in row.get('role_types', []) if item['id'] in queues), None)
        if family:
            queues[family].append(row)
    ordered = []
    while any(queues.values()):
        for queue in queues.values():
            if queue:
                ordered.append(queue.popleft())
    return ordered


def capability_evidence(job, profile):
    """Show transferable experience with an exact source fact for each match."""
    patterns = [
        ('Process discovery & requirements', r'map (?:business )?processes|process mapping|translating requirements', r'\bdiscovery|workflow reviews?|\bprocess(?:es)?\b|\brequirements\b|business analysis'),
        ('Project coordination & handover', r'manage.{0,40}projects|project.{0,80}change control|stakeholder.{0,80}handover', r'\bproject|\bdelivery|\bcoordina|\broadmap|\bstakeholder|\bhandover'),
        ('AI guidance & adoption', r'AI Hub|AI.assisted.{0,80}guidance|governed.{0,40}AI', r'\bAI\b|\bLLMs?\b|\bagents\b|\badoption|\benablement'),
        ('Workflow automation', r'Power Automate|approval workflow|Python utility', r'\bautomation|\bworkflows?\b|Power Platform|Power Automate'),
        ('Systems & service support', r'administer.{0,50}(?:Microsoft 365|Entra)|ServiceNow incidents|IT onboarding', r'Microsoft 365|\bsystems?\b|\bsupport\b|\bincidents?\b|\bservice desk\b'),
        ('Application releases & integrations', r'NetSuite|ODBC|sandbox UAT', r'\bapplications?\b|\bERP\b|\bNetSuite\b|\bintegration|\breleases?\b|\bUAT\b'),
    ]
    target = job.title + '\n' + job.description
    facts = [fact for entry in profile.experience for fact in entry.bullets]
    evidence = []
    for label, source_pattern, listing_pattern in patterns:
        fact = next((fact for fact in facts if re.search(source_pattern, fact, re.I)), None)
        listing = re.search(listing_pattern, target, re.I)
        if fact and listing:
            evidence.append({'label': label, 'fact': fact, 'listing_term': listing[0]})
    return evidence
