from pathlib import Path
import json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
for v in ('FAST_WORKER','FAST_WORKER_W2'):
 d=json.loads((S/'output'/('019_N4_V2_C2_science_deviation_TASK_'+v+'_REPLAY.json')).read_text())
 for r in d['rows']:
  print(v,r['phase'],r['worker_ms'],r['worker_metadata']['multirate_mechanics_certificates']['worker_exact_reuse'])
