"""Bounded, user-requested recovery of missing vacancy metadata, with provenance."""
from __future__ import annotations
import copy
import hashlib
import re
from datetime import datetime
from urllib.parse import urlsplit

from .models import Job, utcnow
from .listing_info import extract_dates
from .listing_view import (normalize_listing, source_problem, same_role, employer_known,
                           confirmed_listing_employer, listing_view, RECOMMENDATIONS)
from .locations import location_info

LABELS = {'employer':'Employer', 'salary':'Pay', 'location':'Location',
          'arrangement':'Work arrangement', 'employment_type':'Employment type',
          'posted':'Posted date', 'closes':'Closing date'}
BATCH_LIMIT = 10
VERSION = 1


def source_hash(job):
    return hashlib.sha256(Job.model_validate(job).model_dump_json().encode()).hexdigest()


def current_report(row, report):
    return report if report and report.get('source_hash') == source_hash(row['job']) else None


def known_value(value):
    return bool(value and str(value).strip().casefold() not in {'not stated','location not stated','unknown','not available','n/a','tbd','—','-'})


def missing_fields(row):
    view, loc, dates = row['reading_view'], row['location_info'], row['listing']
    missing=[]
    if not employer_known(view.get('employer') or row['job']['employer']): missing.append('employer')
    if view['salary']['status']=='not_stated': missing.append('salary')
    if not loc.get('stated') or not known_value(loc.get('display')): missing.append('location')
    if not known_value(loc.get('arrangement')): missing.append('arrangement')
    if not any(f['label']=='Work type' and known_value(f['value']) for f in view['facts']): missing.append('employment_type')
    if not (dates.get('posted_on') or dates.get('posted_hint')): missing.append('posted')
    if not (dates.get('closes_on') or dates.get('closing_hint') or dates.get('closed')): missing.append('closes')
    return missing


def eligible(row):
    return row.get('stage') not in {'applied','archived'} and not row['listing']['closed'] and bool(missing_fields(row))


def cooling_down(report):
    if not report or report.get('version') != VERSION: return False
    try: return (datetime.fromisoformat(utcnow())-datetime.fromisoformat(report['checked_at'])).total_seconds()<86400
    except (ValueError,KeyError,TypeError): return False


def apply_dates(row, report):
    fields=(report or {}).get('fields',{})
    dates=row['listing']
    for field,keys in [('posted',('posted_on','posted_hint')),('closes',('closes_on','closing_hint'))]:
        if field in fields and not any(dates.get(k) for k in keys):
            dates.update(copy.deepcopy(fields[field]['value']))
    if 'closed_notice' in fields: dates['closed_notice']=fields['closed_notice']['value']


def apply_details(row, report):
    """Fill display/evidence inputs only; leave original advert and owner overrides intact."""
    fields=(report or {}).get('fields',{})
    missing=set(missing_fields(row))
    view,loc=row['reading_view'],row['location_info']
    for conflict in (report or {}).get('conflicts',[]):
        view.setdefault('notices',[]).append({'message':'Metadata source conflicts with the saved '+conflict+'; verify the listing.','quote':''})
    for key in missing & fields.keys():
        value=copy.deepcopy(fields[key]['value'])
        if key=='employer': view['employer']=value
        elif key=='salary':
            view['salary']=value
            view['facts'].insert(0,{'label':'Salary','value':value['display']})
        elif key=='location':
            arrangement=loc.get('arrangement')
            loc.update(value)
            if known_value(arrangement):loc['arrangement']=arrangement
        elif key=='arrangement':
            loc['arrangement']=value
            loc['metadata_restrictions']=fields[key]['evidence']
            loc['metadata_location_review']=bool(re.search(r'(?i)must be based|applicant location|only',fields[key]['evidence']))
        elif key=='employment_type':
            view['facts']=[f for f in view['facts'] if f['label']!='Work type']
            view['facts'].append({'label':'Work type','value':value})


def extract_fields(text, job, search_area):
    """Read explicit statements from a single-role page, never search snippets."""
    normalized=normalize_listing(text,job.title)
    normalized=re.sub(r'(?m)^L\d+(?:@P[\d-]+)?:\s?', '',normalized)
    primary=re.split(RECOMMENDATIONS,normalized)[0]
    headings=re.findall(r'(?m)^\s*#{1,6}\s+([^\n]+)',primary[:4000])
    if not headings or not same_role(job.title,headings[0],job.employer):
        raise ValueError('The page does not identify this exact role in its main heading.')
    problem=source_problem(primary,job.title)
    if problem and problem[0]!='closed':raise ValueError(problem[1])
    if problem and problem[0]=='closed':return {'closed_notice':{'value':True,'evidence':problem[1]}},primary
    if re.search(r'(?i)access denied|failed to fetch|unable to resolve open call|just a moment\.\.\.|verify you are human',primary):
        raise ValueError('The page is blocked or unavailable; no metadata was imported.')
    fields={}
    inferred=confirmed_listing_employer(job.model_copy(update={'employer':'Employer on job listing'}),primary)
    if employer_known(inferred):
        if employer_known(job.employer) and inferred.casefold()!=job.employer.casefold():
            raise ValueError('The page names a different employer.')
        fields['employer']={'value':inferred,'evidence':'Employer identified in the same-role page header: '+inferred}
    view=listing_view(primary,job.title,job.employer)
    salary=view['salary']
    if salary['status']=='stated' and not re.search(r'(?i)estimated? (?:annual )?(?:salary|pay)|(?:salary|pay) (?:estimate|guide)|AI.generated',primary):
        fields['salary']={'value':salary,'evidence':salary['evidence']}
    # Use only an explicit location field, not office marketing or the saved search area.
    locmatch=re.search(r'(?im)^\s*(?:Job location|Location|Locations|Based in)\s*[:\n]\s*([^\n]{2,160})',primary[:2000])
    if locmatch:
        loc=location_info({'description':locmatch[0],'location':'','title':job.title,'employer':job.employer},search_area)
        if loc['stated']:fields['location']={'value':loc,'evidence':locmatch[0]}
    restrictions=re.findall(r'(?im)^.*(?:must be based|applicant location|remote.{0,35}only).*$' ,primary)
    if restrictions and 'location' in fields:
        fields['location']['value'].update(metadata_restrictions='\n'.join(restrictions)[:1500],metadata_location_review=True)
    mode=re.search(r'(?im)^\s*(?:Work format|Work arrangement|Workplace type)\s*[:\n]\s*(hybrid|remote|on[- ]?site)\b[^\n]*',primary)
    if mode:
        value={'hybrid':'Hybrid','remote':'Remote'}.get(mode[1].casefold(),'On-site')
        # Retain explicit remote eligibility in the field evidence.
        fields['arrangement']={'value':value,'evidence':'\n'.join([mode[0],*restrictions])[:1500]}
    else:
        board_mode=re.search(r'(?im)^\s*(In-Office|On-site|Onsite|Hybrid|Remote)\s*$',primary[:2000])
        if board_mode:
            value={'hybrid':'Hybrid','remote':'Remote'}.get(board_mode[1].casefold(),'On-site')
            fields['arrangement']={'value':value,'evidence':'\n'.join([board_mode[0],*restrictions])[:1500]}
    for fact in view['facts']:
        if fact['label']=='Work type' and re.fullmatch(r'(?i)(?:permanent|temporary|full[ _-]?time|part[ _-]?time|contract(?:or)?|casual|fixed[ -]term|salaried|internship|other|[ /,])+',fact['value']):
            fields['employment_type']={'value':fact['value'],'evidence':'Employment type: '+fact['value']}
    dates=extract_dates(primary)
    for field,keys in [('posted',('posted_on','posted_hint')),('closes',('closes_on','closing_hint'))]:
        value={k:dates[k] for k in keys if dates.get(k)}
        if value:fields[field]={'value':value,'evidence':' / '.join(dates['date_evidence'].get(k,str(v)) for k,v in value.items())}
    return fields,primary


def refresh_one(workspace, row):
    from .workspace import source_text, search_results, public_listing_url, SourceChanged, ReadInProgress
    job=Job.model_validate(row['job'])
    wanted=missing_fields(row)
    report={'version':VERSION,'source_hash':source_hash(row['job']),'checked_at':utcnow(),'requested':wanted,
            'fields':copy.deepcopy((row.get('metadata_refresh') or {}).get('fields',{})),
            'sources':[],'candidates':[],'outcome':'not_found'}
    original=public_listing_url(str(job.url))
    with workspace.read_guard:
        if row['id'] in workspace.reading_jobs:raise ReadInProgress('This listing is already being checked.')
        workspace.reading_jobs.add(row['id'])
    try:
        def inspect(url, alternate=False):
            entry={'url':url,'status':'unavailable'}
            report['sources'].append(entry)
            try:
                result=workspace.bridge.call('search_service.web_run',{'open':[{'ref_id':url}],'response_length':'long'})
                text=source_text(result)
                values,primary=extract_fields(text,job,workspace.preferences.location)
                if alternate:
                    # Employer/title alone cannot distinguish a repeated vacancy. Require a link back
                    # to the exact saved vacancy as well as matching role and explicit employer.
                    links=re.findall(r'https://[^\s<>"\])]+',primary)
                    linked=False
                    for link in links:
                        try:linked=linked or public_listing_url(link)==original
                        except ValueError:pass
                    if not linked or not values.get('employer') or values['employer']['value'].casefold()!=job.employer.casefold():
                        entry.update(status='needs_review',message='Possible copy; exact vacancy identity is not confirmed.')
                        return
                    loc=values.get('location',{}).get('value',{})
                    if row['location_info'].get('states') and loc.get('states') and not set(loc['states'])&set(row['location_info']['states']):
                        entry.update(status='needs_review',message='Possible copy has a different location.')
                        return
                entry['status']='checked'
                entry['found']=[]
                found_location=values.get('location',{}).get('value',{})
                old_location=row['location_info']
                if old_location.get('states') and found_location.get('states') and not set(old_location['states'])&set(found_location['states']):
                    report.setdefault('conflicts',[]).append('location')
                    entry.update(status='needs_review',message='The page gives a different location; your saved location was kept.')
                for key,value in values.items():
                    if key not in wanted and key!='closed_notice':continue
                    record={**value,'url':url,'checked_at':report['checked_at']}
                    if key in report['fields'] and report['fields'][key]['value']!=record['value']:
                        entry.update(status='needs_review',message='Sources disagree; the earlier verified value was kept.')
                        continue
                    report['fields'][key]=record;entry['found'].append(key)
            except Exception as exc:
                entry['message']=str(exc)[:400]
        inspect(original)
        remaining=[key for key in wanted if key not in report['fields']]
        if remaining and 'closed_notice' not in report['fields']:
            # One metadata-only search per role. No profile, CV or private notes are sent.
            employer=job.employer if employer_known(job.employer) else urlsplit(original).hostname
            query='"'+job.title.replace('"',' ')[:180]+'" '+employer.replace('"',' ')[:100]
            try:
                result=workspace.bridge.call('search_service.web_run',{'system2_search_query':[{'q':query}],'response_length':'long'})
                seen={original}
                for candidate in search_results(result):
                    try:url=public_listing_url(candidate['url'])
                    except ValueError:continue
                    title=candidate['title'].split(' | ')[0]
                    title_match=same_role(job.title,title,job.employer) or bool(re.search(r'(?<!\w)'+re.escape(job.title)+r'(?!\w)',title,re.I))
                    if not title_match:continue
                    same_vacancy_alias=False
                    if url==original and report['sources'][0]['status']=='unavailable':
                        parsed=urlsplit(candidate['url'])
                        if parsed.hostname and (parsed.hostname=='linkedin.com' or parsed.hostname.endswith('.linkedin.com')):
                            alias=parsed._replace(query='',fragment='').geturl()
                            if alias!=original:
                                url=alias;same_vacancy_alias=True
                    if url in seen:continue
                    seen.add(url)
                    if employer_known(job.employer) and job.employer.casefold() not in (candidate['title']+' '+str(candidate['description'])).casefold():continue
                    report['candidates'].append({'url':url,'title':candidate['title'][:250]})
                    inspect(url,alternate=not same_vacancy_alias)
                    if len(report['candidates'])>=2 or all(k in report['fields'] for k in wanted):break
            except Exception as exc:report['search_error']=str(exc)[:400]
        report['filled']=[k for k in wanted if k in report['fields']]
        report['remaining']=[k for k in wanted if k not in report['fields']]
        report['outcome']='closed' if 'closed_notice' in report['fields'] else 'updated' if report['filled'] else 'not_found'
        with workspace.write_lock:
            stored,current=workspace.job(row['id'])
            if source_hash(current.model_dump())!=report['source_hash']:raise SourceChanged('The listing changed during the check; your edit was kept.')
            changes={}
            if 'employer' in report['filled'] and not employer_known(current.employer):
                changes['employer']=report['fields']['employer']['value']
            if 'location' in report['filled'] and 'location' in wanted:
                changes['location']=report['fields']['location']['value']['display']
            if changes:
                history=workspace.get_meta('listing_history:'+row['id'],[])
                history.append({'job':current.model_dump(mode='json'),'saved_at':utcnow(),'reason':'Missing metadata verified against vacancy source'})
                workspace.set_meta('listing_history:'+row['id'],history)
                current=current.model_copy(update=changes)
                with workspace.store.connect() as db:
                    db.execute('UPDATE jobs SET payload=?,updated_at=? WHERE id=?',(current.model_dump_json(),utcnow(),row['id']))
                if stored.get('packet_dir'):workspace.set_meta('packet_source_stale:'+row['id'],stored['packet_dir'])
                report['source_hash']=source_hash(current.model_dump())
            if 'closed_notice' in report['fields']:
                dates=workspace.get_meta('listing:'+row['id'],{})
                dates.update(closed_notice=True,observed_at=report['checked_at'])
                workspace.set_meta('listing:'+row['id'],dates)
            workspace.set_meta('metadata_details:'+row['id'],report)
        return report
    finally:
        with workspace.read_guard:workspace.reading_jobs.discard(row['id'])


def refresh_batch(workspace, ids):
    if not workspace.batch_lock.acquire(blocking=False):raise ValueError('Another listing check is running. Try again after it finishes.')
    progress={'running':True,'total':0,'processed':0,'updated':0,'fields_filled':0,'unresolved':0,'errors':0,'current':'','started_at':utcnow()}
    try:
        selected=set(ids)
        pending=[r for r in workspace.jobs() if r['id'] in selected and eligible(r)]
        rows=[r for r in pending if not cooling_down(r.get('metadata_refresh'))][:BATCH_LIMIT]
        progress.update(total=len(rows),deferred=max(0,len(pending)-len(rows)))
        workspace.set_meta('metadata_refresh_progress',progress)
        for row in rows:
            if workspace.stop_event.is_set():break
            progress['current']=row['job']['title'];workspace.set_meta('metadata_refresh_progress',progress)
            try:
                report=refresh_one(workspace,row)
                progress['updated']+=bool(report['filled'] or report['outcome']=='closed')
                progress['fields_filled']+=len(report['filled'])
                progress['unresolved']+=bool(report['remaining'])
            except Exception as exc:
                progress['errors']+=1;progress['last_error']=str(exc)[:400]
            progress['processed']+=1;workspace.set_meta('metadata_refresh_progress',progress)
        return progress
    finally:
        progress.update(running=False,current='',finished_at=utcnow())
        workspace.set_meta('metadata_refresh_progress',progress)
        workspace.batch_lock.release()
