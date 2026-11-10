import re
from types import SimpleNamespace
from fastapi.testclient import TestClient
from test_workspace import workspace, profile
from campus_agent.workspace_web import create_workspace_app


def test_career_reads_and_mutations_require_workspace_capability(workspace):
    calls=[]
    workspace.career.close()
    workspace.career=SimpleNamespace(close=lambda:None,
        list=lambda job:(calls.append(job) or []),
        get=lambda run:{'run_id':run},
        start=lambda job,feature,options,refresh:{'run_id':'run'},
        cancel=lambda run:{'status':'cancelled'},
    )
    with TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as client:
        token=re.search(r'const token="([^"]+)"',client.get('/').text)[1]
        assert client.get('/api/jobs/job/career-runs').status_code==403
        assert client.get('/api/career-runs/run').status_code==403
        assert client.get('/api/career-runs/run/artifacts/guide_pdf?token=wrong').status_code==403
        assert not calls
        headers={'x-workspace-token':token,'origin':'http://127.0.0.1:8877'}
        assert client.get('/api/jobs/job/career-runs',headers=headers).json()=={'runs':[]}
        assert client.post('/api/jobs/job/career-runs',headers=headers,json={'feature':'interview_prep'}).status_code==200
        assert client.post('/api/career-runs/run/cancel',headers={**headers,'origin':'https://other.example'}).status_code==403


def test_other_app_token_cannot_read_private_career_result(workspace):
    workspace.career.close()
    workspace.career=SimpleNamespace(close=lambda:None,get=lambda run:{'private':'candidate evidence'})
    with TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as first, TestClient(create_workspace_app(workspace),base_url='http://127.0.0.1:8877') as second:
        token=re.search(r'const token="([^"]+)"',first.get('/').text)[1]
        assert second.get('/api/career-runs/run',headers={'x-workspace-token':token}).status_code==403
