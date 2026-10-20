from pathlib import Path
import json,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
for name in ('fast_runtime.py','fast_task_ipc.py','hold_static_mechanics.py'):shutil.copy2(S/'code'/name,S/'versions'/('C9_'+name))
shutil.copy2(W/'hold_compact_key.py',S/'code/hold_compact_key.py')
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('hold_static_schedule'"," flags=flags+(('hold_compact_key',cfg.get('hold_compact_key',False)),)\n flags=flags+(('hold_static_schedule'",1)
t=t.replace(" if cfg.get('hold_static_schedule'):\n  import os"," if cfg.get('hold_compact_key'):\n  import os\n  os.environ['FAST_HOLD_COMPACT_KEY']='C10'\n if cfg.get('hold_static_schedule'):\n  import os",1);p.write_text(t)
p=S/'code/fast_task_ipc.py';t=p.read_text();t=t.replace("  hold_static_mechanics.install()\n packet(sock,0,ready)","  hold_static_mechanics.install()\n if os.environ.get('FAST_HOLD_COMPACT_KEY')=='C10':\n  import hold_compact_key\n  hold_compact_key.install()\n packet(sock,0,ready)",1);p.write_text(t)
for name,base,diag in [('019_C10_science_nominal','014_C9_science_nominal',False),('020_C10_science_deviation','015_C9_science_deviation',False),('021_C10_host_nominal_diagnostic','016_C9_host_nominal_diagnostic',True),('022_C10_host_deviation_diagnostic','017_C9_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C10',hold_compact_key=True,critical_trace=diag,dependencies=[],required_gates=['output/C10_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['019_C10_science_nominal','020_C10_science_deviation'],required_gates=cfg['required_gates']+['versions/019_C10_science_nominal_SCI_GATE.json','versions/020_C10_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C10 registered; no physics dispatched')
