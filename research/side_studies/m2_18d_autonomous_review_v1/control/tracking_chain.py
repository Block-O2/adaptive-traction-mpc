"""Full and phase tracking/torque/schedule diagnosis. No physical integration."""
from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def integ(t,x,lo,hi):return np.tensordot(np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)),x[:-1],axes=(0,0))
def rms(x):return np.sqrt(np.mean(x*x,axis=0))
def process(root,group,arms,label):
 result={};traces={};schedules={}
 for arm in arms:
  folder=root/'source/results'/(group+'_'+arm);su=json.loads((folder/'summary.json').read_text());trans={r['to']:r['time_s'] for r in su['task']['phase_transitions']}
  with np.load(folder/'trace.npz') as z:
   mask=z['stage']=='TASK';t=z['time_s'][mask].copy();data={k:z[k][mask].copy() for k in z.files if z[k].ndim>0 and len(z[k])==len(mask)}
  lo=t[0];hi=t[-1];task=t-lo;truth=data['evaluation_only_human_state_rad_rad_s'];refq=data['reference_q_rad'];refv=data['reference_dq_rad_s'];components={k:data['robot_torque_component_'+k+'_nm'] for k in ['base','position','velocity','allocator','clipping']}
  cmd=sum(components.values());valid=np.all(np.isfinite(cmd),axis=1);assert valid[:-1].all()
  force=np.linalg.norm(data['physical_cuff_force_world_n'],axis=1);moment=np.linalg.norm(data['physical_cuff_moment_world_nm'],axis=1)
  windows={'full':(lo,hi),'OUTBOUND':(lo,trans['HOLD']),'HOLD':(trans['HOLD'],trans['RETURN']),'RETURN':(trans['RETURN'],trans['COMPLETE']),'late_OUTBOUND':(lo+6.5,lo+7.6)}
  measures={}
  for name,(a,b) in windows.items():
   ix=(t>=a-1e-9)&(t<b-1e-9)&valid;w=np.maximum(0,np.minimum(t[1:],b)-np.maximum(t[:-1],a))
   measures[name]=dict(J_F_N_s=float(force[:-1]@w),moment_integral_Nm_s=float(moment[:-1]@w),actual_q_mean_deg=np.rad2deg(truth[ix,:2]).mean(axis=0),position_tracking_RMS_deg=rms(np.rad2deg(truth[ix,:2]-refq[ix])),velocity_tracking_RMS_deg_s=rms(np.rad2deg(truth[ix,2:]-refv[ix])),reference_velocity_TV_deg_s=np.sum(abs(np.diff(np.rad2deg(refv[ix]),axis=0)),axis=0),applied_generalized_action_mean_nm=data['applied_generalized_action_nm'][ix].mean(axis=0),robot_components_RMS_nm={k:rms(v[ix]) for k,v in components.items()},total_robot_torque_RMS_nm=rms(cmd[ix]))
  assert abs(sum(measures[ph]['J_F_N_s'] for ph in ['OUTBOUND','HOLD','RETURN'])-measures['full']['J_F_N_s'])<1e-8
  sched=[]
  for lr in su['learning_records']:
   d=su['decisions'][lr['decision_index']];sp=lr.get('selected_plan',{});ss=sp.get('schedule',{});free=sp.get('execution_screen',{}).get('free_trajectory',{})
   phase='OUTBOUND'
   for tr in su['task']['phase_transitions']:
    if tr['time_s']<=d['decision_request_time_s']+1e-9 and tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase=tr['to']
   sched.append(dict(decision_index=lr['decision_index'],phase=phase,request_task_s=d['decision_request_time_s']-lo,activation_task_s=None if d.get('actual_schedule_start_physics_s') is None else d['actual_schedule_start_physics_s']-lo,activated=lr.get('selected_plan_activated'),duration_s=ss.get('duration_s'),start_q_deg=None if 'start_q_rad' not in ss else np.rad2deg(ss['start_q_rad']),start_dq_deg_s=None if 'start_dq_rad_s' not in ss else np.rad2deg(ss['start_dq_rad_s']),target_q_deg=None if 'target_q_rad' not in ss else np.rad2deg(ss['target_q_rad']),target_dq_deg_s=None if 'target_dq_rad_s' not in ss else np.rad2deg(ss['target_dq_rad_s']),free_status=free.get('status'),common_shift=free.get('common_shift'),differential_shift=free.get('differential_shift'),source_truth_consumed=sp.get('execution_screen',{}).get('deployable_truth_consumed')))
  result[arm]=measures;schedules[arm]=sched;traces[arm]=dict(task=task,force=force,moment=moment,truth=truth,refq=refq,refv=refv,components=components)
 comparisons={}
 for arm in arms:
  if arm=='B':continue
  a=traces[arm];b=traces['B'];assert np.allclose(a['task'],b['task'],rtol=0,atol=1e-8)
  comparisons[arm]={}
  for k in a['components']:
   d=a['components'][k][:-1]-b['components'][k][:-1];comparisons[arm][k]=dict(max_difference_norm_nm=float(np.max(np.linalg.norm(d,axis=1))),rms_difference_norm_nm=float(np.sqrt(np.mean(np.sum(d*d,axis=1)))))
  df=a['force']-b['force'];dt=np.diff(a['task']);comparisons[arm]['contact_force']=dict(delta_J_F_N_s=float(df[:-1]@dt),positive_area_N_s=float(np.maximum(df[:-1],0)@dt),negative_area_N_s=float(np.minimum(df[:-1],0)@dt),min_delta_N=float(df.min()),max_delta_N=float(df.max()))
 fig,axes=plt.subplots(6,1,figsize=(12,13),sharex=True)
 for arm,r in traces.items():
  t=r['task'];axes[0].plot(t,r['force'],label=arm);axes[1].plot(t,np.rad2deg(r['truth'][:,0]-r['refq'][:,0]),label=arm);axes[2].plot(t,np.rad2deg(r['truth'][:,1]-r['refq'][:,1]),label=arm)
  for ax,k in zip(axes[3:],['position','velocity','allocator']):ax.plot(t[:-1],np.linalg.norm(r['components'][k][:-1],axis=1),label=arm)
 for ax,y in zip(axes,['Contact force (N)','Hip q tracking error (deg)','Knee q tracking error (deg)','Position component norm (Nm)','Velocity component norm (Nm)','Allocator component norm (Nm)']):ax.set_ylabel(y);ax.grid(alpha=.2);ax.legend();ax.set_xlim(6.5,7.6)
 axes[-1].set_xlabel('Task time (s)');fig.suptitle(label+' — N2 late OUTBOUND response');fig.tight_layout();(P/'figures').mkdir(exist_ok=True);fig.savefig(P/'figures'/(label+'_tracking.png'),dpi=150);plt.close(fig)
 put('derived/'+label+'_TRACKING_CHAIN.json',dict(unix=time.time(),source_root=str(root),metrics=result,schedules=schedules,paired_component_differences=comparisons,meaning='Stored torque components and tracking are observed channels. Largest component difference is not an independently identified cause. allocated_wrench_world is total command wrench, not pure allocator output.',new_physics=0))
 print('TRACKING_CHAIN',label,[(a,result[a]['full']['J_F_N_s']) for a in arms])
if __name__=='__main__':
 if sys.argv[1]=='historical':process(P.parent/'m2_18d_baseline_qualification_v1','N2',['B','E'],'historical_N2')
 else:
  g=sys.argv[1];rows=json.loads((P/(g+'_RESULTS.json')).read_text())['rows'];process(P,g,[r['arm'] for r in rows if not r['arm'].endswith('repeat')],g)
