from pathlib import Path
import os,json,time,ast,hashlib,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;S=P.parent
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
src=(R/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
for name in ['load','terminal','variations']:exec(ast.get_source_segment(src,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)))
root=S/'m2_18d_early_return_motion_repair_v1';ids=['repair_B','repair_T','repair_D','repair_ER110_R4_120'];Z={i:load(root,i) for i in ids};B=Z['repair_B'];rows=[]
for ident,z in Z.items():
 tr=np.load(root/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';terr=terminal(z)[1];samples=[]
 labels=[('R3_request',next(e['request'] for e in z['events'] if e['phase']=='RETURN' and e['slot']==3)),('R4_request',next(e['request'] for e in z['events'] if e['phase']=='RETURN' and e['slot']==4)),('actual_first_goal_cross',terr['first_goal_crossing_return_s']),('reference_knee_stop',terr['reference_stably_stopped_task_s']),('actual_knee_min',terr['return_min_task_s'])]
 for label,when in labels:
  k=int(np.argmin(abs(z['tf']-when)));fields={}
  for key in ['robot_torque_component_base_nm','robot_torque_component_position_nm','robot_torque_component_velocity_nm','robot_torque_component_allocator_nm','robot_torque_component_clipping_nm','cr12_actuator_command_nm','allocated_wrench_world','task_beta','task_residual_weights_nm','controller_model_version','active_contact_pairs_evaluation_only_json']:
   arr=tr[key]
   if len(arr)==len(ix):arr=arr[ix]
   else:assert len(arr)==len(z['tf']),(key,arr.shape,len(z['tf']))
   value=arr[k];fields[key]=value.tolist() if hasattr(value,'tolist') else value
  samples.append(dict(event=label,event_task_s=when,sampled_task_s=float(z['tf'][k]),actual_q_dq_deg_deg_s=z['truth'][k].tolist(),estimated_q_dq_deg_deg_s=z['estimated'][k].tolist(),reference_q_dq_deg_deg_s=np.r_[z['rq'][k],z['rv'][k]].tolist(),estimation_error_deg_deg_s=(z['estimated'][k]-z['truth'][k]).tolist(),actual_tracking_deg=(z['truth'][k,:2]-z['rq'][k]).tolist(),estimated_tracking_deg=(z['estimated'][k,:2]-z['rq'][k]).tolist(),force_N=float(z['f'][k]),moment_Nm=float(z['moment'][k]),signals=fields))
 q=z['q'];qb=B['q'];bounds=dict(candidate_min_deg=q.min(axis=0).tolist(),candidate_max_deg=q.max(axis=0).tolist(),B_min_deg=qb.min(axis=0).tolist(),B_max_deg=qb.max(axis=0).tolist(),max_delta_deg=(q.max(axis=0)-qb.max(axis=0)).tolist(),min_delta_deg=(q.min(axis=0)-qb.min(axis=0)).tolist(),excursion_delta_deg=(np.ptp(q,axis=0)-np.ptp(qb,axis=0)).tolist(),identity='delta excursion = delta global maximum - delta global minimum; distinct from goal overshoot')
 temporal=[]
 for sig,key in [('v','velocity_deg_s'),('a','acceleration_deg_s2'),('j','jerk_deg_s3')]:
  limit=np.array(B['metric']['motion']['raw']['full'][key]['p95_abs'])*1.1
  for joint in range(2):
   x=z[sig][:,joint];pk=int(np.argmax(abs(x)));high=abs(x)>limit[joint]
   temporal.append(dict(signal=key,joint=['hip','knee'][joint],peak=float(abs(x[pk])),peak_task_s=float(z['t'][pk]),peak_phase=str(z['phase'][pk]),high_sample_reference=float(limit[joint]),high_samples_by_phase={ph:int(np.sum(high&(z['phase']==ph))) for ph in ['OUTBOUND','HOLD','RETURN']},squared_energy_share_by_phase={ph:float(np.sum(x[z['phase']==ph]**2)/np.sum(x*x)) for ph in ['OUTBOUND','HOLD','RETURN']}))
 rows.append(dict(id=ident,snapshots=samples,excursion_decomposition=bounds,motion_temporal=temporal,raw_SG_sensitivity={method:z['metric']['motion'][method]['full'] for method in ['raw','SG5','SG21']},interpretation='Estimator/allocator/force co-evolution observational; no single mediator identified'))
put('derived/TERMINAL_ESTIMATE_AND_COMPENSATION.json',dict(rows=rows,source='historical saved native plus causal trace',new_physics=0,analysis_correction='Initial read-only analysis stopped on task_beta TASK-only array length; each field now explicitly checked against full or TASK grid. No physics or control source changed.'))
fig,axs=plt.subplots(4,1,figsize=(12,10),sharex=True,layout='constrained')
z=Z[ids[-1]];tf=z['tf'];t=z['t'];axs[0].plot(t,z['q'][:,1],label='True Human');axs[0].plot(tf,z['estimated'][:,1],label='Causal estimate');axs[0].plot(tf,z['rq'][:,1],ls='--',label='Issued reference');axs[0].set_ylim(8,13)
axs[1].plot(tf,z['estimated'][:,1]-z['truth'][:,1],label='estimate - truth');axs[1].plot(tf,z['estimated'][:,1]-z['rq'][:,1],label='estimate - reference');axs[1].plot(tf,z['truth'][:,1]-z['rq'][:,1],label='truth - reference')
axs[2].plot(t,z['v'][:,1],label='True Human');axs[2].plot(tf,z['estimated'][:,3],label='Causal estimate');axs[2].plot(tf,z['rv'][:,1],ls='--',label='Issued reference');axs[2].set_ylim(-10,6)
tr=np.load(root/'source/results'/ids[-1]/'trace.npz');ix=tr['stage']=='TASK'
for key,label in [('robot_torque_component_position_nm','position'),('robot_torque_component_velocity_nm','velocity'),('robot_torque_component_allocator_nm','allocator')]:axs[3].plot(tf,np.linalg.norm(tr[key][ix],axis=1),label=label)
for ax,label in zip(axs,['Knee q (deg)','Knee position error (deg)','Knee dq (deg/s)','Torque component norm (Nm)']):ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(16.2,18.1);ax.legend(loc='best',ncol=3,fontsize=8)
axs[-1].set_xlabel('Task time (s); torque norms do not imply additive magnitudes or causal mediation');fig.suptitle('Early RETURN: causal estimate versus truth during terminal undershoot');fig.savefig(P/'figures/terminal_estimate_tracking.png',dpi=150);plt.close(fig)
for f in [P/'derived/TERMINAL_ESTIMATE_AND_COMPENSATION.json',P/'figures/terminal_estimate_tracking.png']:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(dict(status='PASS',ER_excursion=rows[-1]['excursion_decomposition'],ER_snapshots=[{k:x[k] for k in ['event','sampled_task_s','actual_tracking_deg','estimated_tracking_deg','estimation_error_deg_deg_s']} for x in rows[-1]['snapshots']])),flush=True)
