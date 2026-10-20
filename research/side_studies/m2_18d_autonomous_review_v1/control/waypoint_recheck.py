"""Recheck important historical smoothing claims from raw force and native-derived series."""
from pathlib import Path
import os,json,time,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');W=P.parent/'m2_18d_waypoint_smoothing_overnight_v1'
records={r['id']:r for r in json.loads((W/'ALL_ANALYZED_RESULTS.json').read_text())['rows']};cache={}
ids=['development1_E0','development1_E_O_smooth','development1_E_R_smooth','development2_E0','development2_E_OR_smooth','development2_B0','development2_B_OR_smooth']
def load(ident):
 if ident in cache:return cache[ident]
 with np.load(W/'source/results'/ident/'trace.npz') as z:
  ix=z['stage']=='TASK';t=z['time_s'][ix];f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);truth=z['evaluation_only_human_state_rad_rad_s'][ix]
 with np.load(W/'series'/(ident+'.npz')) as z:nt=z['t'].copy();v=z['v'].copy();q=z['q'].copy();a=z['a'].copy();j=z['j'].copy()
 tt=t-t[0];assert np.max(abs(np.column_stack([np.interp(tt,nt,v[:,i]) for i in [0,1]])-truth[:,2:]))<1e-8
 assert np.max(abs(np.column_stack([np.interp(tt,nt,q[:,i]) for i in [0,1]])-truth[:,:2]))<1e-8
 assert np.max(abs(np.gradient(v,nt,axis=0,edge_order=2)-a))<1e-7
 assert np.max(abs(np.gradient(a,nt,axis=0,edge_order=2)-j))<1e-6
 jf=float(f[:-1]@np.diff(t));r=records[ident];assert abs(jf-r['J_F'])<1e-8
 tv=float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum());assert abs(tv-r['full_motion']['velocity_TV'])<1e-8
 cache[ident]=dict(t=tt,f=f,JF=jf,TV=tv);return cache[ident]
def integ(t,x,lo,hi):return float(x[:-1]@np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)))
out=[]
for ident in ids:
 r=records[ident];z=load(ident);b=load(r['matched_baseline']);assert np.allclose(z['t'],b['t'],atol=1e-8,rtol=0)
 delta=z['JF']-b['JF'];tvchange=100*(z['TV']/b['TV']-1);assert abs(tvchange-r['full_TV_v_change_percent'])<1e-8
 windows=[c['local_window_task_s'] for c in r['candidate'].get('changes',[])];support=sum(integ(z['t'],z['f']-b['f'],*iv) for iv in windows)
 out.append(dict(id=ident,matched_baseline=r['matched_baseline'],JF=z['JF'],full_delta_N_s=delta,full_combined_Euclidean_TV_change_percent=tvchange,support_delta_N_s=support,outside_support_delta_N_s=delta-support,reported_motion_pass=r['motion_pass'],raw_force_recomputed=True,native_derived_series_gradient_and_trace_mapping_rechecked=True))
(P/'audit/WAYPOINT_HISTORICAL_RECOMPUTATION.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),rows=out,new_physics=0,scope='Raw 5ms complete force left quadrature; stored native-derived motion series checked against 5ms actual trace and re-differentiated. Does not claim new full native/receipt audit of all old arms. Independent local arithmetic, no old package module imports or writes.'),indent=2)+'\n')
print('WAYPOINT_RECHECK_PASS',[(r['id'],r['full_delta_N_s'],r['full_combined_Euclidean_TV_change_percent']) for r in out])
