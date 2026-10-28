"""Zero-native diagnostic: quadratic, derivative interpolation, and input mapping."""
import sys,time,signal
import numpy as np
from scipy.interpolate import CubicHermiteSpline
from acl2_shared import P,R,read,put,sha,utc
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

def main():
 start=time.time();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('PROXY_ABLATION_180S')));signal.alarm(180);belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json');geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});model=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']));allocator=CuffAwareSagittalAllocator();table=read('models/MODAL_NOMINAL_TABLE.json');actual=read('audit/REFERENCE_RESPONSE_MECHANISM.json')['rows'];variants=[]
 for stride,kind in [(12,'ORIGINAL_HERMITE_DIRECT'),(12,'ISSUED_FIELDS_INTERPOLATED'),(4,'ISSUED_FIELDS_INTERPOLATED'),(1,'ISSUED_FIELDS_INTERPOLATED')]:
  with np.load(P/'history/CAUSAL_STRONG_REFERENCE_TEMPLATE.npz') as z:
   ix=np.unique(np.r_[np.arange(0,len(z['time_s']),stride),len(z['time_s'])-1]);t=z['time_s'][ix];q=z['q'][ix];v=z['dq'][ix];a=z['ddq'][ix];phase=z['phase'][ix]
  curve=CubicHermiteSpline(t,q,v);bounds={ph:(t[np.flatnonzero(phase==ph)[0]],t[np.flatnonzero(phase==ph)[-1]]) for ph in ['OUTBOUND','RETURN']}
  def fields(tau,degree):
   if kind=='ORIGINAL_HERMITE_DIRECT':return curve(tau,degree)
   source=[q,v,a][degree];return np.column_stack([np.interp(tau,t,source[:,d]) for d in range(2)])
  def arithmetic(x):
   qq=q.copy();vv=v.copy();aa=curve(t,2) if kind=='ORIGINAL_HERMITE_DIRECT' else a.copy()
   for j,ph in [(0,'OUTBOUND'),(2,'RETURN')]:
    idx=phase==ph;lo,hi=bounds[ph];T=hi-lo;s=(t[idx]-lo)/T;e=np.sin(np.pi*s)**2;ed=np.pi*np.sin(2*np.pi*s);edd=2*np.pi**2*np.cos(2*np.pi*s);k=4 if j==0 else 5;vs=6 if j==0 else 7;h=np.sin(4*np.pi*s)/(4*np.pi);hd=np.cos(4*np.pi*s);hdd=-4*np.pi*np.sin(4*np.pi*s)
    warp=-.08*x[k]*e+.12*x[vs]*h*e;wd=-.08*x[k]*ed+.12*x[vs]*(hd*e+h*ed);wdd=-.08*x[k]*edd+.12*x[vs]*(hdd*e+2*hd*ed+h*edd);tau=np.clip(t[idx]+T*warp,lo,hi);rate=1+wd;acc=wdd/T
    qq[idx]=fields(tau,0);vv[idx]=fields(tau,1)*rate[:,None];aa[idx]=fields(tau,2)*rate[:,None]**2+fields(tau,1)*acc[:,None];shift=np.radians(.30)*(1 if j==0 else -1)*np.array([x[j]+x[j+1],x[j]-x[j+1]]);qq[idx]+=e[:,None]*shift;vv[idx]+=ed[:,None]/T*shift;aa[idx]+=edd[:,None]/T**2*shift
   w=[]
   for xq,xv,xa in zip(qq,vv,aa):w.append(allocator._prepare_factors(xq,model).action_to_wrench_world@model.inverse_dynamics(xq,xv,xa))
   w=np.asarray(w);dt=np.diff(t);return np.array([np.linalg.norm(w[:-1,:3],axis=1)@dt,np.linalg.norm(w[:-1,3:],axis=1)@dt])
  center=arithmetic(np.zeros(8));rows=[]
  for r in actual:
   z=arithmetic(np.asarray(r['x']));delta=z-center;rows.append(dict(id=r['id'],actual_deltaJF=r['delta_JF_actual'],proxy_deltaJF=float(delta[0]),proxy_deltaJM=float(delta[1]),error_deltaJF=float(delta[0]-r['delta_JF_actual'])))
  variants.append(dict(kind=kind,stride_control_ticks=stride,dt_max_s=float(np.max(np.diff(t))),nominal_center=center,RMSE_deltaJF=float(np.sqrt(np.mean([r['error_deltaJF']**2 for r in rows]))),correct_signs=sum(np.sign(r['actual_deltaJF'])==np.sign(r['proxy_deltaJF']) for r in rows),rows=rows))
  print('PROXY_ABLATION',kind,stride,variants[-1]['RMSE_deltaJF'],flush=True)
 out=dict(utc=utc(),kind='POSTHOC_DEVELOPMENT_INPUT_NUMERICS_ABLATION_NO_NEW_OPTIMIZATION',original_quadratic_table_RMSE=read('audit/REFERENCE_RESPONSE_MECHANISM.json')['diagnostic_RMSE_deltaJF_before'],variants=variants,new_native_steps=0,wall_s=time.time()-start,source_sha256=sha(__file__),limitation='Same eight seen development interventions, no frozen prediction/optimization credit. This separates cheap quadratic error and derivative/field interpolation from remaining hand-designed reference mapping, without proving a unique causal bottleneck.')
 put('audit/PROXY_INPUT_NUMERICS_ABLATION.json',out);signal.alarm(0)
if __name__=='__main__':main()
