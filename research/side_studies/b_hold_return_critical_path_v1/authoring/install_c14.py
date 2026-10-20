from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
assert json.loads((S/'output/C14_LOCAL_EQUIVALENCE.json').read_text())['status']=='PASS'
shutil.copy2(S/'code/fast_runtime.py',S/'versions/C13_fast_runtime.py')
shutil.copy2(W/'hold_mapping_reuse.py',S/'code/hold_mapping_reuse.py')
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('task_decode_once'"," flags=flags+(('hold_mapping_reuse',cfg.get('hold_mapping_reuse',False)),)\n flags=flags+(('task_decode_once'",1)
t=t.replace("  if cfg.get('hold_request_collection'):\n   import hold_request_collection", "  if cfg.get('hold_mapping_reuse'):\n   import hold_mapping_reuse\n   hold_mapping_reuse.reset()\n  if cfg.get('hold_request_collection'):\n   import hold_request_collection",1)
t=t.replace(" if cfg.get('task_decode_once'):\n  import os"," if cfg.get('hold_mapping_reuse'):\n  import hold_mapping_reuse\n  hold_mapping_reuse.install()\n  hold_mapping_reuse.reset()\n if cfg.get('task_decode_once'):\n  import os",1)
t=t.replace(" if CFG.get('hold_request_collection'):\n  import hold_request_collection", " if CFG.get('hold_mapping_reuse'):\n  import hold_mapping_reuse\n  sc.save(ident+'_HOLD_MAPPING_REUSE.json',hold_mapping_reuse.evidence())\n if CFG.get('hold_request_collection'):\n  import hold_request_collection",1);ast.parse(t);p.write_text(t)
for name,base,diag in [('039_C14_science_nominal','035_C13_science_nominal',False),('040_C14_science_deviation','036_C13_science_deviation',False),('041_C14_host_nominal_diagnostic','037_C13_host_nominal_diagnostic',True),('042_C14_host_deviation_diagnostic','038_C13_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C14_PURE_HOLD_MAPPING',hold_mapping_reuse=True,dependencies=[],required_gates=['output/C14_LOCAL_EQUIVALENCE.json','output/C13_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['039_C14_science_nominal','040_C14_science_deviation'],required_gates=cfg['required_gates']+['versions/039_C14_science_nominal_SCI_GATE.json','versions/040_C14_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C14 pure HOLD mapping registered; original candidate/feedback/current admission retained')
