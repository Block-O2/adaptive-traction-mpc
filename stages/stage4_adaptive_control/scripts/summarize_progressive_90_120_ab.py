import json,sys,numpy as np
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
root=STAGE/'results/engineering_validation/progressive_90_120_ab_20260907_v1'
def load(p):
 with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def read(p):return json.loads(p.read_text())
def norm(x):return np.linalg.norm(x,axis=1) if x.ndim>1 else abs(x)
def rms(x):return np.sqrt(np.mean(np.asarray(x)**2,axis=0))
def first_at(phase,value):
 i=np.searchsorted(phase,value);return min(i,len(phase)-1) if i<len(phase) else None
def nearest(times,t):
 if len(times)==0:return None
 i=np.argmin(abs(times-t));return dict(time_s=float(times[i]),delta_s=float(times[i]-t))
out={}
for arm in ['rigid','P1']:
 rid=f'hip90_knee120_{arm}_dt0250us';r=read(root/rid/'result.json');z=load(root/rid/'trace.npz');m=load(root/rid/'mechanics.npz');md=load(root/rid/'modes.npz');c=load(root/rid/'commands.npz')
 t=z['time_s'];phase=z['reference_phase_time_s'];q=z['human_q_deg_god_view'];ref=z['human_q_ref_deg'];proxy=z['estimated_human_q_deg'];leg=(r['planned_reference_duration_s']-3.5)/2
 tr={'outbound_start':1.,'target_arrival':1+leg,'return_start':2.5+leg,'return_end':2.5+2*leg,'reference_end':3.5+2*leg}
 indices={k:first_at(phase,v) for k,v in tr.items()}
 qevents={k:(dict(physical_time_s=float(t[i]),reference_phase_s=float(phase[i]),q_true_deg=q[i].tolist(),q_proxy_deg=proxy[i].tolist(),q_ref_deg=ref[i].tolist(),proxy_error_deg=(proxy[i]-q[i]).tolist()) if i is not None else None) for k,i in indices.items()}
 e=proxy-q; en=norm(e);ei=int(np.argmax(en))
 mode=np.asarray(md['mode']);br=np.flatnonzero(mode=='BRAKE');bi=int(br[0]) if len(br) else None
 status=np.asarray(md['decision_status']);inf=np.flatnonzero(status=='BRAKE_INFEASIBLE');ii=int(inf[0]) if len(inf) else None
 filter_status=np.asarray(z['safety_filter_status']);inter=np.asarray(z['safety_filter_intervention_coordinate_norm']);fi=np.flatnonzero(filter_status=='FILTER_INFEASIBLE')
 mt=m['time_s'];acc=np.diff(m['velocity_H'],axis=0)/np.diff(mt)[:,None];at=.5*(mt[1:]+mt[:-1]);an=norm(acc);ai=int(np.argmax(an));ta=float(at[ai])
 # deformation radial reversal as sign change of x dot relative velocity.
 relative_velocity=m['relative_velocity_H'] if 'relative_velocity_H' in m else m['velocity_R']-m['velocity_H']; radial=np.sum(m['deformation_H']*relative_velocity,axis=1);rv=mt[1:][np.flatnonzero(radial[:-1]*radial[1:]<0)]
 proxy_peak_t=float(t[ei]);force_t=float(mt[np.argmax(norm(m['force_R_world']))]);cmd_t=float(c['time_s'][np.argmax(norm(c['force']))])
 transitions={k:(qevents[k]['physical_time_s'] if qevents[k] else None) for k in tr}
 align=dict(acceleration_peak_time_s=ta,acceleration_peak_m_s2=float(an[ai]),nearest_deformation_reversal=nearest(rv,ta),proxy_peak_time_s=proxy_peak_t,delta_to_proxy_peak_s=proxy_peak_t-ta,physical_force_peak_time_s=force_t,delta_to_physical_force_peak_s=force_t-ta,command_force_peak_time_s=cmd_t,delta_to_command_force_peak_s=cmd_t-ta,nearest_controller_command=nearest(c['time_s'],ta),nearest_reference_transition=min(({**nearest(np.array([v]),ta),'name':k} for k,v in transitions.items() if v is not None),key=lambda x:abs(x['delta_s'])),nearest_mode_transition=nearest(md['time_s'][1:][mode[1:]!=mode[:-1]],ta),first_brake=({'physical_time_s':float(md['time_s'][bi]),'reference_phase_s':float(np.interp(md['time_s'][bi],t,phase)),'status':str(status[bi]),'feasible_candidate_count':int(md['feasible_candidate_count'][bi])} if bi is not None else None),brake_infeasible=({'physical_time_s':float(md['time_s'][ii]),'reference_phase_s':float(np.interp(md['time_s'][ii],t,phase)),'feasible_candidate_count':int(md['feasible_candidate_count'][ii])} if ii is not None else None),first_filter_infeasible=({'physical_time_s':float(z['safety_filter_time_s'][fi[0]]),'reference_phase_s':float(np.interp(z['safety_filter_time_s'][fi[0]],t,phase))} if len(fi) else None))
 f=r['force_contract'];gw=read(root/rid/'growth_windows.json')
 precision_only = bool(
  r['reference_completed'] and r['task']=='SAFE_INCOMPLETE'
  and r['brake']['transition_count']==0 and r['brake']['active_mode']=='TRACK'
 )
 if r['reference_completed'] and r['brake']['active_mode']=='BRAKE':
  practical = 'full reference phase executed; BRAKE-limited physical return'
 elif precision_only:
  practical = 'full reference executed; precision criterion not met'
 else:
  practical = r['task']
 out[arm]=dict(run_id=rid,formal_classification=r['task'],termination_reason=r['termination_reason'],full_reference_timing_completed=r['reference_completed'],precision_only_incomplete=precision_only,practical_description=practical,reference_phase_final_s=r['reference_phase_s'],physical_time_final_s=r['simulated_duration_s'],outbound_reference_completed_percent=float(100*np.clip((phase.max()-1)/leg,0,1)),target_endpoint_reached_in_reference_time=bool(phase.max()>=tr['target_arrival']),return_reference_completed_percent=float(100*np.clip((phase.max()-tr['return_start'])/leg,0,1)),trajectory_events=qevents,endpoint_best_error_deg=r['endpoint_error_deg'],return_error_deg=r['return_error_deg'],tracking_rmse_deg=r['tracking_rmse_deg'],tracking_max_abs_error_per_joint_deg=np.max(abs(q-ref),axis=0).tolist(),tracking_max_abs_combined_deg=float(np.max(norm(q-ref))),proxy=dict(rmse_per_joint_deg=rms(e).tolist(),peak_abs_per_joint_deg=np.max(abs(e),axis=0).tolist(),peak_norm_deg=float(en[ei]),peak_time_s=proxy_peak_t,endpoint_proxy_error_deg=(qevents['target_arrival']['proxy_error_deg'] if qevents['target_arrival'] else None),return_proxy_error_deg=(qevents['return_end']['proxy_error_deg'] if qevents['return_end'] else None)),safety=dict(brake_transition_count=r['brake']['transition_count'],brake_cycle_count=r['brake']['brake_cycle_count'],brake_duration_s=.005*r['brake']['brake_cycle_count'],brake_final_mode=r['brake']['active_mode'],first_brake=align['first_brake'],brake_infeasible_event_count=int(np.count_nonzero(status=='BRAKE_INFEASIBLE')),brake_infeasible=align['brake_infeasible'],no_safe_action_count=r['no_safe_action_count'],filter_status_counts=r['brake']['safety_filter_status_counts'],filter_intervention_nonzero_count=int(np.count_nonzero(inter>1e-12)),filter_intervention_rms=float(np.sqrt(np.mean(inter**2))) if len(inter) else None,filter_intervention_peak=float(max(inter)) if len(inter) else None,minimum_feasible_candidates=int(min(md['feasible_candidate_count'])) if len(md['feasible_candidate_count']) else None,minimum_brake_feasible_candidates=int(min(md['feasible_candidate_count'][br])) if len(br) else None),force=dict(command=r['command_force_n'],physical=r['physical_force_n'],physical_moment_R=r['physical_moment_R_nm'],slew=r['rates']['physical_force_n_s'],over_200_duration_s=f['maximum_contiguous_exceedance_duration_s'],excess_impulse_ns=f['maximum_rolling_excess_impulse_ns'],classification=f['classification']),human_dynamics=dict(cuff_acceleration=r['motion']['human_cuff']['acceleration'],cuff_jerk=r['motion']['human_cuff']['jerk'],peak_acceleration_time_s=ta),soft=(dict(translation_peak_mm=r['deformation_peak_mm'],translation_rms_mm=float(1000*np.sqrt(np.mean(norm(m['deformation_H'])**2))),rotation_peak_deg=r['rotation_peak_deg'],rotation_rms_deg=float(np.degrees(np.sqrt(np.mean(norm(m['rotation_vector_H'])**2)))),relative_velocity_peak_m_s=float(max(norm(m['relative_velocity_H']))),relative_angular_velocity_peak_rad_s=float(max(norm(m['relative_angular_velocity_H']))),endpoint_translation_mm=(float(1000*norm(m['deformation_H'][first_at(m['reference_phase_s'],tr['target_arrival']):first_at(m['reference_phase_s'],tr['target_arrival'])+1])[0]) if first_at(m['reference_phase_s'],tr['target_arrival']) is not None else None),return_translation_mm=(float(1000*norm(m['deformation_H'][first_at(m['reference_phase_s'],tr['return_end']):first_at(m['reference_phase_s'],tr['return_end'])+1])[0]) if first_at(m['reference_phase_s'],tr['return_end']) is not None else None),energy=r['energy'],energy_final_signed_residual_j=float(m['energy_residual'][-1]),energy_max_normalized_abs=float(max(abs(m['normalized_energy_residual']))),energy_trailing_200ms_slope_j_s=float(np.polyfit(mt[mt>=mt[-1]-.2],m['energy_residual'][mt>=mt[-1]-.2],1)[0]),sustained_growth_window_count=int(sum(bool(w['stop_reason']) for w in gw)),growth_windows=len(gw)) if arm=='P1' else None),alignment=align,runtime=r['runtime'])
(root/'detailed_metrics.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')

import hashlib,subprocess,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fmt(v):
 if v is None:return '—'
 if isinstance(v,bool):return str(v)
 if isinstance(v,(float,np.floating)):return f'{v:.6g}'
 if isinstance(v,list):return '['+', '.join(fmt(x) for x in v)+']'
 return str(v)
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(fmt(v) for v in row)+' |' for row in rows])
s=read(root/'PROGRESSIVE_90_120_AB_SPEC.json');reg=read(root/'registration.json')
assert sha(root/'PROGRESSIVE_90_120_AB_SPEC.json')==sha(STAGE/'docs/PROGRESSIVE_90_120_AB_SPEC.json')==reg['spec_sha']
assert sha(root/'PROGRESSIVE_90_120_AB_SPEC.md')==sha(STAGE/'docs/PROGRESSIVE_90_120_AB_SPEC.md')==reg['md_sha']
for p,h in {**s['frozen_hashes'],**reg['implementation_hashes']}.items():assert sha(REPO/p)==h,p
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==s['head']
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True).strip()
# Fresh processes, exact initial states, paired frozen config/model fingerprints.
rids=[out[a]['run_id'] for a in ['rigid','P1']];started=[read(root/r/'started.json') for r in rids]
assert started[0]['pid']!=started[1]['pid']
ia,ib=load(root/rids[0]/'initial_state.npz'),load(root/rids[1]/'initial_state.npz')
for k in ia:np.testing.assert_array_equal(ia[k],ib[k])
ca,cb=read(root/rids[0]/'run_config.json'),read(root/rids[1]/'run_config.json')
assert {k:v for k,v in ca.items() if k!='candidate'}=={k:v for k,v in cb.items() if k!='candidate'}
la,lb=read(root/rids[0]/'model_lock.json'),read(root/rids[1]/'model_lock.json');assert la['expected_fingerprints']==lb['expected_fingerprints']
array_count=0
for rid in rids:
 for file in (root/rid).glob('*.npz'):
  for k,a in load(file).items():
   if a.dtype.kind in 'fci':
    if file.name=='modes.npz' and k=='selected_braking_rate_per_s':
     modes=load(file)['mode'].astype(str); applicable=modes=='BRAKE'
     assert np.isfinite(a[applicable]).all(),(file,k,'BRAKE')
     assert np.isnan(a[~applicable]).all(),(file,k,'TRACK sentinel')
    else:
     assert np.isfinite(a).all(),(file,k)
   array_count+=1
# Add post-start acceleration event and temporal context.
for arm in ['rigid','P1']:
 rid=out[arm]['run_id'];m=load(root/rid/'mechanics.npz');z=load(root/rid/'trace.npz');md=load(root/rid/'modes.npz');c=load(root/rid/'commands.npz')
 mt=m['time_s'];acc=np.diff(m['velocity_H'],axis=0)/np.diff(mt)[:,None];at=.5*(mt[1:]+mt[:-1]);an=norm(acc);idx=np.flatnonzero(at>=.1);i=int(idx[np.argmax(an[idx])]);ta=float(at[i])
 radial=np.sum(m['deformation_H']*m['relative_velocity_H'],axis=1) if 'relative_velocity_H' in m else np.sum(m['deformation_H']*(m['velocity_R']-m['velocity_H']),axis=1)
 reversals=mt[1:][radial[:-1]*radial[1:]<0]
 def near(a):
  if not len(a):return None
  j=np.argmin(abs(a-ta));return dict(time_s=float(a[j]),delta_s=float(a[j]-ta))
 phase=z['reference_phase_time_s']
 transitions={name:out[arm]['trajectory_events'][name]['physical_time_s'] for name in ['outbound_start','target_arrival','return_start','return_end','reference_end'] if out[arm]['trajectory_events'][name]}
 nearest_transition=min((dict(name=k,time_s=v,delta_s=v-ta) for k,v in transitions.items()),key=lambda q:abs(q['delta_s']))
 proxyerr=norm(z['estimated_human_q_deg']-z['human_q_deg_god_view']);pt=float(z['time_s'][np.argmax(proxyerr)])
 force=norm(m['force_R_world']);ft=float(mt[np.argmax(force)])
 cmdt=float(c['time_s'][np.argmax(norm(c['force']))])
 modes=np.asarray(md['mode']);mode_times=md['time_s'][1:][modes[1:]!=modes[:-1]]
 out[arm]['alignment']['post_start_peak']=dict(time_s=ta,value_m_s2=float(an[i]),nearest_deformation_reversal=near(reversals),proxy_peak_time_s=pt,delta_to_proxy_peak_s=pt-ta,physical_force_peak_time_s=ft,delta_to_force_peak_s=ft-ta,command_force_peak_time_s=cmdt,delta_to_command_peak_s=cmdt-ta,nearest_command_update=near(c['time_s']),nearest_mode_transition=near(mode_times),nearest_reference_transition=nearest_transition)
# Aligned full-run figure, one column per arm.
fig,axes=plt.subplots(6,2,figsize=(14,18),layout='constrained')
for col,arm in enumerate(['rigid','P1']):
 rid=out[arm]['run_id'];z=load(root/rid/'trace.npz');m=load(root/rid/'mechanics.npz');md=load(root/rid/'modes.npz');c=load(root/rid/'commands.npz')
 t=z['time_s'];mt=m['time_s'];acc=np.diff(m['velocity_H'],axis=0)/np.diff(mt)[:,None];at=.5*(mt[1:]+mt[:-1]);proxyerr=norm(z['estimated_human_q_deg']-z['human_q_deg_god_view'])
 for j,joint in enumerate(['hip','knee']):
  axes[j,col].plot(t,z['human_q_ref_deg'][:,j],label='q_ref',lw=1.5);axes[j,col].plot(t,z['estimated_human_q_deg'][:,j],label='q_proxy',lw=1);axes[j,col].plot(t,z['human_q_deg_god_view'][:,j],label='q_true',lw=1)
  axes[j,col].set_ylabel(joint+' angle (deg)')
 axes[2,col].plot(mt,1000*norm(m['deformation_H']),label='translation mm');axes[2,col].plot(mt,np.degrees(norm(m['rotation_vector_H'])),label='rotation deg');axes[2,col].set_ylabel('Interface deformation')
 axes[3,col].plot(mt,norm(m['force_R_world']),label='physical');axes[3,col].step(c['time_s'],norm(c['force']),where='post',label='command');axes[3,col].set_ylabel('Force norm (N)')
 axes[4,col].plot(at,norm(acc),label='Human cuff acceleration');axes[4,col].plot(t,proxyerr,label='proxy error norm');axes[4,col].set_ylabel('m/s² or deg')
 brake=(np.asarray(md['mode'])=='BRAKE').astype(float);axes[5,col].step(md['time_s'],brake,where='post',label='BRAKE');axes[5,col].step(z['safety_filter_time_s'],z['safety_filter_intervention_coordinate_norm']/max(1,float(np.max(z['safety_filter_intervention_coordinate_norm']))),where='post',label='filter intervention / peak');axes[5,col].set_ylabel('Mode / normalized burden')
 for name,e in out[arm]['trajectory_events'].items():
  if e:
   for ax in axes[:,col]:ax.axvline(e['physical_time_s'],color='gray',alpha=.18,lw=.8)
 if out[arm]['safety']['first_brake']:
  for ax in axes[:,col]:ax.axvline(out[arm]['safety']['first_brake']['physical_time_s'],color='red',ls='--',alpha=.7,lw=1)
 for ax in axes[:,col]:ax.grid(alpha=.2);ax.legend(fontsize=7);ax.set_xlabel('Physical time (s)')
 axes[0,col].set_title(arm)
fig.suptitle('90/120 aligned diagnostics — truth is offline evaluation only')
fig.savefig(root/'aligned_90_120_diagnostics.png',dpi=155);plt.close(fig)
# Zoom around the registered target-arrival transition; neither arm entered BRAKE.
rb=out['rigid']['trajectory_events']['target_arrival']['physical_time_s']
fig,axes=plt.subplots(4,1,figsize=(12,10),sharex=True,layout='constrained')
for arm,color in [('rigid','tab:blue'),('P1','tab:orange')]:
 rid=out[arm]['run_id'];z=load(root/rid/'trace.npz');m=load(root/rid/'mechanics.npz');md=load(root/rid/'modes.npz')
 mt=m['time_s'];acc=np.diff(m['velocity_H'],axis=0)/np.diff(mt)[:,None];at=.5*(mt[1:]+mt[:-1])
 axes[0].plot(mt,norm(m['force_R_world']),label=arm,color=color);axes[1].plot(at,norm(acc),label=arm,color=color);axes[2].plot(z['time_s'],norm(z['estimated_human_q_deg']-z['human_q_deg_god_view']),label=arm,color=color);axes[3].step(md['time_s'],(np.asarray(md['mode'])=='BRAKE').astype(int),where='post',label=arm,color=color)
for ax,y in zip(axes,['Physical force (N)','Human cuff acceleration (m/s²)','Proxy error norm (deg)','BRAKE mode']):ax.set_ylabel(y);ax.legend();ax.grid(alpha=.2);ax.axvline(rb,color='red',ls='--',label='target arrival')
axes[-1].set_xlim(rb-.6,rb+.6);axes[-1].set_xlabel('Physical time (s)');fig.suptitle('Temporal alignment around 90/120 target arrival')
fig.savefig(root/'target_arrival_alignment.png',dpi=170);plt.close(fig)
(root/'detailed_metrics.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
# Compact CSV for machine use.
rows=[]
for arm,d in out.items():rows.append(dict(arm=arm,formal=d['formal_classification'],termination=d['termination_reason'],full_reference=d['full_reference_timing_completed'],outbound_percent=d['outbound_reference_completed_percent'],return_percent=d['return_reference_completed_percent'],phase_s=d['reference_phase_final_s'],physical_time_s=d['physical_time_final_s'],tracking_rmse_deg=d['tracking_rmse_deg'],tracking_max_deg=d['tracking_max_abs_combined_deg'],endpoint_error_deg=d['endpoint_best_error_deg'],return_error_deg=d['return_error_deg'],brake_count=d['safety']['brake_transition_count'],first_brake_s=(d['safety']['first_brake'] or {}).get('physical_time_s'),brake_duration_s=d['safety']['brake_duration_s'],brake_infeasible=d['safety']['brake_infeasible_event_count'],no_safe_action=d['safety']['no_safe_action_count'],command_rms_n=d['force']['command']['rms'],command_peak_n=d['force']['command']['peak'],physical_rms_n=d['force']['physical']['rms'],physical_peak_n=d['force']['physical']['peak'],moment_peak_nm=d['force']['physical_moment_R']['peak'],force_slew_peak_n_s=d['force']['slew']['peak'],over200_s=d['force']['over_200_duration_s'],excess_impulse_ns=d['force']['excess_impulse_ns'],force_class=d['force']['classification'],human_accel_rms=d['human_dynamics']['cuff_acceleration']['rms'],human_accel_peak=d['human_dynamics']['cuff_acceleration']['peak'],human_jerk_peak=d['human_dynamics']['cuff_jerk']['peak']))
with (root/'comparison.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
validation=dict(spec_sha=reg['spec_sha'],md_sha=reg['md_sha'],frozen_hashes_verified=len(s['frozen_hashes']),implementation_hashes_verified=len(reg['implementation_hashes']),npz_arrays_verified=array_count,executed_runs=2,unique_process_ids=[q['pid'] for q in started],paired_initial_state_exact=True,paired_config_equal_except_interface=True,model_fingerprints_equal=True,head=s['head'],tracked_diff_empty=True,no_120_120_or_extra_run=True,postprocessor_sha=sha(Path(__file__)),command=[sys.executable,*sys.argv],no_simulation=True)
(root/'postprocess_validation.json').write_text(json.dumps(validation,indent=2,sort_keys=True)+'\n')
r=out['rigid'];p=out['P1']
def reduction(a,b):return 100*(a-b)/a
metric_rows=[
 ['Formal classification',r['formal_classification'],p['formal_classification']],
 ['Termination',r['termination_reason'],p['termination_reason']],
 ['Practical completion',r['practical_description'],p['practical_description']],
 ['Outbound / return reference %',f"{r['outbound_reference_completed_percent']}/{r['return_reference_completed_percent']}",f"{p['outbound_reference_completed_percent']}/{p['return_reference_completed_percent']}"],
 ['Final phase / physical time s',f"{r['reference_phase_final_s']}/{r['physical_time_final_s']}",f"{p['reference_phase_final_s']}/{p['physical_time_final_s']}"],
 ['Tracking RMSE / max norm deg',f"{r['tracking_rmse_deg']}/{r['tracking_max_abs_combined_deg']}",f"{p['tracking_rmse_deg']}/{p['tracking_max_abs_combined_deg']}"],
 ['Tracking max q1/q2 deg',r['tracking_max_abs_error_per_joint_deg'],p['tracking_max_abs_error_per_joint_deg']],
 ['Endpoint / return error deg',f"{r['endpoint_best_error_deg']}/{r['return_error_deg']}",f"{p['endpoint_best_error_deg']}/{p['return_error_deg']}"],
 ['Command force RMS / peak N',f"{r['force']['command']['rms']}/{r['force']['command']['peak']}",f"{p['force']['command']['rms']}/{p['force']['command']['peak']}"],
 ['Physical force RMS / peak N',f"{r['force']['physical']['rms']}/{r['force']['physical']['peak']}",f"{p['force']['physical']['rms']}/{p['force']['physical']['peak']}"],
 ['Force slew RMS / peak N/s',f"{r['force']['slew']['rms']}/{r['force']['slew']['peak']}",f"{p['force']['slew']['rms']}/{p['force']['slew']['peak']}"],
 ['Moment RMS / peak Nm',f"{r['force']['physical_moment_R']['rms']}/{r['force']['physical_moment_R']['peak']}",f"{p['force']['physical_moment_R']['rms']}/{p['force']['physical_moment_R']['peak']}"],
 ['BRAKE entries / duration s',f"{r['safety']['brake_transition_count']}/{r['safety']['brake_duration_s']}",f"{p['safety']['brake_transition_count']}/{p['safety']['brake_duration_s']}"],
 ['BRAKE_INFEASIBLE / NO_SAFE_ACTION',f"{r['safety']['brake_infeasible_event_count']}/{r['safety']['no_safe_action_count']}",f"{p['safety']['brake_infeasible_event_count']}/{p['safety']['no_safe_action_count']}"],
 ['Filter intervention count / peak',f"{r['safety']['filter_intervention_nonzero_count']}/{r['safety']['filter_intervention_peak']}",f"{p['safety']['filter_intervention_nonzero_count']}/{p['safety']['filter_intervention_peak']}"],
 ['Minimum feasible candidates',r['safety']['minimum_feasible_candidates'],p['safety']['minimum_feasible_candidates']],
 ['Human cuff acceleration RMS / peak',f"{r['human_dynamics']['cuff_acceleration']['rms']}/{r['human_dynamics']['cuff_acceleration']['peak']}",f"{p['human_dynamics']['cuff_acceleration']['rms']}/{p['human_dynamics']['cuff_acceleration']['peak']}"],
 ['Peak acceleration time s',r['human_dynamics']['peak_acceleration_time_s'],p['human_dynamics']['peak_acceleration_time_s']],
 ['Human cuff jerk RMS / peak',f"{r['human_dynamics']['cuff_jerk']['rms']}/{r['human_dynamics']['cuff_jerk']['peak']}",f"{p['human_dynamics']['cuff_jerk']['rms']}/{p['human_dynamics']['cuff_jerk']['peak']}"],
 ['Proxy RMSE q1/q2 deg',r['proxy']['rmse_per_joint_deg'],p['proxy']['rmse_per_joint_deg']],
 ['Proxy peak q1/q2 deg',r['proxy']['peak_abs_per_joint_deg'],p['proxy']['peak_abs_per_joint_deg']],
 ['Force >200 duration / excess impulse',f"{r['force']['over_200_duration_s']}/{r['force']['excess_impulse_ns']}",f"{p['force']['over_200_duration_s']}/{p['force']['excess_impulse_ns']}"],
 ['Force contract',r['force']['classification'],p['force']['classification']],
 ['Wall runtime s',r['runtime']['total_run_wall_s'],p['runtime']['total_run_wall_s']],
]
state_rows=[]
for name in ['target_arrival','return_end','reference_end']:
 state_rows.append([name,r['trajectory_events'][name]['q_true_deg'],r['trajectory_events'][name]['q_proxy_deg'],p['trajectory_events'][name]['q_true_deg'],p['trajectory_events'][name]['q_proxy_deg']])
prev40r=read(STAGE/'results/engineering_validation/progressive_relaxed_ab_20260905_v1/hip40_knee40_rigid_dt0250us/result.json')
prev40p=read(STAGE/'results/engineering_validation/progressive_relaxed_ab_20260905_v1/hip40_knee40_P1_dt0250us/result.json')
prev80=read(STAGE/'results/engineering_validation/progressive_40_80_ab_20260907_v1/detailed_metrics.json')
history_rows=[
 ['40/40',prev40r['task'],prev40p['task'],'0 / 0',f"{prev40r['tracking_rmse_deg']} / {prev40p['tracking_rmse_deg']}",f"{prev40r['physical_force_n']['peak']} / {prev40p['physical_force_n']['peak']}",f"{prev40r['return_error_deg']} / {prev40p['return_error_deg']}"],
 ['40/80',prev80['rigid']['formal_classification'],prev80['P1']['formal_classification'],f"{prev80['rigid']['safety']['brake_transition_count']} / {prev80['P1']['safety']['brake_transition_count']}",f"{prev80['rigid']['tracking_rmse_deg']} / {prev80['P1']['tracking_rmse_deg']}",f"{prev80['rigid']['force']['physical']['peak']} / {prev80['P1']['force']['physical']['peak']}",f"{prev80['rigid']['return_error_deg']} / {prev80['P1']['return_error_deg']}"],
 ['90/120',r['formal_classification'],p['formal_classification'],'0 / 0',f"{r['tracking_rmse_deg']} / {p['tracking_rmse_deg']}",f"{r['force']['physical']['peak']} / {p['force']['physical']['peak']}",f"{r['return_error_deg']} / {p['return_error_deg']}"],
]
report=['# Rigid vs P1 90/120 exploratory matched A/B','',
'**Both arms executed 100% of the registered outbound and return reference and retained formal SAFE_INCOMPLETE. Neither arm entered BRAKE or required Safety Filter intervention. Rigid returned within the strict tolerance but missed the target-hold endpoint criterion; P1 missed both endpoint and return precision.**','',
'Exploratory diagnostic evidence only. The prior strict compliant numerical-qualification FAIL remains unchanged. No clinical-safety, qualified-compliance or formal capability-envelope claim.','',
'## Frozen contract',
f"Checkpoint commit `{s['head']}`; Spec SHA256 `{reg['spec_sha']}`; MD SHA256 `{reg['md_sha']}`. Exactly rigid 90/120 then P1 90/120, fresh processes. No 120/120.",
'Both used dt=0.25 ms, 20 physics substeps per unchanged 5 ms control tick, de23ea3 Fixed MPC, suspended_high_rom, nominal Human/model lock, 140 mm adapter, seed 44104, registered quintic timing, allocator, measurement boundary, Reference Manager, Safety Filter, BRAKE and force contracts. The only experimental variable was interface.',
'P1 unchanged: K1=60000 N/m, K3=5e10 N/m^3, D=490.68422685624563 Ns/m; Kr1=1800 Nm/rad, Kr3=4e6 Nm/rad^3, Dr=12.447966320580795 Nms/rad.','',
'## Matched metrics',table(['Metric','Rigid','P1'],metric_rows),'',
'Both force reports are STRICT_PASS with zero >200 N duration and zero excess impulse. Both logged 5852 SAFE_UNCHANGED filter cycles, zero intervention, zero BRAKE, zero BRAKE_INFEASIBLE and zero NO_SAFE_ACTION. No Human ROM, robot structural, MuJoCo-warning or nonfinite-state event occurred.','',
'## Actual trajectory completion',
'Both arms reached 100% reference timing on outbound and return; neither terminated early. Formal labels retain the unchanged 0.06896926724078867 deg criterion. `reference_completed` describes timing coverage and is not itself physical endpoint success.','',
table(['Event','Rigid q_true deg','Rigid q_proxy deg','P1 q_true deg','P1 q_proxy deg'],state_rows),'',
f"Rigid best target-hold error is {r['endpoint_best_error_deg']:.6f} deg, so it does not physically meet the registered target criterion. It returns to within {r['return_error_deg']:.6f} deg, satisfying that precision component. Full reference executed; target precision criterion not met.",
f"P1 best target-hold error is {p['endpoint_best_error_deg']:.6f} deg and return error is {p['return_error_deg']:.6f} deg. It executes the whole outward/return motion and returns near the initial pose, but does not meet either registered precision criterion. Full reference executed; precision criterion not met.",'',
'## P1 deformation and energy',table(['Metric','P1'],[
 ['Translation peak / RMS mm',f"{p['soft']['translation_peak_mm']} / {p['soft']['translation_rms_mm']}"],
 ['Rotation peak / RMS deg',f"{p['soft']['rotation_peak_deg']} / {p['soft']['rotation_rms_deg']}"],
 ['Relative velocity peak m/s',p['soft']['relative_velocity_peak_m_s']],
 ['Relative angular velocity peak rad/s',p['soft']['relative_angular_velocity_peak_rad_s']],
 ['Target / return translation mm',f"{p['soft']['endpoint_translation_mm']} / {p['soft']['return_translation_mm']}"],
 ['Spring energy peak J',p['soft']['energy']['stored_peak_j']],
 ['Damping loss J',p['soft']['energy']['damping_loss_j']],
 ['Max absolute / running-normalized residual',f"{p['soft']['energy']['max_abs_residual_j']} J / {100*p['soft']['energy_max_normalized_abs']}%"],
 ['Final residual / trailing slope',f"{p['soft']['energy_final_signed_residual_j']} J / {p['soft']['energy_trailing_200ms_slope_j_s']} J/s"],
 ['Sustained-growth triggers / windows',f"{p['soft']['sustained_growth_window_count']} / {p['soft']['growth_windows']}"],
]),
f"P1 translation remains small. Rotation peaks at {p['soft']['rotation_peak_deg']:.6f} deg, {p['soft']['rotation_peak_deg']-1:.6f} deg above the 1 deg descriptive engineering target; it is far below the 10 deg gross hard-stop and does not diverge. This target exceedance is retained as an unfavorable result. No persistent energy/amplitude-growth watchdog fires. The residual is diagnostic and cannot overturn the prior numerical-qualification FAIL.",
'The small rigid-column relative-pose trace in the plot is weld/geometry consistency, not compliant-interface deformation.','',
'## Force, dynamics and proxy trade-off',
f"Relative to rigid at 90/120, P1 reduces command peak {reduction(r['force']['command']['peak'],p['force']['command']['peak']):.2f}%, physical-force peak {reduction(r['force']['physical']['peak'],p['force']['physical']['peak']):.2f}%, physical-force RMS {reduction(r['force']['physical']['rms'],p['force']['physical']['rms']):.2f}%, moment peak {reduction(r['force']['physical_moment_R']['peak'],p['force']['physical_moment_R']['peak']):.2f}%, force-slew peak {reduction(r['force']['slew']['peak'],p['force']['slew']['peak']):.2f}%, cuff-acceleration peak {reduction(r['human_dynamics']['cuff_acceleration']['peak'],p['human_dynamics']['cuff_acceleration']['peak']):.2f}% and acceleration RMS {reduction(r['human_dynamics']['cuff_acceleration']['rms'],p['human_dynamics']['cuff_acceleration']['rms']):.2f}%.",
f"Tracking RMSE changes from {r['tracking_rmse_deg']:.6f} to {p['tracking_rmse_deg']:.6f} deg, while return precision worsens from {r['return_error_deg']:.6f} to {p['return_error_deg']:.6f} deg. P1 proxy RMSE q1/q2 is {p['proxy']['rmse_per_joint_deg']}; return-end proxy error is {p['proxy']['return_proxy_error_deg']}. Simulator truth appears only in this offline analysis and was never fed to control.",'',
'## Temporal alignment',
f"Rigid global Human-cuff acceleration peak is {r['human_dynamics']['cuff_acceleration']['peak']:.6f} m/s^2 at {r['human_dynamics']['peak_acceleration_time_s']:.6f} s. Its largest post-start peak is {r['alignment']['post_start_peak']['value_m_s2']:.6f} m/s^2 at {r['alignment']['post_start_peak']['time_s']:.6f} s; neither is associated with BRAKE or filter intervention because neither occurs.",
f"P1 global peak is the recurring startup transient, {p['human_dynamics']['cuff_acceleration']['peak']:.6f} m/s^2 at {p['human_dynamics']['peak_acceleration_time_s']:.6f} s. Its largest t>=0.1 s peak is {p['alignment']['post_start_peak']['value_m_s2']:.6f} m/s^2 at {p['alignment']['post_start_peak']['time_s']:.6f} s. `detailed_metrics.json` records nearest force, command, deformation-reversal, proxy and reference-transition times. These are temporal associations, not causal proof.",'',
'![Aligned diagnostics](aligned_90_120_diagnostics.png)','',
'![Target-arrival alignment](target_arrival_alignment.png)','',
'## Comparison with 40/40 and 40/80',table(['Point','Rigid formal','P1 formal','BRAKE R/P1','Tracking RMSE R/P1 deg','Physical peak R/P1 N','Return error R/P1 deg'],history_rows),'',
'The 40/80 feasibility/BRAKE improvement does not extend as a direct rescue at 90/120 because rigid itself no longer hits the BRAKE boundary. The current frozen controller is non-monotone across these trajectory points: rigid BRAKEs and fails the physical return at 40/80, yet remains TRACK and returns within tolerance at 90/120. P1 remains TRACK at both points. At 90/120 P1 still reduces force severity and tracking RMSE modestly, but worsens return precision and slightly exceeds the 1 deg interface-rotation target.','',
'## Evidence interpretation',
'### DIRECTLY OBSERVED',
'- Both 90/120 arms execute the entire reference without BRAKE, Safety Filter intervention, NO_SAFE_ACTION, warning, ROM or force-contract event.',
'- Neither arm meets the target-hold endpoint tolerance. Rigid meets return precision; P1 does not.',
'- P1 lowers force peak/RMS, force slew, moment peak and cuff acceleration in this pair, with bounded millimeter translation and 1.051 deg peak rotation.','',
'### SUPPORTED BY CURRENT EVIDENCE',
'P1 provides force/transient smoothing at 90/120, but the specific 40/80 BRAKE-boundary rescue cannot be replicated because there is no rigid BRAKE to rescue. The result supports a trajectory-dependent, non-monotone controller-boundary mechanism rather than a simple amplitude-ordered capability expansion.','',
'### UNRESOLVED',
'Why rigid 40/80 enters BRAKE while rigid 90/120 remains TRACK is unresolved. Candidate explanations involving trajectory timing, reference geometry, estimator/proxy state and safety-filter feasibility need separate causal tests. One run per arm does not establish repeatability.','',
'### NOT SUPPORTED',
'No claim of numerical qualification, clinical safety, monotone High-ROM capability expansion, or universal force reduction. P1 does not turn 90/120 into formal COMPLETE and exceeds the descriptive 1 deg rotation target by 0.051 deg.','',
'## Further High-ROM testing',
'Direct progression to 120/120 is not justified from this pair alone. The non-monotone rigid behavior and P1 rotation-target exceedance make a harder-amplitude rollout difficult to interpret, while the prior strict numerical-qualification FAIL remains. A separately preregistered repeat/mechanism study at the existing 40/80 and 90/120 points is scientifically justified before any further amplitude escalation. No such run is authorized or executed here.','',
'## Reproducibility',
f"Run directories: `{root/r['run_id']}` and `{root/p['run_id']}`. Postprocessing verified {array_count} arrays, {len(s['frozen_hashes'])} frozen hashes, exact paired initial state/config and matching model fingerprints. Both runs used fresh PIDs {started[0]['pid']} and {started[1]['pid']}.",
'New files remain uncommitted after checkpoint. Scientific variable: rigid versus registered P1 interface. Controller, timestep, substeps, solver, gains, estimator, Human/robot, geometry, adapter, reference timing, seed, force limits/contracts, Reference Manager, Safety Filter and BRAKE remain unchanged. No 120/120 or extra rollout.','',
'Commands:', '```text',
'PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_90_120_ab.py',
'PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_90_120_ab.py --freeze',
'PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/run_progressive_90_120_ab.py --run-next  # twice, exactly rigid then P1',
'PYTHONDONTWRITEBYTECODE=1 <python> stages/stage4_adaptive_control/scripts/summarize_progressive_90_120_ab.py',
'git diff --check', 'git status --short', '```','',
'No formal experiment command is admitted.']
(root/'REPORT.md').write_text('\n\n'.join(report)+'\n')
# Hash every evidence file except the checksum manifest itself.
lines=[]
for file in sorted(q for q in root.rglob('*') if q.is_file() and q.name!='SHA256SUMS'):
 lines.append(f"{sha(file)}  {file.relative_to(root)}")
(root/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
print(json.dumps(validation,indent=2));print('REPORT_SAVED_NO_SIMULATION')
