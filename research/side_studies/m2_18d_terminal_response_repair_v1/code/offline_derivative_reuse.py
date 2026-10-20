from task_bootstrap import *
import pickle,numpy as np
from dataclasses import replace
def main():
 import study_common as sc,batched_mechanics,derivative_reuse as reuse
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1 as cls
 batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'));original=cls.check_quintic;reuse.install();replacement=cls.check_quintic
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));rows=[]
 def evaluate(p,which,shadow=False):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};cls.check_quintic=original if which=='original' else replacement;t=time.monotonic_ns()
  if which=='original':d=clone.decide(**args)
  else:
   with reuse.boundary(sha(p),shadow):d=clone.decide(**args)
  return (time.monotonic_ns()-t)/1e6,sc.digest(replace(d,runtime_ms=0.))
 expected=[evaluate(p,'original')[1] for p in paths]
 for i,p in enumerate(paths):assert evaluate(p,'reused',True)[1]==expected[i]
 for repeat in range(8):
  for which in (('original','reused') if repeat%2==0 else ('reused','original')):
   for i,p in enumerate(paths):
    ms,decision=evaluate(p,which);assert decision==expected[i],'COMPLETE_DECISION_CHANGED';rows.append(dict(round=repeat,implementation=which,snapshot=str(p),elapsed_ms=ms,full_decision_exact=True))
 baseline=float(np.mean([r['elapsed_ms'] for r in rows if r['implementation']=='original']));reused=float(np.mean([r['elapsed_ms'] for r in rows if r['implementation']=='reused']));out=dict(status='PASS',no_physics=True,complete_decision_checks=len(rows)+len(paths),baseline_C2_mean_ms=baseline,reused_mean_ms=reused,reduction_percent=100*(baseline-reused)/baseline,rows=rows,cache_events=reuse.EVENTS,scope='pure original derivative polynomial maximum; unchanged roots, polyval, acceptance and thresholds; constant translation proof still separately calculated',classification='EXACT_EQUIVALENT_OFFLINE_PASS_PHYSICS_GATE_PENDING')
 save(STUDY/'reports/OFFLINE_DERIVATIVE_REUSE.json',out);print(json.dumps({k:out[k] for k in ('status','complete_decision_checks','baseline_C2_mean_ms','reused_mean_ms','reduction_percent')}))
if __name__=='__main__':main()
