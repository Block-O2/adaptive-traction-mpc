from pathlib import Path
import sys,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
for ident in sys.argv[1:]:
 r=json.loads((S/'reports'/(ident+'_FAULT_REVIEW.json')).read_text())
 print(json.dumps(dict(id=ident,horizon=r.get('original_primary_horizon'),bridges=r.get('original_handoff_bridges'),fallback=[x for x in r.get('original_safe_fallback_events',[]) if x.get('request_id') in (7,None)][:8],next_request=r.get('following_original_request')),indent=2)[:6500])
