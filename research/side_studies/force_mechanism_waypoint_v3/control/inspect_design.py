from pathlib import Path
import json, numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');O=S/'adaptive_continuous_coordination_optimization_v1'
su=json.loads((O/'source/results/development_B0/summary.json').read_text());count={}
for lr in su['learning_records']:
 d=su['decisions'][lr['decision_index']];ph=d['phase'];slot=count.get(ph,0);count[ph]=slot+1
 sc=lr['selected_plan']['schedule']
 print(ph,slot,'request_task',round(d['decision_request_time_s']-10.05,4),'duration',sc.get('duration_s'),'target_deg',np.degrees(sc['target_q_rad']).round(3).tolist(),'keys',list(sc) if slot==3 else '')
 if ph=='OUTBOUND' and slot==3:print('DESIGN_SCHEDULE',json.dumps(sc))
f=O/'source/stages/stage4_adaptive_control/src/traction_mpc_stage4/estimator_v2.py';s=f.read_text().splitlines()
for lo,hi in [(143,173),(768,803)]:print('\n'.join(f'{i+1}:{s[i]}' for i in range(lo-1,hi)))
print('fixture', (O/'tests/fixture.py').read_text()[:2500])
