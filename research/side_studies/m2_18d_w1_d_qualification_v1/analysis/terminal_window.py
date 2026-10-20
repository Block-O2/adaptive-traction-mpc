from pathlib import Path
import os,sys,json,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
sp=importlib.util.spec_from_file_location('independent_raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
out={};fig,ax=plt.subplots(7,1,figsize=(13,17),sharex=True,layout='constrained')
for arm,co in [('B','#666666'),('T','#0072b2'),('D','#cc3377')]:
 ident='W1_'+arm;folder=P/'source/results'/ident;tr=np.load(folder/'trace.npz');z=np.load(P/'motion_series'/(ident+'.npz'));ix=tr['stage']=='TASK';origin=tr['time_s'][ix][0];tt=tr['time_s']-origin;t=z['time_s']-origin;sel=(tt>=16.4)&(tt<=17.1);sn=(t>=16.4)&(t<=17.1);peak=int(np.argmax(abs(z['acceleration_rad_s2'][:,1])));pt=float(t[peak]);narrow=[];near_receipts=[]
 for x in raw.array_items(folder/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  tm=x['time_s']-origin
  if pt-.006-1e-9<=tm<=pt+.006+1e-9:narrow.append({k:x.get(k) for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']})
 # Exact trace nodes around the D failure time, independent of each arm's peak.
 jj=np.flatnonzero((tt>=16.685-1e-8)&(tt<=16.715+1e-8));fields=['time_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','cr12_actuator_command_nm','robot_torque_component_allocator_nm','robot_torque_component_clipping_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm','allocated_wrench_world','dev_d_measured_sleeve_gap_m','shank_bed_contact_evaluation_only','active_contact_pairs_evaluation_only_json','selected_schedule_label','safety_mode']
 records=[{k:tr[k][i].tolist() for k in fields} for i in jj];su=json.loads((folder/'summary.json').read_text());events=[]
 for x in raw.array_items(folder/'runtime_artifacts.json.gz','command_receipts'):
  tm=x.get('start_physics_s',-1)-origin
  if 16.68-1e-9<=tm<=16.72+1e-9:near_receipts.append(x)
 for lr in su['learning_records']:
  if lr['end_time_s']-origin<16.4 or lr['start_time_s']-origin>17.1:continue
  d=su['decisions'][lr['decision_index']];events.append(dict(decision_index=lr['decision_index'],request_task_s=d['decision_request_time_s']-origin,start_task_s=lr['start_time_s']-origin,end_task_s=lr['end_time_s']-origin,schedule=lr['selected_plan']['schedule'],activation=d.get('activation_outcome'),screen=lr['selected_plan']['execution_screen']))
 valid=tr['stage']=='TASK';clip=np.linalg.norm(tr['robot_torque_component_clipping_nm'][valid],axis=1);contacts=tr['shank_bed_contact_evaluation_only'][valid]
 out[arm]=dict(knee_acceleration_peak_task_s=pt,knee_acceleration_peak_deg_s2=float(np.rad2deg(abs(z['acceleration_rad_s2'][peak,1]))),native_window_around_own_peak=narrow,trace_window_around_D_peak=records,receipts_around_D_peak=near_receipts,events=events,clipping_norm_max_full_task=float(np.nanmax(clip)) if np.any(np.isfinite(clip)) else None,clipping_finite_samples=int(np.isfinite(clip).sum()),shank_bed_contact_sample_count=int(np.count_nonzero(contacts)))
 ax[0].plot(t[sn],np.rad2deg(z['true_dq_rad_s'][sn,1]),c=co,label=arm);ax[1].plot(t[sn],np.rad2deg(z['acceleration_rad_s2'][sn,1]),c=co);ax[2].plot(t[sn],np.rad2deg(z['jerk_rad_s3'][sn,1]),c=co);ax[3].plot(tt[sel],np.rad2deg(tr['reference_dq_rad_s'][sel,1]),c=co);ax[4].plot(tt[sel],np.linalg.norm(tr['robot_torque_component_allocator_nm'][sel],axis=1),c=co);ax[5].plot(tt[sel],np.linalg.norm(tr['robot_torque_component_clipping_nm'][sel],axis=1),c=co);ax[6].plot(tt[sel],tr['dev_d_measured_sleeve_gap_m'][sel],c=co)
for axis,label in zip(ax,['Actual knee dq deg/s','Raw knee acceleration deg/s2','Raw knee jerk deg/s3','Issued reference knee dq deg/s','Allocator torque norm Nm','Clipping torque norm Nm','Measured sleeve gap m']):axis.set_ylabel(label);axis.axvline(16.7,c='r',ls=':',lw=.7);axis.grid(alpha=.2)
ax[0].legend(ncol=3);ax[-1].set_xlabel('Task seconds');fig.suptitle('W1 terminal D motion spike | observational localization, no mediator attribution');fig.savefig(P/'figures/W1_D_terminal_spike.png',dpi=140);plt.close(fig)
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
(P/'derived/W1_D_TERMINAL_WINDOW.json').write_text(json.dumps(clean(dict(status='OFFLINE_OBSERVATION',arms=out,interpretation='Actual native q/dq and applied command/contacts are preserved around each peak. NaN trace component entries mean unrecorded, not zero clipping/allocator. Coincidence does not establish mediation. Original raw mandatory gates unchanged.')),indent=2,allow_nan=False)+'\n')
print(json.dumps({k:{x:v[x] for x in ['knee_acceleration_peak_task_s','knee_acceleration_peak_deg_s2','clipping_norm_max_full_task','shank_bed_contact_sample_count']} for k,v in out.items()}),flush=True)
