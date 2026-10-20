"""Recompute each candidate's burden failures from native series, separately by phase."""
from pathlib import Path
import os,sys,json,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def read(n):return json.loads((P/n).read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False)+'\n')
def stats(a):return dict(max_abs=np.max(abs(a),axis=0),p95_abs=np.quantile(abs(a),.95,axis=0),rms=np.sqrt(np.mean(a*a,axis=0)))
allrows=[];limit=read('MOTION_ACCEPTANCE_PROTOCOL.json')['primary']['burden_ratio']
for group in ['reproduction','N2','development','U1','U2','U3']:
 if not (P/(group+'_DONE.json')).exists():continue
 rows=read(group+'_RESULTS.json')['rows']
 with np.load(P/'motion_series'/(group+'_B.npz')) as z:
  baseline={k:np.rad2deg(z[v]) for k,v in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2'),('jerk_deg_s3','jerk_rad_s3')]}
 for r in rows:
  ident=r['id'];m=read(r['metrics_path']);details=[];burden=[]
  with np.load(P/'motion_series'/(ident+'.npz')) as z:
   nt=z['time_s'];phase=z['phase'];signals={k:np.rad2deg(z[v]) for k,v in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2'),('jerk_deg_s3','jerk_rad_s3')]}
   for sig,metrics in [('velocity_deg_s',['max_abs','p95_abs','rms']),('acceleration_deg_s2',['max_abs','p95_abs','rms']),('jerk_deg_s3',['p95_abs','rms'])]:
    a=stats(signals[sig]);b=stats(baseline[sig])
    for met in metrics:
     ratios=a[met]/np.maximum(b[met],1e-12);recorded=np.asarray(r['motion']['burden_ratios'][sig+'/'+met]);assert np.max(abs(ratios-recorded))<1e-8
     if np.any(a[met]>b[met]*limit+1e-7):burden.append(sig+'/'+met)
     for joint in range(2):
      if a[met][joint]<=b[met][joint]*limit+1e-7:continue
      x=signals[sig][:,joint];peak=int(np.argmax(abs(x)));tail={ph:int(np.sum((phase==ph)&(abs(x)>b[met][joint]*limit))) for ph in ['OUTBOUND','HOLD','RETURN']}
      details.append(dict(requirement=sig+'/'+met,joint=['hip','knee'][joint],candidate=float(a[met][joint]),matched_B=float(b[met][joint]),ratio=float(ratios[joint]),absolute_peak=dict(task_s=float(nt[peak]-nt[0]),phase=str(phase[peak]),value=float(x[peak])),samples_above_full_B_limit_by_phase=tail,phase_statistics={ph:stats(signals[sig][phase==ph])[met].tolist() for ph in ['OUTBOUND','HOLD','RETURN']}))
  expected=[req for req in r['motion']['failed_requirements'] if '/' in req];assert sorted(set(burden))==sorted(expected),(ident,burden,expected)
  allrows.append(dict(id=ident,motion_pass=r['motion']['acceptance_pass'],failed_requirements=r['motion']['failed_requirements'],independent_raw_burden_reclassification_exact=True,details=details))
put('derived/ALL_CANDIDATE_FAILURE_DIAGNOSES.json',dict(status='PASS',unix=time.time(),rows=allrows,original_thresholds_unchanged=True,clinical_thresholds=False,new_physics=0,scope='Burden component independently reclassified from native series. Dose/tracking/moment and all raw native series themselves verified by separate independent_recompute.'))
print('CANDIDATE_DIAGNOSES_PASS',len(allrows))
