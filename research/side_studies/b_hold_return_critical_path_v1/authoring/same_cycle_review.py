from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
O=S.parent/'b_fast_runtime_completion_v1'
ident=sys.argv[1];root=S if len(sys.argv)<3 else O
s=json.loads((root/'source/results'/ident/'summary.json').read_text())
m=json.loads((root/'output'/f'{ident}_MULTIRATE.json').read_text())
a=json.loads((root/'output'/f'{ident}_EXCLUSIVE_CYCLES.json').read_text())
ids={d['timing_request_id'] for d in s['decisions'] if d.get('phase')=='HOLD'}
requests=[r for r in m['native_requests'] if r['request_id'] in ids]
rows=[]
for r in requests:
 for point in ('request_ns','validation_start_ns'):
  cycle=next((c for c in a['cycles'] if c['start_ns']<=r[point]<c['end_ns']),None)
  if cycle:
   rows.append(dict(request_id=r['request_id'],point=point,start_ns=cycle['start_ns'],end_ns=cycle['end_ns'],duration_ms=cycle['duration_ns']/1e6,exclusive_ms={k:v/1e6 for k,v in cycle['exclusive_ns'].items()},cycle_closes=abs(sum(cycle['exclusive_ns'].values())-cycle['duration_ns'])<=1))
out=dict(id=ident,attribution_only=True,same_cycle=True,rows=rows)
p=S/'reports'/f'{ident}_SAME_CYCLE_BREAKDOWN.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
