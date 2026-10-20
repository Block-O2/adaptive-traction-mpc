"""Causal features and single-segment reuse of B; never predict a repetition."""
from study_common import *
import pickle,traceback
from coordination_adapter import snapshot_task_call
from representation import graph_action
def masked(table,count):
 out=np.asarray(table).reshape(2,5,3).copy()
 for i,p in enumerate(('OUTBOUND','RETURN')):out[i,:min(count[p],5)]=0
 return out
def feature(c,table,count,carry=None):
 carry=np.zeros((2,5,3)) if carry is None else carry
 return np.r_[c['observation'],c.get('richer_previous_residual',[0,0,0]),masked(table,count).ravel(),masked(carry,count).ravel(),[count['OUTBOUND']/5,count['RETURN']/5]].astype(np.float32)
def candidates(c,count,carry,seed=0,n=6):
 rng=np.random.default_rng(seed);history=np.asarray(read('HISTORICAL_K3_DESIGN_REFERENCE.json')['table']).reshape(2,5,3)
 positive=np.ones((2,5,3))*.25;negative=-positive
 reversal=np.broadcast_to(np.array([.35,-.25,.15]),(2,5,3)).copy()
 # Ordinary coherent candidate diversity is frozen before training.
 plans=[np.zeros((2,5,3)),np.asarray(carry).copy(),history.copy(),positive,negative,reversal]
 if seed:
  for i in range(3,6):
   noise=rng.normal(0,.08,(2,5,3));noise[:,1:]=.7*noise[:,:-1]+.3*noise[:,1:];plans[i]=np.clip(plans[i]+noise,-1,1)
 out=[]
 for p,source in zip(plans,['B','carry','historical_design','positive','negative','reversal']):
  p=masked(p,count)
  if not any(np.array_equal(p,q) for q,s in out):out.append((p,source))
 for sign in (1,-1):
  p=np.broadcast_to(np.array([.12,.35,-.25])*sign,(2,5,3)).copy();p[1]*=-1;p=masked(p,count)
  if not any(np.array_equal(p,q) for q,s in out):out.append((p,'cross_phase_reversal_'+str(sign)))
 return out[:n]
def native_local(b,c,table,count):
 """Clone B and request ONE current segment with identical native certification."""
 clone,args=pickle.loads(snapshot_task_call(b['adaptive_planner'],b['arguments']))
 phase=c['phase'];i=count[phase];a=table[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3)
 clone.planner.residual_spec={phase:graph_action(a*.2,c['start_m'])}
 t=time.monotonic();decision=clone.decide(**args);e=decision.executed
 meta=e.execution_screen.get('coordination_residual_v2',{})
 return dict(feasible=bool(e.feasible),proposal_accepted=not meta or meta.get('status')=='ACCEPTED',S=float(e.total_cost),selection_mode=decision.selection_mode,reason=meta.get('reason'),native_wall_s=time.monotonic()-t,duration_s=e.schedule.duration_s if e.schedule else None,target=e.target_q_rad,call_stack=traceback.format_stack(limit=5))
