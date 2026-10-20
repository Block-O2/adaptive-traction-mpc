from task_bootstrap import *
import pickle,numpy as np,types
from dataclasses import replace
def main():
 import study_common as sc,clearance_reuse as cache,batched_mechanics
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanRequest
 cache.install();batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));rows=[]
 def make(p):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};return dict(adaptive_planner=clone,arguments=args,request=PlanRequest(row['request_id'],'TASK',0.,row['sensor_capture_ns'],row['request_ns'],True))
 for p in paths:
  b=make(p);t=time.monotonic_ns();original=b['adaptive_planner'].decide(**b['arguments']);base=(time.monotonic_ns()-t)/1e6
  b=make(p);t=time.monotonic_ns()
  with cache.boundary(b):new=b['adaptive_planner'].decide(**b['arguments'])
  elapsed=(time.monotonic_ns()-t)/1e6;same=sc.digest(replace(original,runtime_ms=0.))==sc.digest(replace(new,runtime_ms=0.));assert same,'COMPLETE_NATIVE_DECISION_CHANGED'
  b=make(p)
  with cache.boundary(b,shadow=True):shadow=b['adaptive_planner'].decide(**b['arguments'])
  assert sc.digest(replace(original,runtime_ms=0.))==sc.digest(replace(shadow,runtime_ms=0.))
  rows.append(dict(snapshot=str(p),sha256=sha(p),original_C2_ms=base,reused_ms=elapsed,complete_decision_exact=same,evidence=cache.EVENTS[-2]))
 out=dict(status='PASS',rows=rows,no_physics=True,baseline_mean_ms=float(np.mean([r['original_C2_ms'] for r in rows])),reused_mean_ms=float(np.mean([r['reused_ms'] for r in rows])),total_hits=sum(r['evidence']['hits'] for r in rows),excluded_field='Only original decision.runtime_ms genuine host elapsed; all scientific values and full certificates remain bit-exact',reuse_scope='one immutable request; constructor inputs plus full polynomial/duration/query key; original last_certificate replayed; original complete proof bit-exact')
 save(STUDY/'reports/OFFLINE_CLEARANCE_REUSE.json',out);print(json.dumps({k:out[k] for k in ('status','baseline_mean_ms','reused_mean_ms','total_hits')}))
if __name__=='__main__':main()
