from pathlib import Path
import json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
cfg=json.loads((S/'queue/016_C9_host_nominal_diagnostic.json').read_text())
cfg.update(id='018_C9_hold_handoff_attribution',attribution=True,front_attribution=True,handoff_exclusive_attribution=True,capture_admission=True,qualifying=False,diagnostic_reason='Locate same-cycle admission/record/feedback work; no promotion from instrumentation')
p=S/'queue'/f"{cfg['id']}.json";assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print(cfg['id'])
