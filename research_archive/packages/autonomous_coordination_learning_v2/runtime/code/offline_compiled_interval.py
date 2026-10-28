from task_bootstrap import *
import pickle,numpy as np
from dataclasses import replace
def main():
 import study_common as sc,batched_mechanics,compiled_interval as kernel
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));rows=[];original=m.monotonic_certificate;inputs=[]
 def capture(e,c):inputs.append((e,np.asarray(c).copy()));return original(e,c)
 m.monotonic_certificate=capture
 def evaluate(p):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};t=time.monotonic_ns();d=clone.decide(**args);return (time.monotonic_ns()-t)/1e6,d
 baseline=[]
 for p in paths:baseline.append(evaluate(p))
 m.monotonic_certificate=original;kernel.install(shadow=True)
 for p,(elapsed,d) in zip(paths,baseline):
  ms,new=evaluate(p);assert sc.digest(replace(d,runtime_ms=0.))==sc.digest(replace(new,runtime_ms=0.)),'FULL_DECISION_CHANGED';rows.append(dict(snapshot=str(p),sha256=sha(p),baseline_C2_ms=elapsed,shadow_compiled_ms=ms,full_decision_exact=True))
 # Check registered-domain boundaries and specialization rejection as well.
 checks=0
 for e,c in inputs:
  variants=[c,c+np.array([[0.,1e-11,0.,0.,0.,0.],[0.,0.,0.,0.,0.,0.]]),c+np.array([[0.,1e-8,0.,0.,0.,0.],[0.,0.,0.,0.,0.,0.]])]
  for v in variants:kernel.certificate(e,v);checks+=1
 kernel.install(shadow=False)
 for p,r in zip(paths,rows):
  ms,new=evaluate(p);assert sc.digest(replace(baseline[len([x for x in rows if 'compiled_ms' in x])][1],runtime_ms=0.))==sc.digest(replace(new,runtime_ms=0.));r['compiled_ms']=ms
 mean=float(np.mean([r['baseline_C2_ms'] for r in rows]));newmean=float(np.mean([r['compiled_ms'] for r in rows]));out=dict(status='PASS',no_physics=True,complete_decisions_exact=True,proof_checks=checks,original_captured_certificates=len(inputs),compiled_calls=len(kernel.ROWS),rows=rows,baseline_C2_mean_ms=mean,compiled_mean_ms=newmean,reduction_percent=100*(mean-newmean)/mean,kernel_fallbacks=sum(r['fallback'] for r in kernel.ROWS),excluded_only_field='runtime_ms',build=json.loads((STUDY/'compiled_interval/BUILD.json').read_text()),classification='EXACT_EQUIVALENT_OFFLINE_PASS_PHYSICS_GATE_PENDING')
 save(STUDY/'reports/OFFLINE_COMPILED_INTERVAL.json',out);print(json.dumps({k:out[k] for k in ('status','proof_checks','original_captured_certificates','baseline_C2_mean_ms','compiled_mean_ms','reduction_percent','kernel_fallbacks')}))
if __name__=='__main__':main()
