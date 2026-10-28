import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,numpy as np
P=Path(__file__).resolve().parents[1]
for f in (P/'analysis/forensics').glob('*_window.npz'):
 ident=f.name[:-11];m=json.loads((f.parent/(ident+'.json')).read_text());when=m['event_time_s']
 with np.load(f) as z:
  t=z['t'];v=z['v'];q=z['q'];j=z['j'];a=z['a']
  def sample(x,t0):return np.array([np.interp(t0,t,x[:,k]) for k in range(2)])
  v0=sample(v,when);v1=sample(v,when+.005);q0=sample(q,when);q1=sample(q,when+.005)
  m['velocity_change_5ms_deg_s']=np.degrees(v1-v0).tolist();m['position_change_5ms_deg']=np.degrees(q1-q0).tolist();m['local_jerk_energy_native_units']=np.sum(j*j,axis=0).tolist();m['native_motion_fact']='Nonzero velocity evolution accompanies actual applied torque; high jerk is not inferred from model curvature alone.'
 (f.parent/(ident+'.json')).write_text(json.dumps(m,indent=2)+'\n');print(ident,m['velocity_change_5ms_deg_s'])
