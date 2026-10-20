from pathlib import Path
import os,json,time,sys,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
sp=importlib.util.spec_from_file_location('independent_raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
rows=read('EXPERIMENT_RESULTS.json')['rows'];M={r['id']:r for r in rows}
if 'repair_ER110_R4_120' not in M:raise SystemExit('Bounded repair not yet measured')
a='repair_ER110_R4_120';b='W1dev_ER110';ra=M[a];rb=M[b];za=np.load(P/'motion_series'/(a+'.npz'));zb=np.load(P/'motion_series'/(b+'.npz'));tr=np.load(P/'source/results'/a/'trace.npz');origin=float(tr['time_s'][tr['stage']=='TASK'][0]);cut=next(e['splice'] for e in ra['events'] if e['early'] and e['early']['slot']==4);ix=za['time_s']<=origin+cut+1e-9
prefix={k:bool(np.array_equal(za[k][ix],zb[k][ix])) for k in ['time_s','true_q_rad','true_dq_rad_s','acceleration_rad_s2']};assert all(prefix.values()),prefix
native_count=0;bad=[]
for x,y in zip(raw.array_items(P/'source/results'/a/'runtime_artifacts.json.gz','native_states_evaluation_only'),raw.array_items(P/'source/results'/b/'runtime_artifacts.json.gz','native_states_evaluation_only')):
 if x['time_s']>origin+cut+1e-9:break
 native_count+=1
 for key in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']:
  if x.get(key)!=y.get(key):bad.append(dict(index=native_count,key=key))
assert not bad,bad[:10]
records=[]
def finite_norm_peak(x):
 y=np.linalg.norm(x,axis=1);y=y[np.isfinite(y)]
 return None if not len(y) else float(y.max())
def finite_maxabs(x):
 return [None if not np.any(np.isfinite(x[:,j])) else float(np.max(abs(x[np.isfinite(x[:,j]),j]))) for j in range(x.shape[1])]
for ident in ['W1dev_D','W1dev_ER110','W1dev_ER120',a]:
 r=M[ident];z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';tf=tr['time_s'][ix]-origin;t=z['time_s']-origin;su=read('source/results/'+ident+'/summary.json');learning=[x for x in su['learning_records'] if su['decisions'][x['decision_index']]['phase']=='RETURN'];d=su['decisions'][learning[-1]['decision_index']];request=d['decision_request_time_s']-origin;native=t>=request-1e-8;sample=tf>=request-1e-8
 records.append(dict(id=ident,terminal_request_task_s=float(request),terminal_and_rest_of_task_acceleration_max_deg_s2=np.max(abs(np.rad2deg(z['acceleration_rad_s2'][native])),axis=0).tolist(),terminal_and_rest_of_task_jerk_RMS_deg_s3=np.sqrt(np.mean(np.rad2deg(z['jerk_rad_s3'][native])**2,axis=0)).tolist(),terminal_allocator_torque_norm_peak_Nm=finite_norm_peak(tr['robot_torque_component_allocator_nm'][ix][sample]),terminal_command_torque_norm_peak_Nm=finite_norm_peak(tr['cr12_actuator_command_nm'][ix][sample]),terminal_reference_velocity_max_deg_s=finite_maxabs(np.rad2deg(tr['reference_dq_rad_s'][ix][sample])),sampled_command_finite_rows=int(np.sum(np.all(np.isfinite(tr['cr12_actuator_command_nm'][ix][sample]),axis=1))),missing_values_are_null=True))
out=dict(status='PASS',unix=time.time(),conditional_added_factor_comparison=dict(new=a,baseline=b,added_factor='RETURN4 duration x1.20, same earlier ER110 policy',shared_actual_prefix_through_task_s=float(cut),native_rows_exact=native_count,native_fields_exact=not bad,task_native_prefix_exact=prefix,cross_cold_parent_full_address_space_hash_equal_claimed=False,scope='cold runs reproduce identical actual native/reference history until added factor; complete address-space equality asserted within each paired parent only'),terminal_windows=records,interpretation='paired policies causally alter reference and actual Human response; allocator/command temporal associations do not uniquely identify a mediator; moving a request is not by itself repair')
put('derived/CAUSAL_RESPONSE_AUDIT.json',out)
fig,ax=plt.subplots(7,1,figsize=(14,17),sharex=True,layout='constrained')
for ident,co in [('W1dev_D','#d55e00'),('W1dev_ER110','#0072b2'),(a,'#009e73')]:
 r=M[ident];z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';t=z['time_s']-origin;tf=tr['time_s'][ix]-origin;v=np.rad2deg(z['true_dq_rad_s'][:,1]);aa=np.rad2deg(z['acceleration_rad_s2'][:,1]);q=np.rad2deg(z['true_q_rad'][:,1]);limit=M['W1dev_B']['complete_metrics']['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]*1.1
 ax[0].plot(t,v,c=co,label=ident);ax[0].plot(tf,np.rad2deg(tr['reference_dq_rad_s'][ix,1]),c=co,ls='--',alpha=.5);ax[1].plot(t,aa,c=co);ax[1].plot(tf,np.rad2deg(tr['reference_ddq_rad_s2'][ix,1]),c=co,ls='--',alpha=.5);ax[2].plot(t,np.cumsum(abs(aa)>limit),c=co);ax[3].plot(t,np.maximum.accumulate(q)-np.minimum.accumulate(q),c=co);ax[4].plot(tf,np.linalg.norm(tr['physical_cuff_force_world_n'][ix],axis=1),c=co);ax[5].plot(tf,np.linalg.norm(tr['robot_torque_component_allocator_nm'][ix],axis=1),c=co);ax[6].plot(tf,np.linalg.norm(np.rad2deg(tr['estimated_human_state_rad_rad_s'][ix,:2]-tr['reference_q_rad'][ix]),axis=1),c=co)
ax[1].set_ylim(-55,70);ax[2].axhline(np.ceil(.05*(len(z['time_s'])+400)),c='r',ls=':');ax[3].axhline(M['W1dev_B']['complete_metrics']['dose']['excursion_deg'][1]+.5,c='r',ls=':');ax[3].set_ylim(110.5,112.0)
for axis,label in zip(ax,['Knee dq actual/ref deg/s','Knee a actual/ref deg/s²\nzoom; D267 peak clipped','Cumulative high a samples','Cumulative knee excursion deg','Force N','Allocator torque norm Nm','Deployable tracking norm deg']):axis.set_ylabel(label);axis.set_xlim(14.8,18.0);axis.grid(alpha=.2);axis.axvline(cut,c='#009e73',ls=':')
ax[0].legend(fontsize=8,ncol=3);ax[-1].set_xlabel('Task seconds; dotted green = bounded RETURN4 splice, red = full matched-B diagnostic bounds');fig.suptitle('Remaining deceleration burden and one added bounded repair — physical native response')
fig.savefig(P/'figures/RETURN_deceleration_zoom.png',dpi=150);plt.close(fig)
print(json.dumps(dict(status='PASS',prefix=out['conditional_added_factor_comparison'],terminal=records)),flush=True)
