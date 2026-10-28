"""Isolated direct, fixed nominal, and learned residual/modal8 searches."""
import copy,time,json,hashlib
import numpy as np
from acl2_shared import P,put,read,sha,utc,decision
from acl2_proxy import Proxy
FAMILY='modal8';CENTER=[0.,0.]
def action(x):return dict(family=FAMILY,x=np.asarray(x,float).tolist(),legacy=CENTER)
class GP:
 def __init__(self,x,y):
  self.x=np.asarray(x);self.y=np.asarray(y);self.length=.9;self.scale=np.maximum(np.std(self.y,axis=0),[.3,.15,.06]);self.K=self.kernel(self.x,self.x)+np.eye(len(x))*1e-5
  self.L=np.linalg.cholesky(self.K);self.alpha=np.linalg.solve(self.L.T,np.linalg.solve(self.L,self.y/self.scale))
 def kernel(self,a,b):return np.exp(-np.sum((a[:,None,:]-b[None,:,:])**2,axis=2)/(2*self.length**2))
 def predict(self,x):
  K=self.kernel(np.asarray(x),self.x);V=np.linalg.solve(self.L,K.T);sd=np.sqrt(np.maximum(1e-10,1-np.sum(V*V,axis=0)))[:,None]*self.scale
  return K@self.alpha*self.scale,sd
 def record(self):return dict(x=self.x,y=self.y,length=self.length,scale=self.scale,alpha=self.alpha,L=self.L)
def best(rows,base):return min([base]+[r for r in rows if r.get('qualified')],key=lambda r:r['JF'])
def sequence(study,C):
 global FAMILY,CENTER
 FAMILY=C.get('family','modal8');CENTER=C.get('center_legacy',[0.,0.])
 assert read(C.get('interface_gate','audit/INTERFACE_GATE.json'))['new_modes_executable'],'INTERFACE_GATE_REQUIRED'
 for tag,fam in [('B','B'),('H150','legacy2')]:yield dict(tag=tag,action=dict(family=fam,legacy=[0,0]))
 if C.get('center_legacy') is not None:yield dict(tag='STRONG',action=dict(family='legacy2',legacy=CENTER))
 base=study.last_row;proxy=Proxy();nom0=proxy.predict(np.zeros(8))[0];rng=np.random.default_rng(C['search_seed'])
 rows={a:[] for a in ['A','B','C']};study.arm_rows=rows
 design=np.vstack([sign*.35*np.eye(8)[i] for i in range(8) for sign in [1,-1]])
 checkpoints=C['checkpoints'];limit=max(checkpoints);min_distance=.035
 for n in range(limit):
  for arm in ['A','B','C']:
   own=rows[arm];chosen=best(own,base);center=np.asarray(chosen['action'].get('x',np.zeros(8)));seen=np.asarray([np.zeros(8)]+[r['action']['x'] for r in own]);source='COMMON_DESIGN';gp=None;mid=None;sd=np.zeros((1,3));pred=None;counterfactual=None;pool_record=None;ids=[];completion_score=None;screen_usable=None
   if n<len(design):x=design[n]
   else:
    # Finite candidate pool; useful local steps plus whole-domain novelty.
    local=[]
    for step in [.35,.175,.0875,.04375]:
     local.extend(np.clip(center+sign*step*np.eye(8)[i],-1,1) for i in range(8) for sign in [1,-1])
    local=np.asarray(local);pool=np.vstack([local,np.clip(center+rng.normal(0,.25,(1024,8)),-1,1),rng.uniform(-1,1,(512,8))])
    dist=np.min(np.linalg.norm(pool[:,None,:]-seen[None,:,:],axis=2),axis=1);keep=dist>min_distance
    if arm=='A':
     # Strong native-only opportunistic coordinate search; no model feedback.
     i=next((i for i in range(len(local)) if keep[i]),None)
     if i is None:i=int(np.flatnonzero(keep)[0])
     x=pool[i];source='DIRECT_OPPORTUNISTIC_PATTERN_SEARCH'
    else:
     physics_keep=keep & (np.linalg.norm(pool-center,axis=1)<=1.1)
     if not np.any(physics_keep):physics_keep=keep.copy()
     nominal=proxy.predict(pool);anchor=np.c_[base['JF']+nominal[:,0]-nom0[0],base['JM']+nominal[:,1]-nom0[1],np.full(len(pool),base['worst_ratio'])]
     if arm=='B':score=anchor[:,0];source='FROZEN_NOMINAL_LOAD_RANKING'
     else:
      xx=[np.zeros(8)];yy=[np.zeros(3)];ids=[base['id']]
      for r in own:
       if not r.get('complete'):continue
       nom=proxy.predict(r['action']['x'])[0];xx.append(r['action']['x']);yy.append([r['JF']-(base['JF']+nom[0]-nom0[0]),r['JM']-(base['JM']+nom[1]-nom0[1]),r['worst_ratio']-base['worst_ratio']]);ids.append(r['id'])
      gp=GP(np.asarray(xx),np.asarray(yy));mu,unc=gp.predict(pool);model=gp.record();completion_x=np.asarray([np.zeros(8)]+[r['action']['x'] for r in own]);completion_y=np.asarray([1.]+[float(r['complete']) for r in own]);completion_kernel=np.exp(-np.sum((pool[:,None,:]-completion_x[None,:,:])**2,axis=2)/(2*.55**2));completion_score=(.5+completion_kernel@completion_y)/(1+completion_kernel.sum(axis=1));model.update(completion_x=completion_x,completion_labels=completion_y,completion_length=.55,completion_prior=[.5,.5],completion_score_scope='kernel-weighted empirical completion score; not calibrated probability',all_feedback_attempt_ids=[base['id']]+[r['id'] for r in own],undefined_full_JF_attempt_ids=[r['id'] for r in own if not r['complete']],undefined_cost_labels_never_imputed=True);model.update(training_attempt_ids=ids,created_utc=utc(),nominal_id=proxy.identity,scope='same-parent modal8; completed actual original-motion outcomes are simulation-only training labels',no_other_arm_feedback=True);mid=hashlib.sha256(json.dumps(__import__('acl2_shared').clean(model),sort_keys=True).encode()).hexdigest();put('models/'+study.condition['name']+'_C_%03d.json'%(n+1),model)
      prediction=anchor+mu;screen=prediction[:,2]+1.0*unc[:,2]<=1.;screen &= prediction[:,1]+unc[:,1]<base['JM']*1.15
      screen &= completion_score>=.65
      screen_usable=bool(np.any(screen&keep))
      # Explicit bounded exploration stays in the same physical permission box;
      # uncertainty is a heuristic until frozen empirical coverage is measured.
      score=prediction[:,0]-.5*unc[:,0]
      if np.any(screen&keep):keep &= screen
      source='RESIDUAL_GP_FORCE_RANKING_AND_EMPIRICAL_MOTION_SCREEN'
     # Trust region is fixed before outcomes; physics is not assumed safe.
     keep &= np.linalg.norm(pool-center,axis=1)<=1.1
     if not np.any(keep):keep=dist>min_distance
     score=np.where(keep,score,np.inf);i=int(np.argmin(score));x=pool[i]
     ni=int(np.argmin(np.where(physics_keep,anchor[:,0],np.inf)));counterfactual=dict(x=pool[ni],anchored_nominal=anchor[ni],nominal_mask_uses_only_bounds_novelty_trust=True,changed_by_learning=bool(arm=='C' and np.linalg.norm(pool[ni]-x)>1e-9))
     pool_record='predictions/'+study.condition['name']+'_'+arm+'_%03d_POOL.json'%(n+1);put(pool_record,dict(pool=pool,allowed_mask=keep,nominal_mask=physics_keep,anchored_nominal=anchor,score=score.tolist() if np.all(np.isfinite(score)) else [float(v) if np.isfinite(v) else None for v in score],chosen_index=i,nominal_counterfactual_index=ni,model_id=mid))
     if arm=='C':pred=prediction[i];sd=unc[i:i+1]
   nominal=proxy.predict(x)[0];anch=np.array([base['JF']+nominal[0]-nom0[0],base['JM']+nominal[1]-nom0[1],base['worst_ratio']])
   if pred is None:pred=anch
   proposal=dict(selection=source,x=x,nominal=nominal,anchored_nominal=anch,predicted_outcome=pred,predicted_sd=sd[0],model_id=mid,nominal_id=proxy.identity,training_attempt_ids=ids if gp is not None else [],feedback_history_ids_all=[r['id'] for r in own],completion_score=float(completion_score[i]) if completion_score is not None else None,completion_screen_had_candidates=screen_usable,full_task_prediction='UNKNOWN: completion score is empirical, not a certificate',other_arm_feedback=False,nominal_counterfactual=counterfactual,candidate_pool_path=pool_record,proxy_query_count=proxy.calls,motion_prediction_scope='simulation empirical outcome; unknown deployable sensing')
   yield dict(tag=arm+'_%03d'%(n+1),action=action(x),category='optimization',prediction=proposal)
   row=copy.deepcopy(study.last_row);row['arm']=arm;own.append(row)
  if n+1 in checkpoints:
   locked={a:best(rows[a],base) for a in rows};put('jobs/'+study.condition['name']+'/CHECKPOINT_%03d.json'%(n+1),dict(utc=utc(),physical_attempts_per_arm=n+1,best=locked,proxy_queries=proxy.calls,rows=rows))
   print('SEARCH_CHECKPOINT',n+1,{a:(locked[a]['JF'],locked[a]['id']) for a in rows},flush=True)
 put('jobs/'+study.condition['name']+'/SELECTION.json',dict(frozen_utc=utc(),best={a:best(rows[a],base) for a in rows},base=base,rows=rows,maximum_attempts_per_arm=limit,proxy_queries=proxy.calls,no_locked_validation_opened=True))
