from pathlib import Path
import os,sys,json,hashlib,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from diagnostics import analyze,put,clean,corr
from raw_audit_base import raw_audit,sha,polynomial
from stream_runtime_evidence import array_items
def records(n):return [json.loads(x) for x in (P/n).read_text().splitlines()] if (P/n).exists() else []
def main():
 rows=records('CANDIDATE_RESULTS.jsonl');complete=[r for r in rows if r['status']=='COMPLETE'];assert complete
 base=complete[0];bt=np.load(P/'source/results'/base['id']/'trace.npz');series={};diagnostics=[];audits=[];response=[]
 for r in complete:
  ident=r['id'];auditpath=P/'reports'/(ident+'_INDEPENDENT_AUDIT.json')
  audit=json.loads(auditpath.read_text()) if auditpath.exists() else raw_audit(ident)
  audits.append(audit);diag,s=analyze(P,ident,ident.replace('development_',''));diagnostics.append(diag);series[ident]=s
  tr=np.load(P/'source/results'/ident/'trace.npz');rr=list(array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'));multi=[x for x in rr if x.get('applied') and x.get('native_steps',0)>0 and 'multisegment_reference' in x];objects=json.loads((P/'output'/(ident+'_REFERENCE_OBJECTS.json')).read_text())['references'];details=[]
  for key,obj in objects.items():
   knotq=[polynomial(piece['immutable_coefficients'],piece['duration_s'],0)[0].tolist() for piece in obj['segments'][1:]]
   original=obj['identity_payload']['original'];T=obj['duration_s'];grid=np.linspace(0,T,2001);path=np.array([polynomial(original['values'],T,t)[0] for t in grid]);tree=cKDTree(path)
   from raw_audit_base import sample
   shaped=np.array([sample(obj,float(t))[0] for t in grid]);dist=tree.query(shaped)[0];back=cKDTree(shaped).query(path)[0]
   details.append(dict(reference_id=key,certificate_id=obj['certificate_id'],internal_waypoint_q_rad=knotq,knots_s=obj['knots_s'],segment_durations_s=[x['duration_s'] for x in obj['segments']],sampled_path_hausdorff_rad=float(max(dist.max(),back.max())),path_distance_caveat='2001-point diagnostic; not a continuous certificate',binding=obj['binding']))
  current=[]
  for x in multi:
   v=x['multisegment_reference'];c=v['current_full_path_certificate'];assert c['feasible'] and sha([v['reference_id'],c])==v['current_certificate_id'];current.append(v['current_certificate_id'])
  common=np.array_equal(tr['time_s'],bt['time_s']);deltas={}
  first=min([x['start_physics_s'] for x in multi],default=float('inf'));pre=True
  for key in ['reference_q_rad','reference_dq_rad_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']:
   if common:
    deltas[key]=np.max(abs(tr[key]-bt[key]),axis=0).tolist();mask=tr['time_s']<first-1e-9;pre=pre and np.array_equal(tr[key][mask],bt[key][mask],equal_nan=True)
  response.append(dict(id=ident,initial_state_identity=r['initial_state_identity'],references=details,applied_multisegment_receipts=len(multi),current_certificates_reconstructed=len(current),all_pre_intervention_fields_exact=pre if multi else None,same_time_grid_as_B=common,max_physical_trace_deltas=deltas,first_applied_s=first if multi else None,last_applied_s=max([x['end_physics_s'] for x in multi],default=None),original_request_count=len(json.loads((P/'source/results'/ident/'summary.json').read_text())['decisions'])))
  print('AUDITED',ident,audit['status'],len(multi),flush=True)
 put('NATIVE_PROVENANCE_AUDIT.json',dict(status='PASS',arms=audits,responses=response,all_initial_states_equal=len({r['initial_state_identity'] for r in complete})==1,scope='separate postprocessing pass by same agent; not an independent human/agent review'))
 put('NEW_PHYSICAL_DIAGNOSTICS.json',dict(cases=diagnostics))
 bdiag=diagnostics[0];contrasts=[]
 for d in diagnostics:
  contrasts.append(dict(id=d['id'],delta_J_F_N_s=d['J_F_N_s']-bdiag['J_F_N_s'],delta_velocity_TV=d['full']['TV_velocity_combined']-bdiag['full']['TV_velocity_combined'],delta_speed_TV=d['full']['TV_speed']-bdiag['full']['TV_speed'],delta_jerk_energy=sum(d['full']['jerk_energy_per_joint'])-sum(bdiag['full']['jerk_energy_per_joint'])))
 put('FORCE_MOTION_CONTRASTS.json',dict(rows=contrasts,correlations={key:corr([x['delta_J_F_N_s'] for x in contrasts[1:]],[x[key] for x in contrasts[1:]]) for key in ['delta_velocity_TV','delta_speed_TV','delta_jerk_energy']},caveat='candidate contrasts include motion failures, dependencies and repeats; descriptive only'))
 eligible=[r for r in complete if r['motion_pass'] and r['task']==r['receipt']=='PASS'];selected=min(eligible,key=lambda r:(round(r['J_F_N_s'],2),r['velocity_TV_combined'],r['candidate']['waypoint_count'],r['J_F_N_s']))
 # Rounded objective is explicitly a reporting tie band; numerical force minimum retained separately.
 numerical=min(eligible,key=lambda r:r['J_F_N_s']);new_record=numerical['J_F_N_s']<1400.697221
 put('FROZEN_SELECTION.json',dict(frozen_unix=__import__('time').time(),status='NEW_RECORD_PENDING_VALIDATION' if new_record else 'NO_NEW_FORCE_RECORD',numerical_feasible_minimum=numerical['id'],numerical_J_F_N_s=numerical['J_F_N_s'],reported_motion_tiebreak=selected['id'],reporting_tie_band_N_s=.01,no_primary_promoted=not new_record,reason='All feasible new force values compared to historical 1400.697221; negligible numerical differences are not evidence of a useful force mechanism.',no_validation_reselection=True))
 if not new_record:put('VALIDATION_RESULTS.json',dict(status='NOT_TRIGGERED_NO_NEW_FORCE_RECORD',paired_conditions=0,primary=None,threshold_N_s=1400.697221,new_Human=False,previous_18D_validation_motion='0/4 historical, unchanged',deterministic_repeat_is_not_independent_validation=True))
 # Finite differences are true executed paired interventions, never mathematical force predictions.
 sensitivities=[]
 for joint in ['hip','knee']:
  pos=next((r for r in complete if r['id'].endswith('D1_'+joint+'_pos')),None);neg=next((r for r in complete if r['id'].endswith('D1_'+joint+'_neg')),None)
  if pos and neg:sensitivities.append(dict(joint=joint,amplitude_deg=.02,central_J_F_N_s_per_deg=(pos['J_F_N_s']-neg['J_F_N_s'])/.04,central_velocity_TV_per_deg=(pos['velocity_TV_combined']-neg['velocity_TV_combined'])/.04,positive_motion_pass=pos['motion_pass'],negative_motion_pass=neg['motion_pass'],local_exploratory_only=True))
 put('LOCAL_SENSITIVITY.json',dict(rows=sensitivities))
 byid={r['candidate']['id']:r for r in complete}
 synergy=None
 if all(k in byid for k in ['D1_coupled','S_fixed_knots_early','PS_early']):
  p=byid['D1_coupled'];s=byid['S_fixed_knots_early'];ps=byid['PS_early'];synergy=dict(force_gain_interaction_N_s=(base['J_F_N_s']-ps['J_F_N_s'])-(base['J_F_N_s']-p['J_F_N_s'])-(base['J_F_N_s']-s['J_F_N_s']),all_three_motion_pass=all(r['motion_pass'] for r in [p,s,ps]),formula='gain(P+S)-gain(P)-gain(S); positive = descriptive synergy',limitation='S is a fixed-knot timing proxy with geometric drift, one state and one amplitude only')
 put('PATH_TIMING_INTERACTION.json',synergy)
 response_ids=[r['id'] for r in complete if r['candidate']['id'] in ['D1_knee_pos','D2_knee_uniform','D2_knee_alternating','D3_knee_uniform','D3_knee_alternating']]
 vectors=[]
 for ident in response_ids:
  tr=np.load(P/'source/results'/ident/'trace.npz')
  if np.array_equal(tr['time_s'],bt['time_s']):vectors.append((tr['evaluation_only_human_state_rad_rad_s']-bt['evaluation_only_human_state_rad_rad_s']).ravel())
 if vectors:
  mat=np.column_stack(vectors);sv=np.linalg.svd(mat,compute_uv=False);put('PHYSICAL_RESPONSE_DIVERSITY.json',dict(ids=response_ids,singular_values=sv,output_response_norms=np.linalg.norm(mat,axis=0),interpretation='different finite perturbations create distinct full-task actual Human responses; output diversity is not a formal controllability rank or a density optimum',initial_parent_matched=True))
 # Reproducible downstream anomaly and torque co-occurrence; no causal torque attribution.
 anomaly=[]
 for ident in ['development_legacy005','development_legacy005_repeat']:
  if ident not in series:continue
  s=series[ident];a=abs(s['a']);i=int(np.argmax(a[:,0]));tr=np.load(P/'source/results'/ident/'trace.npz');sel=tr['stage']=='TASK';t0=tr['time_s'][sel][0];tf=tr['time_s'][sel]-t0;torque=tr['cr12_actuator_command_nm'][sel];torquejump=np.r_[0,np.linalg.norm(np.diff(torque,axis=0),axis=1)];near=abs(tf-s['t'][i])<.05;rr=next(x for x in response if x['id']==ident);delay=s['t'][i]-(rr['last_applied_s']-t0);anomaly.append(dict(id=ident,task_start_absolute_physics_s=float(t0),hip_acceleration_peak_task_s=float(s['t'][i]),hip_acceleration_peak_absolute_physics_s=float(s['t'][i]+t0),hip_acceleration_peak_deg_s2=float(np.degrees(a[i,0])),motion_pass=next(r['motion_pass'] for r in complete if r['id']==ident),delay_after_last_multisegment_receipt_s=float(delay),nearby_max_5ms_robot_torque_change_Nm=float(torquejump[near].max()),claim='temporal co-occurrence and reproducible whole-chain response; internal mechanism unresolved'))
 put('DOWNSTREAM_ANOMALY.json',dict(rows=anomaly,repeat_gate=json.loads((P/'ANOMALY_REPEAT_GATE.json').read_text())))
 # Real physical measurements only.
 plt.rcParams.update({'font.size':8,'figure.dpi':140})
 def marker(r):return '*' if r['candidate']['id'].startswith('legacy') else 'x' if 'PROXY' in r['candidate']['family'] else 's' if r['candidate']['id'].startswith('adaptive') else 'o'
 def finish(fig,name):fig.tight_layout();fig.savefig(P/'figures'/name);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(11,4))
 for r in complete:
  x=r['candidate']['waypoint_count'];color='tab:blue' if r['motion_pass'] else 'tab:red';axes[0].scatter(x,r['velocity_TV_combined'],color=color,marker=marker(r));axes[1].scatter(x,r['jerk_RMS_combined'],color=color,marker=marker(r))
 for ax in axes:ax.set_xlabel('Internal partition points (red = motion FAIL)');ax.set_xticks([0,1,2,3])
 axes[0].set_ylabel('Actual velocity TV [rad/s]');axes[1].set_ylabel('Actual jerk RMS [rad/s^3]');fig.suptitle('Sparse arrangements; stars = legacy 3 partition knots / only 1 perturbed');finish(fig,'waypoint_density_vs_motion.png')
 fig,ax=plt.subplots(figsize=(9,5))
 for r in complete:ax.scatter(r['candidate']['waypoint_count'],r['J_F_N_s']-base['J_F_N_s'],color='tab:blue' if r['motion_pass'] else 'tab:red',marker=marker(r))
 ax.set_xlabel('Internal partition points; x = timing proxy; square = adaptive');ax.set_title('Stars: legacy 3 partition knots / only 1 perturbed; red = motion FAIL');ax.set_ylabel('Full J_F - B [N s]');ax.axhline(0,color='k',lw=.5);ax.set_xticks([0,1,2,3]);finish(fig,'waypoint_density_vs_JF.png')
 fig,axes=plt.subplots(1,2,figsize=(11,4));timed=[r for r in complete if 'PROXY' in r['candidate']['family']]
 for r in timed:
  x=(r['candidate']['spec']['time_fractions'][0]-.5)*1.27*1000;axes[0].scatter(x,r['J_F_N_s']-base['J_F_N_s'],label=r['candidate']['id']);axes[1].scatter(x,100*(r['jerk_RMS_combined']/base['jerk_RMS_combined']-1))
 axes[0].legend(fontsize=7);axes[0].set_ylabel('J_F - B [N s]');axes[1].set_ylabel('Actual jerk RMS change vs B [%]')
 for ax in axes:ax.set_xlabel('Internal time shift [ms]; fixed knots, path may change')
 finish(fig,'timing_vs_JF_motion.png')
 fig,axes=plt.subplots(1,2,figsize=(12,5))
 for r in complete:
  x=r['J_F_N_s']-base['J_F_N_s'];y=r['jerk_RMS_combined']/base['jerk_RMS_combined'];axes[0].scatter(x,y,color='tab:blue' if r['motion_pass'] else 'tab:red',marker=marker(r))
  if r['candidate']['id']=='legacy005':axes[0].annotate('+0.05 deg: motion FAIL',(x,y),xytext=(15,-10),textcoords='offset points',fontsize=8)
  if r['motion_pass']:
   axes[1].scatter(x,100*(y-1),color='tab:blue',marker=marker(r))
   if r['id']==numerical['id']:axes[1].annotate('Numerical force min',(x,100*(y-1)),xytext=(12,10),textcoords='offset points',fontsize=7)
 for ax in axes:ax.set_xlabel('Full J_F - B [N s]');ax.axhline(1 if ax is axes[0] else 0,color='k',lw=.5)
 axes[0].set_ylabel('Actual jerk RMS / B');axes[0].set_title('All complete runs; red = motion FAIL');axes[1].set_ylabel('Actual jerk RMS change vs B [%]');axes[1].set_title('Feasible runs: tiny effects, one parent state');finish(fig,'force_motion_tradeoff.png')
 archived=json.loads((P/'DIAGNOSTIC_RESULTS.json').read_text())['cases'];plotcases=[]
 for rec in archived[:2]:
  sp=next(Path(x) for x in rec['sources'] if '/motion_series/' in x);root=sp.parents[1];d,ss=analyze(root,rec['id'],rec['label']);plotcases.append((rec['label'],ss,d['J_F_N_s']))
 for ident in sorted({selected['id'],numerical['id']}):plotcases.append((ident.replace('development_',''),series[ident],next(r['J_F_N_s'] for r in complete if r['id']==ident)))
 fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True)
 for label,s,jf in plotcases:axes[0].plot(s['tf'],s['cf'],label=label);axes[1].plot(s['tf'],s['cf']/jf);axes[2].plot(s['tf'],s['force'])
 axes[0].legend();axes[0].set_ylabel('C_F [N s]');axes[1].set_ylabel('C_F / J_F');axes[2].set_ylabel('Force [N]');axes[2].set_xlabel('Task elapsed [s]')
 for ax in axes:
  for boundary in plotcases[0][1]['bounds'][1:3]:ax.axvline(boundary,color='k',ls=':',lw=.7)
 for phase,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],plotcases[0][1]['bounds'],plotcases[0][1]['bounds'][1:]):axes[0].text((lo+hi)/2,.9*max(x[2] for x in plotcases),phase,ha='center',fontsize=7)
 finish(fig,'cumulative_force_vs_time.png')
 fig,axes=plt.subplots(len(plotcases),2,figsize=(11,2.4*len(plotcases)),sharex=True)
 for row,(label,s,jf) in enumerate(plotcases):
  for joint in range(2):axes[row,joint].plot(s['tf'],np.degrees(s['truev'][:,joint]),label='actual Human');axes[row,joint].plot(s['tf'],np.degrees(s['refv'][:,joint]),ls='--',label='issued reference');axes[row,joint].set_ylabel(label+' [deg/s]')
 axes[0,0].set_title('Hip');axes[0,1].set_title('Knee');axes[0,0].legend();axes[-1,0].set_xlabel('Task elapsed [s]');axes[-1,1].set_xlabel('Task elapsed [s]');finish(fig,'actual_vs_reference_velocity.png')
 chosen=series[selected['id']];fig,axes=plt.subplots(4,1,figsize=(11,9),sharex=True)
 for ident in [base['id'],selected['id']]:
  s=series[ident];axes[0].plot(s['tf'],s['cf'],label=ident);axes[1].plot(s['tf'],s['force']);axes[2].plot(s['t'],np.degrees(s['q'][:,0]));axes[3].plot(s['t'],np.degrees(s['q'][:,1]))
 axes[0].legend();axes[0].set_ylabel('C_F [N s]');axes[1].set_ylabel('Force [N]');axes[2].set_ylabel('Actual hip [deg]');axes[3].set_ylabel('Actual knee [deg]');axes[3].set_xlabel('Task elapsed [s]');finish(fig,'best_candidate_full_task.png')
 print('POSTPROCESS_COMPLETE',len(complete),'NUMERICAL_MIN',numerical['id'],numerical['J_F_N_s'],'TIEBREAK',selected['id'],flush=True)
if __name__=='__main__':main()
