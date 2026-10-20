from research_common import *
from scipy.signal import savgol_filter

def analyze(base,ident):
 budget();p=base/'source/results'/ident
 z,ix,quality=unique_trace(p/'trace.npz');t=z['time_s'][ix];truth=z['evaluation_only_human_state_rad_rad_s'][ix]
 # Mapping is empirically verified against the trace at all common physical nodes.
 rows=[]
 for r in array_items(p/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  if t[0]-1e-9<=r['time_s']<=t[-1]+1e-9:rows.append((r['time_s'],r['qpos_evaluation_only'],r['qvel_evaluation_only']))
 nt=np.array([r[0] for r in rows]);nq=np.array([r[1] for r in rows]);nv=np.array([r[2] for r in rows])
 assert len(nt)>2 and np.all(np.diff(nt)>0)
 match=np.searchsorted(nt,t);match=np.clip(match,0,len(nt)-1)
 left=np.maximum(match-1,0);match=np.where(abs(nt[left]-t)<abs(nt[match]-t),left,match)
 close=abs(nt[match]-t)<1e-8
 errors_q=np.max(abs(nq[match[close],:,None]-truth[close,None,:2]),axis=0)
 errors_v=np.max(abs(nv[match[close],:,None]-truth[close,None,2:]),axis=0)
 qi=np.argmin(errors_q,axis=0);vi=np.argmin(errors_v,axis=0)
 assert np.max(errors_q[qi,np.arange(2)])<1e-8 and np.max(errors_v[vi,np.arange(2)])<1e-8,'UNVERIFIED_HUMAN_MAPPING'
 q=nq[:,qi];v=nv[:,vi];dt=np.median(np.diff(nt))
 quality.update(native_samples=len(nt),native_dt_min_s=np.min(np.diff(nt)),native_dt_max_s=np.max(np.diff(nt)),qpos_indices=qi,qvel_indices=vi,mapping_max_error_rad=np.max(errors_q[qi,np.arange(2)]),mapping_max_error_rad_s=np.max(errors_v[vi,np.arange(2)]),common_verified_nodes=int(close.sum()))
 # Phase labels are observations from the original trace, right-continuous at boundaries.
 ni=np.clip(np.searchsorted(t,nt,side='right')-1,0,len(t)-1);phase=z['task_phase'][ix][ni]
 force=z['physical_cuff_force_world_n'][ix];moment=z['physical_cuff_moment_world_nm'][ix];f=np.linalg.norm(force,axis=1);m=np.linalg.norm(moment,axis=1)
 ff=np.gradient(force,t,axis=0,edge_order=2);fr=np.gradient(f,t,edge_order=2)
 err=np.rad2deg(truth[:,:2]-z['reference_q_rad'][ix]);rv=z['reference_dq_rad_s'][ix];ra=z['reference_ddq_rad_s2'][ix]
 out={'id':ident,'sources':{str(p/'trace.npz'):sha(p/'trace.npz'),str(p/'runtime_artifacts.json.gz'):sha(p/'runtime_artifacts.json.gz')},'quality':quality,'actual_human':{},'reference':{'velocity_deg_s':stats(np.rad2deg(rv)),'acceleration_deg_s2':stats(np.rad2deg(ra)),'jerk_deg_s3':stats(np.rad2deg(np.gradient(ra,t,axis=0,edge_order=2)))},'control_command':{'robot_actuator_torque_Nm':stats(z['cr12_actuator_command_nm'][ix]),'applied_human_generalized_action_Nm':stats(z['applied_generalized_action_nm'][ix])},'contact':{'force_N':stats(f),'force_vector_rate_N_s':stats(np.linalg.norm(ff,axis=1)),'force_magnitude_rate_N_s':stats(fr),'force_integral_N_s':np.sum(z['interval_force_cost_n_s'][ix]),'moment_Nm':stats(m),'moment_integral_left_Nm_s':np.sum(m[:-1]*np.diff(t))},'tracking_true_reference_deg':stats(err),'tracking_RMS_deg':np.sqrt(np.mean(err**2,axis=0)),'clearance':{'session_min_m':np.min(z['session_shank_clearance_m'][ix]),'measured_sleeve_min_m':np.min(z['dev_d_measured_sleeve_gap_m'][ix])},'shank_representative_point':'NOT_EVALUABLE: raw native arrays do not contain a true shank marker/geometry contract. Robot cuff signals are not relabeled human shank.','physical_cuff':{'velocity_m_s':stats(np.linalg.norm(z['physical_cuff_linear_velocity_world_m_s'][ix],axis=1)),'acceleration_m_s2':stats(np.linalg.norm(np.gradient(z['physical_cuff_linear_velocity_world_m_s'][ix],t,axis=0,edge_order=2),axis=1))},'windows':[]}
 for window in [0,5,21]:
  vv=v if not window else savgol_filter(v,window,3,axis=0,mode='interp')
  a=np.gradient(vv,nt,axis=0,edge_order=2);j=np.gradient(a,nt,axis=0,edge_order=2)
  signals={'velocity_deg_s':np.rad2deg(vv),'acceleration_deg_s2':np.rad2deg(a),'jerk_deg_s3':np.rad2deg(j)}
  label='raw' if not window else 'savgol_'+str(window)
  out['actual_human'][label]={'window_nominal_s':window*dt,'full':{k:stats(b) for k,b in signals.items()},'phases':{ph:{k:stats(b[phase==ph]) for k,b in signals.items()} for ph in ['OUTBOUND','HOLD','RETURN']}}
  if not window:
   out['actual_human'][label]['angle_excursion_deg']=np.rad2deg(np.ptp(q,axis=0))
   out['actual_human'][label]['duration_s']=nt[-1]-nt[0]
   out['actual_human'][label]['peak_events']={k:[{'joint':d,'time_s':float(nt[idx]),'value':float(b[idx,d]),'phase':str(phase[idx]),'within_1ms_edge':bool(idx<4 or idx>=len(nt)-4)} for d in range(2) for idx in np.argsort(abs(b[:,d]))[-5:][::-1]] for k,b in signals.items()}
   raw=signals
   np.savez_compressed(OUT/'motion_series'/f'{base.name}_{ident}.npz',time_s=nt,true_q_rad=q,true_dq_rad_s=v,derived_ddq_rad_s2=a,derived_jerk_rad_s3=j,phase=phase)
 summary=load(p/'summary.json');events=[]
 for r in summary['task']['phase_transitions']:
  if t[0]-.1<=r['time_s']<=t[-1]+.1:events.append(('PHASE_'+r['to'],r['time_s'],.1))
 ep=base/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
 if ep.exists():
  for r in load(ep)['rows']:
   if r['physically_executed_nonzero']:
    for receipt in r['actual_command_receipts']:
     for k in ['start_physics_s','end_physics_s']:events.append(('PLAN_'+str(r['request_id'])+'_'+k,receipt[k],.05))
 # Zero-crossing detector is a descriptive event rule, not a burden threshold.
 for d in range(2):
  cross=np.flatnonzero(v[:-1,d]*v[1:,d]<0)
  for idx in cross:
   lo=max(0,idx-int(.02/dt));hi=min(len(v),idx+int(.02/dt)+1)
   if np.max(abs(np.rad2deg(v[lo:hi,d])))>=.5:events.append(('REVERSAL_JOINT_'+str(d),nt[idx],.02))
 seen=set()
 for typ,at,half in events:
  key=(typ,round(at,7))
  if key in seen:continue
  seen.add(key);mask=abs(nt-at)<=half;fm=abs(t-at)<=half
  if not mask.any():continue
  out['windows'].append({'kind':typ,'center_s':at,'half_width_s':half,'actual_human':{k:stats(b[mask]) for k,b in raw.items()},'force_N':stats(f[fm]),'force_rate_N_s':stats(fr[fm]),'moment_Nm':stats(m[fm]),'tracking_deg':stats(err[fm]),'measured_clearance_min_m':np.min(z['dev_d_measured_sleeve_gap_m'][ix][fm]) if fm.any() else None})
 axis=load(base/'reports'/(ident+'_AXES.json'));out['native_safety']=axis['metric']['physical_audit'];out['native_J_F_N_s']=axis['metric']['J_F'];out['native_force_peak_N']=axis['metric']['force_peak'];out['native_moment_integral_Nm_s']=axis['metric']['moment_integral'];out['native_moment_peak_Nm']=axis['metric']['moment_peak'];out['native_phase_durations']=axis['metric']['phase_durations']
 return out

def main():
 (OUT/'motion_series').mkdir(exist_ok=True);runs=[];pairs=[]
 for pkg in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1']:
  base=ROOT/pkg
  for pair in load(base/'PAIRED_RESULTS.json')['pairs']:
   assert pair['status']=='VALID_PAIR'
   br=analyze(base,pair['B_id']);mr=analyze(base,pair['M2_id']);runs.extend([br,mr])
   deltas={}
   for filt in br['actual_human']:
    deltas[filt]={k:{metric:np.asarray(mr['actual_human'][filt]['full'][k][metric])-br['actual_human'][filt]['full'][k][metric] for metric in ['max_abs','p95_abs','p99_abs','rms']} for k in ['velocity_deg_s','acceleration_deg_s2','jerk_deg_s3']}
   pairs.append({'package':pkg,'B_id':br['id'],'M2_id':mr['id'],'motion_deltas_M2_minus_B':deltas,'J_F_delta_N_s':mr['native_J_F_N_s']-br['native_J_F_N_s'],'moment_integral_delta_Nm_s':mr['native_moment_integral_Nm_s']-br['native_moment_integral_Nm_s'],'tracking_RMS_delta_deg':mr['tracking_RMS_deg']-br['tracking_RMS_deg'],'angle_excursion_delta_deg':mr['actual_human']['raw']['angle_excursion_deg']-br['actual_human']['raw']['angle_excursion_deg'],'duration_delta_s':mr['actual_human']['raw']['duration_s']-br['actual_human']['raw']['duration_s']})
   save('motion_series/'+pkg+'_'+br['id']+'_AUDIT.json',br);save('motion_series/'+pkg+'_'+mr['id']+'_AUDIT.json',mr)
   print('MOTION_PAIR',pkg,br['id'],json.dumps({k:{a:np.asarray(v).tolist() for a,v in x.items()} for k,x in deltas['raw'].items()}),flush=True)
 save('MOTION_BURDEN_AUDIT.json',{'status':'SUPPORTED descriptive native-motion comparison; acceptance UNRESOLVED','protocol_sha256':sha(OUT/'PREREGISTERED_PROTOCOL.json'),'pairs':pairs,'run_audit_files':[str(OUT/'motion_series'/f'{p}_{r}_AUDIT.json') for p in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1'] for r in [a['id'] for a in runs] if (OUT/'motion_series'/f'{p}_{r}_AUDIT.json').exists()],'sampling_limit':'Motion from dense native states; contact, reference and tracking from sensor/evaluation trace. Derivatives are finite-difference outcomes, no clinical inference.','shank_kinematics_status':'NOT_EVALUABLE'})
if __name__=='__main__':main()
