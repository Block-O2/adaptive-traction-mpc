"""Fixed small kernel cost ensemble and separate observed-risk classifier."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

def floors(names):
 out=[]
 for n in names:
  if 'onehot' in n: v=1.
  elif any(x in n for x in ['elapsed_s','remaining_s','duration_s','source_age_s','horizon_s','governor_progress']):v=.5
  elif 'history_measured_JF' in n:v=100.
  elif 'history_measured_JM' in n:v=10.
  elif 'peak_jerk' in n:v=1000.
  elif 'peak_acceleration' in n:v=5.
  elif 'guard_counts' in n or 'history_samples' in n:v=1000.
  elif 'peak_correction' in n:v=10.
  elif 'history_context_rejections' in n or 'decision_counts' in n:v=1.
  elif 'torque' in n:v=10.
  elif 'measured_force' in n:v=10.
  elif 'measured_moment' in n:v=1.
  elif 'residual_weights' in n:v=10.
  elif 'beta' in n:v=5.
  elif 'reference_ddq' in n:v=5.
  elif 'dq' in n or 'velocity' in n:v=.2
  elif 'rotation' in n:v=.2
  elif 'displacement' in n or 'position' in n:v=.02
  else:v=.1
  out.append(v)
 return np.array(out)
def kernel(a,b,l):return np.exp(-.5*np.mean(((a[:,None,:]-b[None,:,:])/l)**2,axis=2))
def fit_cost(rows,history=True):
 names=rows[0]['feature_names'];ix=[i for i,n in enumerate(names) if history or not n.startswith('history_')];use=[names[i] for i in ix];X=np.array([r['features'] for r in rows])[:,ix];xc=X.mean(0);xs=np.maximum(X.std(0),floors(use));Z=(X-xc)/xs
 Y=np.array([[r['labels']['tail_JF'],r['labels']['tail_JM'],r['labels']['remaining_time_s']] for r in rows]);D=Y.copy()
 for g in sorted(set(r['group'] for r in rows)):
  j=np.array([r['group']==g for r in rows]);D[j]-=Y[j].mean(0)
 target=np.column_stack([Y,D]);yc=target.mean(0);ys=np.maximum(target.std(0),[.01,.001,.01,.01,.001,.01]);lengths=[.5,1.,2.];weights=[]
 for l in lengths:weights.append(np.linalg.solve(kernel(Z,Z,l)+np.eye(len(Z))*.01,(target-yc)/ys).tolist())
 return dict(schema='v6.cost_and_within_menu_tail.v1',feature_names=use,x_center=xc.tolist(),x_scale=xs.tolist(),scale_floor=floors(use).tolist(),train_x=Z.tolist(),target_center=yc.tolist(),target_scale=ys.tolist(),weights=weights,lengths=lengths,train_ids=[r['id'] for r in rows],train_parent_groups=sorted(set(r['group'] for r in rows)),history=history,target_names=['tail_JF','tail_JM','remaining_time_s','menu_centered_tail_JF','menu_centered_tail_JM','menu_centered_remaining_time_s'],continuation_policy=rows[0]['continuation_policy'],uncertainty='ensemble disagreement; not calibrated confidence',include_complete_failure_costs=True)
def predict_cost(model,inputs):
 look=dict(zip(inputs['feature_names'],inputs['features']));x=np.array([look[n] for n in model['feature_names']]);z=(x-model['x_center'])/model['x_scale'];Z=np.array(model['train_x']);pred=[]
 for l,w in zip(model['lengths'],model['weights']):pred.append(np.array(model['target_center'])+np.array(model['target_scale'])*(kernel(Z,z[None,:],l).T@np.array(w))[0])
 pred=np.array(pred);d=float(np.min(np.sqrt(np.mean((Z-z)**2,axis=1))));return dict(mean=pred.mean(0).tolist(),std=pred.std(0).tolist(),distance=d)
def fit_risk(rows):
 X=np.array([r['features'] for r in rows]);y=np.array([r['labels_evaluation_only']['already_native_peak_failed'] for r in rows],float);xc=X.mean(0);xs=np.maximum(X.std(0),[.5,.8,3.,6.,500.,1000.,.05,.05]);Z=(X-xc)/xs;A=np.c_[np.ones(len(Z)),Z]
 if not (np.any(y==0) and np.any(y==1)):return {'available':False,'reason':'INSUFFICIENT_POSITIVE_AND_NEGATIVE_NATIVE_PEAK_LABELS'}
 weights=np.where(y==1,.5/max(y.mean(),1e-9),.5/max(1-y.mean(),1e-9));reg=.1
 def obj(w):
  z=A@w;pen=w.copy();pen[0]=0.;loss=float(np.mean(weights*(np.logaddexp(0,z)-y*z))+.5*reg*(pen@pen));grad=A.T@(weights*(expit(z)-y))/len(y)+reg*pen;return loss,grad
 opt=minimize(obj,np.zeros(A.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-12})
 return dict(available=True,schema='v6.observed_native_peak_risk_logistic.v1',x_center=xc.tolist(),x_scale=xs.tolist(),weights=opt.x.tolist(),train_ids=[r['id'] for r in rows],positive_ids=[r['id'] for r in rows if r['labels_evaluation_only']['already_native_peak_failed']],train_groups=sorted(set(r['group'] for r in rows)),threshold=.5,objective=float(opt.fun),converged=bool(opt.success),scope='predict an already occurred native peak violation from causal observer local history; not full eligibility or calibrated failure probability; old B continuation does not label future smooth-policy risk',train_x=Z.tolist())
def predict_risk(model,inputs):
 if not model.get('available'):return None
 x=np.array(inputs['local_risk_features']);z=(x-model['x_center'])/model['x_scale'];w=np.array(model['weights']);return float(expit(w[0]+z@w[1:]))
def causal_inputs(row):return {k:row[k] for k in ['tag','feature_names','features','local_risk_features']}
def select(bundle,rows):
 # This function never accesses labels, qualified, metrics or evaluation-only peaks.
 causal=[dict(inputs=causal_inputs(r),short_JF=r['short_JF']) for r in rows];pred=[]
 for r in causal:
  p=predict_cost(bundle['cost'],r['inputs']);rp=predict_risk(bundle['risk'],r['inputs']);mean=p['mean'];p.update(tag=r['inputs']['tag'],risk=rp,short_JF=r['short_JF'],score=r['short_JF']+mean[bundle['score_index']]);pred.append(p)
 allowed=[r for r in pred if r['distance']<=bundle['ood_distance_limit'] and (r['risk'] is None or r['risk']<.5)]
 chosen=min(allowed,key=lambda r:r['score'])['tag'] if allowed else 'COMPOSE';unrestricted=min(pred,key=lambda r:r['score'])['tag']
 return dict(choice=chosen,unrestricted_cost_choice=unrestricted,rows=pred,reason='CAUSAL_RISK_AND_DOMAIN_SCREEN_THEN_COST' if allowed else 'FROZEN_COMPOSE_FALLBACK_UNCERTAIN',future_qualification_mask_used=False)
class QualificationMemory:
 """Only an original monitor can set failure; no critic value can clear it."""
 def __init__(self):self.original_failure=False
 def observe_original_contract(self,failed):self.original_failure=self.original_failure or bool(failed)
 def eligible_for_cost_ranking(self):return not self.original_failure
