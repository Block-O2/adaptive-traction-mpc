from pathlib import Path
import os,json,time,copy
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def series(ident):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';origin=float(tr['time_s'][ix][0])
 return dict(t=z['time_s']-origin,q=z['true_q_rad'],v=z['true_dq_rad_s'],a=z['acceleration_rad_s2'],j=z['jerk_rad_s3'],phase=z['phase'],tf=tr['time_s'][ix]-origin,f=np.linalg.norm(tr['physical_cuff_force_world_n'][ix],axis=1),m=np.linalg.norm(tr['physical_cuff_moment_world_nm'][ix],axis=1),rq=tr['reference_q_rad'][ix],rv=tr['reference_dq_rad_s'][ix],truth=tr['evaluation_only_human_state_rad_rad_s'][ix],allocator=tr['robot_torque_component_allocator_nm'][ix],command=tr['cr12_actuator_command_nm'][ix],origin=origin)
def variations(z):
 return {ph:{'TV_v':float(np.linalg.norm(np.diff(z['v'][ix],axis=0),axis=1).sum()),'TV_a':float(np.linalg.norm(np.diff(z['a'][ix],axis=0),axis=1).sum()),'jerk_RMS':float(np.sqrt(np.mean(np.sum(z['j'][ix]**2,axis=1))))} for ph,ix in [('full',np.ones(len(z['t']),bool))]+[(ph,z['phase']==ph) for ph in ['OUTBOUND','HOLD','RETURN']]}
groups=[g for g in ['W1dev','repair','repeat','W2'] if (P/(g+'_RESULTS.json')).exists()];rows=[];M={};Z={};V={}
for g in groups:
 for r in read(g+'_RESULTS.json')['rows']:
  ident=r['id'];m=read('reports/'+ident+'_MEASURED.json');M[ident]=m;z=series(ident);Z[ident]=z;V[ident]=variations(z);row=copy.deepcopy(r);row['complete_metrics']=m;row['actual_variations']=V[ident]
  if r['candidate'].get('early'):
   dz=Z[g+'_D'];dm=M[g+'_D'];dv=V[g+'_D'];bm=M[g+'_B'];su=read('source/results/'+ident+'/summary.json');events=[]
   for lr in su['learning_records']:
    d=su['decisions'][lr['decision_index']];sc=lr['selected_plan']['execution_screen'];comp=d.get('rolling_composite');events.append(dict(index=lr['decision_index'],phase=d['phase'],request=d['decision_request_time_s']-z['origin'],activation=lr['start_time_s']-z['origin'],splice=lr['start_time_s']-z['origin']+(float(comp['splice_elapsed_s']) if comp else 0.),duration=lr['selected_plan']['schedule']['duration_s'],target=lr['selected_plan']['schedule']['target_q_rad'],pass_velocity=lr['selected_plan']['schedule']['target_dq_rad_s'],early=sc.get('early_return_duration'),posture=sc.get('second_round_posture'),activated=lr['selected_plan_activated']))
   first=next(e['splice'] for e in events if e['early']);pre=z['t']<first-1e-9;comparable=z['q'].shape==dz['q'].shape and np.allclose(z['t'],dz['t'],atol=1e-8,rtol=0)
   detail=[]
   for key,sig in [('velocity_deg_s','v'),('acceleration_deg_s2','a'),('jerk_deg_s3','j')]:
    limit=np.array(bm['motion']['raw']['full'][key]['p95_abs'])*1.1;signal=abs(np.rad2deg(z[sig]))
    for j in range(2):
     over=signal[:,j]>limit[j]+1e-7;idx=np.flatnonzero(over);parts=np.split(idx,np.flatnonzero(np.diff(idx)>1)+1) if len(idx) else [];peak=int(np.argmax(signal[:,j]));cum=np.cumsum(over);budget=int(np.ceil(.05*(len(z['t'])+400)))
     detail.append(dict(signal=key,joint=['hip','knee'][j],full_matched_B_p95_times_1p1=float(limit[j]),over_samples=int(over.sum()),peak_task_s=float(z['t'][peak]),peak_phase=str(z['phase'][peak]),peak_abs=float(signal[peak,j]),irreversible_p95_count_crossing_s=None if cum[-1]<=budget else float(z['t'][np.flatnonzero(cum>budget)[0]]),pre_splice_over_samples=int(np.sum(over&pre)),by_phase={ph:int(np.sum(over&(z['phase']==ph))) for ph in ['OUTBOUND','HOLD','RETURN']},intervals=[dict(start=float(z['t'][a[0]]),end=float(z['t'][a[-1]]),samples=len(a)) for a in parts]))
   qdeg=np.rad2deg(z['q']);exc=np.maximum.accumulate(qdeg,axis=0)-np.minimum.accumulate(qdeg,axis=0);be=np.array(bm['dose']['excursion_deg'])+.5
   dsave=M[g+'_B']['J_F_N_s']-dm['J_F_N_s'];saving=M[g+'_B']['J_F_N_s']-m['J_F_N_s'];retention=saving/dsave
   row.update(delta_J_F_vs_T_N_s=m['J_F_N_s']-M[g+'_T']['J_F_N_s'],delta_J_F_vs_D_N_s=m['J_F_N_s']-dm['J_F_N_s'],D_force_saving_retention_fraction=retention,eligible_primary=bool(r['all_original_qualifications'] and r['motion']['gain_percent']>=1. and retention>=.8),delta_variation_vs_D={ph:{k:V[ident][ph][k]/dv[ph][k]-1 for k in ['TV_v','TV_a','jerk_RMS']} for ph in V[ident]},actual_response_comparable_grid=bool(comparable),first_early_splice_task_s=first,events=events,failure_window_diagnostics=detail,excursion_failure_windows=[dict(joint=['hip','knee'][j],first_exceeds_final_B_plus_tolerance=None if not np.any(exc[:,j]>be[j]+1e-7) else float(z['t'][np.flatnonzero(exc[:,j]>be[j]+1e-7)[0]]),max_task_s=float(z['t'][np.argmax(qdeg[:,j])]),min_task_s=float(z['t'][np.argmin(qdeg[:,j])]),pre_splice_excursion=float(np.ptp(qdeg[pre,j]))) for j in range(2)])
   if comparable:
    changed=np.max(abs(np.c_[z['q']-dz['q'],z['v']-dz['v']]),axis=1)>1e-10
    row.update(actual_q_change_max_deg=np.rad2deg(np.max(abs(z['q']-dz['q']),axis=0)).tolist(),actual_dq_change_max_deg_s=np.rad2deg(np.max(abs(z['v']-dz['v']),axis=0)).tolist(),first_actual_q_dq_difference_task_s=None if not np.any(changed) else float(z['t'][np.flatnonzero(changed)[0]]),pre_splice_q_dq_exact=bool(np.array_equal(z['q'][pre],dz['q'][pre]) and np.array_equal(z['v'][pre],dz['v'][pre])))
  rows.append(row)
put('EXPERIMENT_RESULTS.json',dict(status='COMPLETE_REPORTED_PHYSICAL_RESULTS' if all((P/(g+'_DONE.json')).exists() for g in groups) else 'INTERIM',created_unix=time.time(),groups=groups,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',rows=rows,no_unmatched_absolute_force_ranking=True))
# Each development group is a separate complete matched comparison.
for g in groups:
 repairs=[r for r in rows if r['id'].startswith(g+'_') and r['candidate'].get('early')]
 if not repairs:continue
 fig,ax=plt.subplots(11,1,figsize=(15,25),sharex=True,layout='constrained');bm=M[g+'_B'];vlim=bm['motion']['raw']['full']['velocity_deg_s']['p95_abs'][1]*1.1;alim=bm['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]*1.1
 tags=['B','T','D']+[r['candidate']['id'] for r in repairs];colors=['#777777','#0072b2','#d55e00','#009e73','#cc79a7','#e69f00']
 for tag,co in zip(tags,colors):
  z=Z[g+'_'+tag];t=z['t'];tf=z['tf'];v=np.rad2deg(z['v'][:,1]);a=np.rad2deg(z['a'][:,1]);q=np.rad2deg(z['q'][:,1]);j=np.rad2deg(z['j'][:,1]);exc=np.maximum.accumulate(q)-np.minimum.accumulate(q)
  ax[0].plot(tf,np.rad2deg(z['rv'][:,1]),c=co,ls='--',alpha=.5);ax[0].plot(t[::8],v[::8],c=co,label=tag);ax[1].plot(t[::4],a[::4],c=co);ax[2].plot(t[::8],j[::8],c=co);ax[3].plot(t,np.cumsum(abs(v)>vlim),c=co);ax[3].plot(t,np.cumsum(abs(a)>alim),c=co,ls='--');ax[4].plot(t,exc,c=co);ax[5].plot(tf,z['f'],c=co);ax[6].plot(tf,np.r_[0,np.cumsum(z['f'][:-1]*np.diff(tf))],c=co);ax[7].plot(tf,np.linalg.norm(np.rad2deg(z['truth'][:,:2]-z['rq']),axis=1),c=co);ax[8].plot(tf,z['m'],c=co);ax[9].plot(tf,np.linalg.norm(z['allocator'],axis=1),c=co)
  r=next((x for x in repairs if x['candidate']['id']==tag),None)
  if r:
   for k,mark in enumerate(['|','o','x']):ax[10].scatter([e[['request','activation','splice'][k]] for e in r['events']],[k+.1*tags.index(tag)]*len(r['events']),c=co,marker=mark,s=18)
 for axis,label in zip(ax,['Knee dq deg/s actual/ref','Knee a deg/s²','Knee jerk deg/s³','High samples solid v / dash a','Cumulative knee excursion deg','Force N','Cumulative J_F N s','Tracking norm deg','Moment norm Nm','Allocator torque norm Nm','Repair request / activation / splice']):
  axis.set_ylabel(label);axis.grid(alpha=.2);axis.set_xlim(0,19.03)
  for e in repairs[0]['events']:
   if e['early']:axis.axvline(e['splice'],c='#009e73',ls=':',lw=.8)
 ax[3].axhline(np.ceil(.05*(len(Z[g+'_B']['t'])+400)),c='r',ls=':');ax[4].axhline(bm['dose']['excursion_deg'][1]+.5,c='r',ls=':');ax[0].legend(ncol=len(tags));ax[-1].set_xlabel('Complete task seconds; red levels = matched-B diagnostic bounds, original complete gates unchanged');fig.suptitle(g+' — early RETURN physical comparison; solid actual / dashed reference')
 fig.savefig(P/'figures'/(g+'_early_return_timeline.png'),dpi=140);plt.close(fig)
print(json.dumps(dict(status='PASS',rows=[dict(id=r['id'],JF=r['J_F_N_s'],qualified=r['all_original_qualifications'],failed=r['motion']['failed_requirements'],gain=r['motion']['gain_percent'],eligible=r.get('eligible_primary'),variation=r.get('delta_variation_vs_D',{}).get('full')) for r in rows])),flush=True)

