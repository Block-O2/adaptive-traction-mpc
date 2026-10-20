from pathlib import Path
import json,math
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
z=np.load(P/'motion_series/W1_D.npz');b=read('reports/W1_B_MEASURED.json');su=read('source/results/W1_D/summary.json');t=z['time_s']-z['time_s'][0];counts={};events=[]
for lr in su['learning_records']:
 d=su['decisions'][lr['decision_index']];ph=d['phase'];i=counts.get(ph,0);counts[ph]=i+1
 if ph=='RETURN':events.append(dict(slot=i,request=d['decision_request_time_s']-z['time_s'][0],activation=lr['start_time_s']-z['time_s'][0]))
cuts=[next(e for e in events if e['slot']==i) for i in [2,5]];Nmax=len(t)+400;max_count=math.ceil(.05*Nmax);out=[]
for e in cuts:
 pre=t<=e['request']+1e-9;stats={}
 for key,signal in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2')]:
  limit=np.array(b['motion']['raw']['full'][key]['p95_abs'])*1.1+1e-7;over=abs(np.rad2deg(z[signal]))>limit;cnt=over[pre].sum(axis=0)
  stats[key]=dict(counts=cnt.tolist(),limit=limit.tolist(),max_count_original_duration_tolerance=max_count,irreversible_p95_failure=(cnt>max_count).tolist())
 exc=np.rad2deg(np.ptp(z['true_q_rad'][pre],axis=0));be=np.array(b['dose']['excursion_deg'])+.5+1e-7
 out.append(dict(**e,p95=stats,prefix_excursion_deg=exc.tolist(),B_full_excursion_plus_tolerance_deg=be.tolist(),irreversible_excursion_failure=(exc>be).tolist()))
result=dict(status='OFFLINE_MATHEMATICAL_LOWER_BOUND',source='actual W1 D native q/dq under unchanged original gate and 0.1s full-duration tolerance',maximum_native_samples=Nmax,rows=out,interpretation='At RETURN2 the original bounds do not prove repair impossible. At terminal RETURN5, any flags true identify already accumulated burden that a strictly later-only intervention cannot erase. This is not an instantaneous new gate or proof of a unique causal mechanism.')
(P/'derived/W1_D_IRREVERSIBLE_PREFIX_BOUNDS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
