"""Exercise the actual browser filter function without a browser or private data."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest


def test_source_exclusions_apply_to_all_ordinary_views_but_keep_history():
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    html=(Path(__file__).parents[1]/'campus_agent/workspace.html').read_text()
    function=next(line for line in html.splitlines() if line.startswith('function stageMatches('))
    script=function+'''\nconst assert=require('node:assert/strict');
const blocked={source_policy:{status:'excluded'},stage:'saved',top_listing:true,fit:{status:'Good match',percent:100},listing:{}};
for(const view of ['all','top','matches','review','unrated','prepared','saved','archived'])assert.equal(stageMatches(blocked,view),false,view);
assert.equal(stageMatches(blocked,'excluded'),true);
assert.equal(stageMatches({...blocked,stage:'applied'},'applied'),true);
assert.equal(stageMatches({...blocked,source_policy:null},'excluded'),false);
assert.equal(stageMatches({...blocked,source_policy:null},'all'),true);
'''
    subprocess.run([node,'-e',script],check=True,capture_output=True,text=True)
