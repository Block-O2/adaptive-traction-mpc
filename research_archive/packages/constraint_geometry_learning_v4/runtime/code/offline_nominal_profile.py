"""Locate the unavoidable original B nominal work on saved causal snapshots."""
from task_bootstrap import *
import pickle,cProfile,pstats,io,numpy as np
def main():
 import study_common as sc
 import batched_mechanics
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'))
 rows=[];prof=cProfile.Profile()
 def evaluate(p):
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);clone.planner.residual_spec={};t=time.monotonic_ns();decision=clone.decide(**args);elapsed=(time.monotonic_ns()-t)/1e6
  return elapsed,np.asarray(decision.executed.target_q_rad),decision.selection_mode
 for p in paths:
  elapsed,target,mode=evaluate(p);rows.append(dict(snapshot=str(p),input_sha256=sha(p),original_ms=elapsed,target=target.tolist(),mode=mode))
 batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
 for p,r in zip(paths,rows):
  elapsed,target,mode=evaluate(p);r.update(C2_ms=elapsed,target_exact=bool(np.array_equal(target,np.asarray(r['target']))),mode_equal=mode==r['mode']);assert r['target_exact'] and r['mode_equal']
 prof.enable()
 for p in paths:evaluate(p)
 prof.disable();stats=pstats.Stats(prof);top=[]
 for (path,line,name),(cc,nc,tt,ct,callers) in sorted(stats.stats.items(),key=lambda x:x[1][3],reverse=True)[:60]:top.append(dict(path=path,line=line,name=name,primitive_calls=cc,total_calls=nc,total_ms=tt*1000,cumulative_ms=ct*1000))
 out=dict(status='PASS',no_physics=True,no_repetition_prediction=True,source='Immutable captured public planner/model/reference arguments at an already occurred boundary.',rows=rows,original_ms=dict(mean=float(np.mean([r['original_ms'] for r in rows])),p50=float(np.median([r['original_ms'] for r in rows]))),C2_ms=dict(mean=float(np.mean([r['C2_ms'] for r in rows])),p50=float(np.median([r['C2_ms'] for r in rows]))),profile_top=top,profile_overhead='cProfile numbers are localization only; unprofiled elapsed is separately recorded',attribution='This original B decision obtains the certified nominal target needed by current-state M2 context; candidate budget/Q inference cannot remove it while retaining exact B semantics.')
 save(STUDY/'reports/OFFLINE_ORIGINAL_B_NOMINAL_PROFILE.json',out);print(json.dumps({k:out[k] for k in ('status','original_ms','C2_ms','profile_top')}))
if __name__=='__main__':main()
