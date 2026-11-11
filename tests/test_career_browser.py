"""Career flow against a real local server and an isolated synthetic workspace."""
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
from test_career import employer_pages


@pytest.mark.skipif(not os.getenv('PLAYWRIGHT_EXECUTABLE_PATH'), reason='Set Chromium path for browser integration')
def test_career_dialog_research_prep_practice_cache_and_cancel(tmp_path, profile):
    from playwright.sync_api import sync_playwright, expect
    bridge = FakeBridge()
    entered, release = threading.Event(), threading.Event()
    block = [False]
    original_call = bridge.call
    def call(name, args=None):
        if 'search' in name and 'google_drive' not in name:
            if block[0]:
                entered.set()
                release.wait(15)
            return employer_pages(args, 'Example Employer')
        return original_call(name, args)
    bridge.call = call
    ws = Workspace(tmp_path / 'workspace', bridge)
    ws.save_profile(profile.model_copy(update={'is_example': False}))
    job = Job(source_id='browser-fixture', title='Service Coordinator', employer='Example Employer',
              url='https://example.com/jobs/coordinator', location='Melbourne',
              description='Coordinate service support and documentation across the customer operations team.')
    ws.add_job(job, full=True)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_workspace_app(ws), log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.05)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ['PLAYWRIGHT_EXECUTABLE_PATH'], headless=True)
            page = browser.new_page(viewport={'width': 1360, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/')
            expect(page.locator('#count-jobs')).to_have_text('1')
            page.evaluate('(id)=>openJob(id)', job.identity)
            page.locator('#career-research-job').click()
            expect(page.locator('#career-dialog')).to_be_visible()
            expect(page.locator('#career-disclosure')).to_be_visible()
            assert not ws.career.list(job.identity), 'Opening disclosure must not dispatch research'
            page.locator('#career-scopes input[value="pay"]').uncheck()
            page.locator('#career-start').click()
            expect(page.locator('#career-status')).to_contain_text('ready_for_review', timeout=15000)
            research = ws.career.list(job.identity)[0]
            assert research['options']['scope'] == ['employer', 'role']
            expect(page.locator('#career-downloads a')).to_have_count(4)
            href = page.locator('#career-downloads a').first.get_attribute('href')
            response = page.request.get(f'http://127.0.0.1:{port}'+href)
            assert response.ok and response.body().startswith(b'PK')
            page.locator('#career-reviewed').click()
            expect(page.locator('#career-review-status')).to_contain_text('approved')
            page.locator('[data-close="career-dialog"]').click()
            page.locator('#career-research-job').click()
            expect(page.locator('#career-status')).to_contain_text('ready_for_review')
            assert len(ws.career.list(job.identity)) == 1
            page.locator('[data-close="career-dialog"]').click()
            page.locator('#career-interview-job').click()
            page.locator('#career-stage').select_option('panel')
            page.locator('#career-prep-minutes').fill('45')
            page.locator('#career-communication').fill('Short bullets and pause cues')
            page.locator('#career-frameworks input[value="STAR"]').check()
            page.locator('#career-start').click()
            expect(page.locator('#career-status')).to_contain_text('ready_for_review', timeout=15000)
            prep = ws.career.list(job.identity)[0]
            assert prep['options']['stage'] == 'panel'
            assert prep['options']['preparation_minutes'] == 45
            assert 'STAR' in prep['options']['frameworks']
            page.locator('#career-practice-start').click()
            expect(page.locator('#career-practice-question')).to_contain_text('Question 1')
            page.locator('#career-practice-answer').fill('I coordinated requests and documented the process for the team.')
            page.locator('#career-practice-submit').click()
            expect(page.locator('#career-practice-feedback')).to_contain_text('Practice feedback')
            page.locator('#career-practice-retry').click()
            page.locator('#career-practice-answer').fill('I documented the service process and checked it with the team.')
            page.locator('#career-practice-submit').click()
            expect(page.locator('#career-practice-answer')).to_be_disabled()
            page.locator('#career-practice-next').click()
            expect(page.locator('#career-practice-question')).to_contain_text('Question 2')
            expect(page.locator('#career-practice-answer')).to_have_value('')
            page.screenshot(path=str(tmp_path / 'career-interview.png'))
            page.locator('[data-close="career-dialog"]').click()
            page.locator('#career-research-job').click()
            expect(page.locator('#career-status')).to_contain_text('ready_for_review')
            block[0] = True
            page.locator('#career-refresh').click()
            assert entered.wait(5)
            expect(page.locator('#career-cancel')).to_be_visible()
            page.locator('#career-cancel').click()
            expect(page.locator('#career-status')).to_contain_text('cancelled')
            release.set()
            assert ws.career.list(job.identity)[0]['status'] == 'cancelled'
            assert not errors, errors
            browser.close()
    finally:
        release.set()
        server.should_exit = True
        thread.join(5)
        sock.close()
