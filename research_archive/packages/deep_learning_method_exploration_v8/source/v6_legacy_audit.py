from pathlib import Path
import json,sys,os,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5'
def put(n,d):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
features=[];risk=[]
for phase,suffix in [('OUTBOUND','O'),('RETURN','R')]:
 model=json.loads((V/'models'/f'CRITIC_COST{suffix}_{phase}.json').read_text());rows=[]
 for g in ['TAIL'+suffix+'1','TAIL'+suffix+'2']:
  rows.extend([r for r in json.loads((V/'models'/f'{g}_TAIL_LABELS.json').read_text()) if r['horizon_s']==.5])
 X=np.array([r['features'] for r in rows]);names=rows[0]['feature_names'];mins=X.min(0);maxs=X.max(0);std=X.std(0)
 test=[r for r in json.loads((V/'models'/f'TAIL{suffix}T_TAIL_LABELS.json').read_text()) if r['horizon_s']==.5]
 T=np.array([r['features'] for r in test]);features.append({'phase':phase,'rows':len(rows),'per_feature':[{'name':n,'min':float(mins[i]),'max':float(maxs[i]),'std':float(std[i]),'constant':bool(maxs[i]-mins[i]<=1e-8),'old_scale':model['x_scale'][i],'test_min':float(T[:,i].min()),'test_max':float(T[:,i].max()),'test_center_shift_scaled':float(abs(T[:,i].mean()-X[:,i].mean())/model['x_scale'][i])} for i,n in enumerate(names)]})
for g in ['TAILO1','TAILO2','TAILOT','TAILR1','TAILR2','TAILRT','TAILRESCUE01']:
 f=V/'models'/f'{g}_TAIL_LABELS.json'
 if not f.exists():continue
 B=json.loads((V/'runtime/reports'/f'{g}_B_MEASURED.json').read_text());lim={k:np.array(B['motion']['raw']['full'][k]['max_abs'])*1.1 for k in ['velocity_deg_s','acceleration_deg_s2','jerk_deg_s3']}
 for row in json.loads(f.read_text()):
  if row['horizon_s']!=.5:continue
  ident=row['id'];ch=json.loads((V/'history'/f'{ident}_CAUSAL_HISTORY.json').read_text());ch=[r for r in ch if r['time_s']<=row['causal_physical_s']+1e-9];t=np.array([x['time_s'] for x in ch]);a=np.array([x['estimated_q_dq'] for x in ch]);v=a[:,2:];dt=np.diff(t);ac=np.diff(v,axis=0)/dt[:,None];jk=np.diff(ac,axis=0)/dt[1:,None]
  causal=np.r_[np.max(abs(v),0),np.max(abs(ac),0),np.max(abs(jk),0),np.ptp(a[:,:2],0)]
  with np.load(V/'runtime/motion_series'/f'{ident}.npz') as z:
   use=z['time_s']<=row['causal_physical_s']-.001
   ratios=np.r_[np.max(abs(np.rad2deg(z['true_dq_rad_s'][use])),0)/lim['velocity_deg_s'],np.max(abs(np.rad2deg(z['acceleration_rad_s2'][use])),0)/lim['acceleration_deg_s2'],np.max(abs(np.rad2deg(z['jerk_rad_s3'][use])),0)/lim['jerk_deg_s3']]
  risk.append({'id':ident,'group':g,'phase':'RETURN' if g.startswith('TAILR') and not g.startswith('TAILRESCUE') else 'OUTBOUND','features':causal.tolist(),'feature_names':['estimated_local_vmax_hip','estimated_local_vmax_knee','estimated_local_amax_hip','estimated_local_amax_knee','estimated_local_jmax_hip','estimated_local_jmax_knee','estimated_local_excursion_hip','estimated_local_excursion_knee'],'available_history_start_s':float(t[0]),'available_at_s':row['causal_physical_s'],'history_scope':'recorded causal stream from fork only; not full-task cumulative history','truth_used_in_features':False,'labels_evaluation_only':{'full_qualified':row['qualified'],'already_native_peak_failed':bool(np.max(ratios)>1+1e-7),'max_native_peak_ratio_by_H':float(np.max(ratios))},'continuation_policy':row['continuation_policy']})
put('analysis/V5_FEATURE_DISTRIBUTIONS.json',features);put('data/LEGACY_B_CAUSAL_RISK_ROWS.json',risk)
put('analysis/LEGACY_RISK_COVERAGE.json',{'rows':len(risk),'full_failures':[r['id'] for r in risk if not r['labels_evaluation_only']['full_qualified']],'irreversible_peak_failures_by_H':[r['id'] for r in risk if r['labels_evaluation_only']['already_native_peak_failed']],'scope':'historical exposed data audit; no new independent validation; no cost labels mixed across continuation policies','by_H_true_peaks_are_labels_not_model_inputs':True})
print('LEGACY_AUDIT',len(risk),'failures',sum(not r['labels_evaluation_only']['full_qualified'] for r in risk),'already peak failed',sum(r['labels_evaluation_only']['already_native_peak_failed'] for r in risk),flush=True)
