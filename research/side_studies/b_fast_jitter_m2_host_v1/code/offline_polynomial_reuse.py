from task_bootstrap import *
import pickle,numpy as np
from dataclasses import replace
def main():
 import study_common as sc,polynomial_reuse as cache,batched_mechanics
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanRequest
 cache.install();batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));rows=[]
 def make(p):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};return dict(adaptive_planner=clone,arguments=args,request=PlanRequest(row['request_id'],'TASK',0.,row['sensor_capture_ns'],row['request_ns'],True))
 for p in paths:
  base=[];fast=[]
  for repeat in range(3):
   b=make(p);t=time.monotonic_ns();original=b['adaptive_planner'].decide(**b['arguments']);base.append((time.monotonic_ns()-t)/1e6)
   b=make(p);t=time.monotonic_ns()
   with cache.boundary(b):new=b['adaptive_planner'].decide(**b['arguments'])
   fast.append((time.monotonic_ns()-t)/1e6);assert sc.digest(replace(original,runtime_ms=0.))==sc.digest(replace(new,runtime_ms=0.)),'COMPLETE_NATIVE_DECISION_CHANGED'
  evidence=cache.EVENTS[-1]
  b=make(p)
  with cache.boundary(b,shadow=True):shadow=b['adaptive_planner'].decide(**b['arguments'])
  assert sc.digest(replace(original,runtime_ms=0.))==sc.digest(replace(shadow,runtime_ms=0.))
  rows.append(dict(snapshot=str(p),input_sha256=sha(p),original_C2_ms=base,reused_ms=fast,complete_decision_exact=True,evidence=evidence))
 baseline=float(np.mean([np.median(r['original_C2_ms']) for r in rows]));fast=float(np.mean([np.median(r['reused_ms']) for r in rows]));out=dict(status='PASS',no_physics=True,rows=rows,baseline_mean_of_state_medians_ms=baseline,reused_mean_of_state_medians_ms=fast,relative_reduction=1-fast/baseline,full_current_model_and_clearance_checks_retained=True,excluded_field='Only decision.runtime_ms genuine host elapsed; all scientific outputs and certificates exact',qualification_claim=False)
 save(STUDY/'reports/OFFLINE_POLYNOMIAL_REUSE.json',out);print(json.dumps({k:out[k] for k in ('status','baseline_mean_of_state_medians_ms','reused_mean_of_state_medians_ms','relative_reduction')}))
if __name__=='__main__':main()
