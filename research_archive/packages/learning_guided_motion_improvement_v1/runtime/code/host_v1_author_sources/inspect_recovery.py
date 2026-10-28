from pathlib import Path
import sys,json,gzip
S=Path('/home/hank/ihear-lab/learning_guided_motion_improvement_v1/runtime');sys.dont_write_bytecode=True
p=S/'source/results/005_M2_guard_off_retry/runtime_artifacts.json.gz'
with gzip.open(p,'rt') as f:x=json.load(f)
print('TOP',list(x))
for k,v in x.items():
 if isinstance(v,dict):print(k,'DICT',list(v)[:45])
 elif isinstance(v,list):print(k,'LIST',len(v),'keys',list(v[0])[:40] if v and isinstance(v[0],dict) else '')
ipc=json.loads((S/'output/005_M2_guard_off_retry_DIRECT_IPC.json').read_text());co=[r['m2_worker_evidence'] for r in ipc['rows'] if 'm2_worker_evidence' in r]
print('WORKER',[dict(request_id=r['request_id'],age=r['source_age_at_worker_return_ms'],late_carry=r['admission']['late_carry'],source=None if not r.get('selection_row') else r['selection_row']['selected_source']) for r in co])
