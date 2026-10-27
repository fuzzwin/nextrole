"""Reuse presentation work only while all its inputs remain identical."""
from concurrent.futures import ThreadPoolExecutor
import json
from test_dashboard_acceptance import candidate,role
from test_workspace import FakeBridge
from campus_agent.workspace import Workspace

TEXT='Location: Melbourne VIC\nRequirements\n- Python workflow automation experience.\n- Power Automate workflow experience.\n- Microsoft 365 systems support experience.'

def setup(tmp_path):
 ws=Workspace(tmp_path,FakeBridge());ws.save_profile(candidate());job=role(TEXT);ws.add_job(job,full=True)
 return ws,job


def test_unchanged_reads_do_not_repeat_assessment_and_results_are_isolated(tmp_path,monkeypatch):
 import campus_agent.fit as module
 original=module.fit_assessment;calls=[]
 def observed(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
 monkeypatch.setattr(module,'fit_assessment',observed)
 ws,job=setup(tmp_path)
 try:
  first=ws.jobs();first[0]['fit']['percent']=-99
  again=ws.jobs()
  assert len(calls)==1 and again[0]['fit']['percent']>=80
 finally:ws.close()


def test_profile_and_employer_corrections_invalidate_saved_assessment(tmp_path):
 ws,job=setup(tmp_path)
 try:
  assert ws.jobs()[0]['fit']['auto_eligible']
  ws.save_profile(candidate().model_copy(update={'experience':[],'skills':[]}))
  assert not ws.jobs()[0]['fit']['auto_eligible']
  ws.save_profile(candidate())
  ws.add_job(job.model_copy(update={'employer':'Unknown'}),full=True)
  assert ws.jobs()[0]['fit']['percent'] is None
 finally:ws.close()


def test_closing_date_and_manual_pins_remain_fresh(tmp_path):
 ws,job=setup(tmp_path)
 try:
  assert ws.jobs()[0]['top_match']
  ws.set_meta('listing:'+job.identity,{'closes_on':'2020-01-01'})
  ws.set_top_listing(job.identity,True)
  value=ws.jobs()[0]
  assert value['fit']['status']=='Closed' and not value['top_match'] and value['top_saved']
 finally:ws.close()


def test_unread_flag_and_location_override_remain_fresh(tmp_path):
 ws,job=setup(tmp_path)
 try:
  assert ws.jobs()[0]['top_match']
  ws.set_meta('location_override:'+job.identity,'Sydney NSW')
  assert not ws.jobs()[0]['top_match']
  with ws.store.connect() as db:db.execute('UPDATE job_details SET full_description=0 WHERE job_id=?',(job.identity,))
  assert ws.jobs()[0]['fit']['percent'] is None
 finally:ws.close()


def test_external_packet_report_changes_are_not_cached(tmp_path):
 from campus_agent.packet_checks import RULESET_VERSION
 ws,job=setup(tmp_path)
 try:
  packet=ws.artifacts/'synthetic';packet.mkdir()
  quality=packet/'quality-report.json'
  quality.write_text(json.dumps({'delivery_ready':True,'errors':[],'pending':[],'ruleset':RULESET_VERSION}))
  (packet/'tailoring.json').write_text(json.dumps({'profile':ws.profile.model_dump(),'document_preferences':ws.document_style().model_dump()}))
  ws.store.update(job.identity,'prepared',str(packet))
  assert ws.jobs()[0]['quality']['delivery_ready']
  quality.write_text(json.dumps({'delivery_ready':False,'errors':['Changed packet'],'pending':[],'ruleset':RULESET_VERSION}))
  assert not ws.jobs()[0]['quality']['delivery_ready']
 finally:ws.close()


def test_simultaneous_readers_share_the_initial_work(tmp_path,monkeypatch):
 import campus_agent.fit as module
 original=module.fit_assessment;calls=[]
 def observed(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
 monkeypatch.setattr(module,'fit_assessment',observed)
 ws,job=setup(tmp_path)
 try:
  with ThreadPoolExecutor(max_workers=4) as pool:values=list(pool.map(lambda _:ws.jobs(),range(4)))
  assert len(calls)==1 and all(v[0]['fit']['auto_eligible'] for v in values)
 finally:ws.close()
