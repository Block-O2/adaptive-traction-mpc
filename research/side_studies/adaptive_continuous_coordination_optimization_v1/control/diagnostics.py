"""Archived signals only; no controller imports and no physics stepping."""
from pathlib import Path
import os,json,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1')
I=P.parent/'adaptive_continuous_coordination_interface_v1';O=P.parent/'ihear_overnight_research_retrospective_v1'
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,allow_nan=False))
def corr(x,y):
 x=np.asarray(x);y=np.asarray(y)
 return dict(pearson=float(np.corrcoef(x,y)[0,1]),spearman=float(spearmanr(x,y).statistic),n=len(x)) if len(x)>3 and min(np.std(x),np.std(y))>1e-12 else dict(pearson=None,spearman=None,n=len(x))
def stats(x):return dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
def analyze(root,ident,label):
 z=np.load(root/'motion_series'/(ident+'.npz'));t=z['time_s'];q=z['true_q_rad'];v=z['true_dq_rad_s'];a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2);ph=z['phase'];t0=t[0];tt=t-t0;dt=np.diff(t)
 assert np.max(abs(dt-.00025))<1e-9
 tr=np.load(root/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';tf=tr['time_s'][m]-t0;force=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1);cf=np.r_[0,np.cumsum(force[:-1]*np.diff(tf))];jf=cf[-1]
 speed=np.linalg.norm(v,axis=1);speedvar=np.abs(np.gradient(speed,t,edge_order=2));tvv=np.r_[np.zeros((1,2)),np.cumsum(abs(np.diff(v,axis=0)),axis=0)];tvc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(v,axis=0),axis=1))]
 det=v[:,0]*a[:,1]-v[:,1]*a[:,0];curv={};epslist=[1e-4,1e-3,1e-2]
 for eps in epslist:
  k=det/(speed*speed+eps*eps)**1.5;raw=np.divide(det,speed**3,out=np.full_like(speed,np.nan),where=speed>eps);valid=(speed[:-1]>eps)&(speed[1:]>eps)
  dk=np.gradient(k,t,edge_order=2)
  curv[str(eps)]=dict(total_variation=float(np.sum(abs(np.diff(k)))),derivative_total_variation=float(np.sum(abs(np.diff(dk)))),integral_abs_curvature_derivative=float(np.sum(abs(dk[:-1])*dt)),masked_raw_total_variation=float(np.sum(abs(np.diff(raw))[valid])),valid_fraction=float(np.mean(speed>eps)),regularized_max_abs=float(np.max(abs(k))))
 k=det/(speed*speed+1e-6)**1.5;dk=np.gradient(k,t,edge_order=2);kdv=np.r_[0,np.cumsum(abs(np.diff(k)))];speedcum=np.r_[0,np.cumsum(abs(np.diff(speed)))];av=np.r_[np.zeros((1,2)),np.cumsum(abs(np.diff(a,axis=0)),axis=0)]
 summary=json.loads((root/'source/results'/ident/'summary.json').read_text());trans={r['to']:r['time_s']-t0 for r in summary['task']['phase_transitions']};bounds=[tf[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']]
 phasecost={p:float(np.interp(hi,tf,cf)-np.interp(lo,tf,cf)) for p,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:])}
 windows={};correlations={}
 for width in [.5,1.]:
  rows=[]
  for lo in np.arange(0,tt[-1]-width+1e-8,width):
   hi=lo+width;sel=(tt>=lo)&(tt<hi);idx=np.flatnonzero(sel);p=str(ph[idx[0]]) if np.all(ph[sel]==ph[idx[0]]) else 'CROSS_PHASE'
   rows.append(dict(start_s=float(lo),end_s=float(hi),phase=p,J_F_N_s=float(np.interp(hi,tf,cf)-np.interp(lo,tf,cf)),speed_mean=float(np.mean(speed[sel])),speed_variation=float(np.interp(hi,tt,speedcum)-np.interp(lo,tt,speedcum)),velocity_TV=float(np.interp(hi,tt,tvc)-np.interp(lo,tt,tvc)),acceleration_RMS=float(np.sqrt(np.mean(np.sum(a[sel]**2,axis=1)))),acceleration_variation=float(np.sum(av[idx[-1]]-av[idx[0]])),jerk_RMS=float(np.sqrt(np.mean(np.sum(j[sel]**2,axis=1)))),curvature_TV=float(np.interp(hi,tt,kdv)-np.interp(lo,tt,kdv))))
  windows[str(width)]=rows;features=['speed_mean','speed_variation','velocity_TV','acceleration_RMS','acceleration_variation','jerk_RMS','curvature_TV']
  correlations[str(width)]={scope:{key:corr([r['J_F_N_s'] for r in rows if scope=='ALL' or r['phase']==scope],[r[key] for r in rows if scope=='ALL' or r['phase']==scope]) for key in features} for scope in ['ALL','OUTBOUND','HOLD','RETURN']}
 lag=[];rows=windows['0.5']
 for shift in [-2,-1,0,1,2]:
  pairs=[(rows[i],rows[i+shift]) for i in range(len(rows)) if 0<=i+shift<len(rows) and rows[i]['phase']==rows[i+shift]['phase']!='CROSS_PHASE']
  lag.append(dict(motion_leads_force_by_s=shift*.5,metrics={key:corr([y['J_F_N_s'] for x,y in pairs],[x[key] for x,y in pairs]) for key in ['speed_variation','velocity_TV','jerk_RMS','curvature_TV']}))
 rec=dict(id=ident,label=label,J_F_N_s=jf,phase_J_F_N_s=phasecost,native_dt_s=.00025,force_grid_s=float(np.median(np.diff(tf))),full=dict(velocity=stats(v),acceleration=stats(a),jerk=stats(j),speed=stats(speed),TV_velocity_per_joint=tvv[-1],TV_velocity_combined=tvc[-1],TV_speed=speedcum[-1],TV_acceleration_per_joint=av[-1],jerk_energy_per_joint=np.sum(j[:-1]**2*dt[:,None],axis=0),curvature=curv),windows=windows,correlations=correlations,lagged_within_phase=lag,boundaries=bounds,sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [root/'motion_series'/(ident+'.npz'),root/'source/results'/ident/'trace.npz',root/'source/results'/ident/'summary.json']})
 series=dict(t=tt,q=q,v=v,a=a,j=j,k=k,kdv=kdv,tvv=tvv,tvc=tvc,tf=tf,cf=cf,force=force,refv=tr['reference_dq_rad_s'][m],truev=tr['evaluation_only_human_state_rad_rad_s'][m,2:],bounds=bounds)
 return rec,series
def main():
 cases=[(I,'interface2_B0','B'),(O,'development_repair2_quality_NATIVE_SCALAR_18_063','18D development'),(I,'interface2_knee_002','+0.02 deg PASS'),(I,'interface1_knee_005','+0.05 deg motion FAIL')]
 records=[];series=[]
 for root,i,label in cases:
  r,s=analyze(root,i,label);records.append(r);series.append(s);print(label,r['J_F_N_s'],r['correlations']['0.5']['ALL'],flush=True)
 for r in records:
  for w,rows in r['windows'].items():
   for x,b in zip(rows,records[0]['windows'][w]):x['benefit_vs_B_N_s']=b['J_F_N_s']-x['J_F_N_s']
  r['largest_benefit_windows']=sorted(r['windows']['0.5'],key=lambda x:x['benefit_vs_B_N_s'],reverse=True)[:5]
 rows=records[0]['windows']['0.5'];eligible=[r for r in rows if r['phase']=='OUTBOUND' and 1.5<=r['start_s']<=2.5]
 chosen=max(eligible,key=lambda r:r['J_F_N_s']*r['velocity_TV'])
 frac=float(np.clip(((chosen['start_s']+chosen['end_s'])/2-1.61)/1.27,.25,.75));put('ADAPTIVE_REFINEMENT_PLAN.json',dict(method='offline product of force accumulation and actual velocity TV; constrained to previously proven outbound slot1 suffix',selected_window=chosen,internal_fraction=frac,online_adaptive_controller=False,truth_firewall='offline research design only, no native truth enters runtime'))
 put('DIAGNOSTIC_RESULTS.json',dict(cases=records,correlation_not_causation=True,force_signal='5ms recorded cuff-force norm, original left quadrature; no native force values fabricated',motion_signal='unfiltered 0.25ms actual Human velocity',curvature='signed curvature in equal-weight radian hip-knee plane; det(v,a)/(||v||^2+eps^2)^(3/2); eps sensitivity 1e-4/1e-3/1e-2 rad/s; raw curvature only above eps'))
 plt.rcParams.update({'font.size':8,'figure.dpi':140})
 def finish(fig,name):fig.tight_layout();fig.savefig(P/'figures'/name);plt.close(fig)
 fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
 for r,s in zip(records,series):
  axes[0].plot(s['tf'],s['cf'],label=r['label']);axes[1].plot(s['tf'],s['cf']/r['J_F_N_s']);axes[2].plot(s['tf'],s['force'])
 for ax in axes:
  for b in series[0]['bounds'][1:3]:ax.axvline(b,color='k',ls=':',lw=.7)
 axes[0].legend();axes[0].set_ylabel('C_F [N s]');axes[1].set_ylabel('C_F / J_F');axes[2].set_ylabel('Force [N]');axes[2].set_xlabel('Task elapsed [s]');finish(fig,'cumulative_force_vs_time.png')
 fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True)
 for r,s in zip(records,series):
  rows=r['windows']['0.5'];x=[(z['start_s']+z['end_s'])/2 for z in rows]
  axes[0].plot(x,[z['J_F_N_s'] for z in rows],label=r['label']);axes[1].plot(x,[z['velocity_TV'] for z in rows]);axes[2].plot(x,[z['jerk_RMS'] for z in rows])
 axes[0].legend();axes[0].set_ylabel('0.5s J_F [N s]');axes[1].set_ylabel('Velocity TV [rad/s]');axes[2].set_ylabel('Jerk RMS [rad/s^3]');axes[2].set_xlabel('Task elapsed [s]');finish(fig,'force_accumulation_vs_motion_variation.png')
 fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True)
 for r,s in zip(records,series):
  for d in range(2):axes[d].plot(s['tf'],np.degrees(s['truev'][:,d]-s['refv'][:,d]),label=r['label'])
 axes[0].legend();axes[0].set_ylabel('Hip actual-issued dq [deg/s]');axes[1].set_ylabel('Knee actual-issued dq [deg/s]');axes[1].set_xlabel('Task elapsed [s]');finish(fig,'actual_vs_reference_velocity.png')
 fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True)
 for r,s in zip(records,series):
  for d in range(2):axes[d].plot(s['t'],s['tvv'][:,d],label=r['label'])
  axes[2].plot(s['t'],s['tvc'])
 axes[0].legend();axes[0].set_ylabel('Hip TV_v');axes[1].set_ylabel('Knee TV_v');axes[2].set_ylabel('Combined TV_v');axes[2].set_xlabel('Task elapsed [s]');finish(fig,'cumulative_velocity_variation.png')
 fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
 for r,s in zip(records,series):axes[0].plot(s['t'],s['k'],label=r['label']);axes[1].plot(s['t'],s['kdv'])
 axes[0].set_yscale('symlog',linthresh=1);axes[0].legend();axes[0].set_ylabel('Regularized signed curvature');axes[1].set_ylabel('TV curvature');axes[1].set_xlabel('Task elapsed [s]');finish(fig,'curvature_and_curvature_variation.png')
if __name__=='__main__':main()
