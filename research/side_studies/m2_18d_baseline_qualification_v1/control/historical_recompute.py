"""Recompute archived four-condition negative results, without new physics."""
from pathlib import Path
import os,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];H=P.parent/'ihear_overnight_research_retrospective_v1'
def read(root,n):return json.loads((root/n).read_text())
def stats(x):return dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
def audit(ident):
 m=read(H,'reports/'+ident+'_MEASURED.json');folder=H/'source/results'/ident;summary=read(folder,'summary.json')
 with np.load(folder/'trace.npz') as z:
  sel=z['stage']=='TASK';t=z['time_s'][sel];f=np.linalg.norm(z['physical_cuff_force_world_n'][sel],axis=1);jf=float(f[:-1]@np.diff(t))
 assert abs(jf-m['J_F_N_s'])<1e-8
 transitions={r['to']:r['time_s'] for r in summary['task']['phase_transitions']};bounds=[t[0],transitions['HOLD'],transitions['RETURN'],transitions['COMPLETE']];phase={}
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  w=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));phase[ph]=float(f[:-1]@w);assert abs(phase[ph]-m['phase_cost']['phases'][ph]['J_F_N_s'])<1e-8
 with np.load(H/'motion_series'/(ident+'.npz')) as z:
  nt=z['time_s'];v=z['true_dq_rad_s'];a=np.gradient(v,nt,axis=0,edge_order=2);j=np.gradient(a,nt,axis=0,edge_order=2)
  for name,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]:
   for key,value in stats(np.rad2deg(x)).items():assert np.max(abs(value-np.asarray(m['motion']['raw']['full'][name][key])))<1e-8
 return dict(id=ident,J_F_N_s=jf,phase_J_F_N_s=phase,motion_statistics_recomputed=True),m
hist=read(H,'VALIDATION_RESULTS.json');rows=[]
for condition in ['V1','V2','V3','V4']:
 b,bm=audit(condition+'_B0_match');a,am=audit(condition+'_frozen_best');record=next(r for r in hist['rows'] if r['condition']==condition and r['arm']=='frozen_best')
 gain=100*(b['J_F_N_s']-a['J_F_N_s'])/b['J_F_N_s'];assert abs(gain-record['gain_percent'])<1e-10
 assert record['motion_pass'] is False
 pr=read(H,'MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];burden_fails=[]
 for sig,label in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
  for met in pr[label]:
   if np.any(np.asarray(am['motion']['raw']['full'][sig][met])>np.asarray(bm['motion']['raw']['full'][sig][met])*pr['burden_ratio']+1e-7):burden_fails.append(sig+'/'+met)
 assert all(r in record['failed_requirements'] for r in burden_fails)
 assert burden_fails,'Original motion fail must have a recomputable burden failure'
 rows.append(dict(condition=condition,B=b,primary=a,gain_percent=gain,reported_motion_pass=False,reported_failed_requirements=record['failed_requirements'],independently_recomputed_burden_failures=burden_fails,other_historical_fairness_failures_preserved_not_reclassified=True))
out=dict(status='PASS',evidence='HISTORICAL_RAW_RECOMPUTATION_NOT_NEW_PHYSICS',motion_PASS=0,denominator=4,rows=rows,method='original complete trace left quadrature/phase clipping and saved native-motion-series dq gradients, no runner/controller/plant import; non-burden fairness labels preserved as historical',new_physics_starts=0)
(P/'audit/HISTORICAL_FAILURE_RECOMPUTATION.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(status='PASS',historical_motion='0/4',recomputed_force_pairs=len(rows),new_physics_starts=0)))
