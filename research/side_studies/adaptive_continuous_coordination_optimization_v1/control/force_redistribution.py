from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');rows=[json.loads(x) for x in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()];b=np.load(P/'source/results/development_B0/trace.npz');bm=b['stage']=='TASK';t=b['time_s'][bm];bf=np.linalg.norm(b['physical_cuff_force_world_n'][bm],axis=1);dt=np.diff(t);out=[]
for r in rows:
 if r['status']!='COMPLETE':continue
 a=np.load(P/'source/results'/r['id']/'trace.npz');m=a['stage']=='TASK'
 if not np.array_equal(a['time_s'][m],t):out.append(dict(id=r['id'],status='TIME_GRID_DIFFERENT_UNALIGNED'));continue
 f=np.linalg.norm(a['physical_cuff_force_world_n'][m],axis=1);delta=f-bf;pos=float(np.maximum(delta[:-1],0)@dt);neg=float(np.minimum(delta[:-1],0)@dt);c=np.r_[0,np.cumsum(delta[:-1]*dt)];ix=int(np.argmax(abs(c)));assert abs(c[-1]-(r['J_F_N_s']-rows[0]['J_F_N_s']))<1e-8
 out.append(dict(id=r['id'],delta_J_F_N_s=float(c[-1]),positive_delta_force_area_N_s=pos,negative_delta_force_area_N_s=neg,absolute_delta_force_area_N_s=pos-neg,max_abs_cumulative_force_delta_N_s=float(abs(c[ix])),max_abs_cumulative_delta_task_s=float(t[ix]-t[0]),peak_abs_force_norm_difference_N=float(np.max(abs(delta))),clinical_interpretation=False))
(P/'TEMPORAL_FORCE_REDISTRIBUTION.json').write_text(json.dumps(dict(rows=out,interpretation='Signed local force changes may cancel in final J_F. Absolute difference area is diagnostic, not the objective and not causal attribution.'),indent=2))
print(json.dumps([r for r in out if r['id']=='development_legacy005'],indent=2))
