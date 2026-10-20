from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
cfg=json.loads((S/'queue/011_C8a_host_nominal_diagnostic.json').read_text());cfg.update(id='013_C8a_host_nominal_diagnostic_retry',prospective_retry_of='011_C8a_host_nominal_diagnostic',retry_reason='Prior commissioning stopped before HOLD/cache activation after observed165ms real service gap; same implementation, no guard/timestamp/science change',registered_unix=time.time())
p=S/'queue'/(cfg['id']+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');print(cfg['id'])
