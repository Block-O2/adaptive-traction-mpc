"""Read-only matched reference/actual-motion mechanism diagnostic; no controller import."""
from pathlib import Path
import os,sys,json,gzip,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False)+'\n')
def stats(v):return dict(max_abs=np.max(abs(v),axis=0),p95_abs=np.quantile(abs(v),.95,axis=0),rms=np.sqrt(np.mean(v*v,axis=0)))
def process(root,group,arms,label):
 traces={};measures={};fig,axes=plt.subplots(4,1,figsize=(11,11),sharex=True)
 for arm in arms:
  ident=group+'_'+arm;folder=root/'source/results'/ident
  with np.load(root/'motion_series'/(ident+'.npz')) as z:
   nt=z['time_s'].copy();q=z['true_q_rad'].copy();v=z['true_dq_rad_s'].copy();a=z['acceleration_rad_s2'].copy();j=z['jerk_rad_s3'].copy();ph=z['phase'].copy()
  with np.load(folder/'native_reference.npz') as z:ref=z['data'].copy()
  with np.load(folder/'trace.npz') as z:
   ix=z['stage']=='TASK';t=z['time_s'][ix].copy();f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1)
  task=nt-nt[0];peak=int(np.argmax(abs(a[:,1])));tv=np.sum(abs(np.diff(np.rad2deg(v),axis=0)),axis=0);tva=np.sum(abs(np.diff(np.rad2deg(a),axis=0)),axis=0)
  measures[arm]=dict(J_F_N_s=float(f[:-1]@np.diff(t)),moment_integral_Nm_s=float(moment[:-1]@np.diff(t)),actual_velocity_TV_deg_s=tv,actual_acceleration_TV_deg_s2=tva,knee_peak=dict(task_s=float(task[peak]),value_deg_s2=float(np.rad2deg(a[peak,1])),phase=str(ph[peak])),raw_acceleration=stats(np.rad2deg(a)),raw_velocity=stats(np.rad2deg(v)),raw_jerk=stats(np.rad2deg(j)),reference_max_abs_acceleration_deg_s2=np.max(abs(np.rad2deg(ref[:,5:7])),axis=0))
  dtask=t-t[0];axes[0].plot(dtask,f,label=arm,alpha=.8);axes[1].plot(ref[:,0],np.rad2deg(ref[:,4]),label=arm,alpha=.8);axes[2].plot(task[::8],np.rad2deg(a[::8,1]),label=arm,alpha=.8);axes[3].plot(dtask[:-1],np.cumsum(f[:-1]*np.diff(t)),label=arm,alpha=.8)
  traces[arm]=dict(t=t,f=f,nt=nt,q=q,v=v,a=a,ph=ph,ref=ref)
 for ax,y in zip(axes,['Cuff force (N)','Issued knee velocity (deg/s)','Actual knee acceleration (deg/s²)','Cumulative task force (N s)']):ax.set_ylabel(y);ax.grid(alpha=.2);ax.legend()
 axes[-1].set_xlabel('Task time (s)');fig.suptitle(label+' — full-task physical traces');fig.tight_layout();(P/'figures').mkdir(exist_ok=True);fig.savefig(P/'figures'/(label+'_full.png'),dpi=150);plt.close(fig)
 # Localize N2 E peak across issued reference and actual state, without asserting mediation.
 E=traces.get('E',traces['B']);ti=int(np.argmax(abs(E['a'][:,1])));tp=E['nt'][ti];task_peak=tp-E['nt'][0]
 windows={}
 for arm,r in traces.items():
  sub=abs((r['nt']-r['nt'][0])-task_peak)<=.15;ri=int(np.argmin(abs(r['ref'][:,0]-task_peak)))
  windows[arm]=dict(anchor_task_s=float(task_peak),reference_sample=r['ref'][ri],actual_q_deg=np.rad2deg(r['q'][np.argmin(abs(r['nt']-tp))]),actual_dq_deg_s=np.rad2deg(r['v'][np.argmin(abs(r['nt']-tp))]),window_accel_max_deg_s2=np.max(abs(np.rad2deg(r['a'][sub])),axis=0))
 if 'B' in measures:
  for arm,m in measures.items():
   m['gain_percent_vs_B']=100*(measures['B']['J_F_N_s']-m['J_F_N_s'])/measures['B']['J_F_N_s'];m['knee_acceleration_max_ratio_vs_B']=m['raw_acceleration']['max_abs'][1]/measures['B']['raw_acceleration']['max_abs'][1]
 put('derived/'+label+'_MECHANISM.json',dict(status='COMPUTED',source_root=str(root),historical=root!=P,measures=measures,E_peak_aligned_windows=windows,interpretation='Reference/actual and time localization are observational. Parameter ablation is a closed-loop intervention, not a uniquely identified mediator. Maxima are raw native numerical derivatives, not clinical judgements.'))
 print(label,[(a,round(m['J_F_N_s'],6),round(m['knee_acceleration_max_ratio_vs_B'],6)) for a,m in measures.items()])
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='historical':process(P.parent/'m2_18d_baseline_qualification_v1','N2',['B','E'],'historical_N2')
 else:
  g=sys.argv[1];rows=json.loads((P/(g+'_RESULTS.json')).read_text())['rows'];process(P,g,[r['arm'] for r in rows if not r['arm'].endswith('repeat')],g)
