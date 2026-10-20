"""Bounded source + saved-state check; no native planning/physics/Q update."""
from task_bootstrap import *
import ast,copy,pickle,numpy as np

def main():
 import native_core as nc
 from native_inference import Networks
 source=STUDY/'code/native_core.py';tree=ast.parse(source.read_text());fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='candidates')
 loads=sorted({x.id for x in ast.walk(fn) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Load)})
 assert 'c' not in loads,'CANDIDATE_GENERATOR_DIRECT_CONTEXT_USE'
 net=Networks(STUDY/'weights/frozen_Q_v1');assert net.meta['selected_Q']=='linear';before=sha(STUDY/'weights/frozen_Q_v1/weights.npz')
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));assert len(paths)==22
 rows=[];checks=0
 for path in paths:
  raw=pickle.loads(path.read_bytes());c=raw['context'];carry=raw['carry'];count=raw['count'];pool=nc.candidates(c,count,carry,2621,6)
  for seed in (0,2621,2026100621):
   for k in (0,1,4,5,6):
    counts={'OUTBOUND':k,'RETURN':6-k};left=nc.candidates(c,counts,carry,seed,6);right=nc.candidates(None,counts,carry,seed,6)
    assert len(left)==len(right) and all(a==b and np.array_equal(p,q) for (p,a),(q,b) in zip(left,right))
    checks+=1
  phase_swapped=copy.deepcopy(c);phase_swapped['phase']='RETURN' if c['phase']=='OUTBOUND' else 'OUTBOUND'
  x=np.asarray([nc.feature(c,p,count,carry) for p,s in pool]);y=np.asarray([nc.feature(phase_swapped,p,count,carry) for p,s in pool]);assert np.array_equal(x,y) and np.array_equal(net.values(x),net.values(y))
  # Isolate the phase-label dependency only. This altered context is an algebraic
  # input probe, not a certified/deployable state or a new Human experiment.
  def action(phase,plan):
   idx=count[phase];return np.asarray(plan)[('OUTBOUND','RETURN').index(phase),idx].tolist() if idx<5 else [0.,0.,0.]
  rows.append(dict(snapshot=str(path),snapshot_sha256=sha(path),phase=c['phase'],coordinator_attempted_counts=count,finite_pool_context_checks=15,phase_label_only_feature_and_Q_equal=True,phase_label_only_probe_is_not_deployable=True,current_action_by_phase=[dict(candidate=s,OUTBOUND=action('OUTBOUND',p),RETURN=action('RETURN',p)) for p,s in pool]))
 assert sha(STUDY/'weights/frozen_Q_v1/weights.npz')==before
 out=dict(status='PASS',source_sha256=sha(source),candidate_function_line=fn.lineno,candidate_function_end_line=fn.end_lineno,context_argument_is_unused=True,candidate_function_loaded_identifiers=loads,saved_states=22,finite_context_independence_checks=checks,phase_label_only_feature_checks=22,rows=rows,physics_attempts_added=0,native_certificate_calls=0,Q_updates=0,weights_sha256=before,interpretation='Frozen candidates depend directly on carry, count masks, candidate seed and fixed historical design, not on c/current state. Frozen feature uses observation/prior residual but no separate phase label; phase/progress changes common observation or indirectly evolves counts/carry. At fixed candidate/carry/count, changing the state contributes common linear-Q bias. Count changes can change the masked plan ranking; phase selects the current action at native_local realization and state changes native feasibility. Neither is learned state×plan preference. Failed actual coordinator counts count attempted proposals rather than physically committed learning actions.')
 out['frozen_inference_dtypes']=dict(feature=str(x.dtype),normalized_feature=str(net.scale(x).dtype),native_values=str(net.values(x).dtype),arrays={k:str(v.dtype) for k,v in net.w.items() if k in ('x_mean','x_scale','linear_W','linear_b','y_mean','y_scale')});out['inference_source_sha256']=sha(STUDY/'code/native_inference.py')
 path=STUDY/'reports/Q_POOL_DEPENDENCY_AUDIT.json'
 if path.exists():shutil.copy2(path,STUDY/'reports'/('Q_POOL_DEPENDENCY_AUDIT_HISTORY_'+sha(path)+'.json'))
 save(path,out);print(json.dumps({k:out[k] for k in ('status','context_argument_is_unused','saved_states','finite_context_independence_checks','phase_label_only_feature_checks','frozen_inference_dtypes','physics_attempts_added','native_certificate_calls','Q_updates')}))
if __name__=='__main__':main()
