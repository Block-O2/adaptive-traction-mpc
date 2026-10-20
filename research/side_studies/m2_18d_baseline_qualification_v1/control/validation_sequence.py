"""Serial execution of the four frozen lawful states after reproduction audit."""
from pathlib import Path
import os,sys,json,subprocess,time
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
assert read('BASELINE_REPRODUCTION.json')['status']=='PASS'
assert read('audit/INDEPENDENT_reproduction.json')['status']=='PASS'
assert not (P/'VALIDATION_SEQUENCE.jsonl').exists(),'Do not rerun this sequence in place'
plan=read('RUN_PLAN.json')
(P/'audit/VALIDATION_DISPATCH_FREEZE.json').write_text(json.dumps(dict(unix=time.time(),conditions=plan['validation_conditions'],selection='original frozen primary only',sequence='one serial owner then independent raw audit per condition; motion FAIL retained, safety/causal/fork/integral failure stops new starts',reproduction_pass=True,independent_reproduction_pass=True),indent=2)+'\n')
for condition in plan['validation_conditions']:
 group=condition['name']
 assert time.time()<plan['dispatch_cutoff_unix']-600
 for script,args in [('own_campaign.py',[group]),('independent_recompute.py',[group])]:
  cp=subprocess.run([sys.executable,'-B',str(P/'control'/script),*args],cwd=P)
  row=dict(group=group,script=script,unix=time.time(),returncode=cp.returncode)
  with (P/'VALIDATION_SEQUENCE.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  if cp.returncode:raise SystemExit(cp.returncode)
print('ALL_FOUR_FROZEN_CONDITIONS_COMPLETE',flush=True)
