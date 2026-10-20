from pathlib import Path
import json,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()]
def state(ident):
 ds=json.loads((S/'output'/(ident+'_DECISIONS.json')).read_text())['rows'];d=next(d for d in ds if d.get('phase')=='RETURN' and d.get('native_index')==0)
 if 'physical_time_s' in d.get('current_inputs',{}):at=d['current_inputs']['physical_time_s']
 else:
  summary=json.loads((S/'source/results'/ident/'summary.json').read_text());m=json.loads((S/'reports'/(ident+'_MEASURED.json')).read_text());start=next(t['time_s'] for t in summary['task']['phase_transitions'] if t['to']=='HOLD')-m['phase_durations']['OUTBOUND'];at=start+d['task_s']
 with np.load(S/'motion_series'/(ident+'.npz')) as z:
  i=int(np.argmin(abs(z['time_s']-at)));assert abs(z['time_s'][i]-at)<1e-8;return z['true_q_rad'][i],z['true_dq_rad_s'][i]
bq,bv=state('baseline_NATIVE_SCALAR_18');br=next(r for r in rows if r['id']=='baseline_NATIVE_SCALAR_18');out=[]
for r in rows:
 if not r['id'].startswith('outbound_'):continue
 q,v=state(r['id']);out.append(dict(id=r['id'],RETURN0_q_max_delta_rad=float(np.max(abs(q-bq))),RETURN0_dq_max_delta_rad_s=float(np.max(abs(v-bv))),RETURN_J_F_delta_N_s=r['phase_J_F_N_s']['RETURN']-br['phase_J_F_N_s']['RETURN']))
x=dict(scope='evaluation-only scientific state, not action inputs',rows=out,max_q_rad=max(r['RETURN0_q_max_delta_rad'] for r in out),max_dq_rad_s=max(r['RETURN0_dq_max_delta_rad_s'] for r in out),max_RETURN_J_F_delta_N_s=max(abs(r['RETURN_J_F_delta_N_s']) for r in out));(S/'RETURN_STATE_PREVIEW.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:v for k,v in x.items() if k!='rows'}))
