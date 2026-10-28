"""Two-dimensional bounded, per-arm isolated search and trajectory-level GP."""
from pathlib import Path
import json,hashlib,time
import numpy as np
from nominal_proxy import P,NominalProxy,digest
METHODS={'A':'DIRECT_NATIVE_OPTIMIZATION','B':'PHYSICS_GUIDED_OPTIMIZATION','C':'LEARNING_RESIDUAL_GUIDED_OPTIMIZATION'}
DESIGN=np.asarray([[.5,0],[-.5,0],[0,.5],[0,-.5]])

def bounded_pool():
 rng=np.random.default_rng(2026102107)
 return np.vstack([np.asarray([[a,b] for a in [-1,-.75,-.5,-.25,0,.25,.5,.75,1] for b in [-1,-.75,-.5,-.25,0,.25,.5,.75,1]]),rng.uniform(-1,1,(2048,2))])

def worst_ratio(m,b,comp):
 vals=[float(np.max(v))/1.1 for v in comp['burden_ratios'].values()]
 vals += [float(np.max(comp['excursion_delta_deg']))/.5,float(np.max(comp['endpoint_abs_delta_deg']))/.5,comp['phase_boundary_max_delta_deg']/.5,comp['duration_abs_delta_s']/.1]
 travel=np.asarray(comp['cumulative_ratio']);vals += [float(np.max(travel))/1.05,float(np.max(.95/travel))]
 vals += [m['moment_integral_Nm_s']/b['moment_integral_Nm_s']/1.25,m['force_peak_N']/b['force_peak_N']/1.05,m['moment_peak_Nm']/b['moment_peak_Nm']/1.05]
 vals += [max(0.,float(np.max(np.asarray(m['tracking_RMS_deg'])-np.asarray(b['tracking_RMS_deg']))))/.5]
 return max(vals)

class ResidualGP:
 def __init__(self,x,y):
  self.x=np.asarray(x,float);self.y=np.asarray(y,float);self.length=.6
  self.scale=np.maximum(np.std(self.y,axis=0),[.05,.03,.005]);self.noise=np.array([.005,.003,.0005])/self.scale
  K=self.kernel(self.x,self.x);self.cholesky=[];self.alpha=[]
  for j in range(3):
   L=np.linalg.cholesky(K+np.eye(len(x))*(self.noise[j]**2+1e-8));self.cholesky.append(L);self.alpha.append(np.linalg.solve(L.T,np.linalg.solve(L,self.y[:,j]/self.scale[j])))
 def kernel(self,a,b):return np.exp(-np.sum((a[:,None,:]-b[None,:,:])**2,axis=2)/(2*self.length**2))
 def predict(self,x):
  x=np.asarray(x,float);K=self.kernel(x,self.x);mu=[];sd=[]
  for j in range(3):
   vv=np.linalg.solve(self.cholesky[j],K.T);mu.append(K@self.alpha[j]*self.scale[j]);sd.append(np.sqrt(np.maximum(0,1-np.sum(vv*vv,axis=0)))*self.scale[j])
  return np.asarray(mu).T,np.asarray(sd).T
 def record(self):return {'x':self.x.tolist(),'residual_targets':self.y.tolist(),'lengthscale_fixed':self.length,'output_scales':self.scale.tolist(),'noise_normalized':self.noise.tolist(),'alpha':[a.tolist() for a in self.alpha],'cholesky':[a.tolist() for a in self.cholesky],'split':'whole candidates; no adjacent-time-step validation','causal_state':'constant same-parent context, recorded separately; no state generalization learned'}

class ArmOptimizer:
 def __init__(self,arm,baseline):
  self.arm=arm;self.baseline=baseline;self.proxy=NominalProxy();self.pool=bounded_pool();self.source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
  self.center_nom=self.proxy.predict([0,0]);self.pool_nom=np.asarray([[self.proxy.predict(x)['nominal_JF'],self.proxy.predict(x)['nominal_JM']] for x in self.pool])
 def calibrated_nominal(self,p):return np.array([self.baseline['JF']+p['nominal_JF']-self.center_nom['nominal_JF'],self.baseline['JM']+p['nominal_JM']-self.center_nom['nominal_JM'],self.baseline['worst_ratio']])
 def fit(self,rows):
  xs=[[0.,0.]];ys=[[0.,0.,0.]];ids=['PUBLIC_ENGINEERING_H150_ANCHOR']
  for r in rows:
   if not r.get('complete'):continue
   p=r['prediction']['nominal'];nom=self.calibrated_nominal(p);xs.append(r['x']);ys.append([r['JF']-nom[0],r['JM']-nom[1],r['worst_ratio']-nom[2]]);ids.append(r['id'])
  gp=ResidualGP(xs,ys);record=gp.record();record.update(public_baseline_anchor=self.baseline,training_attempt_ids=ids,optimizer_source_sha256=self.source_sha,arm='C',nominal_model_id=self.proxy.identity,kind='JF/JM residual GP plus empirical motion-ratio correction around public H150 anchor',target_information='completed causal full JF/JM feedback and evaluation qualification margin; no future target data',no_other_arm_feedback=True)
  mid=digest(record);record['id']=mid;path=P/'models'/('C_%03d_%s.json'%(len(rows)+1,mid[:12]));path.write_text(json.dumps(record,indent=2)+'\n');return gp,mid,str(path.relative_to(P))
 def propose(self,rows):
  assert all(r.get('arm')==self.arm for r in rows),'CROSS_ARM_FEEDBACK_FORBIDDEN'
  n=len(rows);qualified=[r for r in rows if r.get('qualified')];best=min(qualified,key=lambda r:r['JF']) if qualified else None;center=np.asarray(best['x'] if best and best['JF']<self.baseline['JF'] else [0,0],float)
  seen=np.asarray([[0.,0.]]+[r['x'] for r in rows]);gp=None;mid=None;mpath=None
  if self.arm=='C':gp,mid,mpath=self.fit(rows)
  if n<4:x=DESIGN[n];selection='SHARED_REGISTERED_DESIGN'
  elif self.arm=='A':
   x=None
   for step in [.5,.25,.125,.0625,.03125]:
    for direction in [[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,-1],[1,-1],[-1,1]]:
     z=np.clip(center+step*np.asarray(direction),-1,1)
     if np.min(np.linalg.norm(seen-z,axis=1))>1e-7:x=z;break
    if x is not None:break
   assert x is not None,'DIRECT_SEARCH_DOMAIN_EXHAUSTED'
   selection='BOUNDED_OPPORTUNISTIC_PATTERN_SEARCH_REAL_FEEDBACK'
  else:
   distances=np.min(np.linalg.norm(self.pool[:,None,:]-seen[None,:,:],axis=2),axis=1);keep=distances>.08
   if self.arm=='B':
    indices=np.flatnonzero(keep);i=indices[np.argmin(self.pool_nom[indices,0])];selection='UNLEARNED_NOMINAL_PHYSICS_RANK_WITH_NOVELTY'
   else:
    trust=.375 if rows and not rows[-1].get('qualified') else .75
    keep &= np.linalg.norm(self.pool-center,axis=1)<=trust
    indices=np.flatnonzero(keep);assert len(indices),'LOCAL_TRUST_REGION_EXHAUSTED'
    mu,sd=gp.predict(self.pool[indices]);nom=np.c_[self.baseline['JF']+self.pool_nom[indices,0]-self.center_nom['nominal_JF'],self.baseline['JM']+self.pool_nom[indices,1]-self.center_nom['nominal_JM'],np.full(len(indices),self.baseline['worst_ratio'])]
    pred=nom+mu;screen=(pred[:,2]+2*sd[:,2]<=1.)&(pred[:,1]+2*sd[:,1]<=self.baseline['B_JM']*1.25)
    if np.any(screen):
     acquisition=pred[:,0]-.5*sd[:,0];acquisition[~screen]=np.inf;i=indices[np.argmin(acquisition)];selection='GP_RESIDUAL_LOWER_CONFIDENCE_FORCE_CONSERVATIVE_MOTION_SCREEN'
    else:
     local=np.linalg.norm(self.pool[indices]-center,axis=1)<=.25
     if np.any(local):indices=indices[local];pred=pred[local];sd=sd[local]
     i=indices[np.argmin(pred[:,2]+2*sd[:,2])];selection='NO_CONFIDENT_SAFE_PREDICTION_MINIMUM_MOTION_UCB_WITH_NATIVE_FINAL_AUTHORITY'
   x=self.pool[i]
  p=self.proxy.predict(x);cal=self.calibrated_nominal(p);record={'arm':self.arm,'method':METHODS[self.arm],'attempt_index':n+1,'x':x.tolist(),'nominal':p,'baseline_anchored_nominal':cal.tolist(),'selection':selection,'source_sha256':self.source_sha,'training_attempt_ids':[r['id'] for r in rows],'candidate_not_in_previous_arm_attempts':True,'nominal_calibration':'common completed H150 anchor removes constant offset; pure nominal differences preserved','actual_motion_prediction':'UNKNOWN' if self.arm!='C' else 'EMPIRICAL_LOCAL_GP_NOT_SAFETY_AUTHORITY'}
  if gp is not None:
   mu,sd=gp.predict([x]);record.update(learned_prediction=(cal+mu[0]).tolist(),learned_std=sd[0].tolist(),learned_model_id=mid,learned_model_path=mpath,predicted_original_motion_pass=bool(cal[2]+mu[0,2]+2*sd[0,2]<=1))
  record['candidate_id']=digest({'x':x.tolist(),'parameter_indices':[1,6],'coefficient_delta':.002,'base':'FROZEN_H150','optimizer_source_sha256':self.source_sha})
  return x.tolist(),record
