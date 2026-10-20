from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');sys.path.insert(0,str(S/'code'))
from stream_runtime_evidence import array_items
O=S.parent/'b_fast_runtime_completion_v1' if len(sys.argv)<3 else S
ident=sys.argv[1];summary=json.loads((O/'source/results'/ident/'summary.json').read_text());trans=summary['task']['phase_transitions'];start=next(r['time_s'] for r in trans if r['to']=='HOLD');end=next(r['time_s'] for r in trans if r['from']=='HOLD')
for r in array_items(O/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'):
 t=r.get('start_physics_s',-1);p=r.get('reference_progress',{})
 if start<=t<=end+.01 and (t<start+.03 or abs(t-start-.51)<.04 or t>end-.04):
  print(json.dumps({k:r.get(k) for k in ('receipt_index','apply_ns','effective_activation_ns','start_physics_s','source_sample_time_s','reference_progress','applied','q_ref_rad','dq_ref_rad_s','actual_steps_at_prepare','availability_target_step','return_ns')}))
print('HOLD',end-start)
