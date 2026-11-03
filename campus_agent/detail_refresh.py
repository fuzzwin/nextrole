"""Persistent, paced reads of incomplete saved adverts. No delivery actions."""
from __future__ import annotations

import re
import json
import hashlib
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

from .fit import VERSION

KEY = 'saved_detail_refresh'
MAX_ATTEMPTS = 2
RETRY_SECONDS = 24 * 60 * 60
HOST_DELAY = 20


def fresh_state():
    return {'enabled': False, 'items': {}, 'hosts': {}, 'current': None,
            'error': '', 'updated_at': 0}


def source_host(url):
    host=(urlsplit(url).hostname or '').lower().removeprefix('www.')
    return 'linkedin.com' if host=='linkedin.com' or host.endswith('.linkedin.com') else host


def source_context(row):
    payload=row.get('job') or json.loads(row['payload'])
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()+':'+VERSION


class DetailRefreshQueue:
    def __init__(self, workspace, clock=time.time):
        self.workspace, self.clock = workspace, clock
        self.state_lock = threading.RLock()
        self.worker_lock = threading.Lock()
        # A crashed read is reconciled against the current saved row before retry.
        state = self._state()
        if state.get('current'):
            item=state['items'].get(state['current']['id'])
            if item:
                item.update(status='needs_source',message='The app stopped during this read; completion is unknown.',next_attempt=max(item['next_attempt'],self.clock()+HOST_DELAY))
            state['current'] = None
            self._save(state)

    def _state(self):
        return self.workspace.get_meta(KEY, fresh_state())

    def _save(self, state):
        state['updated_at'] = self.clock()
        self.workspace.set_meta(KEY, state)

    def _reconcile(self, state, rows):
        present = {r['id']: r for r in rows}
        for job_id, item in state['items'].items():
            row = present.get(job_id)
            if not row or row.get('stage') in {'applied', 'archived'}:
                item['status'] = 'skipped'
            elif row['fit']['assessment_state'] == 'closed':
                item['status'] = 'closed'
            elif row['fit']['assessment_state'] == 'assessed':
                item['status'] = 'assessed'
        for row in sorted(rows, key=lambda r:r.get('seen_at',''), reverse=True):
            if (row.get('stage') in {'applied','archived'} or row['listing']['closed']
                or row['fit']['assessment_state'] != 'incomplete'):
                continue
            job_id, context = row['id'], source_context(row)
            previous = state['items'].get(job_id)
            if previous and previous['context'] == context:
                if previous['status']=='skipped':
                    previous['status']='needs_source' if previous['attempts'] else 'queued'
                continue
            item = {'context': context, 'attempts': 0, 'status': 'queued',
                    'next_attempt': 0, 'message': '', 'title': row['job']['title'],
                    'host': source_host(row['job']['url'])}
            source = row.get('assessment_source') or {}
            if source.get('revision') == row['revision'] and source.get('version') == VERSION:
                try: attempted = datetime.fromisoformat(source.get('at','').replace('Z','+00:00')).timestamp()
                except (ValueError, TypeError): attempted = 0
                if attempted and source.get('status') in {'blocked','needs_source'}:
                    item.update(attempts=1, next_attempt=attempted + RETRY_SECONDS,
                                status='needs_source', message=source.get('message',''))
            # Directory URLs and already verified mixed adverts cannot supply this role.
            notice = row['fit'].get('assessment_notice','')
            if row['fit'].get('source_state') == 'search_results' or re.search(
                r'(?i)description combines|requirements cannot be reliably assigned|contains unrelated roles',notice):
                item.update(status='held', message=notice, next_attempt=0)
            state['items'][job_id] = item

    def start(self):
        with self.state_lock:
            state = self._state()
            self._reconcile(state, self.workspace.jobs())
            state.update(enabled=True, error='')
            self._save(state)
        return self.summary()

    def pause(self):
        with self.state_lock:
            state = self._state()
            state['enabled'] = False
            self._save(state)
        return self.summary()

    def summary(self):
        with self.state_lock:
            state = self._state()
            items = list(state['items'].values())
            current = state.get('current')
            waiting = [i for i in items if i['status'] in {'queued','needs_source'} and i['attempts'] < MAX_ATTEMPTS]
            next_at = min((max(i['next_attempt'], state['hosts'].get(i['host'],0)) for i in waiting), default=None)
            phase = ('pausing' if current and not state['enabled'] else 'reading' if current else
                     'needs_connection' if state.get('error') else 'paused' if not state['enabled'] else
                     'waiting' if waiting and next_at > self.clock() else 'queued' if waiting else 'finished')
            return {'enabled': state['enabled'], 'phase': phase, 'current': current,
                    'total': len(items), 'checked': sum(i['attempts'] > 0 or i['status'] in {'held','assessed','closed','skipped'} for i in items),
                    'assessed': sum(i['status']=='assessed' for i in items),
                    'closed': sum(i['status']=='closed' for i in items),
                    'needs_source': sum(i['status'] in {'needs_source','held'} for i in items),
                    'waiting': len(waiting), 'next_attempt': next_at, 'error': state.get('error','')}

    def run_batch(self, limit=3):
        if not self.worker_lock.acquire(blocking=False):
            return self.summary()
        try:
            # Existing explicit searches/batches retain priority over background reads.
            if self.workspace.scan_lock.locked() or self.workspace.batch_lock.locked():
                return self.summary()
            for _ in range(limit):
                if self.workspace.stop_event.is_set(): break
                if self.workspace.scan_lock.locked() or self.workspace.batch_lock.locked(): break
                with self.state_lock:
                    state = self._state()
                    if not state['enabled']: break
                    rows = self.workspace.jobs()
                    self._reconcile(state, rows)
                    now = self.clock()
                    candidates = [(job_id,item) for job_id,item in state['items'].items()
                                  if item['status'] in {'queued','needs_source'} and item['attempts'] < MAX_ATTEMPTS
                                  and item['next_attempt'] <= now and state['hosts'].get(item['host'],0) <= now]
                    if not candidates:
                        self._save(state)
                        break
                    job_id, item = candidates[0]
                    row = next(r for r in rows if r['id']==job_id)
                    attempted_context=source_context(row)
                    state['current'] = {'id':job_id,'title':item['title']}
                    item['attempts'] += 1
                    item['next_attempt'] = now + RETRY_SECONDS
                    state['hosts'][item['host']] = now + HOST_DELAY
                    self._save(state)
                outcome, message, connection_error, saved_hash = 'needs_source', '', False, None
                try:
                    saved = self.workspace.hydrate(job_id)
                    saved_hash=saved.get('source_hash')
                    updated = next(r for r in self.workspace.jobs() if r['id']==job_id)
                    outcome = 'edited' if saved.get('revision') and saved['revision']!=updated['revision'] else updated['fit']['assessment_state']
                    if outcome not in {'assessed','closed','edited'}: outcome = 'needs_source'
                    message = updated['fit'].get('assessment_notice','')
                except Exception as exc:
                    from .workspace import ReadInProgress, SourceChanged
                    if isinstance(exc, ReadInProgress): outcome = 'busy'
                    elif isinstance(exc, SourceChanged): outcome = 'edited'
                    message = str(exc)[:500]
                    connection_error = bool(re.search(r'(?i)reconnect|not connected|authentication|not signed in|connector process|approval required|tool not found',message))
                with self.state_lock:
                    state = self._state()  # Preserve a Pause received during network I/O.
                    item = state['items'][job_id]
                    current_row, _ = self.workspace.job(job_id)
                    changed_after_read=(saved_hash!=hashlib.sha256(current_row['payload'].encode()).hexdigest()
                                        if saved_hash else source_context(current_row)!=attempted_context)
                    if outcome in {'busy','edited'} or changed_after_read:
                        item.update(status='queued', attempts=max(0,item['attempts']-(outcome=='busy')), next_attempt=self.clock()+HOST_DELAY)
                    else:
                        item.update(status=outcome, message=message)
                        # Successful reads may change the source revision, including incomplete ones.
                        item['context'] = source_context(current_row)
                    if re.search(r'(?i)429|rate.limit|too many requests',message):
                        state['hosts'][item['host']] = self.clock() + 15*60
                    if connection_error:
                        item.update(status='queued', attempts=max(0,item['attempts']-1), next_attempt=0)
                        state.update(enabled=False, error=message)
                    state['current'] = None
                    self._save(state)
                if connection_error: break
            return self.summary()
        finally:
            self.worker_lock.release()
