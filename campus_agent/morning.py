"""Bounded discovery and own-inbox delivery; no employer submissions."""
from __future__ import annotations

import fcntl
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import Job, utcnow
from .tailor import terms


def search_queries(preferences, extended=False):
    from .role_types import query_plan
    return query_plan(preferences, extended)


def shortlist(job, profile, preferences=None):
    """Conservative rules for a review packet, never an eligibility prediction."""
    title = job.title.lower()
    text = job.description.lower()
    reasons = []
    from .role_types import matched_types
    families = matched_types(job, preferences.role_types if preferences else None)
    if not families:
        reasons.append('Role title is outside your selected role types')
    if re.search(r'\b(chief|director|head of|principal|technical lead|graduate|internship|apprentice)\b', title):
        reasons.append('Role seniority needs manual review')
    # Only the listing text counts: discovery location is a search hint, not evidence.
    if not re.search(r'\b(australia[n]?|melbourne|victoria|vic|nsw|qld|sydney|brisbane|perth|adelaide|canberra|hobart|darwin|geelong)\b', text):
        reasons.append('Australian location could not be established from the listing')
    if re.search(r'\b(no longer available|no longer accepting|position (?:has been )?(?:filled|closed)|job (?:has )?(?:expired|closed)|applications (?:have )?closed)\b', text):
        reasons.append('Listing indicates applications have closed')
    if not re.search(r'\b(apply|application|join our|hiring|recruiting)\b', text):
        reasons.append('An application invitation could not be established')
    if re.search(r'\b(nv1|nv2|baseline clearance|security clearance|australian citizen(?:ship)?|must (?:hold|have|possess).{0,60}(?:certification|degree))\b', text):
        reasons.append('Mandatory eligibility or credentials need manual confirmation')
    if job.employer in {'Employer on job listing', 'Employer in job alert', ''}:
        reasons.append('Employer name needs verification')
    reasons.extend(requirement_gaps(job, profile))
    target = terms(job.description)
    skills = [s for s in profile.skills if terms(s) and terms(s) <= target]
    facts = [b for e in profile.experience for b in e.bullets if len(terms(b) & target) >= 3]
    from .role_types import capability_evidence
    capabilities = capability_evidence(job, profile)
    facts = list(dict.fromkeys(facts + [item['fact'] for item in capabilities]))
    if (len(skills) < 2 and len(capabilities) < 2) or len(facts) < 2:
        reasons.append('Insufficient overlap with confirmed skills and experience')
    return {'selected': not reasons, 'role_types': [{'id': item['id'], 'label': item['label']} for item in families], 'reasons': reasons, 'skills': skills[:10], 'capabilities': capabilities,
            'supporting_facts': facts[:4], 'score': len(skills) * 5 + len(capabilities) * 4 + min(len(facts), 10) * 2,
            'caveat': 'Rule-based shortlist for your review; eligibility and all role requirements still need checking.'}


def requirement_gaps(job, profile):
    text = job.description.lower()
    evidence = ' '.join(profile.skills + [profile.summary] + [b for e in profile.experience for b in e.bullets]).lower()
    # Evaluate explicit requirements separately from benefits, optional skills and related-job cards.
    sections = re.split(r'(?im)^\s*(?:#+\s*)?(?:essential|must have|requirements|what you.{0,24}(?:bring|need|succeed)|qualifications|specialist/technical expertise/qualifications|what we[’\x27]re looking for|what you[’\x27]ll bring)\s*[:\n]', text)
    required = '\n'.join(re.split(r'(?im)^\s*(?:#+\s*)?(?:desirable|nice to have|preferred|benefits|what we offer|about us|why join|compensation|how to apply)\b', section)[0] for section in sections[1:])
    # Core technology in the title is also a strong requirement signal.
    target = required + '\n' + job.title.lower()
    gaps = []
    stacks = {'.NET / C#': r'(?<!\w)(?:\.net|c#)(?!\w)', 'SharePoint Framework (SPFx)': r'\bspfx\b',
              'ShareGate': r'\bshare\s?gate\b', 'Java': r'\bjava\b', 'Terraform': r'\bterraform\b',
              'Kubernetes': r'\bkubernetes\b', 'Dynamics 365': r'\bdynamics(?:\s+365)?\b',
              'Dataverse': r'\bdataverse\b', 'Azure development': r'\bazure development\b'}
    for label, pattern in stacks.items():
        if re.search(pattern, target) and not re.search(pattern, evidence):
            gaps.append('Required ' + label + ' experience is not confirmed in the résumé')
    if re.search(r'\b(?:at least\s+)?\d+\+?\s+years.{0,100}(?:experience|developer|engineer|consulting|business analysis|operations|project)', required):
        gaps.append('Required years of specialist experience need manual confirmation')
    if re.search(r'\b(?:formal tertiary qualifications|(?:degree|qualification).{0,60}(?:information systems|computer science|related discipline))\b', required):
        gaps.append('Required field of tertiary study needs manual confirmation')
    if re.search(r'\bcommercial experience as a (?:senior )?software engineer\b', required) and not any('software engineer' in e.role.lower() for e in profile.experience):
        gaps.append('Commercial software-engineering employment is not confirmed in the résumé')
    return gaps


def _sent_roles(workspace):
    with workspace.store.connect() as db:
        rows = db.execute("SELECT j.id,j.payload FROM jobs j JOIN actions a ON a.job_id=j.id WHERE a.kind='gmail_send_self' AND a.status IN ('done','running','needs_review')").fetchall()
    ids = {r[0] for r in rows}
    signatures = {signature(Job.model_validate_json(r[1])) for r in rows}
    return ids, signatures


def signature(job):
    return re.sub(r'\W+', ' ', job.title.lower()).strip(), re.sub(r'\W+', ' ', job.employer.lower()).strip()


def standout_assessment(job, profile, preferences):
    """A stricter, explainable threshold for an interruption between digests."""
    result = shortlist(job, profile, preferences)
    reasons = list(result['reasons'])
    if result['score'] < 50 or len(result['skills']) < 3 or len(result['capabilities']) < 3 or len(result['supporting_facts']) < 3:
        reasons.append('Not enough confirmed overlap for a standout alert')
    if re.search(r'\b(senior|lead|manager|architect|principal|director|head)\b', job.title, re.I):
        reasons.append('Leadership or senior specialist level needs manual review before an alert')
    city = preferences.location.split()[0]
    home_pattern = r'\b' + re.escape(city) + r'\b'
    if re.search(r'\bVictoria\b', preferences.location, re.I):
        home_pattern += r'|\b(?:Victoria|VIC)\b'
    if not (re.search(home_pattern, job.description, re.I) or
            (re.search(r'\bremote\b', job.description, re.I) and re.search(r'\baustralia\b', job.description, re.I))):
        reasons.append('Standout alerts require the preferred location or Australian remote work')
    evidence = ' '.join(profile.skills + profile.education + [profile.summary] + [b for e in profile.experience for b in e.bullets])
    required = re.split(r'(?i)about you|skills\s*&\s*experience|requirements', job.description, maxsplit=1)
    if len(required) > 1:
        required = re.split(r'(?i)desirable|nice to have|benefits|why join|what we offer', required[1], maxsplit=1)[0]
        for tool in ['Jira', 'Confluence', 'Dataverse', 'Dynamics 365', 'Terraform', 'Kubernetes']:
            if re.search(r'\b' + re.escape(tool) + r'\b', required, re.I) and not re.search(r'\b' + re.escape(tool) + r'\b', evidence, re.I):
                reasons.append('Required ' + tool + ' experience needs confirmation before a standout alert')
        if re.search(r'relevant tertiary qualifications', required, re.I):
            reasons.append('Relevance of tertiary qualifications needs confirmation before a standout alert')
    result.update(selected=not reasons, reasons=list(dict.fromkeys(reasons)), standout=True)
    return result


def run_morning(workspace, extended=False, now=None, session='morning'):
    if session not in {'morning', 'afternoon', 'standout'}:
        raise ValueError('Unknown email check session')
    prefs = workspace.preferences
    if not prefs.morning_enabled or not prefs.morning_recipient:
        raise ValueError('Morning emails are paused. Enable them in Search settings.')
    if session == 'standout' and not prefs.standout_enabled:
        raise ValueError('Standout alerts are paused. Enable them in Search settings.')
    if not workspace.profile or workspace.profile.is_example:
        raise ValueError('A confirmed résumé profile is required')
    # A process lock also protects against simultaneous standalone and dashboard runs.
    with (workspace.data / 'morning.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('A morning run is already active') from None
        local_now = (now or datetime.now(ZoneInfo(prefs.timezone))).astimezone(ZoneInfo(prefs.timezone))
        date = local_now.date().isoformat()
        slot = local_now.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H') if session == 'standout' else date
        key = session + ':' + slot
        existing = workspace.get_meta(key)
        if existing:
            if existing['status'] == 'done':
                return {**existing, 'already_done': True}
            raise ValueError('Today’s run was interrupted or needs review. Inspect Activity and Gmail before resolving; it will not automatically repeat.')
        account = workspace.require_account('gmail')
        if account['email'].lower() != prefs.morning_recipient.lower():
            raise ValueError('The connected Gmail account differs from the authorized morning recipient')
        report = {'date': date, 'session': session, 'at': utcnow(), 'status': 'running', 'extended': extended,
                  'recipient': account['email'], 'packets': [], 'skipped': [], 'errors': []}
        workspace.set_meta(key, report)
        workspace.set_meta('last_morning', report)
        def persist():
            workspace.set_meta(key, report)
            workspace.set_meta('last_morning', report)
        try:
            if prefs.application_sync_enabled:
                report['applications'] = workspace.sync_applications()
                persist()
            report['search'] = workspace.discover(extended=extended)
            # Alerts supplement public discovery; unrelated email is never read.
            try:
                found = workspace.alerts()
                ids = found.get('message_ids', [])[:6 if extended else 3]
                report['alerts_read'] = len(ids)
                for message_id in ids:
                    for link in workspace.read_alert(message_id)['links']:
                        workspace.add_job(Job(source_id='opportunity', **link['job']))
            except Exception as exc:
                report['errors'].append('Job alerts: ' + str(exc)[:300])
            sent_ids, sent_signatures = _sent_roles(workspace)
            candidates = [r for r in workspace.jobs() if r.get('stage') not in {'archived', 'applied'} and r['id'] not in sent_ids]
            candidates.sort(key=lambda r: (workspace.get_meta('listing_checked:' + r['id'], ''), -r['score']))
            from .role_types import spread_candidates, BY_ID
            candidates = spread_candidates(candidates, prefs.role_types)
            report['role_types'] = [BY_ID[item]['label'] for item in prefs.role_types]
            eligible = []
            from .role_types import EXTENDED_LISTING_LIMIT, DAILY_LISTING_LIMIT
            report['listing_limit'] = EXTENDED_LISTING_LIMIT if extended else DAILY_LISTING_LIMIT
            for row in candidates[:report['listing_limit']]:
                job_id = row['id']
                workspace.set_meta('listing_checked:' + job_id, utcnow())
                try:
                    workspace.hydrate(job_id)  # Refresh even previously read listings before sending.
                    _, job = workspace.job(job_id)
                    assessment = standout_assessment(job, workspace.profile, prefs) if session == 'standout' else shortlist(job, workspace.profile, prefs)
                    workspace.set_meta('shortlist:' + job_id, assessment)
                    if assessment['selected'] and signature(job) not in sent_signatures:
                        eligible.append((assessment['score'], job_id, job))
                    else:
                        report['skipped'].append({'title': job.title, 'reasons': assessment['reasons'] or ['Equivalent role already emailed']})
                except Exception as exc:
                    report['skipped'].append({'title': row['job']['title'], 'reasons': [str(exc)[:300]]})
            report['listings_checked'] = min(len(candidates), report['listing_limit'])
            report['shortlisted'] = len(eligible)
            for _, job_id, job in sorted(eligible, key=lambda item: -item[0]):
                if len(report['packets']) >= (1 if session == 'standout' else prefs.morning_max_packets):
                    break
                if signature(job) in sent_signatures:
                    continue
                try:
                    workspace.prepare(job_id)
                    # Sending to the user's inbox is authorized by this routine; employer submission is separate.
                    sent = workspace.gmail_packet(job_id, send=True, standout=session == 'standout')
                    packet = {'job_id': job_id, 'title': job.title, 'employer': job.employer, 'url': str(job.url), 'email': sent}
                    report['packets'].append(packet)
                    sent_signatures.add(signature(job))
                    persist()  # Preserve delivery acknowledgement before optional Drive writes.
                    if prefs.morning_save_drive:
                        packet['drive'] = {kind: workspace.upload(job_id, kind) for kind in ('resume', 'cover')}
                    persist()
                except Exception as exc:
                    report['errors'].append(job.title + ': ' + str(exc)[:400])
                    persist()
            # Standout checks stay silent when nothing qualifies; the packet is the alert.
            if session == 'standout':
                report.update(status='done', finished_at=utcnow(), quiet=not report['packets'])
                persist()
                return report
            # Each digest receipt also explains checks with no verifiable new matches.
            lines = [f'Job Agent {session} check — {date}',
                     f'{len(report["packets"])} tailored packet(s) emailed separately for your review.',
                     f'{report["search"]["found"]} public leads; {report["listings_checked"]} listings checked; {report["shortlisted"]} rule-based matches.',
                     'Review accuracy, eligibility and requirements before applying. No applications have been submitted.',
                     'Search coverage: ' + ('extended (up to 24 queries / 32 listing checks)' if extended else 'daily (up to 10 queries / 12 listing checks)'),
                     'Public indexed listings and configured Gmail job alerts only. Blocked, private and unindexed roles may be missed.']
            lines += ['Search areas: ' + ', '.join(report['role_types'])]
            if report.get('applications'):
                tracking = report['applications']
                lines += [f'Application tracker: {len(tracking["applications"])} recorded; {tracking["new_events"]} new email updates.']
                lines += [a['company']+' — '+a['title']+': '+a['status']+'; '+a['source_url'] for a in tracking['applications']]
            lines += [p['title'] + ' — ' + p['employer'] + ': ' + p['url'] for p in report['packets']]
            lines += ['Skipped: ' + s['title'] + ' — ' + '; '.join(s['reasons']) for s in report['skipped']]
            lines += ['Issue: ' + e for e in report['errors'] + report['search'].get('errors', [])]
            report['summary_pending'] = True
            persist()
            summary = workspace.bridge.call('gmail.send_email', {
                'to': account['email'], 'subject': f'Job Agent {session} check: {date} — {len(report["packets"])} packets',
                'payload': {'mime_type': 'text/plain', 'charset': 'utf-8', 'body': {'content': '\n\n'.join(lines)}},
                'response_fields': ['id']})
            if not summary.get('id'):
                raise ValueError('Gmail did not acknowledge the morning summary; inspect Sent before retrying')
            report.update(status='done', summary_id=summary['id'], summary_pending=False, finished_at=utcnow())
            persist()
            return report
        except Exception as exc:
            report.update(status='needs_review', error=str(exc)[:500])
            persist()
            raise


def run_command(directory, extended=False, port=8877, session='morning'):
    """Use an existing server; otherwise run directly without opening a browser."""
    import httpx
    import time
    from .workspace import Workspace
    directory = directory.resolve()
    origin = f'http://127.0.0.1:{port}'
    with httpx.Client(timeout=15, trust_env=False) as client:
        try:
            response = client.get(origin + '/api/state')
        except httpx.ConnectError:
            response = None
        if response is not None:
            response.raise_for_status()
            state = response.json()
            if state.get('kind') != 'job-workspace' or state.get('path') != str(directory):
                raise ValueError('Port is occupied by another workspace')
            page = client.get(origin + '/')
            page.raise_for_status()
            token = re.search(r'const token="([^"]+)"', page.text)
            if not token:
                raise ValueError('Workspace authorization token missing')
            reply = client.post(origin + '/api/morning', headers={'origin': origin, 'x-workspace-token': token[1]}, json={'extended': extended, 'session': session})
            reply.raise_for_status()
            task_id = reply.json()['task_id']
            deadline = time.monotonic() + 1800
            while time.monotonic() < deadline:
                state = client.get(origin + '/api/state').json()
                task = next((t for t in state['activity']['tasks'] if t['id'] == task_id), None)
                if task and task['status'] != 'running':
                    if task['status'] != 'done':
                        raise ValueError(task['error'])
                    return task['result']
                time.sleep(2)
            raise TimeoutError('Morning run still active; inspect Activity before retrying')
    workspace = Workspace(directory, recover=False)
    try:
        return run_morning(workspace, extended=extended, session=session)
    finally:
        workspace.close()
