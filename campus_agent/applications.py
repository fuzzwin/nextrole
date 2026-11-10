"""Evidence-backed application tracking. Email bodies are data, never instructions."""
from __future__ import annotations

import hashlib
import re
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, parseaddr

from bs4 import BeautifulSoup

from .models import utcnow

APPLICATION_QUERY = ('newer_than:365d -in:trash -in:spam -from:me '
    '-subject:"Job Agent" -subject:"Standout job" '
    '{subject:application subject:interview subject:"position cancelled" subject:"position canceled" '
    '"received your application" "thank you for applying" "thanks for applying"}')
PARSER_VERSION = 2
_SYNC_LOCK_GUARD = threading.Lock()
ATS = r'myworkday\.com|greenhouse(?:-mail)?\.(?:io|com)|pageuppeople\.com|smartrecruiters\.com|lever\.co|ashbyhq\.com|teamtailor\.com|successfactors\.'


def normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.lower().replace('&', ' and ')).strip()


def application_key(company, title):
    return hashlib.sha256((normalize(company) + '|' + normalize(title)).encode()).hexdigest()


def headers(message):
    values = message.get('payload', {}).get('headers', [])
    return {h['name'].lower(): h.get('value', '') for h in values} if isinstance(values, list) else {k.lower():v for k,v in values.items()}


def clean_identity(value, kind):
    value=re.sub(r'\s+',' ',value or '').strip(' !.,:-')
    if kind=='company' and re.search(r'(?i)\b(?:role|position|opportunity)\b',value): return ''
    if kind=='company':
        value=re.sub(r'(?i)^(?:joining (?:the|our) team|working with us|work with us|a career) at\s+', '', value)
    if not value or len(value)> (100 if kind=='company' else 140): return ''
    if re.search(r'(?i)\b(?:we have|we will|your application|your resume|now that|thank you|if your|our team|working with us|joining the team)\b',value): return ''
    return value


def identity_valid(application):
    return bool(clean_identity(application.get('company',''),'company') and clean_identity(application.get('title',''),'title'))


def candidate_metadata(message, applications=()):
    h=headers(message); sender,subject=h.get('from',''),h.get('subject','')
    if 'SENT' in message.get('label_ids',message.get('labelIds',[])) or re.search(r'Job Agent|Standout job',subject,re.I): return False
    if re.search(r'newsletter|recommendations|job alert|new jobs|rebate|registration rebate|credit limit|financial hardship|payment|GitHub Application',sender+' '+subject,re.I): return False
    if re.search(ATS,sender,re.I) or re.search(r'careers|recruit|talent|hiring',sender,re.I): return True
    if any(identity_valid(a) and ((normalize(a['company']) and (' '+normalize(a['company'])+' ') in (' '+normalize(sender+' '+subject)+' ')) or (normalize(a['title']) and (' '+normalize(a['title'])+' ') in (' '+normalize(subject)+' '))) for a in applications): return True
    return bool(re.search(r'application|interview|employment offer',subject,re.I))


def body_text(message):
    plain, markup = [], []
    def walk(part):
        mime = part.get('mime_type', part.get('mimeType', ''))
        if mime in {'text/plain', 'text/html'} and not part.get('filename'):
            value = (part.get('body') or {}).get('content')
            if value:
                (plain if mime == 'text/plain' else markup).append(value)
        for child in part.get('parts') or []:
            walk(child)
    walk(message.get('payload', {}))
    soup = BeautifulSoup('\n'.join(markup), 'html.parser')
    for node in soup(['script','style','head']):
        node.decompose()
    text = '\n'.join(plain) or soup.get_text('\n', strip=True)
    text = re.split(r'(?im)^On .{0,200}wrote:|^-{3,}\s*Original Message', text, maxsplit=1)[0]
    return '\n'.join(line.strip() for line in text.splitlines() if not line.lstrip().startswith('>'))[:30000]


def parse_application(message, applications=()):
    message = message.get('message', message)
    if not candidate_metadata(message, applications):
        return None
    h = headers(message)
    subject, text = h.get('subject', ''), body_text(message)
    compact = re.sub(r'\s+', ' ', text)
    company = title = ''
    for pattern,source in [
        (r'^(.+?) Application Update for\b',subject),
        (r'(?:Role|position|Interview) at\s+([^!\n.]+)',subject),
        (r'(?:application with|interest in (?:joining (?:the|our) team|working with us) at)\s+([^!\n.]+)',subject),
        (r'^(.+?)\s*[-–—]\s*Application Received',subject),
        (r'(?:work with us|joining (?:the|our) team|working with us) at\s+([^!\n.]+)',text),
        (r'(?:role|position) with\s+([^!\n.]+)',text),
        (r'interest in\s+([^,\n.!]+)',text),
    ]:
        match=re.search(pattern,source,re.I)
        if match:
            company=clean_identity(match[1],'company')
            if company: break
    for pattern,source in [
        (r'(?:Application Update for|Interview Invitation\s*[|:]\s*)\s*(.+?)(?: Role at | at |$)',subject),
        (r'for (?:the )?([A-Za-z][A-Za-z &+/-]{3,100}?) position at\s+',text),
        (r'following position:\s*(?:[A-Z]-?\d+\s*[-–—]\s*)?([^\n.]+)',text),
        (r'(?:position of|job title:|role title:)\s+([^\n.]+)',text),
        (r'application for (?:our |the )?([^.!?\n]{3,140}?) (?:role|position)\b',text),
        (r'application for\s+([^.!?\n]{3,140})$',subject),
    ]:
        match=re.search(pattern,source,re.I)
        if match:
            title=clean_identity(match[1],'title')
            if title: break
    known_apps=[a for a in applications if identity_valid(a)]
    sender_name,sender_address=parseaddr(h.get('from',''))
    sender_domain=sender_address.rsplit('@',1)[-1].lower() if '@' in sender_address else ''
    sender_companies={clean_identity(a['company'],'company') for a in known_apps
        if ((' '+normalize(a['company'])+' ') in (' '+normalize(sender_name)+' ') or
            (len(re.sub(r'[^a-z0-9]','',a['company'].lower()))>=4 and
             re.sub(r'[^a-z0-9]','',a['company'].lower())==sender_domain.split('.')[0]))}
    if not company and len(sender_companies)==1: company=sender_companies.pop()
    # Identity inheritance is narrow: an observed thread, or explicit company AND role.
    thread=message.get('thread_id',message.get('threadId'))
    same=[a for a in known_apps if thread and thread in a.get('thread_ids',[])]
    same_keys={application_key(a['company'],a['title']) for a in same}
    if len(same_keys)==1:
        known=same[0]
        if (not company or normalize(company)==normalize(known['company'])) and (not title or normalize(title)==normalize(known['title'])):
            company,title=known['company'],known['title']
    if company and not title:
        matches=[a for a in known_apps if normalize(a['company'])==normalize(company)
            and (' '+normalize(a['title'])+' ') in (' '+normalize(subject+' '+text)+' ')]
        if len({application_key(a['company'],a['title']) for a in matches})==1: title=matches[0]['title']
    status = None
    evidence = None
    signals = [
        ('vacancy_cancelled', r'(?:position|role|vacancy).{0,35}(?:has been |is |was )?cancel(?:l)?ed|(?:cancel this|cancel the|not moving forward with filling) (?:position|role|vacancy)'),
        ('rejected', r'(?:not to move forward|not (?:be )?progressing|not been successful|application.{0,45}unsuccessful|unsuccessful.{0,45}application)'),
        ('withdrawn', r'(?:you have withdrawn|your application has been withdrawn)'),
        ('offer', r'(?:offer of employment|pleased to offer you.{0,80}(?:position|role|job))'),
        ('interview', r'(?:invite you (?:to|for).{0,80}interview|your interview (?:is|has been)|interview invitation)'),
        ('assessment', r'invite you (?:to|for).{0,80}assessment'),
        ('under_review', r'your application is (?:currently )?under review'),
        ('received', r'(?:received your application|thank you for.{0,90}application|thank you for applying|thanks for (?:your application|applying))'),
    ]
    for label, pattern in signals:
        for sentence in [subject]+re.split(r'(?<=[.!?;])\s+|\n+',text):
            if label=='vacancy_cancelled' and re.search(r'(?i)\b(?:not|never|no longer)\b.{0,50}\bcancel',sentence): continue
            if label=='rejected' and re.search(r'(?i)\bnot\b.{0,25}\bunsuccessful\b',sentence): continue
            if label in {'interview','assessment','offer','rejected'}:
                if re.search(r'(?i)^\s*(?:if|should you)\b|\b(?:may|might|could|will invite|will contact)\b',sentence): continue
                if re.search(r'(?i)\b(?:not an? offer|not an? invitation|cancel(?:l)?ed|cancel(?:l)?ing)\b',sentence): continue
            match=re.search(pattern,sentence,re.I)
            if match:
                status,evidence=label,match[0]
                break
        if status: break
    if not status:
        return None
    try:
        date = datetime.fromtimestamp(int(message['internal_date'])/1000, timezone.utc) if message.get('internal_date') else parsedate_to_datetime(h['date'])
        date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except (ValueError, KeyError, TypeError):
        return None
    return {'message_id':message['id'],'thread_id':thread,'at':date.astimezone(timezone.utc).isoformat(),
            'company':company,'title':title,'status':status,'subject':subject,
            'source_url':'https://mail.google.com/mail/u/0/#all/'+message['id'],
            'evidence':evidence,'summary':{'vacancy_cancelled':'Employer reports vacancy cancelled','received':'Application receipt confirmed','under_review':'Application is under review','rejected':'Employer reports application unsuccessful','withdrawn':'Application withdrawal confirmed','offer':'Employment offer mentioned; review terms','interview':'Interview invitation received','assessment':'Assessment invitation received'}[status]+': '+evidence[:220],
            'parser_version':PARSER_VERSION,'sender':h.get('from',''),'needs_review':not(company and title),
            'review_reason':'Employer or exact role is not established. Company contact alone does not identify an application.' if not(company and title) else ''}


def rebuild_applications(events):
    groups = {}
    for event in sorted(events, key=lambda e:e['at']):
        if event['needs_review']:
            continue
        key = application_key(event['company'],event['title'])
        item = groups.setdefault(key, {'id':key,'company':event['company'],'title':event['title'],
            'applied_at':None,'thread_ids':[],'events':[]})
        if event['status']=='received' and item['applied_at'] is None:
            item['applied_at']=event['at']
        if event.get('thread_id') and event['thread_id'] not in item['thread_ids']:
            item['thread_ids'].append(event['thread_id'])
        item['events'].append(event)
        item.update(status=event['status'],last_update_at=event['at'],source_url=event['source_url'],summary=event.get('summary',event.get('evidence','')))
    return sorted(groups.values(),key=lambda a:a['last_update_at'],reverse=True)


def application_for_job(workspace, job):
    return next((a for a in workspace.get_meta('applications', [])
                 if application_key(job.employer,job.title)==a['id']), None)


def ingest_events(workspace, new_events):
    with workspace.write_lock:
        events = {e['message_id']:e for e in workspace.get_meta('application_events', [])}
        changes = [e for e in new_events if events.get(e['message_id'])!=e]
        events.update({e['message_id']:e for e in new_events})
        applications = rebuild_applications(events.values())
        workspace.set_meta('application_events',list(events.values()))
        workspace.set_meta('applications',applications)
        linked = 0
        for row in workspace.store.jobs():
            from .models import Job
            job=Job.model_validate(row['job'])
            match=application_for_job(workspace,job)
            if match:
                with workspace.store.connect() as db:
                    db.execute("INSERT INTO job_details(job_id,stage) VALUES (?,'applied') ON CONFLICT(job_id) DO UPDATE SET stage='applied'",(row['id'],))
                linked+=1
        return {'applications':applications,'new_events':len(changes),'linked_jobs':linked,
                'needs_review':[e for e in events.values() if e['needs_review']]}


def _sync_applications(workspace):
    found=workspace.bridge.call('gmail.search_email_ids',{'query':APPLICATION_QUERY,'max_results':100})
    seen=set(workspace.get_meta('application_mail_seen',[]))
    old_events=workspace.get_meta('application_events',[])
    repaired=set(workspace.get_meta('application_parser_v2_checked',[]))
    repairs=[e['message_id'] for e in old_events if e.get('parser_version',0)<PARSER_VERSION and e['message_id'] not in repaired][:10]
    pending=list(dict.fromkeys(repairs+[i for i in found.get('message_ids',[]) if i not in seen]))[:30]
    known=[a for a in workspace.get_meta('applications',[]) if identity_valid(a)]
    candidates=[]
    # Inspect headers before reading bodies, excluding non-employment applications.
    for message_id in pending:
        meta=workspace.bridge.call('gmail.read_email',{'message_id':message_id,'format':'metadata'})
        meta=meta.get('message',meta)
        if candidate_metadata(meta,known):
            candidates.append(message_id)
        else:
            seen.add(message_id)
    events=[]
    rejected_repairs=set(repairs)-set(candidates)
    for old in old_events:
        if old['message_id'] in rejected_repairs:
            events.append({**old,'needs_review':True,'parser_version':PARSER_VERSION,'review_reason':'Re-read metadata did not confirm employment context. Original evidence retained.','summary':'Earlier classification needs review.'})
    repaired.update(rejected_repairs)
    if candidates:
        result=workspace.bridge.call('gmail.batch_read_email',{'message_ids':candidates})
        messages=result.get('responses',result.get('messages',[]))
        if {m.get('message',m).get('id') for m in messages}!=set(candidates) or len(messages)!=len(candidates):
            raise ValueError('Gmail application readback was incomplete; tracking remains pending')
        for message in messages:
            event=parse_application(message,known)
            if event:
                events.append(event)
            seen.add(message.get('message',message)['id'])
        # Gmail commonly returns a follow-up before its original receipt.
        # Resolve identities from observed receipts in this same batch, too.
        identities = rebuild_applications({e['message_id']:e for e in workspace.get_meta('application_events', []) + events}.values())
        events = [e for e in events if e['message_id'] in rejected_repairs] + [event for message in messages if (event := parse_application(message, identities))]
        parsed_ids={e['message_id'] for e in events}
        for old in old_events:
            if old['message_id'] in candidates and old['message_id'] not in parsed_ids:
                events.append({**old,'needs_review':True,'parser_version':PARSER_VERSION,'review_reason':'Re-read did not confirm the earlier status. Original evidence retained for review.','summary':'Earlier classification needs review.'})
    repaired.update(candidates)
    report=ingest_events(workspace,events)
    workspace.set_meta('application_parser_v2_checked',sorted(repaired))
    workspace.set_meta('application_mail_seen',sorted(seen))
    report.update(at=utcnow(),lookback_days=365,headers_checked=len(pending),bodies_read=len(candidates),
                  more_available=bool(found.get('next_page_token')) or any(i not in seen for i in found.get('message_ids',[])))
    workspace.set_meta('application_sync',report)
    return report


def sync_applications(workspace):
    # Serialize checks on this workspace; never mutate Gmail labels or messages.
    with _SYNC_LOCK_GUARD:
        if not hasattr(workspace,'_application_sync_lock'): workspace._application_sync_lock=threading.Lock()
    if not workspace._application_sync_lock.acquire(blocking=False): raise ValueError('An application check is already running')
    try: return _sync_applications(workspace)
    finally: workspace._application_sync_lock.release()
