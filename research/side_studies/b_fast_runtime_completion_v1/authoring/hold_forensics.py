from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
ident=sys.argv[1];summary=json.loads((S/'source/results'/ident/'summary.json').read_text());m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text())
print('TASK',json.dumps(summary['task'],indent=2)[:6000])
for row in summary['decisions']:
 if row.get('phase')=='HOLD':print('HOLD_DECISION',json.dumps(row,indent=2)[:5500])
for row in summary['learning_records']:
 if row.get('selected_plan',{}).get('phase')=='HOLD' or row.get('selected_plan',{}).get('candidate',{}).get('phase')=='HOLD':print('HOLD_LEARNING',json.dumps(row,indent=2)[:1800])
requests={row['timing_request_id'] for row in summary['decisions'] if row.get('phase')=='HOLD'}
print('HOLD_REQUESTS',json.dumps([r for r in m['native_requests'] if r['request_id'] in requests],indent=2))
t=(S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py').read_text()
print('CAPTURE_KEYS','\n'.join(l for l in t.splitlines() if 'sensor_task_clock' in l or 'reference_governor' in l))
