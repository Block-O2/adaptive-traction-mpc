"""Completed-history nominal reference-load approximation, never closed-loop truth."""
from pathlib import Path
import os,sys,json,time
import numpy as np
from scipy.interpolate import CubicHermiteSpline
from acl2_shared import P,R,put,read,sha,utc
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

class Proxy:
 def __init__(self):
  self.table=read('models/MODAL_NOMINAL_TABLE.json');self.identity=sha(P/'models/MODAL_NOMINAL_TABLE.json');self.calls=0
 def predict(self,x):
  x=np.atleast_2d(np.asarray(x,float));self.calls+=len(x)
  y=np.asarray(self.table['center'])+x@np.asarray(self.table['linear']).T+(x*x)@np.asarray(self.table['quadratic']).T
  return y

def build():
 start=time.time();belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json')
 geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()})
 model=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']))
 alloc=CuffAwareSagittalAllocator()
 template=P/'history/CAUSAL_STRONG_REFERENCE_TEMPLATE.npz'
 if not template.exists():template=P/'history/CAUSAL_H150_REFERENCE_TEMPLATE.npz'
 with np.load(template) as z:
  ix=np.unique(np.r_[np.arange(0,len(z['time_s']),12),len(z['time_s'])-1]);t=z['time_s'][ix];q=z['q'][ix];v=z['dq'][ix];phase=z['phase'][ix]
 # Whole completed historical nominal plan is public prior. Counterfactual
 # smooth phase modes approximate slot-local execution; no robot/contact state
 # or proposed candidate future output enters this computation.
 curve=CubicHermiteSpline(t,q,v);bounds={}
 for ph in ['OUTBOUND','RETURN']:
  idx=np.flatnonzero(phase==ph);bounds[ph]=(t[idx[0]],t[idx[-1]])
 def arithmetic(x):
  qq=q.copy();vv=v.copy();aa=curve(t,2)
  for j,ph in [(0,'OUTBOUND'),(2,'RETURN')]:
   idx=phase==ph;lo,hi=bounds[ph];T=hi-lo;s=(t[idx]-lo)/T
   e=np.sin(np.pi*s)**2;ed=np.pi*np.sin(2*np.pi*s);edd=2*np.pi**2*np.cos(2*np.pi*s)
   k=4 if j==0 else 5;vs=6 if j==0 else 7
   h=np.sin(4*np.pi*s)/(4*np.pi);hd=np.cos(4*np.pi*s);hdd=-4*np.pi*np.sin(4*np.pi*s)
   warp=-.08*x[k]*e+.12*x[vs]*h*e
   wd=-.08*x[k]*ed+.12*x[vs]*(hd*e+h*ed)
   wdd=-.08*x[k]*edd+.12*x[vs]*(hdd*e+2*hd*ed+h*edd)
   tau=np.clip(t[idx]+T*warp,lo,hi);rate=1+wd;acc=wdd/T
   qq[idx]=curve(tau);vv[idx]=curve(tau,1)*rate[:,None];aa[idx]=curve(tau,2)*rate[:,None]**2+curve(tau,1)*acc[:,None]
   direction=1 if j==0 else -1;shift=np.radians(.30)*direction*np.array([x[j]+x[j+1],x[j]-x[j+1]])
   qq[idx]+=e[:,None]*shift;vv[idx]+=ed[:,None]/T*shift;aa[idx]+=edd[:,None]/T**2*shift
  w=[]
  for a,b,c in zip(qq,vv,aa):
   tau=model.inverse_dynamics(a,b,c);w.append(alloc._prepare_factors(a,model).action_to_wrench_world@tau)
  w=np.asarray(w);dt=np.diff(t);f=np.linalg.norm(w[:,:3],axis=1);m=np.linalg.norm(w[:,3:],axis=1)
  return np.r_[f[:-1]@dt,m[:-1]@dt,[f[:-1][phase[:-1]==ph]@dt[phase[:-1]==ph] for ph in ['OUTBOUND','HOLD','RETURN']]]
 center=arithmetic(np.zeros(8));linear=[];quad=[];rows=[]
 for k in range(8):
  x=np.zeros(8);x[k]=.5;plus=arithmetic(x);x[k]=-.5;minus=arithmetic(x)
  linear.append(plus-minus);quad.append(2*(plus+minus-2*center));rows.append(dict(dim=k,plus_half=plus,minus_half=minus))
 put('models/MODAL_NOMINAL_TABLE.json',dict(schema='acl2.nominal.modal8.v1',created_utc=utc(),kind='smooth phase reference-template approximation with original estimated Human inverse dynamics/allocator; separated quadratic interpolation',center=center,linear=np.asarray(linear).T,quadratic=np.asarray(quad).T,exact_arithmetic_rows=rows,training_native_steps=0,model_arithmetic_evaluations=17,wall_s=time.time()-start,inputs={'template_sha256':sha(template),'belief_sha256':sha(P/'history/CAUSAL_COMMISSIONED_BELIEF.json'),'source_sha256':sha(Path(__file__))},limitation='Phase smooth modes approximate discrete request modes and closed-loop response. Actual motion/tracking/admission/contact are UNKNOWN. No prediction of future Human truth. Offline ranking only.'))
 print('NOMINAL_PROXY_BUILT',time.time()-start,flush=True)
if __name__=='__main__':build()
