from io import BytesIO
from threading import Event
from time import monotonic, sleep
from xml.etree import ElementTree
from zipfile import ZipFile
import re

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from campus_agent.application_workflow import carry_review
from campus_agent.workspace_web import create_workspace_app
from test_workspace import workspace, profile, role
from test_source_completion import SOURCE_AD
from test_career import employer_pages


def test_revalidation_carries_a_review_only_for_unchanged_criteria():
    before = {'id':'0', 'quote':'Administer Microsoft 365.', 'importance':'essential', 'kind':'competency',
              'evidence_state':'direct', 'evidence':[{'text':'Administered Microsoft 365.'}], 'transfer_reason':'Direct delivery.'}
    review = {'requirements':[before], 'reviewed_by':'user'}
    current = {**before, 'id':'2', 'quote':'Administer Microsoft\n365.'}
    result = carry_review(review, [current])
    assert result['percent'] == 100 and result['reviewed_by'] == 'user'
    assert result['requirements'][0]['id'] == '2'
    assert carry_review(review, [{**current, 'importance':'standard'}]) is None
    assert carry_review(review, [{**current, 'quote':'Administer Microsoft 365 and Purview.'}]) is None


def wait_for(client, url, headers, predicate):
    end = monotonic() + 10
    while monotonic() < end:
        run = client.get(url, headers=headers).json()
        if predicate(run):
            return run
        sleep(.05)
    pytest.fail('Preparation task did not finish')


@pytest.mark.parametrize('output_format,delivery', [('zip','email'), ('pdf','download'), ('files','download')])
def test_prepare_full_package_uses_real_document_exports(workspace, role, output_format, delivery):
    job = role.model_copy(update={'description': SOURCE_AD})
    workspace.add_job(job, full=True)
    original = workspace.bridge.call
    parts_sent = []
    sequence = []
    started, continue_read = Event(), Event()

    def call(tool, data=None):
        if tool == 'search_service.web_run':
            if 'open' in data and data['open'][0]['ref_id'] == str(job.url):
                sequence.append('advert')
                started.set()
                assert continue_read.wait(5)
                return {'text': SOURCE_AD}
            sequence.append('research')
            return employer_pages(data, 'Example Employer')
        if tool == 'gmail.send_email':
            sequence.append('send')
            assert data['to'] == 'owner@example.com'
            parts_sent.extend(data['payload']['parts'][1:])
            return {'id':'sent-id'}
        if tool == 'gmail.read_email':
            return {'payload':{'parts':[{'filename':part['filename']} for part in parts_sent]}}
        return original(tool,data)

    workspace.bridge.call = call
    workspace.connect()
    url = f'/api/jobs/{job.identity}/preparation'
    with TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as client:
        page = client.get('/').text
        assert 'Prepare full package' in page
        token = re.search(r'const token="([^"]+)"',page)[1]
        headers = {'origin':'http://127.0.0.1:8877','x-workspace-token':token}
        assert client.get(url).status_code == 403
        options = {'format':output_format, 'delivery':delivery, 'deeper_fit':False}
        try:
            launch = client.post(url,headers=headers,json=options)
            assert launch.status_code == 200, launch.text
            assert started.wait(3)
            again = client.post(url,headers=headers,json=options).json()
            assert again['id'] == launch.json()['id']
        finally:
            continue_read.set()
        run = wait_for(client,url,headers,lambda r:r['status'] != 'running')
        assert run['status'] == 'ready', run.get('error')
        assert sequence[0] == 'advert' and 'research' in sequence and 'send' not in sequence
        paths = {}
        for file in run['files']:
            route = f"{url}/{run['id']}/files/{file['name']}"
            assert client.get(route).status_code == 403
            response = client.get(route,headers=headers)
            assert response.status_code == 200, response.text[:300]
            paths[file['name']] = response.content
        if output_format == 'zip':
            assert len(paths) == 1
            with ZipFile(BytesIO(next(iter(paths.values())))) as archive:
                assert len(archive.namelist()) == 11 and archive.testzip() is None
                with ZipFile(BytesIO(archive.read('Job research guide.docx'))) as word:
                    ElementTree.fromstring(word.read('word/document.xml'))
        elif output_format == 'pdf':
            assert len(paths) == 1 and len(PdfReader(BytesIO(next(iter(paths.values())))).pages) >= 7
        else:
            assert len(paths) == 11 and {'Resume.pdf','Cover Letter.pdf','Preparation summary.pdf'} <= set(paths)
        assert client.get(f"{url}/{run['id']}/files/secret",headers=headers).status_code == 400
        email = f"{url}/{run['id']}/email"
        assert client.post(email,headers=headers,json={'reviewed':False}).status_code == 400
        if delivery == 'email':
            assert client.post(email,headers=headers,json={'reviewed':True}).status_code == 200
            done = wait_for(client,url,headers,lambda r:r['mail']['status'] != 'sending')
            assert done['mail']['status'] == 'sent' and done['mail']['message_id'] == 'sent-id'
            assert client.post(email,headers=headers,json={'reviewed':True}).json()['mail']['status'] == 'sent'
            assert sequence.count('send') == 1
        else:
            assert client.post(email,headers=headers,json={'reviewed':True}).status_code == 400
