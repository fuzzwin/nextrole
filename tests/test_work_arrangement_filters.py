"""Geography and arrangement combine without widening other filters."""
import json
from pathlib import Path
import subprocess


def test_combined_work_filters_and_legacy_saved_choices():
    html=(Path(__file__).parents[1]/'campus_agent/workspace.html').read_text()
    names=['normaliseWorkBrowsing','australianLocationTarget','remoteListingText','remoteLocationAllowed','australianRemoteMatches','locationAndWorkMatches','locationMatches','stageMatches','vacancyMatches','filterJobRows']
    lines=html.splitlines()
    js='\n'.join(next(l for l in lines if l.startswith('const '+n+'=')) for n in ['WORK_MODES','AU_STATE_NAMES','AU_CITY_STATES'])
    js+='\n'+'\n'.join(next(l for l in lines if l.startswith('function '+n+'(')) for n in names)
    js+='\n'+html[html.index('function displayedCoverage('):html.index('function skillGauge(')]
    js+=r'''
const assert=require('node:assert/strict');
function row(id,city,mode,description='',country='Australia'){
 return {id,stage:'saved',role_types:[{id:'automation'}],job:{title:'Automation Specialist',employer:'Example',description},full_description:true,fit:{percent:57},listing:{closed:false},location_info:{stated:!!city,display:city?city+', '+country:'Location not stated',cities:country==='Australia'&&city?[city]:[],states:country==='Australia'&&city?[AU_CITY_STATES[city]]:[],arrangement:mode}};
}
const options={view:'all',query:'',types:['automation'],location:'city:Melbourne',workModes:['Hybrid','Remote'],includeAustralianRemote:true};
const rows=[row('mel-hybrid','Melbourne','Hybrid'),row('mel-remote','Melbourne','Remote'),row('syd-remote','Sydney','Remote'),row('syd-hybrid','Sydney','Hybrid'),row('mel-office','Melbourne','On-site'),row('unknown','', 'Remote'),row('usa','Boston','Remote','US only','United States'),row('explicit-au','','Remote','This role is fully remote within Australia.'),row('nsw-only','Sydney','Remote','You must be based in NSW.'),row('nsw-name','Sydney','Remote','Candidates must be based in New South Wales.'),row('vic-only','Melbourne','Remote','VIC residents only.'),row('city-only','Geelong','Remote','Geelong residents only.')];
assert.deepEqual(filterJobRows(rows,options,'2026-11-03').map(r=>r.id),['mel-hybrid','mel-remote','syd-remote','explicit-au','vic-only']);
assert.deepEqual(filterJobRows(rows,{...options,includeAustralianRemote:false},'2026-11-03').map(r=>r.id),['mel-hybrid','mel-remote','vic-only']);
assert.deepEqual(filterJobRows(rows,{...options,workModes:['Hybrid']},'2026-11-03').map(r=>r.id),['mel-hybrid']);
assert.deepEqual(filterJobRows(rows,{...options,workModes:['On-site']},'2026-11-03').map(r=>r.id),['mel-office']);
assert.equal(locationAndWorkMatches(row('x','Melbourne',''),{...options,workModes:['Not stated']}),true);
assert.equal(locationAndWorkMatches(row('x','Sydney','Remote'),{...options,location:'unknown'}),false);
assert.equal(locationAndWorkMatches(row('x','Sydney','Remote'),{...options,location:'place:Philippines'}),false);
assert.equal(locationAndWorkMatches(row('x','Boston','Remote','Location: Remote Australia. United States only','United States'),options),false);
assert.equal(locationAndWorkMatches(row('x','','Remote','Remote anywhere in Australia'),options),true);
assert.equal(locationAndWorkMatches(row('x','','Remote','We operate in Australia. This role is remote.'),options),false);
assert.equal(filterJobRows(rows,{...options,types:['project_delivery']},'2026-11-03').length,0);
assert.equal(filterJobRows(rows,{...options,minimum:60},'2026-11-03').length,0);
rows[0].fit.percent=null;rows[0].evidence_preview={percent:75};
assert.equal(filterJobRows(rows,{...options,minimum:60},'2026-11-03').some(r=>r.id==='mel-hybrid'),true);
rows[0].evidence_preview.percent=0;
assert.equal(displayedCoverage(rows[0]),0);
rows[0].listing.closed=true;
assert.equal(filterJobRows(rows,{...options,hideClosed:true},'2026-11-03').some(r=>r.id==='mel-hybrid'),false);
assert.equal(locationAndWorkMatches(row('conflict','Melbourne','Remote','NSW only'),options),false);
assert.equal(locationAndWorkMatches(row('restricted','Sydney','Remote','This role is only available to candidates based in NSW.'),options),false);
assert.equal(locationAndWorkMatches(row('restricted','Sydney','Remote','Only applicants based in Sydney are eligible.'),options),false);
assert.equal(vacancyMatches({listing:{closed:true}},'closed'),true);
assert.equal(vacancyMatches({fit:{assessment_state:'closed'}},'not_closed'),false);
assert.equal(vacancyMatches({listing:{days_to_close:0}},'closing'),true);
assert.equal(vacancyMatches({listing:{days_to_close:7}},'closing'),true);
assert.equal(vacancyMatches({listing:{days_to_close:8}},'closing'),false);
assert.equal(vacancyMatches({listing:{days_to_close:null}},'closing'),false);
assert.equal(vacancyMatches({listing:{}},'unknown'),true);
assert.equal(vacancyMatches({listing:{closed:true}},'unknown'),false);
assert.equal(filterJobRows(rows,{...options,availability:'closed'},'2026-11-03').length,1);
const migrated=normaliseWorkBrowsing({location:'mode:Remote',query:'python',types:['automation']});
assert.equal(migrated.location,'');assert.deepEqual(migrated.workModes,['Remote']);assert.equal(migrated.query,'python');assert.equal(migrated.includeAustralianRemote,true);
const modern=normaliseWorkBrowsing({location:'city:Melbourne',workModes:['Remote','Hybrid','Remote','bad'],includeAustralianRemote:false});
assert.deepEqual(modern.workModes,['Hybrid','Remote']);assert.equal(modern.location,'city:Melbourne');assert.equal(modern.includeAustralianRemote,false);
console.log(JSON.stringify({passed:true}));
'''
    result=subprocess.run(['node','-e',js],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['passed']
