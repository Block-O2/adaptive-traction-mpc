from task_bootstrap import *
import pickle,numpy as np
from dataclasses import replace
def main():
 import study_common as sc,batched_mechanics,compiled_trig as kernel
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'));original=m._trig_bounds
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));rows=[]
 def evaluate(p):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};t=time.monotonic_ns();d=clone.decide(**args);return (time.monotonic_ns()-t)/1e6,sc.digest(replace(d,runtime_ms=0.))
 kernel.install(shadow=True)
 # Deterministic endpoints, interval widths, cancellation and domain limits.
 test=np.random.default_rng(2026100783);checks=0
 for lo,hi in [(-4.,-4.),(4.,4.),(0.,0.),(-0.,0.),(-4.,4.),(-1e-12,1e-12),*[(float(a),float(a+d)) for a,d in zip(test.uniform(-3.8,3.8,1000),test.uniform(0.,.1,1000))]]:
  for cosine in (False,True):kernel.bounds(lo,hi,cosine);checks+=1
 expected=[];m._trig_bounds=original;m._endpoint_bounds.cache_clear();original.cache_clear()
 for p in paths:expected.append(evaluate(p)[1])
 # Alternate order and empty original mutable memoization per round. No
 # physics, predictions, planted future Human state, or candidate generation.
 for repeat in range(8):
  for which in (('original','compiled') if repeat%2==0 else ('compiled','original')):
   m._trig_bounds=original if which=='original' else kernel.bounds;kernel.SHADOW=False;m._endpoint_bounds.cache_clear();original.cache_clear();kernel.bounds.cache_clear()
   for i,p in enumerate(paths):
    ms,decision=evaluate(p);assert decision==expected[i],'COMPLETE_DECISION_CHANGED';rows.append(dict(round=repeat,implementation=which,snapshot=str(p),elapsed_ms=ms,full_decision_exact=True))
 baseline=float(np.mean([r['elapsed_ms'] for r in rows if r['implementation']=='original']));compiled=float(np.mean([r['elapsed_ms'] for r in rows if r['implementation']=='compiled']));out=dict(status='PASS',no_physics=True,proof_checks=checks,complete_decision_checks=len(rows),baseline_C2_mean_ms=baseline,compiled_mean_ms=compiled,reduction_percent=100*(baseline-compiled)/baseline,rows=rows,original_caches_retained='immutable exact angle bounds lru8192 and full endpoint input lru8192',original_certificate_and_thresholds_unchanged=True,build=json.loads((STUDY/'compiled_trig/BUILD.json').read_text()),classification='EXACT_EQUIVALENT_OFFLINE_PASS_PHYSICS_GATE_PENDING')
 save(STUDY/'reports/OFFLINE_COMPILED_TRIG.json',out);print(json.dumps({k:out[k] for k in ('status','proof_checks','complete_decision_checks','baseline_C2_mean_ms','compiled_mean_ms','reduction_percent')}))
if __name__=='__main__':main()
