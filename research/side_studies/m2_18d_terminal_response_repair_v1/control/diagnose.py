"""Read archived evidence only. No controller, plant, or runner imports."""
from pathlib import Path
import os,json,gzip,hashlib,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_autonomous_review_v1';Q=S/'m2_18d_baseline_qualification_v1'
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(x):return dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
def items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';dec=json.JSONDecoder()
  while True:
   part=f.read(65536)
   if not part:raise ValueError('Missing '+key)
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip();assert buf.startswith('[');buf=buf[1:];break
   buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:row,end=dec.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('Truncated '+key)
    buf+=part;continue
   yield row;buf=buf[end:]
def event_times(v,t0):
 if isinstance(v,dict):
  return {k:(x-t0 if isinstance(x,(int,float)) and (k.endswith('physics_s') or k in ['splice_time_s','start_time_s','end_time_s']) else event_times(x,t0)) for k,x in v.items() if not isinstance(x,list) or len(x)<30}
 if isinstance(v,list):return [event_times(x,t0) for x in v]
 return v
results={};series={}
for root,g,arm in [(A,'N2',a) for a in ['B','E','C','R']]+[(Q,'N1',a) for a in ['B','E']]:
 ident=g+'_'+arm;folder=root/'source/results'/ident;su=json.loads((folder/'summary.json').read_text());z=np.load(folder/'trace.npz');mask=z['stage']=='TASK';t0=z['time_s'][mask][0];t=z['time_s'][mask]-t0;D={k:z[k][mask] for k in z.files if z[k].ndim and len(z[k])==len(mask)}
 ms=np.load(root/'motion_series'/(ident+'.npz'));nt=ms['time_s']-t0;q=np.rad2deg(ms['true_q_rad']);v=np.rad2deg(ms['true_dq_rad_s']);a=np.rad2deg(ms['acceleration_rad_s2']);j=np.rad2deg(ms['jerk_rad_s3'])
 ref=np.load(folder/'native_reference.npz')['data'];peak=np.argmax(abs(a[:,1]));outbound=t<9.005-1e-8
 schedules=[]
 for lr in su['learning_records']:
  d=su['decisions'][lr['decision_index']];sp=lr.get('selected_plan',{});ss=sp.get('schedule',{});rt=d['decision_request_time_s']-t0
  if rt>9.:continue
  schedules.append(dict(index=lr['decision_index'],request_s=rt,activation_s=d.get('actual_schedule_start_physics_s',np.nan)-t0,duration_s=ss.get('duration_s'),q0_deg=np.rad2deg(ss['start_q_rad']),dq0_deg_s=np.rad2deg(ss['start_dq_rad_s']),target_deg=np.rad2deg(ss['target_q_rad']),pass_velocity_deg_s=np.rad2deg(ss['target_dq_rad_s']),free=sp.get('execution_screen',{}).get('free_trajectory'),q_est_deg=np.rad2deg(lr['observation'][:2]),dq_est_deg_s=np.rad2deg(lr['observation'][2:]),decision_keys=list(d)))
 runtime=json.loads(gzip.open(folder/'runtime_artifacts.json.gz','rt').read())
 selected_events={k:event_times(runtime.get(k),t0) for k in ['future_handoff_bridges','rolling_splice_events','safe_fallback_events','reference_governor_records','sample_supported_arrival','sample_supported_dwell']}
 requests=[]
 for r in runtime['requests']:
  src=r.get('source_simulation_version',{}).get('sim_time_s')
  if src is not None and 5<t0*-1+src<8:
   requests.append({k:r.get(k) for k in ['request_id','outcome','reason','source_sample_time_s','activation_age_ms','fallback_intervals','fallback_physics_s','source_simulation_version','receipt_simulation_version','activation_simulation_version']})
 force=np.linalg.norm(D['physical_cuff_force_world_n'],axis=1);moment=np.linalg.norm(D['physical_cuff_moment_world_nm'],axis=1);trans={r['to']:r['time_s']-t0 for r in su['task']['phase_transitions']};phase={}
 for name,lo,hi in [('OUTBOUND',0,trans['HOLD']),('HOLD',trans['HOLD'],trans['RETURN']),('RETURN',trans['RETURN'],trans['COMPLETE'])]:
  w=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));phase[name]=dict(J_F_N_s=float(force[:-1]@w),moment_integral_Nm_s=float(moment[:-1]@w),duration_s=hi-lo)
 reach={}
 for name,time,qx,vx in [('actual',nt,q,v),('issued',ref[:,0],np.rad2deg(ref[:,1:3]),np.rad2deg(ref[:,3:5]))]:
  reach[name]={}
  for tol in [.5,.1]:
   rr=[]
   for k in range(2):
    ix=np.flatnonzero((time<9.005)&(np.abs(qx[:,k]-120)<=tol));rr.append(None if not len(ix) else float(time[ix[0]]))
   reach[name][str(tol)]=rr
 windows={}
 for label,lo,hi in [('pre_stop',schedules[-1]['request_s']-.15,schedules[-1]['request_s']),('stop',schedules[-1]['request_s'],schedules[-1]['request_s']+.3),('peak',nt[peak]-.025,nt[peak]+.025)]:
  ix=(t>=lo)&(t<hi);err=np.rad2deg(D['evaluation_only_human_state_rad_rad_s'][ix,:2]-D['reference_q_rad'][ix]);windows[label]=dict(lo=lo,hi=hi,tracking_RMS_deg=np.sqrt(np.mean(err*err,axis=0)),dq_error_RMS_deg_s=np.sqrt(np.mean(np.rad2deg(D['evaluation_only_human_state_rad_rad_s'][ix,2:]-D['reference_dq_rad_s'][ix])**2,axis=0)),torque_components_RMS_norm_Nm={k:float(np.sqrt(np.mean(np.sum(D['robot_torque_component_'+k+'_nm'][ix]**2,axis=1)))) for k in ['base','position','velocity','allocator','clipping']},force_range_N=[force[ix].min(),force[ix].max()],moment_range_Nm=[moment[ix].min(),moment[ix].max()])
 n=nt[peak];ri=np.argmin(abs(ref[:,0]-n));ti=np.argmin(abs(t-n));
 results[ident]=dict(source=str(folder),task_duration_s=t[-1],J_F_N_s=force[:-1]@np.diff(t),phases=phase,native_burden=dict(velocity=stats(v),acceleration=stats(a),jerk=stats(j)),knee_peak=dict(task_s=n,value_deg_s2=a[peak,1],q_deg=q[peak],dq_deg_s=v[peak],issued_at_nearest_sample=ref[ri],nearest_trace_task_s=t[ti],actual_minus_issued_q_deg=q[peak]-np.rad2deg(ref[ri,1:3])),reach=reach,schedules=schedules,windows=windows,events=selected_events,requests=requests,native_samples=len(nt))
 series[ident]=dict(t=t,D=D,nt=nt,q=q,v=v,a=a,ref=ref,schedules=schedules)
 print(ident,'peak',round(n,6),round(a[peak,1],6),'reach',reach['actual'],flush=True)
put('derived/TERMINAL_DIAGNOSIS.json',results)
# Earliest raw cross-prefix divergence: same commissioning does not imply same task prefix.
comparisons={}
for x,y in [('N2_E','N1_E'),('N2_E','N2_B')]:
 aa=series[x];bb=series[y];row={}
 for k in ['reference_q_rad','reference_dq_rad_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','robot_torque_component_allocator_nm']:
  assert np.max(abs(aa['t']-bb['t']))<1e-8
  d=np.max(abs(aa['D'][k]-bb['D'][k]),axis=1);ix=np.flatnonzero(d>1e-9);row[k]=dict(first_task_s=None if not len(ix) else aa['t'][ix[0]],max_abs_difference=float(d.max()),threshold_native_units=1e-9)
 comparisons[x+'__'+y]=row
put('derived/EARLIEST_DIFFERENCES.json',comparisons)
# Common task clock: N2 B/E and one PASS prefix. Separate joint curves, events, actual response.
fig,axs=plt.subplots(9,1,figsize=(15,22),sharex=True)
colors={'N2_B':'#444444','N2_E':'#c42a32','N1_E':'#147d92'}
for ident in colors:
 r=series[ident];c=colors[ident];t=r['t'];nt=r['nt'];ref=r['ref'];D=r['D']
 for k in range(2):
  axs[k].plot(nt[::4],r['q'][::4,k],color=c,label=ident+' actual');axs[k].plot(ref[:,0],np.rad2deg(ref[:,1+k]),'--',color=c,alpha=.7,label=ident+' issued')
  for ss in r['schedules']:
   axs[k].plot(ss['request_s'],ss['target_deg'][k],marker='x',color=c)
   axs[2+k].plot(ss['request_s'],ss['pass_velocity_deg_s'][k],marker='o',mfc='white',color=c)
  axs[2+k].plot(nt[::4],r['v'][::4,k],color=c,label=ident+' actual');axs[2+k].plot(ref[:,0],np.rad2deg(ref[:,3+k]),'--',color=c,alpha=.6)
 axs[4].plot(t,np.rad2deg(D['evaluation_only_human_state_rad_rad_s'][:,1]-D['reference_q_rad'][:,1]),color=c,label=ident+' knee');axs[4].plot(t,np.rad2deg(D['evaluation_only_human_state_rad_rad_s'][:,0]-D['reference_q_rad'][:,0]),':',color=c,alpha=.6)
 axs[5].plot(nt[::3],r['a'][::3,1],color=c,label=ident+' actual knee');axs[5].plot(ref[:,0],np.rad2deg(ref[:,6]),'--',color=c,alpha=.45,label=ident+' issued knee')
 for k,style in [('allocator','-'),('velocity','--'),('position',':')]:axs[6].plot(t,np.linalg.norm(D['robot_torque_component_'+k+'_nm'],axis=1),style,color=c,alpha=.8,label=ident+' '+k)
 axs[7].plot(t,np.linalg.norm(D['physical_cuff_force_world_n'],axis=1),color=c,label=ident)
 row=list(colors).index(ident)
 for ss in r['schedules']:
  if not 5<ss['request_s']<7.7:continue
  rt=ss['request_s'];act=ss['activation_s'];end=act+ss['duration_s']
  axs[8].plot([act,end],[row,row],color=c,lw=5,alpha=.45);axs[8].plot(rt,row,'x',color=c);axs[8].plot(act,row,'^',color=c)
  axs[8].annotate(f"req {rt:.3f}; act {act:.3f}; end {end:.3f}",(rt,row),xytext=(3,10),textcoords='offset points',fontsize=8)
 axs[5].axvline(results[ident]['knee_peak']['task_s'],color=c,alpha=.5)
for ax in axs[:2]:ax.axhline(120,color='black',lw=.7,alpha=.5)
limit=results['N2_B']['native_burden']['acceleration']['max_abs'][1]*1.1
axs[5].axhline(-limit,color='black',ls=':',label='N2 matched B × 1.10')
labels=['Hip q (deg); × selected target','Knee q (deg); × selected target','Hip dq (deg/s); ○ target pass speed','Knee dq (deg/s); ○ target pass speed','q error (deg); solid knee / dotted hip','Knee acceleration (deg/s²)','Robot component norm (Nm)','Measured cuff force (N)','Request × / activation ▲ / schedule duration']
for ax,label in zip(axs,labels):ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(5.25,7.65)
for ax in axs[:8]:ax.legend(loc='upper left',ncol=3,fontsize=7)
axs[8].set_yticks(range(3),list(colors));axs[-1].set_xlabel('Task clock (s); physics clock = task + 10.05 s')
fig.suptitle('Archived physical evidence — N2 terminal response, matched B and N1 motion PASS\nDashed: issued reference; solid: actual native response. Events alone do not establish causation.',fontsize=13)
fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(P/'figures/N2_terminal_timeline.png',dpi=150);plt.close(fig)
print(json.dumps(clean(comparisons)),flush=True)
