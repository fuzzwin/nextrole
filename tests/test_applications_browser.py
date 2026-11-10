"""Compact applications table uses synthetic mail evidence only."""
import os
import socket
import threading
import time
import pytest
import uvicorn
from test_workspace import FakeBridge, profile
from campus_agent.models import Job
from campus_agent.workspace import Workspace
from campus_agent.workspace_web import create_workspace_app

@pytest.mark.skipif(not os.getenv('PLAYWRIGHT_EXECUTABLE_PATH'), reason='Set Chromium path for browser check')
def test_compact_application_rows_and_mobile_expansion(tmp_path, profile):
    from playwright.sync_api import sync_playwright, expect
    ws=Workspace(tmp_path/'workspace',FakeBridge())
    ws.save_profile(profile.model_copy(update={'is_example':False}))
    job=Job(source_id='application-fixture',title='Service Coordinator',employer='Example Care',url='https://example.com/jobs/123',location='Melbourne',description='Coordinate care and services.')
    ws.add_job(job,full=True)
    at='2026-11-10T10:00:00+00:00'
    summary='Application received. The employer will review your evidence; no interview is confirmed.'
    ws.set_meta('applications',[{'id':'a1','company':'Example Care','title':'Service Coordinator','status':'received','applied_at':at,'last_update_at':at,'source_url':'https://mail.google.com/mail/u/0/#all/test1','events':[{'subject':'Thank you for applying','summary':summary,'evidence':'We received your application'}]}, {'id':'a2','company':'Example Other','title':'Malformed legacy body '+('long narrative text '*40),'status':'under_review','applied_at':None,'last_update_at':at,'source_url':'https://mail.google.com/mail/u/0/#all/test2','events':[{'subject':'Application update','summary':'Your application is under review. '+('Additional explanation '*30)}]}])
    ws.set_meta('application_sync',{'at':at,'needs_review':[{'subject':'Possible interview update','source_url':'https://mail.google.com/mail/u/0/#all/test3','review_reason':'More than one role at this employer; exact application needs confirmation.'}]})
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_workspace_app(ws),log_level='error'))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ['PLAYWRIGHT_EXECUTABLE_PATH'],headless=True)
            page=browser.new_page(viewport={'width':1360,'height':900});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{port}/')
            expect(page.locator('#count-jobs')).to_have_text('1')
            page.locator('[data-view="applications"]').click()
            table=page.get_by_role('table',name='Tracked applications')
            expect(table).to_be_visible();expect(table.locator('tbody tr')).to_have_count(2)
            expect(table.get_by_role('link',name='Email ↗')).to_have_count(2)
            expect(table.get_by_role('button',name='Saved role')).to_have_count(1)
            for height in table.locator('tbody tr').evaluate_all('(rows)=>rows.map(r=>r.getBoundingClientRect().height)'):assert height<115
            table.locator('tbody tr').nth(1).get_by_text('Details',exact=True).click()
            expect(table.get_by_text('Saved role text:',exact=False)).to_be_visible()
            page.evaluate('renderApplications()')
            expect(table.get_by_text('Saved role text:',exact=False)).to_be_visible()
            table.locator('tbody tr').nth(1).get_by_text('Details',exact=True).click()
            page.screenshot(path=str(tmp_path/'applications-desktop.png'))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            expect(table.locator('tbody tr')).to_have_count(2)
            page.screenshot(path=str(tmp_path/'applications-mobile.png'))
            page.evaluate("state.activity.tasks.push({id:'sync-fixture',kind:'Check Gmail applications',status:'running'});renderApplications()")
            expect(page.locator('#sync-applications')).to_be_disabled()
            assert not errors
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=5);ws.close()
