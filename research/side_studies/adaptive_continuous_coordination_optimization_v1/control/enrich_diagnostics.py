from pathlib import Path
import sys,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');sys.path.insert(0,str(P/'control'))
import numpy as np
from diagnostics import corr,put
def main():
 d=json.loads((P/'DIAGNOSTIC_RESULTS.json').read_text());rows=[]
 for rec in d['cases']:
  seriespath=next(Path(s) for s in rec['sources'] if '/motion_series/' in s);z=np.load(seriespath);t=z['time_s'];v=z['true_dq_rad_s'];a=np.gradient(v,t,axis=0,edge_order=2);speed=np.linalg.norm(v,axis=1);tt=t-t[0];det=v[:,0]*a[:,1]-v[:,1]*a[:,0];sens={}
  for eps in [1e-4,1e-3,1e-2]:
   k=det/(speed**2+eps**2)**1.5;c=np.r_[0,np.cumsum(abs(np.diff(k)))];values={}
   for w,win in rec['windows'].items():
    metrics=[float(np.interp(r['end_s'],tt,c)-np.interp(r['start_s'],tt,c)) for r in win]
    values[w]={ph:corr([r['J_F_N_s'] for r in win if ph=='ALL' or r['phase']==ph],[x for x,r in zip(metrics,win) if ph=='ALL' or r['phase']==ph]) for ph in ['ALL','OUTBOUND','RETURN']}
   sens[str(eps)]=values
  windows=rec['windows']['0.5'];n=max(1,int(np.ceil(len(windows)/4)));top_force=sorted(range(len(windows)),key=lambda i:windows[i]['J_F_N_s'],reverse=True)[:n];concentration={}
  for metric in ['speed_variation','velocity_TV','acceleration_RMS','acceleration_variation','jerk_RMS','curvature_TV']:
   top=sorted(range(len(windows)),key=lambda i:windows[i][metric],reverse=True)[:n];concentration[metric]=dict(top_quartile_motion_window_force_fraction=sum(windows[i]['J_F_N_s'] for i in top)/sum(r['J_F_N_s'] for r in windows),top_force_top_motion_overlap=len(set(top)&set(top_force)),top_window_count=n,total_window_count=len(windows))
  rows.append(dict(id=rec['id'],curvature_epsilon_correlations=sens,force_motion_concentration=concentration,high_force_windows=[windows[i] for i in top_force]))
 put('CORRELATION_SENSITIVITY.json',dict(cases=rows,filtering='none',nonsignificance='no independent-sample significance test for serial deterministic windows'))
 print('CORRELATION_ENRICHMENT',len(rows))
if __name__=='__main__':main()
