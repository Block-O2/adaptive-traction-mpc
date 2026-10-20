from pathlib import Path
import sys,json,numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3');sys.path.insert(0,str(P/'control'))
from analyze_mechanism import load,put
cases={n:load(label) for n,label in [('B','B0'),('18D','18D')]};rows=[]
for n,z in cases.items():
 count={}
 for lr in z['su']['learning_records']:
  d=z['su']['decisions'][lr['decision_index']];ph=d['phase'];slot=count.get(ph,0);count[ph]=slot+1;sc=lr['selected_plan']['schedule']
  ev=next((e for e in z['events'] if e['kind']=='splice' and e.get('request_id')==d['timing_request_id']),None)
  rows.append(dict(case=n,phase=ph,slot=slot,request_task_s=d['decision_request_time_s']-10.05,activation_task_s=d['actual_schedule_start_physics_s']-10.05,splice_task_s=None if ev is None else ev['task_s'],duration_s=sc['duration_s'],target_q_deg=np.degrees(sc['target_q_rad']).tolist(),target_dq_deg_s=np.degrees(sc['target_dq_rad_s']).tolist(),executed_label=d['executed_label'],free_meta=lr['selected_plan'].get('execution_screen',{}).get('free_trajectory')))
put('derived/SCHEDULE_COMPARISON.json',dict(rows=rows,scope='Matched phase and ordinal request for supplementary mechanism inspection; primary plots retain task/absolute time. Differing slot times are not treated as independent interventions.'))
print(json.dumps([{k:v for k,v in r.items() if k!='free_meta'} for r in rows if r['slot'] in [2,3,4] and r['phase']!='HOLD'],indent=2))
