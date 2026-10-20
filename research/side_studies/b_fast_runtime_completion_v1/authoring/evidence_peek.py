from pathlib import Path
import sys,json,collections
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
for ident in sys.argv[1:]:
 p=S/'reports'/(ident+'_FUNCTIONAL.json')
 if not p.exists():continue
 r=json.loads(p.read_text());l=r.get('legacy_result',{})
 out=dict(id=ident,functional=r['functional'],strict=r.get('legacy_strict'),failed_checks=[k for k,v in r.get('functional_checks',{}).items() if not v],service=r.get('service_gap_ms'),phase_times={k:v for k,v in l.items() if 'phase' in k or 'duration' in k},source_activation={k:v for k,v in l.items() if 'age' in k and not isinstance(v,list)},steps=r.get('actual_native_steps'),backlog=r.get('wall_physics',{}))
 for root in ('output',):
  p=S/root/(ident+'_COMPLETED_RESULT_SERVICE.json')
  if p.exists():out['completed_service_notifications']=json.loads(p.read_text())['rows']
 print(json.dumps(out))
