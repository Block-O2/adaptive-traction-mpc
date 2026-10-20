from pathlib import Path
import sys,os,pickle,json,time,copy,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc,native_vectors,native_small_kernels,native_geometry,native_value_tree,native_quintic
native_vectors.install(expanded=True);native_small_kernels.install();native_geometry.install();native_value_tree.install();native_quintic.install()
from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as p
from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
from traction_mpc_stage4 import estimator_v2 as ma
original=p.AdaptiveMechanicsScreenV22.evaluate;captures=[];before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
def capture(self,belief,candidate,schedule):
 out=original(self,belief,candidate,schedule)
 if len(captures)<64:captures.append(pickle.dumps((self,belief,candidate,schedule),protocol=5))
 return out
p.AdaptiveMechanicsScreenV22.evaluate=capture
ident='036_N9_V3_A1_C1c_science_nominal'
rows=pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes())
for row in rows:
 if 'expected' in row:op.execute_task_snapshot(row['payload'])
p.AdaptiveMechanicsScreenV22.evaluate=original
import native_mechanics
_,fast=native_mechanics.install();cases=0;first=None;timings={'original':[],'N10':[]};call_counts=[]
for payload in captures:
 self,belief,candidate,schedule=pickle.loads(payload)
 for repeat in range(3):
  if repeat:
   schedule=copy.deepcopy(schedule);schedule.coefficients[:,0]+=repeat*1e-6
  start_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS;start=time.monotonic_ns();wanted=original(self,belief,candidate,schedule);timings['original'].append((time.monotonic_ns()-start)/1e6);middle=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
  start=time.monotonic_ns();actual=fast(self,belief,candidate,schedule);timings['N10'].append((time.monotonic_ns()-start)/1e6);end=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
  assert middle-start_calls==end-middle==self.sample_count
  if wanted!=actual and first is None:first=dict(expected=wanted,actual=actual)
  for delta in (-2e-9,2e-9):
   limited=p.AdaptiveMechanicsScreenV22(force_limit_n=max(1e-9,wanted['peak_force_n']+delta),moment_limit_nm=max(1e-9,wanted['peak_moment_nm']+delta),sample_count=self.sample_count)
   assert original(limited,belief,candidate,schedule)==fast(limited,belief,candidate,schedule)
  call_counts.append(dict(original=middle-start_calls,native=end-middle));cases+=1
out=dict(status='PASS' if first is None else 'FAIL',captured_original_calls=len(captures),perturbed_cases=cases,threshold_accept_reject_cases=cases*2,bit_exact=first is None,first_difference=first,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,same_model_calls_per_screen=True,timing_ms={k:dict(zip(('p50','p95','p99','max'),np.percentile(v,[50,95,99,100]).tolist())) for k,v in timings.items()},native_physics_steps=0,scope='same original sample times, every inverse/allocator/residual call in original order; pure outer finite/max loop compiled')
sc.save('N10_MECHANICS_LOCAL_REGRESSION.json',out);print(json.dumps(out))
