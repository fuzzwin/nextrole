from test_workspace import workspace, profile
from campus_agent.models import Job
from campus_agent.listing_view import listing_view
from campus_agent.fit import fit_assessment
from test_dashboard_acceptance import candidate


def make_job(n, text='Brief search snippet for an IT systems specialist role.', employer='Example Employer'):
    return Job(source_id='opportunity',title='IT Systems Specialist',employer=employer,url=f'https://example.com/jobs/{n}',location='Melbourne',description=text)


def test_inline_requirements_and_nonverbatim_summary(workspace):
    job=make_job(1,'About the role: Support systems. Requirements: Requires hands-on Python automation experience. You need experience supporting Microsoft 365 systems.')
    workspace.add_job(job,full=True)
    row=workspace.jobs()[0]
    assert row['fit']['assessment_state']=='assessed'
    assert row['fit']['percent'] is not None
    lead=make_job(2,'LINKEDIN LISTING SUMMARY (not verbatim employer text)\nRequirements\n- Python experience is required for the role.')
    workspace.add_job(lead,full=True)
    assert next(r for r in workspace.jobs() if r['id']==lead.identity)['fit']['percent'] is None


def test_batch_caps_reads_persists_block_and_continues(workspace):
    jobs=[make_job(i) for i in range(14)]
    for job in jobs: workspace.add_job(job)
    def call(tool,args):
        url=args['open'][0]['ref_id']
        if url.endswith('/0'): return {'content':'access denied'}
        return {'content':'Location: Melbourne VIC\nAbout the role\n'+'Support business systems and automation. '*10+'\nRequirements\n- Requires hands-on Python automation experience.\n- You need Microsoft 365 systems support experience.'}
    workspace.bridge.call=call
    first=workspace.assess_batch([j.identity for j in jobs])
    assert first['processed']==12 and first['blocked']==1 and first['remaining']==2
    blocked=next(r for r in workspace.jobs() if r['id']==jobs[0].identity)
    assert blocked['assessment_source']['status']=='blocked'
    second=workspace.assess_batch([j.identity for j in jobs])
    assert second['processed']==2 and second['remaining']==0
    assert next(r for r in workspace.jobs() if r['id']==jobs[1].identity)['fit']['percent'] is not None


def test_discovery_reads_new_relevant_listing_and_assesses(workspace):
    calls=[]
    def call(tool,args):
        calls.append(args)
        if 'system2_search_query' in args:
            return {'results':[{'title':'IT Systems Specialist at Example Employer','url':'https://example.com/jobs/new-role','snippet':'Support Python systems and business automation in a Melbourne based specialist role.'}]}
        return {'content':'Location: Melbourne VIC\nAbout the role\n'+'Support systems and automation. '*12+'\nRequirements\n- Requires hands-on Python automation experience.\n- You need Microsoft 365 systems support experience.'}
    workspace.bridge.call=call
    result=workspace.discover()
    assert result['new']==1 and result['assessment']['processed']==1
    assert workspace.jobs()[0]['fit']['percent'] is not None
    assert sum('open' in c for c in calls)==1


def test_requirement_sentence_and_company_or_benefit_prose(workspace):
    text = 'Overview\nSupport company systems. Requires hands-on Python automation experience.\nAbout us\nOur company requires integrity and builds great tools.\nBenefits\nYou need a holiday and our generous leave supports you.'
    job=make_job(120,text)
    workspace.add_job(job,full=True)
    fit=workspace.jobs()[0]['fit']
    assert fit['percent'] is not None
    requirements=[r['text'] for r in fit['requirements']]
    assert any('Requires hands-on Python' in r for r in requirements)
    assert not any('integrity' in r or 'holiday' in r for r in requirements)


def test_skips_archived_and_applied_and_retries_changed_source(workspace):
    jobs=[make_job(i+200) for i in range(3)]
    for job in jobs: workspace.add_job(job)
    with workspace.store.connect() as db:
        db.execute("UPDATE job_details SET stage='archived' WHERE job_id=?",(jobs[0].identity,))
        db.execute("UPDATE job_details SET stage='applied' WHERE job_id=?",(jobs[1].identity,))
    workspace.bridge.call=lambda *_: {'content':'access denied'}
    result=workspace.assess_batch([j.identity for j in jobs])
    assert result['processed']==1 and result['blocked']==1
    changed=jobs[2].model_copy(update={'description':'A changed search description for the same role and employer.'})
    workspace.add_job(changed,full=True)
    assert workspace.assess_batch([changed.identity])['processed']==1


def test_inline_company_benefits_and_generic_summary(workspace):
    job=make_job(320,'Requirements: Python automation experience. Benefits: We offer free lunch and generous leave. About us: Our company is seeking a certified sustainability partner.')
    workspace.add_job(job,full=True)
    fit=workspace.jobs()[0]['fit']
    texts=[r['text'] for r in fit['requirements']]
    assert any('Python automation' in t for t in texts)
    assert not any('lunch' in t or 'sustainability' in t for t in texts)
    summary=make_job(321,'This is a job description summary, not verbatim employer text.\nRequirements\n- Python automation experience is required.')
    workspace.add_job(summary,full=True)
    assert next(r for r in workspace.jobs() if r['id']==summary.identity)['fit']['percent'] is None


def test_refresh_keeps_old_packet_but_marks_it_stale(workspace):
    import json
    job=make_job(400)
    workspace.add_job(job)
    directory=workspace.artifacts/'old-packet'
    directory.mkdir()
    (directory/'tailoring.json').write_text(json.dumps({'job_revision':job.revision,'profile':workspace.profile.model_dump(),'document_preferences':workspace.document_style().model_dump()}))
    (directory/'quality-report.json').write_text(json.dumps({'delivery_ready':True,'errors':[],'ruleset':'old'}))
    workspace.store.update(job.identity,'prepared',str(directory))
    changed=job.model_copy(update={'description':'A complete changed source advert with different requirements.'})
    workspace.add_job(changed,full=True)
    row=workspace.jobs()[0]
    assert row['packet_dir']==str(directory) and row['status']=='prepared'
    assert row['listing_stale'] and not row['quality']['delivery_ready']
    assert 'Listing changed' in ' '.join(row['quality']['errors'])


def test_inflight_role_does_not_block_other_batch_reads(workspace):
    a,b=make_job(401),make_job(402)
    workspace.add_job(a);workspace.add_job(b)
    workspace.reading_jobs.add(a.identity)
    workspace.bridge.call=lambda *_:{'content':'access denied'}
    result=workspace.assess_batch([a.identity,b.identity])
    assert result['processed']==1 and result['blocked']==1 and result['remaining']==1
    assert next(r for r in workspace.jobs() if r['id']==a.identity)['assessment_source'] is None


def test_discovery_records_deferred_reads_when_batch_running(workspace):
    workspace.bridge.call=lambda tool,args: {'results':[{'title':'IT Systems Specialist at Example Employer','url':'https://example.com/jobs/deferred','snippet':'Support Python systems and automation in Melbourne for business teams.'}]}
    workspace.batch_lock.acquire()
    try:
        report=workspace.discover()
    finally:
        workspace.batch_lock.release()
    assert report['new']==1 and report['assessment']['deferred']
    assert report['assessment']['remaining']==1
    assert workspace.get_meta('last_search')['assessment']['deferred']


def test_inflight_read_preserves_user_edit(workspace):
    import threading
    from campus_agent.workspace import SourceChanged
    job=make_job(450)
    workspace.add_job(job)
    started=threading.Event(); proceed=threading.Event(); errors=[]
    def call(*_):
        started.set(); assert proceed.wait(5)
        return {'content':'Location: Melbourne VIC\n'+('Support systems and teams. '*15)+'\nRequirements\n- Python automation experience.'}
    workspace.bridge.call=call
    def run():
        try: workspace.hydrate(job.identity)
        except Exception as exc: errors.append(exc)
    thread=threading.Thread(target=run);thread.start();assert started.wait(5)
    edited=job.model_copy(update={'description':'User pasted original advert with correct employer.', 'employer':'Correct Employer'})
    with workspace.write_lock: workspace.add_job(edited,full=True)
    proceed.set();thread.join(5)
    assert isinstance(errors[0],SourceChanged)
    assert workspace.job(job.identity)[1].description==edited.description
    assert workspace.job(job.identity)[1].employer=='Correct Employer'


def test_indeed_header_resolves_only_title_matched_company(workspace):
    from campus_agent.listing_view import confirmed_listing_employer
    text='# Power Platform Consultant\n\nExample Ltd .css-abc{color:red}\n\n(part of Parent)\n\n3.6 out of 5 stars\n\nMelbourne VIC\n## Full job description\nRequirements\n- Python experience required.'
    job=Job(source_id='test',employer='Employer on job listing',title='Power Platform Consultant - Melbourne VIC - Indeed.com',url='https://au.indeed.com/viewjob?jk=123',location='Melbourne',description=text)
    assert confirmed_listing_employer(job,text)=='Example Ltd'
    assert confirmed_listing_employer(job.model_copy(update={'title':'Different Role'}),text)=='Employer on job listing'
    workspace.add_job(job,full=True)
    assert workspace.jobs()[0]['reading_view']['employer']=='Example Ltd'


def test_indeed_header_never_uses_location_rating_navigation_or_placeholder():
    from campus_agent.listing_view import confirmed_listing_employer
    job=Job(source_id='test',employer='Employer on job listing',title='Power Platform Consultant - Melbourne VIC - Indeed.com',url='https://au.indeed.com/viewjob?jk=123',location='Melbourne',description='A synthetic role description.')
    for value in ['Melbourne VIC','Remote','3.6 out of 5 stars','Apply now','Employer not disclosed','Sydney NSW','Hybrid','Unknown']:
        text='# Power Platform Consultant\n\n'+value+'\n\nMelbourne VIC\n## Full job description\nRequirements\n- Python experience required.'
        assert confirmed_listing_employer(job,text)==job.employer, value
    for value in ['Example Employer','Avanade','Example Ltd .css-abc{color:red}']:
        text='# Power Platform Consultant\n\n'+value+'\n\n3.6 3.6 out of 5 stars\n\nMelbourne VIC\n## Full job description\nRequirements\n- Python experience required.'
        assert confirmed_listing_employer(job,text)==value.split(' .css-')[0]
    assert confirmed_listing_employer(job,'# Power Platform Consultant\n\nMystery Name\n## Full job description\nbody')==job.employer
