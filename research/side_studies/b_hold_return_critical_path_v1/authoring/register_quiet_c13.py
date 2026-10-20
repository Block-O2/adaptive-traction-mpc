from pathlib import Path
import json,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
shutil.copy2(S/'code/fast_runtime.py',S/'versions/C15_REJECTED_AFTER_HOST_fast_runtime.py')
shutil.copy2(S/'versions/C13_fast_runtime.py',S/'code/fast_runtime.py')
for name,base in [('047_C13_host_nominal_quiet','037_C13_host_nominal_diagnostic'),('048_C13_host_deviation_quiet','038_C13_host_deviation_diagnostic')]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,critical_trace=False,attribution=False,capture_task_inputs=False,capture_controller_full=False,capture_admission=False,handoff_exclusive_attribution=False,qualification_group='quiet_development_smoke',performance_context='Single physical owner; no simultaneous local model benchmarks or artifact scans')
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
out=dict(status='REGISTERED',version='C13 restored byte-identical runtime module',runtime_sha256=hashlib.sha256((S/'code/fast_runtime.py').read_bytes()).hexdigest(),math_or_control_changes=False,diagnostic_trace=False,C16={'equivalence':'PASS','local_speed_benefit':False,'physical_attempts':0},gate_authority=['035_C13_science_nominal_SCI_GATE.json','036_C13_science_deviation_SCI_GATE.json'])
(S/'reports/QUIET_C13_REGISTRATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
