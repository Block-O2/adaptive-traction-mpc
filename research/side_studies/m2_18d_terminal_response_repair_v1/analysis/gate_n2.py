from pathlib import Path
import json,subprocess,sys,time
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
def read(n):return json.loads((P/n).read_text())
assert read('N2_DONE.json')['all_children_joined']
assert read('N2_OWNER.json')['returncode']==0
subprocess.run([sys.executable,'-B',str(P/'control/independent_recompute.py'),'N2'],check=True)
rows=read('N2_RESULTS.json')['rows'];by={r['arm']:r for r in rows}
for a in ['T','T_repeat']:
 r=by[a];assert r['motion']['acceptance_pass'] and r['absolute_safety'] and r['task']=='PASS' and r['receipt']=='PASS' and r['motion']['gain_percent']>=1.
for n in ['N2_PAIR_GATE.json','N2_PARENT_GATE.json','audit/N2_T_REPEAT.json','audit/N2_B_ARCHIVE_GATE.json','audit/N2_E_ARCHIVE_GATE.json','audit/INDEPENDENT_N2.json']:assert read(n)['status']=='PASS'
assert json.loads((L/'audit/INTERVENTION_EXECUTION_AUDIT.json').read_text())['status']=='PASS'
assert json.loads((L/'audit/NEW_PREFIX_PROVENANCE.json').read_text())['status']=='PASS'
out=dict(status='PASS',unix=time.time(),hypothesis='Single terminal suffix duration factor 1.5',repeat_exact=True,N2_complete_motion_task_safety_causal_gain_pass=True,archival_B_E_exact=True,independent_raw_recomputation=True,new_prefix='U1 fixed before N2 physics',parameters_unchanged=True)
(P/'N2_T_GATE.json').write_text(json.dumps(out,indent=2)+'\n');print('N2_GATE PASS')
