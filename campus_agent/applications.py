"""Evidence-backed application tracking. Email bodies are data, never instructions."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from .models import utcnow

APPLICATION_QUERY = ('newer_than:365d -in:trash -in:spam -from:me '
    '-subject:"Job Agent" -subject:"Standout job" '
    '{subject:application subject:"interview invitation" subject:"your interview" '
    '"received your application" "thank you for applying" "thanks for applying"}')
ATS = r'myworkday\.com|greenhouse(?:-mail)?\.(?:io|com)|pageuppeople\.com|smartrecruiters\.com|lever\.co|ashbyhq\.com|teamtailor\.com|successfactors\.'


def normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.lower().replace('&', ' and ')).strip()


def application_key(company, title):
    return hashlib.sha256((normalize(company) + '|' + normalize(title)).encode()).hexdigest()


def headers(message):
    values = message.get('payload', {}).get('headers', [])
    return {h['name'].lower(): h.get('value', '') for h in values} if isinstance(values, list) else {k.lower():v for k,v in values.items()}


def candidate_metadata(message, applications=()):
    h = headers(message)
    sender, subject = h.get('from', ''), h.get('subject', '')
    if 'SENT' in message.get('label_ids', []) or re.search(r'Job Agent|Standout job', subject, re.I):
        return False
    if re.search(r'newsletter|recommendations|job alert|new jobs|rebate|registration|credit limit|financial hardship|payment|GitHub Application', sender + ' ' + subject, re.I):
        return False
    if re.search(ATS, sender, re.I) or re.search(r'careers|recruit|talent|hiring', sender, re.I):
        return True
    if re.search(r'interview invitation|your interview', subject, re.I):
        return True
    if any(normalize(a['company']) in normalize(sender + ' ' + subject) or normalize(a['title']) in normalize(subject) for a in applications):
        return True
    return bool(re.search(r'application|interview|employment offer', subject, re.I) and
                re.search(r'\b(?:IT|AI|automation|project|systems|delivery|business analyst|engineer|developer|specialist|consultant)\b', subject, re.I))


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
    for pattern, source in [
        (r'(?:application with|interest in)\s+(.+?)[!,.]?(?:$|\n)',subject),
        (r'^(.+?)\s*[-–—]\s*Application Received',subject),
        (r'work with us at\s+([^!\n]+)',text),
        (r'interest in\s+([^,\n]+)',text),
    ]:
        match = re.search(pattern, source, re.I)
        if match:
            company = match[1].strip(' !.,')
            break
    for pattern, source in [
        (r'following position:\s*(?:[A-Z]-?\d+\s*[-–—]\s*)?([^\n.]+)',text),
        (r'position of\s+([^\n.]+)',text),
        (r'application for (?:our |the )?(.+?) role\b',compact),
        (r'application for\s+(.+)$',subject),
    ]:
        match = re.search(pattern, source, re.I)
        if match:
            title = match[1].strip(' !.,')
            break
    # Status replies can inherit identity only from the same observed thread.
    thread = message.get('thread_id', message.get('threadId'))
    known = next((a for a in applications if thread and thread in a.get('thread_ids', [])), None)
    if known:
        company, title = company or known['company'], title or known['title']
    status = None
    evidence = None
    signals = [
        ('rejected', r'(?:not to move forward|not (?:be )?progressing|not been successful|application.{0,45}unsuccessful|unsuccessful.{0,45}application)'),
        ('withdrawn', r'(?:you have withdrawn|your application has been withdrawn)'),
        ('offer', r'(?:offer of employment|pleased to offer you.{0,80}(?:position|role|job))'),
        ('interview', r'(?:invite you (?:to|for).{0,80}interview|your interview (?:is|has been)|interview invitation)'),
        ('assessment', r'invite you (?:to|for).{0,80}assessment'),
        ('under_review', r'your application is (?:currently )?under review'),
        ('received', r'(?:received your application|thank you for.{0,90}application|thank you for applying|thanks for (?:your application|applying))'),
    ]
    for label, pattern in signals:
        match = re.search(pattern, subject + '\n' + compact, re.I)
        if match:
            status, evidence = label, match[0]
            break
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
            'evidence':evidence,'needs_review':not(company and title)}


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
        item.update(status=event['status'],last_update_at=event['at'],source_url=event['source_url'])
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


def sync_applications(workspace):
    found=workspace.bridge.call('gmail.search_email_ids',{'query':APPLICATION_QUERY,'max_results':100})
    seen=set(workspace.get_meta('application_mail_seen',[]))
    pending=[i for i in found.get('message_ids',[]) if i not in seen][:30]
    known=workspace.get_meta('applications',[])
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
    if candidates:
        result=workspace.bridge.call('gmail.batch_read_email',{'message_ids':candidates})
        messages=result.get('responses',result.get('messages',[]))
        if len(messages)!=len(candidates):
            raise ValueError('Gmail application readback was incomplete; tracking remains pending')
        for message in messages:
            event=parse_application(message,known)
            if event:
                events.append(event)
            seen.add(message.get('message',message)['id'])
        # Gmail commonly returns a follow-up before its original receipt.
        # Resolve identities from observed receipts in this same batch, too.
        identities = rebuild_applications(workspace.get_meta('application_events', []) + events)
        events = [event for message in messages if (event := parse_application(message, identities))]
    report=ingest_events(workspace,events)
    workspace.set_meta('application_mail_seen',sorted(seen))
    report.update(at=utcnow(),lookback_days=365,headers_checked=len(pending),bodies_read=len(candidates),
                  more_available=bool(found.get('next_page_token')) or any(i not in seen for i in found.get('message_ids',[])))
    workspace.set_meta('application_sync',report)
    return report
