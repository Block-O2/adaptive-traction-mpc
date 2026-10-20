from pathlib import Path
import os,json,time,hashlib,copy
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def series(ident):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');ix=tr['stage']=='TASK';origin=tr['time_s'][ix][0]
 return dict(t=z['time_s']-origin,q=z['true_q_rad'],v=z['true_dq_rad_s'],a=z['acceleration_rad_s2'],j=z['jerk_rad_s3'],phase=z['phase'],tf=tr['time_s'][ix]-origin,f=np.linalg.norm(tr['physical_cuff_force_world_n'][ix],axis=1),rq=tr['reference_q_rad'][ix],rv=tr['reference_dq_rad_s'][ix])
def variations(z):
 return {ph:{'TV_v':float(np.linalg.norm(np.diff(z['v'][ix],axis=0),axis=1).sum()),'TV_a':float(np.linalg.norm(np.diff(z['a'][ix],axis=0),axis=1).sum()),'jerk_RMS':float(np.sqrt(np.mean(np.sum(z['j'][ix]**2,axis=1))))} for ph,ix in [('full',np.ones(len(z['t']),bool))]+[(ph,z['phase']==ph) for ph in ['OUTBOUND','HOLD','RETURN']]}
groups=[g for g in ['W1','R0','O0','W2'] if (P/(g+'_RESULTS.json')).exists()];rows=[];M={};Z={};V={}
for g in groups:
 for r in read(g+'_RESULTS.json')['rows']:
  ident=r['id'];m=read('reports/'+ident+'_MEASURED.json');M[ident]=m;z=series(ident);Z[ident]=z;V[ident]=variations(z)
  row=copy.deepcopy(r);row['complete_metrics']=m;row['actual_variations']=V[ident]
  if r['candidate']['id'].startswith('D'):
   tz=Z[g+'_T'];tm=M[g+'_T'];tv=V[g+'_T'];su=read('source/results/'+ident+'/summary.json');pe=[]
   for lr in su['learning_records']:
    p=lr['selected_plan']['execution_screen'].get('second_round_posture')
    if p:pe.append(dict(decision_index=lr['decision_index'],request_task_s=lr['request_time_s']-z['t'][0]-(np.load(P/'motion_series'/(ident+'.npz'))['time_s'][0]),activation_task_s=lr['start_time_s']-(np.load(P/'motion_series'/(ident+'.npz'))['time_s'][0]),metadata=p))
   first=min([p['request_task_s'] for p in pe],default=0.);pre=z['t']<first-1e-9
   delta={ph:{k:V[ident][ph][k]/tv[ph][k]-1 for k in ['TV_v','TV_a','jerk_RMS']} for ph in V[ident]}
   detail=[]
   for key,sig in [('velocity_deg_s','v'),('acceleration_deg_s2','a'),('jerk_deg_s3','j')]:
    limit=np.array(M[g+'_B']['motion']['raw']['full'][key]['p95_abs'])*1.1;signal=abs(np.rad2deg(z[sig]))
    for j in range(2):
     over=signal[:,j]>limit[j]+1e-7;idx=np.flatnonzero(over);parts=np.split(idx,np.flatnonzero(np.diff(idx)>1)+1) if len(idx) else []
     peak=int(np.argmax(signal[:,j]));detail.append(dict(signal=key,joint=['hip','knee'][j],limit=float(limit[j]),over_samples=int(over.sum()),peak_task_s=float(z['t'][peak]),peak_phase=str(z['phase'][peak]),peak_abs=float(signal[peak,j]),by_phase={ph:int(np.sum(over&(z['phase']==ph))) for ph in ['OUTBOUND','HOLD','RETURN']},intervals=[dict(start=float(z['t'][a[0]]),end=float(z['t'][a[-1]]),samples=len(a)) for a in parts]))
   qdeg=np.rad2deg(z['q']);exc=np.maximum.accumulate(qdeg,axis=0)-np.minimum.accumulate(qdeg,axis=0);be=np.array(M[g+'_B']['dose']['excursion_deg'])+.5
   row['excursion_failure_windows']=[dict(joint=['hip','knee'][j],first_exceeds_final_B_plus_tolerance=None if not np.any(exc[:,j]>be[j]+1e-7) else float(z['t'][np.flatnonzero(exc[:,j]>be[j]+1e-7)[0]]),max_task_s=float(z['t'][np.argmax(qdeg[:,j])]),min_task_s=float(z['t'][np.argmin(qdeg[:,j])])) for j in range(2)]
   row.update(delta_J_F_vs_T_N_s=m['J_F_N_s']-tm['J_F_N_s'],delta_variation_vs_T=delta,posture_events=pe,first_D_request_task_s=first,actual_q_change_max_deg=np.rad2deg(np.max(abs(z['q']-tz['q']),axis=0)).tolist(),actual_dq_change_max_deg_s=np.rad2deg(np.max(abs(z['v']-tz['v']),axis=0)).tolist(),pre_D_q_dq_exact=bool(np.array_equal(z['q'][pre],tz['q'][pre]) and np.array_equal(z['v'][pre],tz['v'][pre])),failure_window_diagnostics=detail,retains_force_vs_B_ge_1percent=r['motion']['gain_percent']>=1.,incremental_force_vs_T=m['J_F_N_s']<tm['J_F_N_s'])
  rows.append(row)
effects={}
for control,description in [('R0','remove RETURN0 while holding W1 OUTBOUND and seed'),('O0','replace OUTBOUND0 by V1 while holding W1 RETURN and seed')]:
 if control not in groups:continue
 effects[control]=dict(intervention=description,interpretation='conditional background-rule effect at W1 corner; no missing-corner interaction decomposition or latent mediator attribution',arms={})
 for arm in ['B','T','D']:
  a=Z[control+'_'+arm];b=Z['W1_'+arm];r=next(x for x in rows if x['id']==control+'_'+arm);w=next(x for x in rows if x['id']=='W1_'+arm)
  ix=a['t']<10.025-1e-8
  effects[control]['arms'][arm]=dict(pre_RETURN_q_dq_exact_equal=bool(np.array_equal(a['q'][ix],b['q'][ix]) and np.array_equal(a['v'][ix],b['v'][ix])),max_q_difference_deg_by_phase={ph:np.rad2deg(np.max(abs(a['q'][a['phase']==ph]-b['q'][b['phase']==ph]),axis=0)).tolist() for ph in ['OUTBOUND','HOLD','RETURN']},velocity_p95_ratio_to_own_B=(np.array(M[control+'_'+arm]['motion']['raw']['full']['velocity_deg_s']['p95_abs'])/np.array(M[control+'_B']['motion']['raw']['full']['velocity_deg_s']['p95_abs'])).tolist(),full_velocity_p95_deg_s=M[control+'_'+arm]['motion']['raw']['full']['velocity_deg_s']['p95_abs'],full_acceleration_p95_deg_s2=M[control+'_'+arm]['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'],full_excursion_deg=M[control+'_'+arm]['dose']['excursion_deg'],qualified=r['all_original_qualifications'],failed=r['motion']['failed_requirements'],gain_percent_vs_own_B=r['motion']['gain_percent'],D_vs_T_J_F_delta_N_s=r.get('delta_J_F_vs_T_N_s'),comparison_scope='no pooled absolute J_F ranking across backgrounds')
put('derived/BACKGROUND_CONTROL_EFFECTS.json',effects)
put('EXPERIMENT_RESULTS.json',dict(status='COMPLETE_REPORTED_PHYSICAL_RESULTS',created_unix=time.time(),evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',groups=groups,rows=rows,background_controls=effects,no_unmatched_force_ranking=True,historical_records_unchanged=True))
w=next(r for r in rows if r['id']=='W1_D');rep=next((r for r in rows if r['id']=='W1_D_repeat'),None);passed=w['all_original_qualifications'];qualified=[r['id'] for r in rows if r['candidate']['id']=='D' and r['all_original_qualifications']]
validation=dict(status='W1_D_PASS' if passed else 'W1_D_FAIL',W1_D_executed=True,W1_D_both_intents_executed=w['intervention_executed'],W1_D_all_original_qualifications=passed,W1_D_failed_requirements=w['motion']['failed_requirements'],W1_D_gain_vs_B_percent=w['motion']['gain_percent'],W1_D_delta_J_F_vs_T_N_s=w['delta_J_F_vs_T_N_s'],W1_D_retains_force_vs_B=w['retains_force_vs_B_ge_1percent'],W1_D_incremental_force_vs_T=w['incremental_force_vs_T'],W1_D_motion_variations_vs_T=w['delta_variation_vs_T']['full'],W1_repeat_executed=rep is not None,W1_repeat_gate=read('audit/W1_D_repeat_REPEAT_GATE.json') if (P/'audit/W1_D_repeat_REPEAT_GATE.json').exists() else None,W2_executed='W2' in groups,new_prefixes_with_fully_qualified_D=qualified,qualified_background_combinations=[x.split('_')[0] for x in qualified],independent_new_OUTBOUND_state_validation_established=bool('W2_D' in qualified),broader_baseline_promoted=False,scope='same Human; exact registered legal backgrounds; deterministic repeat adds no new state; W1 exposed before current protocol, fixed D selected previously',no_reselection=True,original_gates_unchanged=True)
put('VALIDATION_RESULTS.json',validation)
fig,ax=plt.subplots(7,1,figsize=(14,17),sharex=True,layout='constrained')
for arm,co in [('B','#666666'),('T','#0072b2'),('D','#cc3377')]:
 z=Z['W1_'+arm];m=M['W1_'+arm];ax[0].plot(z['tf'],z['f'],c=co,label=arm);ax[1].plot(z['tf'],np.r_[0,np.cumsum(z['f'][:-1]*np.diff(z['tf']))],c=co);ax[2].plot(z['t'][::6],np.rad2deg(z['v'][::6,1]),c=co);ax[3].plot(z['t'],np.rad2deg(z['a'][:,1]),c=co)
 q=np.rad2deg(z['q']);ax[4].plot(z['t'],(np.maximum.accumulate(q,axis=0)-np.minimum.accumulate(q,axis=0))[:,1],c=co);ax[5].plot(z['t'][::8],np.rad2deg(z['q'][::8,1]),c=co);ax[5].plot(z['tf'],np.rad2deg(z['rq'][:,1]),c=co,ls='--',alpha=.45);ax[6].plot(z['t'],np.r_[0,np.cumsum(np.linalg.norm(np.diff(z['v'],axis=0),axis=1))],c=co)
for axis,label in zip(ax,['Force N','Cumulative J_F N s','Knee velocity deg/s','Knee acceleration deg/s2','Cumulative knee excursion deg','Knee actual/ref deg','Cumulative velocity TV rad/s']):
 axis.set_ylabel(label);axis.grid(alpha=.2);axis.set_xlim(0,19.03)
 for t in [9.005,10.025]:axis.axvline(t,c='.5',lw=.7)
 for pe in w['posture_events']:axis.axvline(pe['request_task_s'],c='#6a3d9a',ls=':',lw=.8)
ax[0].legend(ncol=3);ax[-1].set_xlabel('Task seconds | dotted purple: actual frozen D posture requests');fig.suptitle('W1 matched B / frozen T / frozen D | '+validation['status']+'\nFull task, unchanged original qualification gates; actual Human solid / reference dashed')
fig.savefig(P/'figures/W1_D_qualification_timeline.png',dpi=140);plt.close(fig)
print(json.dumps(dict(validation=validation,summary=[dict(id=r['id'],JF=r['J_F_N_s'],qualified=r['all_original_qualifications'],failed=r['motion']['failed_requirements'],gain=r['motion']['gain_percent'],delta=r.get('delta_J_F_vs_T_N_s'),variation=r.get('delta_variation_vs_T',{}).get('full')) for r in rows])),flush=True)
