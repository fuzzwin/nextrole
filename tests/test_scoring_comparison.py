import re

from fastapi.testclient import TestClient

from campus_agent import semantic
from campus_agent.scoring_comparison import CONTROL_CASES, run_controls
from campus_agent.workspace_web import create_workspace_app
from test_assessment_flow import make_job
from test_workspace import profile, workspace


def test_rules_only_controls_run_without_inference(monkeypatch):
    def unavailable(*args):
        raise AssertionError('Rules-only review attempted inference')

    monkeypatch.setattr(semantic, 'call_model', unavailable)
    report = run_controls()
    assert report['rules']['correct'] == len(CONTROL_CASES)
    assert report['rules']['percent'] == 33
    assert report['qwen'] is None


def test_comparison_route_returns_source_bound_preview_without_saving_a_rating(workspace):
    text = 'Requirements\n- Python automation experience.\n- Microsoft 365 support experience.'
    job = make_job(938, text)
    workspace.add_job(job, full=True)
    url = f'/api/jobs/{job.identity}/compare-evidence'
    with TestClient(create_workspace_app(workspace), base_url='http://127.0.0.1:8877') as client:
        assert client.post(url, json={'with_qwen':False}).status_code == 403
        token = re.search(r'const token="([^"]+)"', client.get('/').text)[1]
        headers = {'origin':'http://127.0.0.1:8877', 'x-workspace-token':token}
        response = client.post(url, headers=headers, json={'with_qwen':False})
        assert response.status_code == 200
        preview = response.json()
        assert preview['qwen'] is None
        assert {row['quote'] for row in preview['rules']['requirements']} == {
            'Python automation experience.', 'Microsoft 365 support experience.'}
        assert workspace.get_meta('semantic:'+job.identity) is None
        assert workspace.jobs()[0]['fit']['percent'] is None
