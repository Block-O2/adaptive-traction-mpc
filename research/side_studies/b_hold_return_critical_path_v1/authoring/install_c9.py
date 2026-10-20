from pathlib import Path
import json,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
for name in ('fast_runtime.py','fast_task_ipc.py','hold_static_mechanics.py'):shutil.copy2(S/'code'/name,S/'versions'/('C8a_'+name))
shutil.copy2(W/'hold_static_schedule.py',S/'code/hold_static_schedule.py')
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('hold_static_mechanics'"," flags=flags+(('hold_static_schedule',cfg.get('hold_static_schedule',False)),)\n flags=flags+(('hold_static_mechanics'",1)
t=t.replace(" if cfg.get('hold_static_mechanics'):\n  import os", " if cfg.get('hold_static_schedule'):\n  import os\n  os.environ['FAST_HOLD_STATIC_SCHEDULE']='C9'\n if cfg.get('hold_static_mechanics'):\n  import os",1);p.write_text(t)
p=S/'code/fast_task_ipc.py';t=p.read_text();t=t.replace(" if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':\n  import hold_static_mechanics", " if os.environ.get('FAST_HOLD_STATIC_SCHEDULE')=='C9':\n  import hold_static_schedule\n  hold_static_schedule.install()\n if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':\n  import hold_static_mechanics",1)
t=t.replace("  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':result['hold_static_mechanics']=hold_static_mechanics.evidence()", "  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':result['hold_static_mechanics']=hold_static_mechanics.evidence()\n  if os.environ.get('FAST_HOLD_STATIC_SCHEDULE')=='C9':result['hold_static_schedule']=hold_static_schedule.evidence()",1)
t=t.replace("  if self.value.get('hold_static_mechanics'):ROWS[-1]['hold_static_mechanics']=self.value['hold_static_mechanics']", "  if self.value.get('hold_static_mechanics'):ROWS[-1]['hold_static_mechanics']=self.value['hold_static_mechanics']\n  if self.value.get('hold_static_schedule'):ROWS[-1]['hold_static_schedule']=self.value['hold_static_schedule']",1);p.write_text(t)
for name,base,diag in [('014_C9_science_nominal','009_C8a_science_nominal',False),('015_C9_science_deviation','010_C8a_science_deviation',False),('016_C9_host_nominal_diagnostic','011_C8a_host_nominal_diagnostic',True),('017_C9_host_deviation_diagnostic','012_C8a_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C9',hold_static_schedule=True,critical_trace=diag,dependencies=[],required_gates=['output/C9_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['014_C9_science_nominal','015_C9_science_deviation'],required_gates=cfg['required_gates']+['versions/014_C9_science_nominal_SCI_GATE.json','versions/015_C9_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C9 registered; no physics dispatched')
