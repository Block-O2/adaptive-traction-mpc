from pathlib import Path
import os,sys,json,shutil,ast
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_autonomous_multitrack_v1'
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'code'),str(P/'control')]
import study_common as sc
from stream_runtime_evidence import array_items
import numpy as np
import matplotlib.pyplot as plt
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
def put(n,x):(P/n).write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(p):return json.loads(p.read_text())
z=np.load(A/'source/results/Adev_ER/trace.npz');ix=z['stage']=='TASK';origin=z['time_s'][ix][0];t=z['time_s'][ix]-origin;state=z['estimated_human_state_rad_rad_s'][ix];ref=z['reference_q_rad'][ix];refv=z['reference_dq_rad_s'][ix];refa=z['reference_ddq_rad_s2'][ix]
n=np.load(A/'motion_series/Adev_ER.npz');nt=n['time_s']-origin;q=np.rad2deg(n['true_q_rad']);v=np.rad2deg(n['true_dq_rad_s']);a=np.rad2deg(n['acceleration_rad_s2']);su=read(A/'source/results/Adev_ER/summary.json');geo=PlanarCuffGeometry(**{k:np.asarray(val) if isinstance(val,list) else val for k,val in su['learning_records'][0]['adaptive_state']['effective_geometry'].items()})
events=[]
for label,tt in [('R4_request',15.335),('goal_crossing',16.5085),('reference_stop',16.895),('R5_splice',16.945),('actual_knee_minimum',17.166),('post_recovery',17.5)]:
 i=int(np.argmin(abs(t-tt)));x=state[i];model=StateResidualHumanModel(geometry=geo,beta=z['task_beta'][i],rom_human=sc.rt.high_rom_deployable_prior(),residual_weights_nm=z['task_residual_weights_nm'][i]);force=z['physical_cuff_force_world_n'][ix][i];moment=z['physical_cuff_moment_world_nm'][ix][i];tau=geo.generalized_input_from_wrench(x[:2],force,moment);mat=model.mass_matrix(x[:2]);actual_acc=np.array([np.interp(t[i],nt,a[:,j]) for j in range(2)])
 events.append(dict(label=label,requested_task_s=tt,trace_task_s=t[i],issued_q_deg=np.rad2deg(ref[i]),issued_dq_deg_s=np.rad2deg(refv[i]),issued_ddq_deg_s2=np.rad2deg(refa[i]),estimated_state_deg_deg_s=np.rad2deg(x),actual_q_deg=[np.interp(tt,nt,q[:,j]) for j in range(2)],actual_dq_deg_s=[np.interp(tt,nt,v[:,j]) for j in range(2)],native_acceleration_at_trace_deg_s2=actual_acc,causal_acceleration_deg_s2=np.rad2deg(z['actual_human_acceleration_rad_s2'][ix][i]),unprojected_PD_acceleration_deg_s2=np.rad2deg([180,140]*(ref[i]-x[:2])+[28,22]*(refv[i]-x[2:])),model_acceleration_sensed_wrench_deg_s2=np.rad2deg(model.continuous_dynamics(x,tau)[2:]),model_acceleration_requested_action_deg_s2=np.rad2deg(model.continuous_dynamics(x,z['applied_generalized_action_nm'][ix][i])[2:]),model_mass_matrix=mat,knee_inertia_from_hip_acceleration_nm=float(mat[1,0]*np.radians(actual_acc[0])),knee_inertia_from_knee_acceleration_nm=float(mat[1,1]*np.radians(actual_acc[1])),measured_generalized_input_nm=tau,requested_generalized_action_nm=z['applied_generalized_action_nm'][ix][i],robot_torque_nm=z['cr12_actuator_command_nm'][ix][i],clearance_m={k:z[k][ix][i] for k in ['session_shank_clearance_m','dev_d_session_envelope_clearance_m','dev_d_measured_sleeve_gap_m']},contact=bool(z['shank_bed_contact_evaluation_only'][ix][i])))
attempts=[]
for r in array_items(A/'source/results/Adev_ER/runtime_artifacts.json.gz','execution_attempts'):
 tt=r['source_sample_time_s']-origin
 if 15.3<=tt<=18.:
  proj=r.get('incremental_acceleration_projection');rec=dict(task_s=tt,applied=r.get('applied'),native_steps=r.get('native_steps'),incremental=proj,clearance=r.get('clearance_feedback'))
  if proj is not None:
   va=np.array([np.interp(tt,nt,v[:,j]) for j in range(2)]);vb=np.array([np.interp(tt+.005,nt,v[:,j]) for j in range(2)])
   rec['actual_next_5ms_mean_accel_deg_s2']=(vb-va)/.005
  attempts.append(rec)
put('derived/TERMINAL_EXECUTION_ATTEMPTS.json',attempts)
projs=[r for r in attempts if r['incremental'] is not None]
errors={}
for key in ['raw_rad_s2','projected_rad_s2','measured_rad_s2']:
 er=np.array([np.rad2deg(r['incremental'][key])-r['actual_next_5ms_mean_accel_deg_s2'] for r in projs]);errors[key]=dict(rmse_deg_s2=np.sqrt(np.mean(er*er,axis=0)),p95_abs_deg_s2=np.quantile(abs(er),.95,axis=0),bias_deg_s2=np.mean(er,axis=0))
b=np.load(A/'motion_series/Adev_B.npz');bq=np.rad2deg(b['true_q_rad']);summary=dict(events=events,projection_count=len(projs),projection_active_count=sum(bool(r['incremental']['active']) for r in projs),next5ms_acceleration_prediction_errors=errors,ER_min_max_deg=[np.min(q,axis=0),np.max(q,axis=0)],B_min_max_deg=[np.min(bq,axis=0),np.max(bq,axis=0)],minimum_change_deg=np.min(q,axis=0)-np.min(bq,axis=0),maximum_change_deg=np.max(q,axis=0)-np.max(bq,axis=0),excursion_difference_deg=np.ptp(q,axis=0)-np.ptp(bq,axis=0),target_definition=dict(registered_return_deg=[5.,10.],issued_robust_terminal_deg=np.rad2deg(ref[-1]).tolist(),overshoot_report_uses='issued terminal 9.5deg; original task target remains10deg; never change denominator silently'),terminal_clipping_max_nm=float(np.max(abs(z['robot_torque_component_clipping_nm'][ix][(t>=15.3)&(t<=18.)]))),terminal_shank_bed_contact_count=int(np.sum(z['shank_bed_contact_evaluation_only'][ix][(t>=15.3)&(t<=18.)])))
put('derived/DETAILED_TERMINAL_DIAGNOSIS.json',summary)
sources={}
names=['human_waypoint_shadow.py','human_waypoint_feedback_mpc.py','human_waypoint_scheduler.py','cr12_plant.py','cr12_robot.py','mechanics.py','loaded_execution.py','loaded_supervisor.py','hold_stabilizer.py','split_acceleration_monitor.py','controller_interface.py','estimator_v2.py','cuff_allocator.py','executable_command.py','phase3_human_waypoint.py','functional_benchmark.py','runtime_coordination_residual_v2.py','activation_validation.py','scientific_scheduler.py','rolling_suffix_splice.py','receipt_reference_governor.py']
for f in (P/'source/stages').rglob('*.py'):
 if f.name in names:
  lines=f.read_text().splitlines();matches=[dict(line=i+1,text=l) for i,l in enumerate(lines) if any(k in l for k in ['def command(', 'class ','position_gain','velocity_gain','desired_acceleration =','bias_torque','force_position','force_velocity','joint_torque_base','incremental_acceleration','NOMINAL_PHYSICS_DT','CONTROL_DT','ADAPTATION_DT','spring','stiffness','damping','mj_step','source_sample_time_s >=','short_horizon','mass_matrix','inverse_dynamics','generalized_input_from_wrench'])]
  sources[str(f.relative_to(P))]=dict(sha256=sc.sha(f),matches=matches)
put('audit/CONTROL_SOURCE_INDEX.json',sources)
# Zoom actual plotted ranges, rather than retaining full-task autoscale.
fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True,layout='constrained')
for arm,color in [('B','#777777'),('ER','#0072b2')]:
 tr=np.load(A/('source/results/Adev_'+arm+'/trace.npz'));ti=tr['stage']=='TASK';origin2=tr['time_s'][ti][0];tf=tr['time_s'][ti]-origin2;nn=np.load(A/('motion_series/Adev_'+arm+'.npz'));tn=nn['time_s']-origin2;qn=np.rad2deg(nn['true_q_rad'][:,1]);mask=(tn>=16.3)&(tn<=17.8);maskf=(tf>=16.3)&(tf<=17.8)
 axs[0].plot(tn[mask],qn[mask],c=color,label=arm+' actual');axs[0].plot(tf[maskf],np.rad2deg(tr['reference_q_rad'][ti][maskf,1]),c=color,ls='--',label=arm+' reference')
 axs[1].plot(tf[maskf],np.rad2deg(tr['estimated_human_state_rad_rad_s'][ti][maskf,1]-tr['reference_q_rad'][ti][maskf,1]),c=color,label=arm+' estimated tracking error')
 axs[2].plot(tn[mask],qn[mask]-9.5,c=color,label=arm+' actual minus issued goal')
axs[0].set_ylim(7.9,20.5);axs[2].set_ylim(-1.4,1.2)
for ax,label in zip(axs,['Knee angle (deg)','Tracking error (deg)','Actual minus terminal goal (deg)']):ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend();ax.axvline(16.895,c='grey',ls=':');ax.axvline(17.166,c='grey',ls='--');ax.set_xlim(16.3,17.8)
axs[2].axhline(0,c='black',lw=.7);axs[-1].set_xlabel('Task time (s); dotted: ER reference stop; dashed: ER actual minimum');fig.savefig(P/'figures/04_overshoot_before_after.png',dpi=150);plt.close(fig)
for f in [P/'derived/DETAILED_TERMINAL_DIAGNOSIS.json',P/'audit/CONTROL_SOURCE_INDEX.json',P/'figures/04_overshoot_before_after.png']:
 dst=R/f.relative_to(P);dst.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(f,dst)
print(json.dumps(sc.clean(dict(status='PASS',events=events,projection_count=len(projs),projection_active_count=summary['projection_active_count'],errors=errors))),flush=True)
