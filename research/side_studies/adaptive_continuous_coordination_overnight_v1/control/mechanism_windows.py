from pathlib import Path
import json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];j=json.loads((P/'DIAGNOSTIC_RESULTS.json').read_text());ids=[r['id'] for r in j['runs'][:2]];allrows=[]
for ident in ids:
 z=np.load(P/'audit'/(ident+'_diagnostic.npz'));t=z['t'];nt=z['nt'];rows=[]
 for lo in np.arange(0,19,.25):
  hi=min(lo+.25,19.03);it=(t>=lo)&(t<hi);ix=(nt>=lo)&(nt<hi)
  if not it.any() or not ix.any():continue
  tvv=np.interp(hi,nt,z['tvv'])-np.interp(lo,nt,z['tvv']);tva=np.interp(hi,nt,z['tva'])-np.interp(lo,nt,z['tva']);jf=np.interp(hi,t,z['I'])-np.interp(lo,t,z['I'])
  rows.append(dict(start_s=lo,end_s=hi,phase=str(z['phase'][np.flatnonzero(it)[0]]),force_mean_N=jf/(hi-lo),moment_mean_Nm=float(z['M'][it].mean()),speed_L1_mean_deg_s=float(np.rad2deg(np.abs(z['nv'][ix])).sum(axis=1).mean()),acceleration_L1_mean_deg_s2=float(np.rad2deg(np.abs(z['na'][ix])).sum(axis=1).mean()),TV_v_rad_s=tvv,TV_a_rad_s2=tva,mean_q_deg=np.rad2deg(z['nq'][ix]).mean(axis=0).tolist()))
 correlations={}
 for ph in ['OUTBOUND','RETURN']:
  phrows=[r for r in rows if r['phase']==ph];F=np.array([r['force_mean_N'] for r in phrows]);correlations[ph]={key:float(np.corrcoef(F,[r[key] for r in phrows])[0,1]) for key in ['moment_mean_Nm','speed_L1_mean_deg_s','acceleration_L1_mean_deg_s2','TV_a_rad_s2']}
 acc=np.median([r['acceleration_L1_mean_deg_s2'] for r in rows if r['phase']!='HOLD']);highforce=np.quantile([r['force_mean_N'] for r in rows],.75)
 highstatic=[r for r in rows if r['force_mean_N']>=highforce and r['acceleration_L1_mean_deg_s2']<=acc]
 allrows.append(dict(id=ident,bin_width_s=.25,rows=rows,correlations=correlations,high_force_lower_acceleration_windows=highstatic,thresholds=dict(high_force_N=highforce,low_acceleration_deg_s2=acc),classification='CORRELATIONAL',causality='No mechanism isolation, no posture/gravity causal attribution'))
(P/'audit/FORCE_MOTION_WINDOWS.json').write_text(json.dumps(dict(runs=allrows),indent=2));print(json.dumps([dict(id=x['id'],correlations=x['correlations'],high_force_lower_acceleration_windows=x['high_force_lower_acceleration_windows'][:5]) for x in allrows]),flush=True)
