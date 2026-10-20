from pathlib import Path
import os,json,time,hashlib,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies'); R=Path(__file__).resolve().parents[1]; P=S/R.name
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def load(root,ident):
 z=np.load(root/'motion_series'/(ident+'.npz'));tr=np.load(root/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';origin=float(tr['time_s'][ix][0]);m=read(root/'reports'/(ident+'_MEASURED.json'));su=read(root/'source/results'/ident/'summary.json')
 a=dict(t=z['time_s']-origin,q=np.rad2deg(z['true_q_rad']),v=np.rad2deg(z['true_dq_rad_s']),a=np.rad2deg(z['acceleration_rad_s2']),j=np.rad2deg(z['jerk_rad_s3']),phase=z['phase'],tf=tr['time_s'][ix]-origin,rq=np.rad2deg(tr['reference_q_rad'][ix]),rv=np.rad2deg(tr['reference_dq_rad_s'][ix]),truth=np.rad2deg(tr['evaluation_only_human_state_rad_rad_s'][ix]),estimated=np.rad2deg(tr['estimated_human_state_rad_rad_s'][ix]),f=np.linalg.norm(tr['physical_cuff_force_world_n'][ix],axis=1),moment=np.linalg.norm(tr['physical_cuff_moment_world_nm'][ix],axis=1),allocator=tr['robot_torque_component_allocator_nm'][ix],command=tr['cr12_actuator_command_nm'][ix],clipping=tr['robot_torque_component_clipping_nm'][ix],contact=tr['shank_bed_contact_evaluation_only'][ix],metric=m,events=[],origin=origin)
 counts={}
 for lr in su['learning_records']:
  d=su['decisions'][lr['decision_index']];ph=d['phase'];slot=counts.get(ph,0);counts[ph]=slot+1;sc=lr['selected_plan']['schedule'];co=d.get('rolling_composite')
  a['events'].append(dict(phase=ph,slot=slot,index=lr['decision_index'],request=d['decision_request_time_s']-origin,activation=lr['start_time_s']-origin,splice=lr['start_time_s']-origin+(float(co['splice_elapsed_s']) if co else 0.),duration=sc['duration_s'],target_deg=np.rad2deg(sc['target_q_rad']).tolist(),pass_velocity_deg_s=np.rad2deg(sc['target_dq_rad_s']).tolist(),activated=lr['selected_plan_activated'],deployable_state_deg_deg_s=np.rad2deg(d['deployable_state_rad_rad_s']).tolist(),reference_state_deg_deg_s=np.rad2deg(d['reference_state_rad_rad_s']).tolist(),remaining_s=d['phase_remaining_s'],source_age_s=d['plan_age_s']))
 return a
def terminal(z):
 out=[]
 for j in range(2):
  goal=float(z['rq'][-1,j]);mask=(abs(z['rq'][:,j]-goal)<1e-9)&(abs(z['rv'][:,j])<1e-8)&(z['tf']>10.)
  stable=np.logical_and.accumulate(mask[::-1])[::-1];stop=float(z['tf'][np.flatnonzero(stable)[0]])
  idx=np.flatnonzero(z['t']>=stop-1e-8);imin=idx[np.argmin(z['q'][idx,j])];imin_return=np.flatnonzero(z['phase']=='RETURN')[np.argmin(z['q'][z['phase']=='RETURN',j])]
  qi=float(np.interp(stop,z['t'],z['q'][:,j]));vi=float(np.interp(stop,z['t'],z['v'][:,j]));after=(z['tf']>=stop-1e-8)&(z['tf']<=z['t'][imin]+1e-8)
  crossings=np.flatnonzero((z['q'][:,j]<goal)&(z['phase']=='RETURN'))
  out.append(dict(joint=['hip','knee'][j],goal_deg=goal,reference_stably_stopped_task_s=stop,actual_q_at_ref_stop_deg=qi,actual_dq_at_ref_stop_deg_s=vi,actual_min_after_stop_deg=float(z['q'][imin,j]),actual_min_after_stop_task_s=float(z['t'][imin]),overshoot_below_goal_after_ref_stop_deg=max(0.,goal-float(z['q'][imin,j])),continuing_displacement_after_ref_stop_deg=qi-float(z['q'][imin,j]),min_delay_from_ref_stop_s=float(z['t'][imin]-stop),return_overshoot_below_goal_deg=max(0.,goal-float(z['q'][imin_return,j])),return_min_task_s=float(z['t'][imin_return]),first_goal_crossing_return_s=None if not len(crossings) else float(z['t'][crossings[0]]),allocator_norm_max_during_continuation=float(np.linalg.norm(z['allocator'][after],axis=1).max()) if np.any(after) else None,clipping_norm_max_during_continuation=float(np.linalg.norm(z['clipping'][after],axis=1).max()) if np.any(after) else None,contact_samples_during_continuation=int(np.count_nonzero(z['contact'][after]))))
 return out
def variations(z):
 result={}
 for ph,ix in [('full',np.ones(len(z['t']),bool))]+[(s,z['phase']==s) for s in ['OUTBOUND','HOLD','RETURN']]:
  result[ph]=dict(velocity_TV_deg_s=float(np.linalg.norm(np.diff(z['v'][ix],axis=0),axis=1).sum()),acceleration_TV_deg_s2=float(np.linalg.norm(np.diff(z['a'][ix],axis=0),axis=1).sum()),combined_jerk_RMS_deg_s3=float(np.sqrt(np.mean(np.sum(z['j'][ix]**2,axis=1)))))
 return result
sources={};records=[];Z={}
sets=[('m2_18d_terminal_response_repair_v1',['N2','U1'],['B','E','T']),('m2_18d_terminal_expanded_prefix_validation_v1',['V1','V2'],['B','E','T']),('m2_18d_w1_d_qualification_v1',['W1','R0','O0'],['B','T','D']),('m2_18d_early_return_motion_repair_v1',['repair'],['B','T','D','ER110_R4_120'])]
for study,conditions,arms in sets:
 root=S/study
 for condition in conditions:
  results=read(root/(condition+'_RESULTS.json'));rr=results.get('rows',results if isinstance(results,list) else [])
  for arm in arms:
   ident=condition+'_'+arm;m=read(root/'reports'/(ident+'_MEASURED.json'));bm=read(root/'reports'/(condition+'_B_MEASURED.json'));fr=m['motion']['raw']['full'];br=bm['motion']['raw']['full'];row=next((r for r in rr if r.get('id')==ident),{})
   z=load(root,ident);Z[condition+'_'+arm]=z
   source_paths=[root/'reports'/(ident+'_MEASURED.json'),root/'motion_series'/(ident+'.npz'),root/'source/results'/ident/'trace.npz',root/'source/results'/ident/'summary.json']
   for p in source_paths:sources[str(p)]=dict(sha256=sha(p),size=p.stat().st_size)
   rec=dict(state=condition,arm=arm,id=ident,source=str(root),archived_row_keys=list(row),archived_all_original_qualifications=row.get('all_original_qualifications'),archived_motion=row.get('motion'),axes=m['axes'],native_safety=m['native_physical_audit']['pass_'],J_F=m['J_F_N_s'],gain_vs_own_B_percent=100*(1-m['J_F_N_s']/bm['J_F_N_s']),force_RMS_N=float(np.sqrt(np.mean(z['f']**2))),force_peak_N=m['force_peak_N'],moment_integral_Nm_s=m['moment_integral_Nm_s'],moment_ratio_vs_B=m['moment_integral_Nm_s']/bm['moment_integral_Nm_s'],moment_peak_Nm=m['moment_peak_Nm'],tracking_RMS_deg=m['tracking_RMS_deg'],tracking_delta_vs_B_deg=(np.array(m['tracking_RMS_deg'])-bm['tracking_RMS_deg']).tolist(),clearance_m=m['clearance'],raw_full_motion=fr,SG5_full=m['motion']['SG5']['full'],SG21_full=m['motion']['SG21']['full'],excursion_deg=m['dose']['excursion_deg'],excursion_delta_vs_B_deg=(np.array(m['dose']['excursion_deg'])-bm['dose']['excursion_deg']).tolist(),knee_v95_ratio_vs_B=fr['velocity_deg_s']['p95_abs'][1]/br['velocity_deg_s']['p95_abs'][1],knee_a95_ratio_vs_B=fr['acceleration_deg_s2']['p95_abs'][1]/br['acceleration_deg_s2']['p95_abs'][1],terminal=terminal(z),variations=variations(z),phase_cost=m['phase_cost'],events=z['events'])
   records.append(rec)
put('derived/HISTORICAL_NATIVE_AUDIT.json',dict(status='READ_ONLY_NATIVE_REANALYSIS_NO_NEW_PHYSICS',records=records,definitions=dict(overshoot='max(0, final issued reference q - actual minimum q) during RETURN; also restricted to after reference remains at final q with zero dq',continued_motion='actual q at stable reference stop minus subsequent minimum; separate from overshoot and from matched-B excursion delta',native_period_s=.00025,trace_period_s=.005,force_integral='original full TASK 5ms left quadrature',risk_features='offline history analysis only; full matched-B future quantiles and truth unavailable online')))
put('audit/HISTORICAL_ANALYSIS_SOURCES.json',sources)
tags=['repair_B','repair_T','repair_D','repair_ER110_R4_120']; colors=['#777777','#0072b2','#d55e00','#009e73'];labs=['B','T','D','Early RETURN']
fig,axs=plt.subplots(6,1,figsize=(12,16),sharex=True,layout='constrained')
for tag,c,lab in zip(tags,colors,labs):
 z=Z[tag];t=z['t'];tf=z['tf'];axs[0].plot(t,z['q'][:,1],color=c,label=lab);axs[0].plot(tf,z['rq'][:,1],color=c,ls='--',alpha=.6);axs[1].plot(t,z['v'][:,1],color=c);axs[1].plot(tf,z['rv'][:,1],color=c,ls='--',alpha=.6);axs[2].plot(tf,z['truth'][:,1]-z['rq'][:,1],color=c);axs[3].plot(tf,np.linalg.norm(z['allocator'],axis=1),color=c);axs[4].plot(tf,z['f'],color=c);axs[5].plot(tf,z['moment'],color=c)
for ax,label in zip(axs,['Knee q (deg)','Knee dq (deg/s)','Actual minus reference (deg)','Allocator torque norm (Nm)','Cuff force norm (N)','Cuff moment norm (Nm)']):
 ax.set_ylabel(label);ax.set_xlim(15.2,18.5);ax.grid(alpha=.2)
 for e in Z[tags[-1]]['events']:
  if e['phase']=='RETURN' and e['slot']>=4:ax.axvline(e['splice'],color='#009e73',ls=':',lw=.8)
axs[0].legend(ncol=4);axs[-1].set_xlabel('Task time (s); solid = actual, dashed = issued reference; green dotted = Early RETURN splice');fig.suptitle('Historical terminal response: overshoot and continuing motion are distinct')
fig.savefig(P/'figures/terminal_response_historical.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(4,1,figsize=(12,12),sharex=True,layout='constrained')
for tag,c,lab in zip(tags,colors,labs):
 z=Z[tag];t=z['t']
 for i,key in enumerate(['v','a','j']):axs[i].plot(t,z[key][:,1],color=c,label=lab,lw=.65)
 axs[3].plot(t,np.r_[0,np.cumsum(np.linalg.norm(np.diff(z['v'],axis=0),axis=1))],color=c)
for ax,lab in zip(axs,['Knee velocity (deg/s)','Knee acceleration (deg/s2)','Knee raw jerk (deg/s3)','Cumulative joint velocity TV (deg/s)']):ax.set_ylabel(lab);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
axs[0].legend(ncol=4);axs[-1].set_xlabel('Complete task time (s), native 0.25 ms derivatives; no endpoint deletion');fig.suptitle('Actual Human motion: complete-task distributions and localized transients');fig.savefig(P/'figures/motion_time_distribution.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True,layout='constrained')
for tag,c,lab in zip(tags,colors,labs):
 z=Z[tag];tf=z['tf'];axs[0].plot(tf,z['f'],c=c,label=lab);axs[1].plot(tf,np.r_[0,np.cumsum(z['f'][:-1]*np.diff(tf))],c=c);axs[2].plot(tf,np.r_[0,np.cumsum(z['moment'][:-1]*np.diff(tf))],c=c)
for ax,lab in zip(axs,['Cuff force (N)','Cumulative J_F (N s)','Cumulative moment integral (Nm s)']):ax.set_ylabel(lab);ax.grid(alpha=.2)
axs[0].legend(ncol=4);axs[-1].set_xlabel('Complete task time (s)');fig.suptitle('Paired force and moment burdens — original full integration');fig.savefig(P/'figures/force_and_cumulative_cost.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(15,4.8),layout='constrained');base=next(r for r in records if r['id']=='repair_B')
for tag,c,lab in zip(tags,colors,labs):
 r=next(r for r in records if r['id']==tag)
 for ax,y in zip(axs,[r['moment_integral_Nm_s'],r['tracking_RMS_deg'][1],r['excursion_delta_vs_B_deg'][1]]):ax.scatter(r['J_F'],y,c=c,s=65,label=lab);ax.annotate(lab,(r['J_F'],y),xytext=(4,4),textcoords='offset points',fontsize=8)
for ax,label in zip(axs,['Moment integral (Nm s)','Knee tracking RMS (deg)','Knee excursion minus matched B (deg)']):ax.set_ylabel(label);ax.set_xlabel('Full J_F (N s)');ax.grid(alpha=.2)
axs[2].axhline(.5,c='red',ls=':',label='Frozen motion limit');fig.suptitle('W1 paired trade-offs: lower force alone does not establish qualification');fig.savefig(P/'figures/force_motion_moment_tradeoff.png',dpi=150);plt.close(fig)
states=['N2','U1','V1','V2','W1','R0','O0'];fig,axs=plt.subplots(1,3,figsize=(14,5),layout='constrained')
for i,key in enumerate(['knee_v95_ratio_vs_B','knee_a95_ratio_vs_B','excursion_delta_vs_B_deg']):
 vals=[next(r for r in records if r['state']==s and r['arm']=='T')[key] for s in states];vals=[v[1] if isinstance(v,list) else v for v in vals];axs[i].bar(states,vals,color=['#0072b2']*4+['#d55e00','#009e73','#d55e00']);axs[i].axhline(.5 if i==2 else 1.1,c='red',ls=':');axs[i].set_title(['Knee velocity p95 / own B','Knee acceleration p95 / own B','Knee excursion minus own B (deg)'][i]);axs[i].grid(axis='y',alpha=.2)
fig.suptitle('Historical T applicability map; states share one Human, some share prefix history');fig.savefig(P/'figures/state_qualification_differences.png',dpi=150);plt.close(fig)
for f in [P/'derived/HISTORICAL_NATIVE_AUDIT.json',*list((P/'figures').glob('*.png'))]:
 dest=R/f.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
print(json.dumps(dict(status='PASS',records=len(records),terminal={tag:terminal(Z[tag])[1] for tag in tags},new_physics=0)),flush=True)
