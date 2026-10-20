from pathlib import Path
import json,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
ident=sys.argv[1]
d=json.loads((S/'reports'/(ident+'_FUNCTIONAL.json')).read_text());print('REVIEW',json.dumps({k:v for k,v in d['legacy_result'].items() if k not in ('meaningful_plans','nontrivial_candidates','activation_requests')},indent=2)[:7500])
summary=json.loads((S/'source/results'/ident/'summary.json').read_text());print('TASK',json.dumps(summary['task'],indent=2)[:7000])
ids=[r['timing_request_id'] for r in summary['decisions'] if r.get('phase')=='HOLD']
m=json.loads((S/'output'/(ident+'_MULTIRATE.json')).read_text());print('HOLD_TIMING',json.dumps([r for r in m['native_requests'] if r['request_id'] in ids],indent=2))
if '--source' not in sys.argv:sys.exit(0)
text=(S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py').read_text().splitlines()
for i,l in enumerate(text):
 if 'snapshot_task_call(' in l or 'submit_task(' in l or ('_execute_interval(' in l and not l.startswith('def')) or 'next_control_tick(' in l:
  print('SOURCE',i+1);print('\n'.join(f'{j+1}: {text[j]}' for j in range(max(0,i-35),min(len(text),i+50))))
