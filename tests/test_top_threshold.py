import re
import pytest
from fastapi.testclient import TestClient
from test_workspace import workspace, profile, role
from test_fit import profile as evidence_profile
from campus_agent.workspace import Preferences
from campus_agent.workspace_web import create_workspace_app


def seventy_role(workspace, role):
    p=evidence_profile(['Coordinated projects.','Managed stakeholders.','Managed change control.'])
    p.skills=[]
    workspace.save_profile(p)
    job=role.model_copy(update={'title':'Project Coordinator','location':'Melbourne VIC','description':
        'About the role\nThe environment includes Python.\nRequirements\n- Experience coordinating projects.\n- Experience managing stakeholders.\n- Experience managing change control.'})
    workspace.add_job(job,full=True)
    return job


def test_legacy_seventy_percent_cannot_trigger_automatic_top(workspace,role):
    job=seventy_role(workspace,role)
    assert Preferences().auto_top_threshold==70
    row=workspace.jobs()[0]
    assert row['legacy_fit']['percent']==70 and row['fit']['percent'] is None
    assert not row['fit']['auto_eligible'] and not row['top_match']
    workspace.save_preferences(workspace.preferences.model_copy(update={'auto_top_threshold':71}))
    assert not workspace.jobs()[0]['top_match']
    workspace.set_top_listing(job.identity,True)
    assert workspace.jobs()[0]['top_listing']
    workspace.save_preferences(workspace.preferences.model_copy(update={'auto_top_threshold':70}))
    assert not workspace.jobs()[0]['top_match']
    workspace.add_job(job.model_copy(update={'description':job.description+'\n- Kubernetes development experience required.'}),full=True)
    assert not workspace.jobs()[0]['top_match']
    assert workspace.jobs()[0]['top_saved']


def test_top_settings_save_is_scoped_and_does_not_contact_connectors(workspace):
    before=workspace.preferences.model_dump()
    app=create_workspace_app(workspace)
    with TestClient(app,base_url='http://127.0.0.1:8877') as client:
        token=re.search(r'const token="([^"]+)"',client.get('/').text)[1]
        headers={'origin':'http://127.0.0.1:8877','x-workspace-token':token}
        response=client.post('/api/top-settings',json={'enabled':False,'threshold':82},headers=headers)
        assert response.status_code==200
        assert workspace.preferences.model_dump()=={**before,'auto_top_enabled':False,'auto_top_threshold':82}
        assert not workspace.bridge.calls
        for threshold in [69,101,70.5,True,None]:
            response=client.post('/api/top-settings',json={'enabled':True,'threshold':threshold},headers=headers)
            assert response.status_code==400
        assert workspace.preferences.auto_top_threshold==82
        response=client.post('/api/top-settings',json={'enabled':True,'threshold':70},headers=headers)
        assert response.status_code==200
        assert workspace.get_meta('preferences')['auto_top_threshold']==70
