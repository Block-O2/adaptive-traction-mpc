"""Causal completed-history reference-template load proxy; no physics calls.

A model of the proposed reference and nominal human demand, not robot/contact
closed-loop truth. Actual tracking, motion qualification and task remain unknown.
"""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime'
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

def digest(x):return hashlib.sha256(json.dumps(sc.clean(x),sort_keys=True,separators=(',',':')).encode()).hexdigest()
class NominalProxy:
 def __init__(self,build=False):
  self.path=P/'models/NOMINAL_PROXY_TABLE.json';self.calls=0
  if build:self.build()
  self.table=json.loads(self.path.read_text());self.identity=sc.sha(self.path)
 def build(self):
  start=time.time();belief=json.loads((P/'history/CAUSAL_COMMISSIONED_BELIEF.json').read_text())
  geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()})
  self.model=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']))
  self.allocator=CuffAwareSagittalAllocator()
  with np.load(P/'history/CAUSAL_H150_REFERENCE_TEMPLATE.npz') as z:
   ix=np.unique(np.r_[np.arange(0,len(z['time_s']),4),len(z['time_s'])-1]);self.t=z['time_s'][ix];self.ph=z['phase'][ix];self.q=z['q'][ix];self.v=z['dq'][ix];self.a=z['ddq'][ix]
  self.origin=self.q[0];self.goal=np.max(self.q,axis=0);self.span=self.goal-self.origin
  self.grid=np.linspace(-1,1,17)
  center=self.arithmetic([0,0]);rows=[]
  for dim in range(2):
   arr=[]
   for v in self.grid:
    x=np.zeros(2);x[dim]=v;arr.append(self.arithmetic(x))
   rows.append(arr)
  table={'schema':'lgmi.nominal_reference_proxy.v1','created_unix':time.time(),'inputs':{'template_sha256':sc.sha(P/'history/CAUSAL_H150_REFERENCE_TEMPLATE.npz'),'belief_sha256':sc.sha(P/'history/CAUSAL_COMMISSIONED_BELIEF.json'),'source_sha256':sc.sha(Path(__file__))},'kind':'reference-template plus exact original nominal inverse dynamics and allocator','parameter_indices':[1,6],'coefficient_delta':.002,'grid':self.grid,'center':center,'dimension_rows':rows,'model_arithmetic_evaluations':35,'native_steps':0,'wall_s':time.time()-start,'motion_task_contact_prediction':'UNKNOWN; template derivatives do not establish actual native motion','source_model':'StateResidualHumanModel with high_rom deployable_prior and completed commissioned causal belief'}
  self.path.write_text(json.dumps(sc.clean(table),indent=2,allow_nan=False)+'\n')
 def arithmetic(self,x):
  q=self.q.copy();v=self.v.copy();a=self.a.copy()
  for dim,ph in enumerate(['OUTBOUND','RETURN']):
   idx=self.ph==ph;origin,span=(self.origin,self.span) if dim==0 else (self.goal,-self.span)
   m=np.clip(np.mean((self.q[idx]-origin)/span,axis=1),0,1);md=np.mean(self.v[idx]/span,axis=1);mdd=np.mean(self.a[idx]/span,axis=1)
   e=np.sin(np.pi*m)**2;ed=np.pi*np.sin(2*np.pi*m);edd=2*np.pi**2*np.cos(2*np.pi*m)
   scale=.002*float(x[dim]);direction=span*np.array([1.,-1.])
   q[idx]+=direction*(scale*e[:,None]);v[idx]+=direction*(scale*(ed*md)[:,None]);a[idx]+=direction*(scale*(edd*md*md+ed*mdd)[:,None])
  w=[]
  for i,(qq,vv,aa) in enumerate(zip(q,v,a)):
   tau=self.model.inverse_dynamics(qq,vv,aa);factors=self.allocator._prepare_factors(qq,self.model);ww=factors.action_to_wrench_world@tau;w.append(ww)
   if i in [0,len(q)//2,len(q)-1]:assert np.max(abs(ww-self.allocator.allocate(tau,qq,self.model)['wrench_world']))<1e-9,'ALLOCATOR_ARITHMETIC_EQUIVALENCE'
  w=np.asarray(w);dt=np.diff(self.t);f=np.linalg.norm(w[:,:3],axis=1);mom=np.linalg.norm(w[:,3:],axis=1);jerk=np.gradient(a,self.t,axis=0,edge_order=2)
  return np.r_[f[:-1]@dt,mom[:-1]@dt,[f[:-1][self.ph[:-1]==ph]@dt[self.ph[:-1]==ph] for ph in ['OUTBOUND','HOLD','RETURN']],np.max(abs(np.degrees(v)),axis=0),np.max(abs(np.degrees(a)),axis=0),np.sqrt(np.mean(np.degrees(jerk)**2,axis=0)),np.degrees(np.ptp(q,axis=0)),np.degrees(q[-1])]
 def predict(self,x):
  x=np.asarray(x,float);assert x.shape==(2,) and np.all(abs(x)<=1+1e-12)
  self.calls+=1;center=np.asarray(self.table['center']);y=center.copy();grid=np.asarray(self.table['grid'])
  for dim in range(2):
   rows=np.asarray(self.table['dimension_rows'][dim]);y+=np.array([np.interp(x[dim],grid,rows[:,j]) for j in range(rows.shape[1])])-center
  return {'x':x.tolist(),'nominal_JF':float(y[0]),'nominal_JM':float(y[1]),'phase_JF':dict(zip(['OUTBOUND','HOLD','RETURN'],y[2:5].tolist())),'template_velocity_max_deg_s':y[5:7].tolist(),'template_acceleration_max_deg_s2':y[7:9].tolist(),'template_jerk_rms_deg_s3':y[9:11].tolist(),'template_excursion_deg':y[11:13].tolist(),'template_terminal_deg':y[13:15].tolist(),'actual_tracking':'UNKNOWN','actual_motion_margin':'UNKNOWN','actual_task_feasibility':'UNKNOWN','model_id':self.identity,'new_native_steps':0}
if __name__=='__main__':
 p=NominalProxy(build=True);zero=p.predict([0,0]);assert abs(zero['nominal_JF']-p.table['center'][0])<1e-10
 print(json.dumps({'center':zero,'wall_s':p.table['wall_s']}),flush=True)
