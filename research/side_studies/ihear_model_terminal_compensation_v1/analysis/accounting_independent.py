"""Check physical work from raw-verified row counts minus each live prefix."""
from pathlib import Path
import json,time
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
acc=read('ATTEMPT_ACCOUNTING.json');raw={r['id']:r for g in ['Dev','Ctrl','W2'] for r in read('audit/INDEPENDENT_'+g+'.json')['checks']};rows=[]
for r in acc['rows']:
 fork=read('audit/'+r['group']+'_FORK_CONTEXT.json');prefix=int(round(fork['physical_s']/.00025));assert abs(prefix*.00025-fork['physical_s'])<1e-8
 if r['id'] in raw:total=raw[r['id']]['native_rows'];origin='Independently streamed native row count'
 else:
  partial=read('output/'+r['id']+'_PARTIAL_COMPUTE.json');total=partial['native_physics_steps'];assert total==prefix;origin='Preserved failure counter equals captured live prefix; no post-fork step'
 expected=total-prefix if r['kind']=='FULL_TASK_FORK' else total
 assert expected==r['actual_new_native_steps'],(r['id'],expected,r['actual_new_native_steps'])
 rows.append(dict(id=r['id'],total_native_rows_or_preserved_failure_counter=total,live_prefix_steps=prefix,inherited_steps=prefix if r['kind']=='FULL_TASK_FORK' else 0,independent_new_steps=expected,evidence=origin))
assert sum(r['independent_new_steps'] for r in rows)==acc['actual_new_native_steps']
out=dict(status='PASS',unix=time.time(),new_physics=0,method='Full runs use independently streamed native counts; subtract exact live-prefix physics clock / .00025 only for forks. Failed child has zero new steps; failed parent retains prefix.',total_actual_new_native_steps=sum(r['independent_new_steps'] for r in rows),rows=rows)
(P/'audit/INDEPENDENT_ATTEMPT_ACCOUNTING.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status='PASS',actual_new_steps=out['total_actual_new_native_steps'])))
