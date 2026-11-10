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
from .career_render import RESEARCH_AREAS, render, check_references, check_decision

TERMINAL = {'ready_for_review', 'failed', 'cancelled', 'budget_exhausted'}
VERSION = 'career-1.0.0'

def now(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
def digest(value): return hashlib.sha256(encoded(value).encode()).hexdigest()
def public_url(value):
    try:
        from ipaddress import ip_address
        p = urlsplit(str(value)); host = p.hostname or ''
        if p.scheme != 'https' or p.username or p.password or not host or host in {'localhost'} or host.endswith(('.local','.localhost')): return ''
        try:
            if not ip_address(host).is_global: return ''
        except ValueError: pass
        return str(value)
    except ValueError: return ''

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
        if set(o)-{'stage','frameworks','max_web_calls','max_seconds','scope','preparation_minutes','communication_preferences'}: raise ValueError('Unsupported career options')
        scope=o.get('scope',['employer','role','pay'])
        if not isinstance(scope,list) or not scope or any(x not in {'employer','role','pay'} for x in scope): raise ValueError('Invalid research scope')
        minutes=o.get('preparation_minutes',30)
        if type(minutes) is not int or not 5<=minutes<=240: raise ValueError('Preparation time must be 5–240 minutes')
        preferences=o.get('communication_preferences','')
        if not isinstance(preferences,str) or len(preferences)>500: raise ValueError('Communication preferences must be under 500 characters')
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
        if not row or job is None: raise ValueError('Saved role not found')
        # Only the current candidate, never examples, mail, referees or credentials.
        profile=self.workspace.profile.model_dump()
        profile={k:profile.get(k) for k in ('summary','headline','skills','education','experience','is_example','credentials','availability','technical_projects')}
        if profile.get('is_example'): raise ValueError('Replace the example profile before preparing career material')
        enriched = next((x for x in self.workspace.jobs() if x['id']==job_id), {}) if hasattr(self.workspace,'jobs') else {}
        snapshot={'details':{k:enriched.get(k) for k in ('reading_view','location_info','listing','fit')},'job':job.model_dump(mode='json'),'profile':profile,'job_revision':row.get('revision',''),'captured_at':now()}
        if feature=='interview_prep':
            prior=next((x for x in self.list(job_id) if x['feature']=='deep_research' and x['status']=='ready_for_review' and x['snapshot']['job']==snapshot['job'] and x['snapshot']['profile']==profile and time.time()-datetime.fromisoformat(x['created_at']).timestamp()<86400),None)
            if prior: snapshot['research']={'run_id':prior['id'],'output_hash':prior['output_hash'],'review':prior['review'],'sources':prior['result']['sources']}
        key=digest({'owner':self.owner,'job_id':job_id,'job':snapshot['job'],'details':snapshot['details'],'research':snapshot.get('research'),'profile':profile,'feature':feature,'options':o,'version':VERSION})
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute("SELECT data FROM runs WHERE owner=? AND cache_key=? AND status IN ('queued','running','ready_for_review') ORDER BY created DESC",(self.owner,key)).fetchall()
            for (data,) in existing:
                previous=json.loads(data)
                active=previous['status'] in {'queued','running'}
                fresh=time.time()-datetime.fromisoformat(previous['created_at']).timestamp()<86400
                if active or (not refresh and fresh): return {'run_id':previous['id'],'cached':not active,'reused':True}
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
            findings=[]
            if r['feature']=='deep_research':
                employer=observed['vacancy']['employer']
                areas=[]
                if 'role' in r['options']['scope']: areas.append('role responsibilities '+observed['vacancy']['title'])
                if 'pay' in r['options']['scope']: areas.append('salary remuneration '+observed['vacancy']['title']+' '+observed['vacancy']['locations'][0])
                if 'employer' in r['options']['scope']: areas.extend(RESEARCH_AREAS)
                if len(areas)>r['options']['max_web_calls']: findings.append('Selected scope exceeds the call budget; remaining employer topics are explicitly unverified.')
                for i,area in enumerate(areas):
                    self._active(rid,deadline)
                    if self.get(rid)['usage']['web_calls']>=r['options']['max_web_calls']: break
                    query=f'"{employer[:150]}" {observed["vacancy"]["title"][:120]} {area}'
                    try:
                        response=self._web(rid,{'system2_search_query':[{'q':query}],'response_length':'long'},deadline)
                        for n,source in enumerate(research_sources(response)):
                            ref=f'web_{i}_{n}'
                            observed['sources'][ref]={'kind':'secondary','label':f"{area}: {source['label']}",'locator':f'Connected search query: {query}; checked {now()}. Identity and claim require review.','url':source['url'],'excerpt':source['excerpt']}
                        # Search snippets are leads, not company facts. Preserve for review.
                    except TimeoutError: raise
                    except Exception as exc:
                        findings.append(f'{area}: source access failed ({type(exc).__name__}); unknown retained.')
                    self._update(rid,progress={'message':f'Checked {area}','completed':i+1,'total':len(areas)},partial_sources=observed['sources'])
            brief=render(observed,report)
            errors=check_references(observed,report,brief)+check_decision(observed,report)
            if r['feature']=='deep_research':
                brief += '\n## Retrieved research leads — verify before relying on them\n'
                for ref,source in observed['sources'].items():
                    if ref.startswith('web_'):
                        brief += f"\n### {source['label']}\n{source['url']}\n\n{source['excerpt']}\n"
            if r['feature']=='interview_prep':
                try: interview(observed,report,guide)
                except (ValueError,KeyError,TypeError) as exc: errors.append(str(exc))
                brief=self._guide_markdown(observed,guide)+ '\n\n'+brief
            result={'mode':'extractive','limited_draft':bool(errors),'title':observed['vacancy']['title'],'markdown':brief,'quick_markdown':self._quick(observed,guide),'observations':observed,'assessment':report,'guide':guide,'questions':questions,'sources':observed['sources'],'validation':{'passed':not errors,'findings':errors+findings,'scope':'Structural harness checks only. Search leads and candidate assertions need human review; no semantic model verification.'},'limitations':['Extractive draft from saved evidence; no generative model has been called.','Search leads do not verify employer identity or claims.','No application or email was submitted.']}
            result['output_hash']=digest(result)
            self._active(rid,deadline)
            self._update(rid,status='ready_for_review',result=result,output_hash=result['output_hash'],progress={'message':'Limited draft: more evidence needed' if errors else 'Draft ready for your review','completed':1,'total':1})
        except InterruptedError: pass
        except TimeoutError as exc: self._update(rid,status='budget_exhausted',error=str(exc))
        except Exception as exc: self._update(rid,status='failed',error=f'{type(exc).__name__}: {str(exc)[:300]}')
    def _draft(self,r):
        j=r['snapshot']['job']; p=r['snapshot']['profile']; sources={}
        details=r['snapshot'].get('details',{}); view=details.get('reading_view') or {}; location=details.get('location_info') or {}
        sources['advert']={'kind':'employer','label':'Saved vacancy text (employer claims, not independently verified)','locator':f"Frozen saved role {r['job_id']}",'url':public_url(j.get('url','')),'excerpt':str(j.get('description',''))[:20000]}
        sources['application']={'kind':'application_record','label':'Application status not verified in this run','locator':'No submission check performed. Check your application records before applying.'}
        sources['profile']={'kind':'candidate','label':'Your saved profile summary','locator':'Frozen local profile summary','excerpt':str(p.get('summary') or '')}
        for key,value in r['snapshot'].get('research',{}).get('sources',{}).items():
            if key.startswith('web_'): sources['research_'+key]=value
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
        vacancy={'id':r['job_id'],'employer':str(j.get('employer') or 'Employer unconfirmed'),'title':str(j.get('title') or 'Role unconfirmed'),'mode':location.get('arrangement') or 'Not verified','employment':next((str(x.get('value')) for x in view.get('facts',[]) if isinstance(x,dict) and x.get('label')=='Work type' and x.get('value')), 'Not verified'),'locations':[str(j.get('location') or 'Not stated')],'source':'advert','status':'closed' if (details.get('listing') or {}).get('closed') else 'unknown','deadline':(details.get('listing') or {}).get('closes_on') or None}
        observed={'checked_on':now()[:10],'vacancy':vacancy,'submission':{'status':'unconfirmed','description':'No application receipt was checked in this run.','source':'application'},'sources':sources,'employer_pay':None}
        salary=view.get('salary') or {}
        if salary.get('status')=='stated' and salary.get('minimum') and salary.get('maximum') and salary.get('currency') and salary.get('period'):
            observed['employer_pay']={'low':int(salary['minimum']),'high':int(salary['maximum']),'currency':salary['currency'],'basis':salary.get('display') or str(salary['period'])}
        questions=[{'id':'intro','question':'Tell me about your relevant experience for this role.','evidence':p.get('summary') or 'Add your summary.'}]
        stage_questions={'recruiter':'What are your availability, work arrangement preferences and pay expectations?','hiring_manager':'Which supported example best demonstrates delivery against this role’s priorities?','panel':'How did you work with stakeholders with different priorities?','technical':'Explain the reasoning and checks behind a technical decision you actually made.','practical':'How would you clarify and approach a practical task in this role?','unknown':'What would you like to confirm about the interview format?'}
        questions.append({'id':'stage','question':stage_questions[r['options']['stage']],'evidence':'Use confirmed personal evidence, or label a hypothetical approach clearly.'})
        cards=[]
        # Rank real statements by overlap only; never convert keywords into achievements.
        words=set(re.findall(r'\b[a-z]{4,}\b',str(j.get('description','')).lower()))
        facts.sort(key=lambda item:len(words & set(re.findall(r'\b[a-z]{4,}\b',item[1].lower()))),reverse=True)
        for n,(ref,fact) in enumerate(facts[:4]):
            q=f"Talk me through this example from your profile: {fact}"
            cards.append({'kind':'past_experience','question':q,'answer':f'Your saved evidence says: “{fact}”\nExplain the context, your own actions and the observed outcome. Details not recorded here must be confirmed by you.','follow_up':'What did you personally do, and what outcome can you support?','bullets':[fact,'Add only context and outcomes you can substantiate.'],'cues':['Context','My action','Evidence'],'sources':[ref]})
            questions.append({'id':f'experience_{n}','question':q,'evidence':fact})
        questions.append({'id':'proposal','question':'How would you approach your first month in this role?','evidence':'Future proposal only; do not describe it as past delivery.'})
        report={'vacancy':vacancy,'submission':observed['submission'],'employer_pay':observed['employer_pay'],'estimated_pay':None,'pay_note':'No pay benchmark was verified.','claims':[{'id':f'area_{i}','area':a,'kind':'unknown','text':f'{a} has not been verified for this employer.','sources':[],'question':f'What reliable employer evidence confirms {a.lower()}?'} for i,a in enumerate(RESEARCH_AREAS)],'fit':[{'requirement':'Confirm material requirements against the original advert','level':'Gap','detail':'This extractive run does not independently assess competency or alter the saved fit score. Compare each requirement with the sourced work examples below.','sources':['advert']}],'stories':[{'label':sources[ref]['label'],'answer':fact,'cues':['Context','Action','Outcome to confirm'],'sources':[ref]} for ref,fact in facts[:4]],'action':'hold','decision':'Review the evidence and confirm vacancy and application status.','next_step':'Open the original advert and confirm requirements, closing date and whether you have already applied.','application_files':[],'pilot':'Proposed approach, not past experience: clarify the employer’s priority, agree a small safe trial, measure the agreed outcome, then decide whether to expand.','questions':['What are the most important outcomes in the first three months?','What constraints and support will shape the role?','What are the pay range, work arrangement and next hiring steps?']}
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
        guide['strategy']['rehearsal'] += f" Set aside {r['options']['preparation_minutes']} minutes: review evidence first, then rehearse and check uncertain details."
        if r['options']['communication_preferences']:
            guide['strategy']['rehearsal'] += ' Your speaking preferences (self-directed): '+r['options']['communication_preferences']
        return observed,report,guide,questions
    def _guide_markdown(self,observed,guide):
        lines=['# Interview preparation — evidence draft','This is an extractive rehearsal draft. Confirm placeholders before speaking.','## Introduction',guide['opening'],'## Why this role',guide['why'],'## Answer strategy',guide['strategy']['selection'],guide['strategy']['rehearsal']]
        for method in guide['strategy']['methods']:
            lines+=['## '+method['name']+' — '+method['kind'],method['question']]
            lines += [f'- **{label}** {value}' for label,value in method['steps']]
        for card in guide['cards']: lines+=['## '+card['question'],card['answer'],'Cues: '+' → '.join(card['cues']),card['follow_up']]
        lines+=['## Questions for the recruiter',guide['recruiter'],'## Hiring manager',guide['manager'],'## Recovery',guide['recovery']]
        for ref,source in observed['sources'].items():
            if ref.startswith(('credential_','project_')) or ref=='availability': lines += ['## '+source['label'],source['excerpt']+' ['+ref+']']
        return '\n\n'.join(lines)
    def _quick(self,observed,guide):
        vacancy=observed['vacancy']
        lines=['# Quick rehearsal sheet',vacancy['employer']+' — '+vacancy['title'],guide['opening'],'## Three examples to rehearse']
        for card in guide['cards'][:3]: lines += [card['answer'],'Cues: '+' → '.join(card['cues'])]
        if len(guide['cards'])<3: lines.append('Add more real examples: fewer than three were found in your saved experience.')
        lines += ['## Three employer questions','1. What outcomes matter most in the first three months?','2. Which constraints and support shape this role?','3. What are the pay range, work arrangement and next hiring steps?','## Company and role','Company claims need verification. Role: '+vacancy['title'],'## When unsure',guide['recovery'],'## Proposal',guide['pilot']['text']]
        return '\n\n'.join(lines)
    def review(self,rid,disposition,output_hash=None):
        if disposition not in {'approved','changes_requested'}: raise ValueError('Invalid review disposition')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE'); r=self._read(db,rid)
            if r['status']!='ready_for_review': raise ValueError('Only completed output can be reviewed')
            if disposition=='approved' and not r['result']['validation']['passed']: raise ValueError('Add the missing evidence and regenerate before approving this limited draft')
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
            from .career_exports import export_run
            return Path(export_run(directory,r)[kind])
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
