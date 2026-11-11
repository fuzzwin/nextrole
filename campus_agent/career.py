"""Private, bounded career research and extractive interview preparation.

Generic validation/render contracts adapted from the supplied Career Opportunity
Harness. Structural checks are not semantic or employer verification.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from .career_contract import FRAMEWORKS, interview
from .career_research import GAP_QUESTIONS, research, role_matrix, technology_passages
from .career_render import RESEARCH_AREAS, render, check_references, check_decision
from .career_technology import add_candidate_technology, technology_lines, technology_rows

TERMINAL = {'ready_for_review', 'failed', 'cancelled', 'budget_exhausted'}
VERSION = 'career-1.4.0'

def now(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
def digest(value): return hashlib.sha256(encoded(value).encode()).hexdigest()
def public_url(value):
    from .source_policy import source_exclusion
    if source_exclusion(value): return ''
    try:
        from ipaddress import ip_address
        p = urlsplit(str(value)); host = p.hostname or ''
        if p.scheme != 'https' or p.username or p.password or not host or host in {'localhost'} or host.endswith(('.local','.localhost')): return ''
        try:
            if not ip_address(host).is_global: return ''
        except ValueError: pass
        from .workspace import public_listing_url
        return public_listing_url(str(value))
    except ValueError: return ''

def readable_public_url(value):
    url = public_url(value)
    if not url:
        return ''
    original = urlsplit(value)
    if (original.hostname or '').endswith('.linkedin.com'):
        regional = original._replace(query='', fragment='').geturl()
        if public_url(regional) == url:
            return regional
    return url


def research_sources(response):
    """Extract source-owned fields/blocks; never attribute neighbouring text."""
    found=[]; texts=[]
    def walk(node):
        if isinstance(node,dict):
            url=public_url(node.get('url') or node.get('link') or '')
            if url:
                excerpt=next((node[k] for k in ('snippet','excerpt','description','text','content') if isinstance(node.get(k),str)), '')
                found.append({'url':url,'label':str(node.get('title') or node.get('label') or url),'excerpt':excerpt[:3500]})
                return
            for value in node.values(): walk(value)
        elif isinstance(node,list):
            for value in node: walk(value)
        elif isinstance(node,str): texts.append(node)
    walk(response)
    heading=re.compile(r'(?m)^([^\n]+?)\s*\((https://[^\s)]+)\)')
    for text in texts:
        blocks=list(heading.finditer(text))
        for i,match in enumerate(blocks):
            url=public_url(match[2])
            if url:
                end=blocks[i+1].start() if i+1<len(blocks) else len(text)
                found.append({'url':url,'label':match[1].strip(),'excerpt':text[match.end():end].strip()[:3500]})
        if not blocks:
            # URL-only leads have no attributable excerpt.
            for url in re.findall(r'https://[^\s<>"\\)\]]+',text):
                url=public_url(url)
                if url: found.append({'url':url,'label':url,'excerpt':'No source-specific readable excerpt returned.'})
    unique={}
    for source in found: unique.setdefault(source['url'],source)
    return list(unique.values())[:8]

def _criterion_text(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def _research_fit(row, reviewed, legacy, facts):
    item = reviewed or legacy or {}
    by_text = {text: ref for ref, text in facts}
    matches = [by_text[evidence['text']] for evidence in item.get('evidence', [])
               if isinstance(evidence, dict) and evidence.get('text') in by_text]
    state = item.get('evidence_state')
    level = 'Gap'
    label = 'Evidence unconfirmed'
    detail = 'Look for a specific example with your contribution and outcome.'
    if state == 'confirmed_gap' and matches:
        label = 'Confirmed gap'
        detail = item.get('transfer_reason') or 'The saved review marks a gap.'
    elif matches and state != 'unknown':
        level = 'Direct' if state == 'direct' or (not reviewed and item.get('value')==1) else 'Transferable'
        label = {'strong_transfer':'Strong transfer','partial_transfer':'Partial transfer','foundation':'Foundation'}.get(state,level)
        detail = item.get('transfer_reason') or 'Review the saved example and its scope.'
    return {'requirement': row['quote'], 'level': level, 'label': label, 'detail': detail,
            'sources': list(dict.fromkeys(['advert', *matches])), 'category': row['category']}


class CareerService:
    def __init__(self, workspace, recover=True):
        self.workspace = workspace
        self.owner = digest(str(workspace.root.resolve()))
        self.path = workspace.data / 'career.db'
        self.directory = workspace.artifacts / 'career'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='career')
        self.calls = ThreadPoolExecutor(max_workers=2, thread_name_prefix='career-web')
        self.closed = threading.Event()
        self.artifact_lock = threading.RLock()
        self.dispatch_lock = threading.RLock()
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, owner TEXT NOT NULL, job_id TEXT NOT NULL, cache_key TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, data TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS career_cache ON runs(owner,cache_key,status)')
            db.execute('CREATE TABLE IF NOT EXISTS practice (id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL)')
            if recover:
                for rid, data in db.execute("SELECT id,data FROM runs WHERE owner=? AND status IN ('queued','running')", (self.owner,)).fetchall():
                    r = json.loads(data); r.update(status='cancelled', updated_at=now(), error='Interrupted when the app stopped. Start again to continue.')
                    db.execute('UPDATE runs SET status=?,data=? WHERE id=?', ('cancelled',encoded(r),rid))
    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db: yield db
        finally: db.close()
    def _read(self, db, rid):
        row = db.execute('SELECT data FROM runs WHERE id=? AND owner=?',(rid,self.owner)).fetchone()
        if not row: raise ValueError('Career run not found')
        return json.loads(row[0])
    def get(self, rid):
        with self._db() as db: return self._read(db,rid)
    def list(self, job_id):
        with self._db() as db:
            return [json.loads(x[0]) for x in db.execute('SELECT data FROM runs WHERE owner=? AND job_id=? ORDER BY created DESC',(self.owner,job_id))]
    def _update(self, rid, **changes):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE'); r=self._read(db,rid)
            if r['status'] in TERMINAL: return r
            r.update(changes,updated_at=now())
            db.execute('UPDATE runs SET status=?,data=? WHERE id=? AND owner=?',(r['status'],encoded(r),rid,self.owner))
            return r
    def start(self, job_id, feature, options=None, refresh=False):
        if self.closed.is_set(): raise ValueError('Career service is stopping')
        if feature not in {'deep_research','interview_prep'}: raise ValueError('Unknown career feature')
        o=dict(options or {})
        if set(o)-{'stage','frameworks','max_web_calls','max_seconds','scope','preparation_minutes','communication_preferences','technology_links','company_links','alternate_vacancy_url'}: raise ValueError('Unsupported career options')
        scope=o.get('scope',['employer','role','pay'])
        if not isinstance(scope,list) or not scope or any(x not in {'employer','role','pay'} for x in scope): raise ValueError('Invalid research scope')
        minutes=o.get('preparation_minutes',30)
        if type(minutes) is not int or not 5<=minutes<=240: raise ValueError('Preparation time must be 5–240 minutes')
        preferences=o.get('communication_preferences','')
        if not isinstance(preferences,str) or len(preferences)>500: raise ValueError('Communication preferences must be under 500 characters')
        links=o.get('technology_links', [])
        if not isinstance(links,list) or len(links)>3 or any(not isinstance(link,str) or len(link)>1500 for link in links):
            raise ValueError('Enter up to three public technology evidence links.')
        if links and (feature!='deep_research' or 'role' not in scope):
            raise ValueError('Select Role & fit in Deep Research to check technology links.')
        public_links=[readable_public_url(link.strip()) for link in links]
        if any(not url for url in public_links):
            raise ValueError('Technology evidence links need an allowed public HTTPS address.')
        o['technology_links']=list(dict.fromkeys(public_links))
        company_links=o.get('company_links',[])
        if not isinstance(company_links,list) or len(company_links)>3:
            raise ValueError('Enter up to three official employer links.')
        if company_links and (feature!='deep_research' or 'employer' not in scope):
            raise ValueError('Select Employer in Deep Research to check employer links.')
        checked_links=[]
        for link in company_links:
            if (not isinstance(link,dict) or set(link)!={'url','focus'} or not isinstance(link['url'],str)
                or len(link['url'])>1500 or not isinstance(link['focus'],str) or len(link['focus'])>100):
                raise ValueError('Each employer link needs a public URL and an optional short phrase.')
            url=readable_public_url(link['url'].strip())
            if not url:
                raise ValueError('Employer evidence links need an allowed public HTTPS address.')
            value={'url':url,'focus':link['focus'].strip()}
            if value not in checked_links:
                checked_links.append(value)
        o['company_links']=checked_links
        alternate=o.get('alternate_vacancy_url') or ''
        if not isinstance(alternate,str) or len(alternate)>1500:
            raise ValueError('Enter a public URL for another copy of the vacancy.')
        if alternate and (feature!='deep_research' or 'role' not in scope):
            raise ValueError('Select Role & fit in Deep Research to check another vacancy link.')
        o['alternate_vacancy_url']=readable_public_url(alternate.strip()) if alternate.strip() else None
        if alternate.strip() and not o['alternate_vacancy_url']:
            raise ValueError('The alternate vacancy needs an allowed public HTTPS address.')
        o.update(scope=scope,preparation_minutes=minutes,communication_preferences=preferences)
        stage=o.get('stage','unknown')
        if stage not in {'unknown','recruiter','hiring_manager','panel','technical','practical'}: raise ValueError('Unknown interview stage')
        names=o.get('frameworks',['ICAN+','CAR','Approach'])
        if not isinstance(names,list) or not names: raise ValueError('Choose at least one framework')
        names=[x.replace('Present-Past-Future','Present–Past–Future') for x in names if isinstance(x,str)]
        if not names or len(names)!=len(set(names)) or any(x not in FRAMEWORKS for x in names): raise ValueError('Unknown or duplicate framework')
        for key, default, upper in [('max_web_calls',8,12),('max_seconds',180,300)]:
            v=o.get(key,default)
            if type(v) is not int or not 1 <= v <= upper: raise ValueError(f'Invalid {key}')
            o[key]=v
        o.update(stage=stage,frameworks=names)
        row,job=self.workspace.job(job_id)
        from .source_policy import require_allowed_source
        if not row or job is None: raise ValueError('Saved role not found')
        require_allowed_source(job.model_dump(mode='json')['url'])
        # Only the current candidate, never examples, mail, referees or credentials.
        profile=self.workspace.profile.model_dump()
        profile={k:profile.get(k) for k in ('summary','headline','skills','education','experience','is_example','credentials','availability','technical_projects')}
        if profile.get('is_example'): raise ValueError('Replace the example profile before preparing career material')
        enriched = next((x for x in self.workspace.jobs() if x['id']==job_id), {}) if hasattr(self.workspace,'jobs') else {}
        snapshot={'details':{k:enriched.get(k) for k in ('reading_view','location_info','listing','fit')},'job':job.model_dump(mode='json'),'profile':profile,'job_revision':row.get('revision',''),'captured_at':now()}
        reviewed=(enriched.get('evidence_comparison') or {}).get('reviewed') or {}
        snapshot['details']['reviewed_requirements']=reviewed.get('requirements', [])
        if feature=='interview_prep':
            recent=[x for x in self.list(job_id)
                    if x['feature']=='deep_research' and x['status']=='ready_for_review'
                    and x['snapshot']['job']==snapshot['job'] and x['snapshot']['profile']==profile
                    and time.time()-datetime.fromisoformat(x['created_at']).timestamp()<86400]
            prior=next((x for x in recent if x['result'].get('quality',{}).get('export_ready')
                        and 'employer' in x['options']['scope']),None)
            checked_stack=next((x for x in recent if x['result'].get('validation',{}).get('passed')
                                and any(row['scope'] in {'related','company'}
                                        for row in x['result']['assessment'].get('technology',[]))),None)
            if prior:
                snapshot['research']={'run_id':prior['id'],'output_hash':prior['output_hash'],'review':prior['review'],
                                      'sources':prior['result']['sources'],'claims':prior['result']['assessment']['claims'],
                                      'gaps':prior['result']['quality']['gaps']}
            if checked_stack:
                research_snapshot=snapshot.setdefault('research',{'sources':{}})
                research_snapshot['technology_run_id']=checked_stack['id']
                research_snapshot['technology']=checked_stack['result']['assessment']['technology']
                research_snapshot['sources'].update(
                    {ref:src for ref,src in checked_stack['result']['sources'].items() if ref.startswith('technology_')}
                )
        key=digest({'owner':self.owner,'job_id':job_id,'job':snapshot['job'],'details':snapshot['details'],'research':snapshot.get('research'),'profile':profile,'feature':feature,'options':o,'version':VERSION})
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute("SELECT data FROM runs WHERE owner=? AND cache_key=? AND status IN ('queued','running','ready_for_review') ORDER BY created DESC",(self.owner,key)).fetchall()
            for (data,) in existing:
                previous=json.loads(data)
                active=previous['status'] in {'queued','running'}
                fresh=time.time()-datetime.fromisoformat(previous['created_at']).timestamp()<86400
                if active or (not refresh and fresh and previous['result'].get('quality', {}).get('export_ready')): return {'run_id':previous['id'],'cached':not active,'reused':True}
            rid=uuid.uuid4().hex
            r={'id':rid,'run_id':rid,'job_id':job_id,'feature':feature,'status':'queued','created_at':now(),'updated_at':now(),'snapshot':snapshot,'options':o,'version':VERSION,'progress':{'message':'Queued','completed':0,'total':o['max_web_calls'] if feature=='deep_research' else 1},'usage':{'input_tokens':None,'cached_input_tokens':None,'output_tokens':None,'cost_aud':None,'credits':None,'web_calls':0,'web_calls_definition':'Reserved attempts; an attempt cancelled before dispatch may be included.','budget_mode':'call-and-time-limited','note':'No model generation. Connected search usage and billing are not exposed.'},'result':None,'review':None}
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?,?)',(rid,self.owner,job_id,key,'queued',time.time(),encoded(r)))
        self.pool.submit(self._run,rid)
        return {'run_id':rid,'cached':False,'reused':False}
    def cancel(self,rid):
        with self.dispatch_lock: return self._update(rid,status='cancelled',error='Cancelled by you')
    def close(self):
        self.closed.set()
        with self._db() as db:
            ids=[r[0] for r in db.execute("SELECT id FROM runs WHERE owner=? AND status IN ('queued','running')",(self.owner,))]
        for rid in ids: self.cancel(rid)
        self.pool.shutdown(wait=False,cancel_futures=True); self.calls.shutdown(wait=False,cancel_futures=True)
    def _active(self,rid,deadline):
        if self.closed.is_set() or self.get(rid)['status'] in TERMINAL: raise InterruptedError('Run stopped')
        if time.monotonic() >= deadline: raise TimeoutError('Time budget exhausted')
    def _web(self,rid,args,deadline):
        self._active(rid,deadline)
        r=self.get(rid); usage=r['usage']
        if usage['web_calls'] >= r['options']['max_web_calls']: raise TimeoutError('Search budget exhausted')
        usage['web_calls']+=1; self._update(rid,usage=usage)
        def dispatch():
            with self.dispatch_lock:
                self._active(rid,deadline)
                # The operation is admitted before cancellation; results still cannot commit after cancel.
            return self.workspace.bridge.call('search_service.web_run',args)
        with self.dispatch_lock:
            self._active(rid,deadline)
            future=self.calls.submit(dispatch)
        try: result=future.result(timeout=max(.01,deadline-time.monotonic()))
        except TimeoutError: future.cancel(); raise
        self._active(rid,deadline)
        return result
    def _run(self,rid):
        r=self._update(rid,status='running'); deadline=time.monotonic()+r['options']['max_seconds']
        try:
            self._active(rid,deadline)
            observed,report,guide,questions=self._draft(r)
            quality={'export_ready':True,'verified_topics':[],'gaps':[],'blockers':[]}
            if r['feature']=='deep_research':
                quality=research(
                    observed, report, r['options']['scope'], r['options']['max_web_calls'],
                    lambda args: self._web(rid,args,deadline), research_sources,
                    lambda message,done,total: self._update(rid,progress={'message':message,'completed':done,'total':total}),
                    technology_links=r['options'].get('technology_links', []),
                    company_links=r['options'].get('company_links', []),
                    alternate_vacancy_url=r['options'].get('alternate_vacancy_url'),
                )
            add_candidate_technology(report,observed['sources'])
            brief=render(observed,report)
            errors=check_references(observed,report,brief)+check_decision(observed,report)
            if r['feature']=='interview_prep':
                try: interview(observed,report,guide)
                except (ValueError,KeyError,TypeError) as exc: errors.append(str(exc))
                brief=self._guide_markdown(observed,guide,report)+'\n\n'+brief
                quality['verified_topics']=[entry['area'] for entry in report['claims'] if entry['kind']=='confirmed']
                quality['gaps']=report.get('research_gaps',[])
            quality['blockers']+=errors
            quality['export_ready']=not quality['blockers']
            result={'mode':'extractive','limited_draft':not quality['export_ready'],'title':observed['vacancy']['title'],
                    'markdown':brief,'quick_markdown':self._quick(observed,guide,report,r['feature']),
                    'observations':observed,'assessment':report,'guide':guide,'questions':questions,'sources':observed['sources'],
                    'quality':quality,'validation':{'passed':not errors,'findings':errors,'scope':'Document structure and evidence references.'},
                    'limitations':['Public statements are attributed to their publisher. Personal examples come from your saved profile.']}
            result['output_hash']=digest(result)
            self._active(rid,deadline)
            message='Ready for your review' if quality['export_ready'] else 'Preview only · more evidence needed before export'
            self._update(rid,status='ready_for_review',result=result,output_hash=result['output_hash'],progress={'message':message,'completed':1,'total':1})
        except InterruptedError: pass
        except TimeoutError as exc: self._update(rid,status='budget_exhausted',error=str(exc))
        except Exception as exc: self._update(rid,status='failed',error=f'{type(exc).__name__}: {str(exc)[:300]}')
    def _draft(self,r):
        j=r['snapshot']['job']; p=r['snapshot']['profile']; sources={}
        details=r['snapshot'].get('details',{}); view=details.get('reading_view') or {}; location=details.get('location_info') or {}
        sources['advert']={'kind':'employer','label':'Saved vacancy text (employer claims, not independently verified)','locator':f"Frozen saved role {r['job_id']}",'url':public_url(j.get('url','')),'excerpt':str(j.get('description',''))[:20000]}
        sources['advert']['read_url']=readable_public_url(str(j.get('url','')))
        sources['application']={'kind':'application_record','label':'Application status not verified in this run','locator':'No submission check performed. Check your application records before applying.'}
        sources['profile']={'kind':'candidate','label':'Your saved profile summary','locator':'Frozen local profile summary','excerpt':str(p.get('summary') or '')}
        for key,value in r['snapshot'].get('research',{}).get('sources',{}).items():
            if key.startswith(('employer_','technology_')): sources[key]=value
        for ix,credential in enumerate(p.get('credentials') or []):
            sources[f'credential_{ix}']={'kind':'candidate','label':'Candidate-reported credential — not registry verified','locator':'Frozen saved credential record','excerpt':encoded(credential)}
        if p.get('availability'): sources['availability']={'kind':'candidate','label':'Candidate-reported availability','locator':'Frozen profile availability','excerpt':p['availability']}
        for ix,project in enumerate(p.get('technical_projects') or []):
            sources[f'project_{ix}']={'kind':'candidate','label':'Private project — not employer work','locator':'Frozen project record; stage is candidate-reported','excerpt':encoded(project)}
        facts=[]
        for ix,e in enumerate(p.get('experience') or []):
            for bi,bullet in enumerate(e.get('bullets',[])):
                if not str(bullet).strip(): continue
                ref=f'experience_{ix}_{bi}'
                sources[ref]={'kind':'candidate','label':f"{e.get('role','Role')} — {e.get('organization','Organisation')}",'locator':f"Saved experience {ix+1}, bullet {bi+1}; {e.get('dates','dates not stated')}",'excerpt':bullet}
                facts.append((ref,bullet))
        from .locations import location_info
        extracted=location_info(j, '') if not location.get('stated') else location
        place=extracted['display'] if extracted.get('stated') else str(j.get('location') or 'Not stated')
        vacancy={'id':r['job_id'],'employer':str(j.get('employer') or 'Employer unconfirmed'),'title':str(j.get('title') or 'Role unconfirmed'),'mode':location.get('arrangement') or extracted.get('arrangement') or 'Not verified','employment':next((str(x.get('value')) for x in view.get('facts',[]) if isinstance(x,dict) and x.get('label')=='Work type' and x.get('value')), 'Not verified'),'locations':[place],'source':'advert','status':'closed' if (details.get('listing') or {}).get('closed') else 'unknown','deadline':(details.get('listing') or {}).get('closes_on') or None}
        if vacancy['mode']=='Not verified' and re.search(r'\bthis is a remote (?:role|position)\b', sources['advert']['excerpt'], re.I):
            vacancy['mode']='Remote'
        if vacancy['employment']=='Not verified':
            employment=re.search(r'(?im)^[ \t]*(?:[*•-][ \t]+)?(?:#{1,6}[ \t]+)?(?:employment|work|job) type(?:[ \t]*:[ \t]*|[ \t]*(?:\n[ \t]*)+)(contract|temporary|casual|permanent|full[ -]time|part[ -]time)\b', sources['advert']['excerpt'])
            if employment:
                vacancy['employment']=employment[1].capitalize()
        observed={'checked_on':now()[:10],'vacancy':vacancy,'submission':{'status':'unconfirmed','description':'No application receipt was checked in this run.','source':'application'},'sources':sources,'employer_pay':None}
        from .listing_view import salary_info
        salary=salary_info(sources['advert']['excerpt'])
        if salary['status']=='not_stated':
            salary=view.get('salary') or {}
        if salary.get('status')=='stated' and salary.get('minimum') and salary.get('maximum') and salary.get('currency') and salary.get('period'):
            observed['employer_pay']={'low':int(salary['minimum']),'high':int(salary['maximum']),'currency':salary['currency'],'basis':'per '+str(salary['period']), 'advertised_text':salary.get('display')}
        questions=[{'id':'intro','question':'Tell me about your relevant experience for this role.','evidence':p.get('summary') or 'Add your summary.'}]
        stage_questions={'recruiter':'What are your availability, work arrangement preferences and pay expectations?','hiring_manager':'Which supported example best demonstrates delivery against this role’s priorities?','panel':'How did you work with stakeholders with different priorities?','technical':'Explain the reasoning and checks behind a technical decision you actually made.','practical':'How would you clarify and approach a practical task in this role?','unknown':'What would you like to confirm about the interview format?'}
        questions.append({'id':'stage','question':stage_questions[r['options']['stage']],'evidence':'Use confirmed personal evidence, or label a hypothetical approach clearly.'})
        cards=[]
        # Rank real statements by overlap only; never convert keywords into achievements.
        words=set(re.findall(r'\b[a-z]{4,}\b',str(j.get('description','')).lower()))
        facts.sort(key=lambda item:len(words & set(re.findall(r'\b[a-z]{4,}\b',item[1].lower()))),reverse=True)
        for n,(ref,fact) in enumerate(facts[:4]):
            action=fact.split()[0].strip(',').lower()
            spoken='I '+fact[0].lower()+fact[1:] if action.endswith(('ed','ied')) or action in {'built','led','ran','wrote','made','set','drove'} else fact
            q='How have you handled a similar task?' if n==0 else ('What did you contribute in another relevant example?' if n==1 else 'Which other example shows how you work?')
            cards.append({'kind':'past_experience','question':q,'answer':spoken,'follow_up':'What did you personally do, and what outcome can you support?','bullets':[fact,'Add only context and outcomes you can substantiate.'],'cues':['Context','My action','Evidence'],'sources':[ref]})
            questions.append({'id':f'experience_{n}','question':q,'evidence':fact})
        questions.append({'id':'proposal','question':'How would you approach your first month in this role?','evidence':'Future proposal only; do not describe it as past delivery.'})
        report={'vacancy':vacancy,'submission':observed['submission'],'employer_pay':observed['employer_pay'],'estimated_pay':None,'pay_note':'No pay benchmark was verified.','claims':[{'id':f'area_{i}','area':a,'kind':'unknown','text':f'{a} has not been verified for this employer.','sources':[],'question':GAP_QUESTIONS[a]} for i,a in enumerate(RESEARCH_AREAS)],'fit':[{'requirement':'Confirm material requirements against the original advert','level':'Gap','detail':'This extractive run does not independently assess competency or alter the saved fit score. Compare each requirement with the sourced work examples below.','sources':['advert']}],'stories':[{'label':sources[ref]['label'],'answer':fact,'cues':['Context','Action','Outcome to confirm'],'sources':[ref]} for ref,fact in facts[:4]],'action':'hold','decision':'Review the evidence and confirm vacancy and application status.','next_step':'Open the original advert and confirm requirements, closing date and whether you have already applied.','application_files':[],'pilot':'Proposed approach, not past experience: clarify the employer’s priority, agree a small safe trial, measure the agreed outcome, then decide whether to expand.','questions':['What are the most important outcomes in the first three months?','What constraints and support will shape the role?','What are the pay range, work arrangement and next hiring steps?']}
        report['technology']=[]
        if r['feature']=='interview_prep' or 'role' in r['options']['scope']:
            report['technology']=technology_rows(technology_passages(sources['advert']['excerpt'],vacancy), 'vacancy', 'advert')
        prior=r['snapshot'].get('research')
        if prior:
            if 'claims' in prior:
                report['claims']=prior['claims']
                report['research_gaps']=prior['gaps']
            report['technology'] += [row for row in prior.get('technology',[]) if row['scope'] in {'related','company'}]
        if r['feature']=='deep_research' and 'role' in r['options']['scope']:
            matrix=role_matrix(sources['advert']['excerpt'],vacancy)
            if extracted.get('evidence') not in {'Saved by you','Saved listing location'} and extracted.get('stated') and _criterion_text(str(j.get('location') or '')) not in {'',_criterion_text(place)}:
                report['saved_location_difference']=str(j['location'])
            reviewed={_criterion_text(item['quote']):item for item in details.get('reviewed_requirements',[]) if item.get('quote')}
            legacy={_criterion_text(item['text']):item for item in (details.get('fit') or {}).get('requirements',[])}
            fit=[]
            for row in matrix:
                if row['kind']!='competency' or row['importance']=='optional':
                    continue
                key=_criterion_text(row['quote'])
                fit.append(_research_fit(row, reviewed.get(key), legacy.get(key), facts))
            if fit:
                report['fit']=fit
            report['questions']=[
                'Which advertised deliverable would you prioritise in the first month, and what baseline will we use?',
                'Who does the work today, who signs off on changes, and who owns the outcome after handover?',
                'Which tools, data and decision authority would be available to the person in this role?',
                'Can you confirm the employing entity, work location, arrangement and pay basis?',
            ]
        else:
            requirements=(details.get('fit') or {}).get('requirements',[])
            if requirements:
                report['fit']=[]
                for ix,item in enumerate(requirements[:30]):
                    refs=['advert']; matched=[]
                    for ev in item.get('evidence',[]):
                        text=ev.get('text','') if isinstance(ev,dict) else str(ev)
                        ref=next((key for key,bullet in facts if text==bullet),None)
                        if ref: refs.append(ref); matched.append(text)
                    report['fit'].append({'requirement':item['text'],'level':'Direct' if matched and item.get('value')==1 else 'Transferable' if matched else 'Gap','detail':'; '.join(item.get('reasons') or []) or ('Saved matching evidence: '+'; '.join(matched) if matched else 'Needs evidence confirmation.'),'sources':refs})
                    if ix<3: questions.append({'id':f'requirement_{ix}','question':'What evidence demonstrates: '+item['text'],'evidence':'; '.join(matched) or 'No confirmed supporting example saved.'})
        fact=facts[0][1] if facts else 'No work example has been saved. Add a real example before using a past-experience answer.'
        factref=facts[0][0] if facts else 'profile'
        methods=[]
        for name in r['options']['frameworks']:
            kind='past_experience' if name in {'CAR','STAR','ICAN+'} else ('proposal' if name=='Approach' else 'positioning')
            steps=[]
            for idx,label in enumerate(FRAMEWORKS[name]):
                if kind=='proposal': content=['Clarify the employer’s goal, constraints and stakeholders.','Compare a small number of options against agreed success criteria.','Propose a bounded trial and review measured outcomes before expanding.'][idx]
                else: content=f'Saved evidence anchor: “{fact}”' if idx==1 else f'{label}: add your own confirmed detail; this detail is not established by the saved evidence.'
                steps.append([label,content])
            methods.append({'name':name,'kind':kind,'question':(cards[0]['question'] if cards else 'Describe a real work example you can support.') if name in {'CAR','STAR'} else ('How would you approach your first month in this role?' if name=='Approach' else ('Tell me about yourself and your relevant experience.' if name in {'ICAN+','Present–Past–Future'} else 'What is your view on this role’s main priority, and why?')),'cues':'Context → my actions → supported outcome','steps':steps,'sources':['advert'] if kind=='proposal' else [factref]})
        guide={'framework_sources':{},'opening':str(p.get('summary') or 'Add your own evidence-based introduction.'),'opening_sources':['profile'],'why':f"Explain your interest in {vacancy['title']} using the actual responsibilities in the saved advert. Your motivation is not inferred.",'why_sources':['advert'],'recruiter':'Confirm availability, location, work arrangement, pay expectations and the next step.','manager':'Choose a sourced example; distinguish your contribution from team outcomes.','recovery':'Pause, ask for clarification, and say when you do not know. Offer a future approach without presenting it as experience.','cards':cards,'pilot':{'kind':'proposal','sources':['advert'],'text':report['pilot']},'strategy':{'methods':methods,'defaults':r['options']['frameworks'][:3],'selection':f"Stage: {r['options']['stage']}. Use CAR/STAR for real past examples, Approach for hypothetical tasks, and PREP for a concise view.",'rehearsal':'Practise one question at a time. Speak naturally; confirm missing context and outcomes before rehearsing. Feedback is a simple local heuristic, not a hiring prediction.'}}
        if prior and 'claims' in prior:
            remit=next((claim for claim in prior['claims'] if claim['area']==RESEARCH_AREAS[-1] and claim['kind']=='confirmed'),None)
            business=next((claim for claim in prior['claims'] if claim['area']==RESEARCH_AREAS[0] and claim['kind']=='confirmed'),None)
            if remit:
                guide['why']=f"The advert describes this priority: “{remit['text']}” One example I can discuss is the work below."
            if business:
                guide['why']+=f" Company context from the employer: “{business['text']}”"
                guide['why_sources']+=business['sources']
        guide['strategy']['rehearsal'] += f" Set aside {r['options']['preparation_minutes']} minutes: review evidence first, then rehearse and check uncertain details."
        if r['options']['communication_preferences']:
            guide['strategy']['rehearsal'] += ' Your speaking preferences (self-directed): '+r['options']['communication_preferences']
        return observed,report,guide,questions
    def _guide_markdown(self,observed,guide,report):
        lines=['# Interview preparation — evidence draft','Rehearse these answers against your saved examples. Use the follow-ups to add details you can substantiate.','## Introduction',guide['opening'],'## Why this role',guide['why'],'## Answer strategy',guide['strategy']['selection'],guide['strategy']['rehearsal']]
        for card in guide['cards']: lines+=['## '+card['question'],card['answer'],'Cues: '+' → '.join(card['cues']),card['follow_up']]
        for method in guide['strategy']['methods']:
            lines+=['## '+method['name']+' — '+method['kind'],method['question']]
            lines += [f'- **{label}** {value}' for label,value in method['steps']]
        lines+=['## Questions for the employer', *['- '+question for question in report['questions']], '## When you need to clarify a question',guide['recovery']]
        for ref,source in observed['sources'].items():
            if ref.startswith(('credential_','project_')) or ref=='availability': lines += ['## '+source['label'],source['excerpt']+' ['+ref+']']
        return '\n\n'.join(lines)
    def _quick(self,observed,guide,report,feature):
        vacancy=observed['vacancy']
        title=vacancy['employer']+' — '+vacancy['title']
        claims=[claim for claim in report['claims'] if claim['kind']=='confirmed']
        if feature=='deep_research':
            lines=['# Job research brief',title]
            pay=report['employer_pay']
            lines += ['## Pay', (pay.get('advertised_text') or pay['basis']) if pay else 'Advertised pay remains unconfirmed.']
            role=report.get('role_research') or {}
            lines += ['## Job', ' · '.join([*vacancy['locations'],vacancy['mode'],vacancy['employment']]),
                      report['decision'], report['next_step']]
            lines.append('## Company')
            public=[c for c in claims if c['area']!=RESEARCH_AREAS[-1]][:2]
            if not public:
                lines.append('Company context remains open.')
            for claim in public:
                source=observed['sources'][claim['sources'][0]]
                lines += [claim['text'],f"[{source['label']}]({source['url']})"]
            if role.get('duties'):
                lines += ['## What they need',*['- '+duty for duty in role['duties'][:2]]]
            lines += technology_lines(report,observed['sources'],compact=True)
            lines += ['## Your evidence and next question']
            linked=next((ref for row in report['fit'] for ref in row['sources'] if ref.startswith('experience_')),None)
            if linked:
                lines.append(observed['sources'][linked]['excerpt'])
            lines.append(report['questions'][0])
            return '\n\n'.join(lines)
        lines=['# Quick rehearsal sheet',title,guide['opening'],'## Examples to rehearse']
        for card in guide['cards'][:3]: lines += [card['answer'],'Cues: '+' → '.join(card['cues'])]
        if claims:
            lines += ['## Company and role',guide['why']]
        lines += technology_lines(report,observed['sources'],compact=True)
        lines += ['## Ask next',*['- '+question for question in report['questions']],'## First-month approach',guide['pilot']['text']]
        return '\n\n'.join(lines)
    def review(self,rid,disposition,output_hash=None):
        if disposition not in {'approved','changes_requested'}: raise ValueError('Invalid review disposition')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE'); r=self._read(db,rid)
            if r['status']!='ready_for_review': raise ValueError('Only completed output can be reviewed')
            if disposition=='approved' and not r['result'].get('quality',{}).get('export_ready'): raise ValueError('Add the missing evidence and regenerate before approving this limited draft')
            if output_hash is not None and output_hash!=r.get('output_hash'): raise ValueError('Output changed; review the current draft')
            r['review']={'disposition':disposition,'output_hash':r['output_hash'],'reviewed_at':now()}
            db.execute('UPDATE runs SET data=? WHERE id=? AND owner=?',(encoded(r),rid,self.owner))
            return r
    def artifact(self,rid,kind):
        r=self.get(rid)
        if r['status']!='ready_for_review': raise ValueError('Output is not ready')
        if kind not in {'markdown','quick_markdown','guide_docx','guide_pdf','quick_docx','quick_pdf'}: raise ValueError('Unknown artifact')
        with self.artifact_lock:
            directory=self.directory / rid; directory.mkdir(parents=True,exist_ok=True)
            if kind in {'markdown','quick_markdown'}:
                path=directory/(kind+'.md'); path.write_text(r['result'][kind],encoding='utf-8'); return path
            return Path(self.export_files(rid,directory)[kind])
    def export_files(self,rid,directory):
        from .career_exports import export_run
        r=self.get(rid)
        if r['status']!='ready_for_review':
            raise ValueError('Output is not ready')
        quality=r['result'].get('quality') or {}
        if not quality.get('export_ready') or not r['result']['validation']['passed']:
            raise ValueError(' '.join(quality.get('blockers') or ['Run the updated source checks before exporting this draft.']))
        with self.artifact_lock:
            return export_run(directory,r)
    def create_practice(self,rid):
        r=self.get(rid)
        if r['status']!='ready_for_review' or r['feature']!='interview_prep': raise ValueError('Complete Interview Prep first')
        sid=uuid.uuid4().hex; questions=r['result']['questions']
        state={'id':sid,'run_id':rid,'output_hash':r['output_hash'],'status':'active','mode':'heuristic','question_index':0,'total':len(questions),'questions':questions,'current_question':questions[0],'answers':[],'created_at':now()}
        with self._db() as db: db.execute('INSERT INTO practice VALUES (?,?,?)',(sid,self.owner,encoded(state)))
        return state
    def _practice(self,db,sid):
        row=db.execute('SELECT data FROM practice WHERE id=? AND owner=?',(sid,self.owner)).fetchone()
        if not row: raise ValueError('Practice session not found')
        return json.loads(row[0])
    def get_practice(self,sid):
        with self._db() as db: return self._practice(db,sid)
    def practice_answer(self,sid,answer,retry=False):
        if not isinstance(answer,str) or not answer.strip() or len(answer)>12000: raise ValueError('Enter an answer of 1–12000 characters')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE'); s=self._practice(db,sid)
            if s['status']!='active': raise ValueError('Practice is complete')
            q=s['current_question']; prior=[a for a in s['answers'] if a['question_id']==q['id']]
            if bool(prior)!=bool(retry): raise ValueError('Use retry to replace an answered question, or answer the current question first')
            words=re.findall(r'\w+',answer.lower()); evidence=set(re.findall(r'\w+',q['evidence'].lower()))
            overlap=len(set(words)&evidence)/max(1,len(evidence)); length=len(words)
            feedback={'mode':'heuristic','confidence':'low','meaning':'Practice signals only; no truth verification or hiring prediction.','scores':{},'observations':{'evidence_word_overlap':round(overlap,2),'length_guidance':'Within the 40–220 word practice range' if 40<=length<=220 else 'Consider a 40–220 word spoken answer'},'notes':['Word overlap and answer length are measured; relevance and factual accuracy need your review.','Confirm every added claim, number and outcome against your actual experience.'],'word_count':length}
            s['answers'].append({'question_id':q['id'],'answer':answer.strip(),'feedback':feedback,'attempt':len(prior)+1,'answered_at':now()})
            s['feedback']=feedback; db.execute('UPDATE practice SET data=? WHERE id=? AND owner=?',(encoded(s),sid,self.owner)); return s
    def practice_next(self,sid):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE'); s=self._practice(db,sid)
            if s['status']!='active': return s
            if not any(a['question_id']==s['current_question']['id'] for a in s['answers']): raise ValueError('Answer the current question first')
            s['question_index']+=1; s.pop('feedback',None)
            if s['question_index']>=s['total']: s.update(status='complete',current_question=None)
            else: s['current_question']=s['questions'][s['question_index']]
            db.execute('UPDATE practice SET data=? WHERE id=? AND owner=?',(encoded(s),sid,self.owner)); return s
