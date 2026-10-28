"""Learn issued-reference response from completed causal control histories.

The learned profile is used for offline candidate ranking only. Actual execution
still receives ordinary modal parameters and passes every original certificate.
"""
from pathlib import Path
import os,sys,time,json,copy,traceback
import numpy as np
from acl2_shared import P,R,put,read,sha,utc,decision
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

class ResponseModel:
 def __init__(self,weights='models/REFERENCE_RESPONSE_WEIGHTS.npz'):
  self.weights_path=P/weights;self.identity=sha(self.weights_path)
  with np.load(self.weights_path) as z:
   self.t=z['time_s'];self.base=z['base'];self.basis=z['basis'];self.valid=z['valid'].astype(bool)
  belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json');geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});self.human=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']));self.allocator=CuffAwareSagittalAllocator();self.calls=0
 @staticmethod
 def features(x):
  x=np.asarray(x);z=np.zeros(x.shape[:-1]+(16,));z[...,::2]=np.maximum(x,0);z[...,1::2]=np.maximum(-x,0);return z
 def profile(self,x):
  z=self.features(x)
  if np.any(z[~self.valid]>1e-12):raise ValueError('UNDEFINED_REFERENCE_AFTER_KNOWN_INCOMPLETE_DIRECTION')
  return self.base+np.tensordot(z,self.basis,axes=1)
 def arithmetic(self,x):
  y=self.profile(x);w=[];self.calls+=1
  for q,v,a in zip(y[:,0:2],y[:,2:4],y[:,4:6]):w.append(self.allocator._prepare_factors(q,self.human).action_to_wrench_world@self.human.inverse_dynamics(q,v,a))
  w=np.asarray(w);dt=np.diff(self.t);return np.array([np.linalg.norm(w[:-1,:3],axis=1)@dt,np.linalg.norm(w[:-1,3:],axis=1)@dt])

def export_weights(mapping,base_id,output):
 def load(ident,grid=None):
  with np.load(R/'source/results'/ident/'trace.npz') as z:
   ix=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][ix];y=np.c_[z['reference_q_rad'][ix],z['reference_dq_rad_s'][ix],z['reference_ddq_rad_s2'][ix]]
  if grid is None:
   take=np.unique(np.r_[np.arange(0,len(t),2),len(t)-1]);return t[take],y[take]
  return np.column_stack([np.interp(grid,t,y[:,i]) for i in range(6)])
 t,base=load(base_id);basis=np.zeros((16,len(t),6));valid=np.zeros(16,dtype=bool);labels=[]
 for k,ident in mapping.items():
  r=read('attempts/'+ident+'_RESULT.json');labels.append(dict(id=ident,signed_direction=k,task_complete=r['complete'],qualified=r['qualified'],reference_target_defined=r['complete'],full_cost_defined=r['complete']))
  if not r['complete']:continue
  basis[k]=(load(ident,t)-base)/.35;valid[k]=True
 f=P/output;f.parent.mkdir(exist_ok=True,parents=True);np.savez_compressed(f,time_s=t,base=base,basis=basis,valid=valid)
 return labels

def quadratic(model):
 start=time.time();h=.35;F0=model.arithmetic(np.zeros(8));L=np.zeros((16,2));Q=np.zeros((16,16,2));Fh={}
 def point(k,scale):
  x=np.zeros(8);x[k//2]=scale*(1 if k%2==0 else -1);return x
 for i in np.flatnonzero(model.valid):
  f1=model.arithmetic(point(i,h));f2=model.arithmetic(point(i,2*h));Fh[i]=f1;Q[i,i]=(f2-2*f1+F0)/(2*h*h);L[i]=(f1-F0-Q[i,i]*h*h)/h
 for i in np.flatnonzero(model.valid):
  for j in np.flatnonzero(model.valid):
   if j<=i or j//2==i//2:continue
   fij=model.arithmetic(point(i,h)+point(j,h));cross=(fij-Fh[i]-Fh[j]+F0)/(h*h);Q[i,j]=Q[j,i]=cross/2
 return dict(center=F0,linear=L,quadratic=Q,wall_s=time.time()-start,arithmetic_queries=model.calls)

def build():
 start=time.time();A=read('ACTIVATION.json');expected=['CORE_A_%03d'%i for i in range(1,17)];assert all((P/'attempts'/(s+'_RESULT.json')).exists() for s in expected),'COMMON16_NOT_COMPLETE'
 labels=export_weights({i:s for i,s in enumerate(expected)},'CORE_STRONG','models/REFERENCE_RESPONSE_WEIGHTS.npz');model=ResponseModel();base=read('attempts/CORE_STRONG_RESULT.json');F0=model.arithmetic(np.zeros(8));quad=quadratic(model)
 put('models/REFERENCE_RESPONSE_QUADRATIC.json',quad)
 rng=np.random.default_rng(2026102217);pool=[np.zeros(8)]
 for i in range(8):
  for s in [-1,-.7,-.35,.35,.7,1]:
   x=np.zeros(8);x[i]=s;pool.append(x)
 for _ in range(4096):
  x=np.zeros(8);dims=rng.choice(8,int(rng.integers(1,5)),replace=False);x[dims]=rng.uniform(-1,1,len(dims));pool.append(x)
 pool=np.asarray(pool);z=ResponseModel.features(pool);keep=(np.linalg.norm(pool,axis=1)<=1.1)&np.all((z<=1e-12)|model.valid[None,:],axis=1)&(np.linalg.norm(pool,axis=1)>.05)
 approx=np.asarray(quad['center'])+z@np.asarray(quad['linear'])+np.einsum('ni,ijk,nj->nk',z,np.asarray(quad['quadratic']),z)
 naive=read('models/MODAL_NOMINAL_TABLE.json');oldnom=np.asarray(naive['center'])+pool@np.asarray(naive['linear']).T+(pool*pool)@np.asarray(naive['quadratic']).T;oldi=int(np.argmin(np.where(keep,oldnom[:,0],np.inf)))
 score=np.where(keep,approx[:,0]+1e-4*np.sum(abs(pool),axis=1),np.inf);order=np.argsort(score)[:24];exact=[]
 for i in order:
  f=model.arithmetic(pool[i]);exact.append(dict(index=int(i),x=pool[i],nominal=f,anchored_prediction=np.array([base['JF'],base['JM']])+f-F0,quadratic_nominal=approx[i]))
 exact.sort(key=lambda r:r['nominal'][0]);selected=[]
 for r in exact:
  if any(np.linalg.norm(np.asarray(r['x'])-np.asarray(s['x']))<.15 for s in selected):continue
  selected.append(r)
  if len(selected)==3:break
 assert len(selected)==3,'NO_DISTINCT_RESPONSE_CANDIDATES'
 f=model.arithmetic(pool[oldi]);counter=dict(index=oldi,x=pool[oldi],nominal=f,anchored_prediction=np.array([base['JF'],base['JM']])+f-F0,original_nominal_prediction=np.array([base['JF'],base['JM']])+oldnom[oldi,:2]-np.asarray(naive['center'])[:2])
 record=dict(utc=utc(),kind='LEARNED_SIGNED_ISSUED_REFERENCE_RESPONSE_WITH_ORIGINAL_NOMINAL_LOAD',training_attempt_ids=['CORE_STRONG']+expected,training_physical_tasks=17,reference_labels_only=True,Human_true_state_labels=False,context='one nominal Human and fixed causal prefix; no state-conditioned generalization learned',outcome_labels=labels,weights_sha256=model.identity,quadratic_sha256=sha(P/'models/REFERENCE_RESPONSE_QUADRATIC.json'),base_id=base['id'],base_JF=base['JF'],base_JM=base['JM'],nominal_center=F0,valid_directions=model.valid,model_queries=model.calls,wall_s=time.time()-start,new_native_steps=0,limitation='Additive piecewise-linear issued-reference response with unknown modal interactions/extrapolation. No actual Human motion or calibrated uncertainty prediction. Profiles are ranking intermediates, never sent directly to the controller.',source_sha256=sha(__file__))
 put('models/REFERENCE_RESPONSE_MODEL.json',record);put('predictions/REFERENCE_RESPONSE_SHORTLIST.json',dict(utc=utc(),selected=selected,counterfactual=counter,model=record,cheap_candidate_queries=len(pool),exact_nominal_arithmetic_queries=model.calls,all_candidates_frozen_before_new_native=True))
 np.savez_compressed(P/'models/REFERENCE_RESPONSE_CANDIDATE_POOL.npz',x=pool,keep=keep,approximation=approx,original_nominal=oldnom)
 for i,r in enumerate(selected+[counter]):np.savez_compressed(P/'predictions'/('RESPONSE_PROFILE_%02d.npz'%(i+1)),time_s=model.t,predicted_reference=model.profile(r['x']),x=r['x'])
 # New whole-task tests use the identical real control interface and permissions.
 history=read('history/RECOVERY_TEST_PLAN.json');cond=copy.deepcopy(history['condition']);cond['name']='RESPONSE';acts=[dict(tag='B',action=dict(family='B')),dict(tag='H150',action=dict(family='legacy2',legacy=[0,0])),dict(tag='STRONG',action=base['action'])]
 for i,r in enumerate(selected+[counter]):
  tag='MODEL_%02d'%(i+1) if i<3 else 'NOMINAL_COUNTERFACTUAL';acts.append(dict(tag=tag,action=dict(family='modal8_retimed',x=r['x'].tolist(),legacy=base['action']['legacy']),category='engineering',prediction=dict(kind='FROZEN_REFERENCE_RESPONSE_FORWARD_PREDICTION',model_weights_sha256=model.identity,training_attempt_ids=record['training_attempt_ids'],predicted_JF=float(r['anchored_prediction'][0]),predicted_JM=float(r['anchored_prediction'][1]),predicted_reference_path='predictions/RESPONSE_PROFILE_%02d.npz'%(i+1),actual_Human_motion='UNKNOWN',calibrated_uncertainty='NOT_ESTABLISHED',counterfactual_original_nominal_winner=i==3)))
 config=dict(group='RESPONSE',condition=cond,B=history['arms'][0],H150=history['arms'][1],actions=acts,mode='development',local_stop_unix=A['t0_unix']+8.2*3600)
 put('jobs/RESPONSE_CONFIG.json',config);put('runtime/RESPONSE_TEST_PLAN.json',dict(condition=cond,arms=history['arms']));put('queue/008d_RESPONSE_PHYSICS.json',dict(id='008d_RESPONSE_PHYSICS',script='acl2_worker_owned.py',args=['jobs/RESPONSE_CONFIG.json'],timeout_s=1800,latest_start_unix=A['t0_unix']+7.8*3600,requires=['models/REFERENCE_RESPONSE_MODEL.json']))
 decision('Actual issued reference is the dominant missing input in the local approximate physics prior','Fit common17 causal-reference histories, rank pool with nominal load, freeze4 forward tests',{'model_queries':model.calls,'cheap_pool':len(pool),'new_native_tests':4,'fit_wall_s':time.time()-start},'No target future reference/force is consumed; unknown full targets for incomplete directions remain excluded and labelled','Execute frozen supplementary tests, report total17+4 prior/new task cost plus overhead; no primary A/B/C update',['models/REFERENCE_RESPONSE_MODEL.json','predictions/REFERENCE_RESPONSE_SHORTLIST.json'])
 print('RESPONSE_MODEL_READY',model.calls,len(pool),'wall',time.time()-start,flush=True)

if __name__=='__main__':
 try:build()
 except BaseException as e:
  put('models/REFERENCE_RESPONSE_BUILD_FAILURE.json',dict(utc=utc(),error=str(e),traceback=traceback.format_exc(),status='NOT_RUN_MODEL_BUILD_FAILURE'))
  put('jobs/008d_RESPONSE_PHYSICS/END.json',dict(utc=utc(),status='NOT_RUN_MODEL_BUILD_FAILURE',no_native_started=True));raise
