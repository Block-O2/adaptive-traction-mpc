from pathlib import Path
import json,os,time,hashlib,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
from v6_observed_history import arrays,NAMES
from v6_observed_risk import fit,predict
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5'
def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
permissions={r['id']:r['permission_status'] for r in json.loads((V/'audit/ACTION_PERMISSION_ALL.json').read_text())['rows']};rows=[];sources=[];seen=set();start=time.perf_counter();usage0=resource.getrusage(resource.RUSAGE_SELF)
for rf in sorted((V/'attempts').glob('*_RESULT.json')):
 r=json.loads(rf.read_text());ident=r['id'];g=ident.rsplit('_',1)[0]
 if permissions.get(ident)!='PASS' or not r['complete']:continue
 # IDs contain underscores in action tags; use the original START ledger to recover job identity.
 events=[json.loads(l) for l in (V/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];record=next((e for e in events if e['event']=='START' and e['id']==ident),None)
 if record is None:continue
 g=record['group'];cfg=json.loads((V/'experiments'/f'{g}.json').read_text());bf=V/'runtime/reports'/f'{g}_B_MEASURED.json';nf=V/'runtime/motion_series'/f'{ident}.npz';raw=V/'runtime/source/results'/ident
 if not bf.exists() or not nf.exists():continue
 B=json.loads(bf.read_text());su=json.loads((raw/'summary.json').read_text());data=json.loads((V/'runtime/output'/f'{ident}_DATA.json').read_text());branch=data['branch_start'];phase_at_fork=branch['phase'];prefix=cfg['condition'].get('prefix',{});shared={'OUTBOUND':prefix.get('OUTBOUND',[])}
 if phase_at_fork=='RETURN':shared['RETURN']=prefix.get('RETURN',[])
 family=hashlib.sha256(json.dumps({'phase':phase_at_fork,'count':branch['count'],'shared_prefix':shared},sort_keys=True).encode()).hexdigest()[:16]
 with np.load(raw/'trace.npz') as z:
  use=z['stage']=='TASK';t=z['time_s'][use];est=z['estimated_human_state_rad_rad_s'][use];force=z['physical_cuff_force_world_n'][use];moment=z['physical_cuff_moment_world_nm'][use]
 with np.load(nf) as z:nt=z['time_s'];q=z['true_q_rad'];v=z['true_dq_rad_s'];acc=z['acceleration_rad_s2'];jerk=z['jerk_rad_s3']
 transitions=su['task']['phase_transitions'];times=sorted(set(float(lr['request_time_s'])+.5 for lr in su['learning_records'] if 'request_time_s' in lr));limits={k:np.array(B['motion']['raw']['full'][k]['max_abs'])*1.1 for k in ['velocity_deg_s','acceleration_deg_s2']};max_total_native_samples=int(np.ceil((B['dose']['duration_s']+.1)/.00025))+2
 for at in times:
  if at>t[-1]+1e-9 or at<t[0]+.05:continue
  phase='OUTBOUND'
  for tr in transitions:
   if tr['time_s']<=at+1e-9 and tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase=tr['to']
  features=arrays(t,est,force,moment,at,phase);cut=nt<=at-.001
  if cut.sum()<3:continue
  ratios=[]
  for key,sig in [('velocity_deg_s',v),('acceleration_deg_s2',acc),('jerk_deg_s3',jerk)]:
   values=np.rad2deg(sig[cut])
   if key in limits:ratios.extend((np.max(abs(values),axis=0)/limits[key]).tolist())
   rms_limit=np.array(B['motion']['raw']['full'][key]['rms'])*1.1;ratios.extend(np.sqrt(np.sum(values**2,axis=0)/max_total_native_samples/rms_limit**2).tolist())
   p95_limit=np.array(B['motion']['raw']['full'][key]['p95_abs'])*1.1;ratios.extend((np.sum(abs(values)>p95_limit,axis=0)/(np.ceil(.05*max_total_native_samples)+2)).tolist())
  ex=np.rad2deg(np.ptp(q[cut],axis=0));travel=np.rad2deg(np.sum(abs(np.diff(q[cut],axis=0)),axis=0));ratios.extend((ex/(np.array(B['dose']['excursion_deg'])+.5)).tolist());ratios.extend((travel/(np.array(B['dose']['cumulative_travel_deg'])*1.05)).tolist());ratios.extend([features[11]/(B['moment_integral_Nm_s']*1.25),features[12]/(B['force_peak_N']*1.05),features[13]/(B['moment_peak_Nm']*1.05)])
  target=bool(max(ratios)>1+1e-7)
  assert not (r['qualified'] and target),'IRREVERSIBLE_LABEL_CONTRADICTS_ORIGINAL_GATE:'+ident
  dedup=hashlib.sha256(np.asarray(features).round(10).tobytes()+str(target).encode()+family.encode()).hexdigest()
  if dedup in seen:continue
  seen.add(dedup);rows.append(dict(id=ident+'@'+format(at,'.6f'),trajectory=ident,job_group=g,state_family=family,phase=phase,at_physical_s=at,features=features,feature_names=NAMES,already_irreversible_failure=target,max_original_irreversible_ratio_by_H=max(ratios),truth_used_in_features=False,history='TASK observer and measured wrench through H only',label='original native maxima/excursion/travel and measured cumulative JM/peaks already exceeded by H; no future continuation cost'))
 sources.append(ident)
put('data/WHOLE_HISTORY_RISK_ROWS_V4.json',rows);model=fit(rows);cv=[]
for fam in sorted(set(r['state_family'] for r in rows)):
 train=[r for r in rows if r['state_family']!=fam];m=fit(train)
 for r in rows:
  if r['state_family']!=fam:continue
  prob=predict(m,{'history_risk_features':r['features']}) if m.get('available') else None;cv.append(dict(id=r['id'],family=fam,failed=r['already_irreversible_failure'],predicted_risk=prob,training_support_available=m.get('available',False),rejected=None if prob is None else prob>=.5))
usage=resource.getrusage(resource.RUSAGE_SELF);out=dict(model=model,frozen_unix=time.time(),schema='v6.expanded_observed_risk.freeze.v4',training_data_sha256=hashlib.sha256((P/'data/WHOLE_HISTORY_RISK_ROWS_V4.json').read_bytes()).hexdigest(),source_sha256={n:hashlib.sha256((P/'source'/n).read_bytes()).hexdigest() for n in ['v6_expand_risk_corpus.py','v6_observed_history.py','v6_observed_risk.py']},cross_validation=cv,source_trajectories=sources,rows=len(rows),state_families=len(set(r['state_family'] for r in rows)),positive_state_families=len(set(r['state_family'] for r in rows if r['already_irreversible_failure'])),fit_resources=dict(wall_s=time.perf_counter()-start,cpu_user_s=usage.ru_utime-usage0.ru_utime,cpu_system_s=usage.ru_stime-usage0.ru_stime,peak_rss_kib=usage.ru_maxrss,new_native_steps=0),test_outcomes_seen=False,scope='all old exposed raw; independent whole-state-family CV, then new frozen v6 tests; different future policies pooled only for already occurred risk, never cost')
put('models/WHOLE_HISTORY_RISK_V4_FROZEN.json',out);put('analysis/EXPANDED_RISK_COVERAGE_V4.json',{k:v for k,v in out.items() if k not in ['model','cross_validation']});print('EXPANDED_RISK',len(rows),'state families',out['state_families'],'positive families',out['positive_state_families'],'CV TP',sum(r['rejected'] is True and r['failed'] for r in cv),'FN',sum(r['rejected'] is False and r['failed'] for r in cv),'FP',sum(r['rejected'] is True and not r['failed'] for r in cv),'unknown',sum(r['rejected'] is None for r in cv),flush=True)
