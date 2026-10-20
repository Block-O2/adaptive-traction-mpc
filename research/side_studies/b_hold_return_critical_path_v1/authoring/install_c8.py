from pathlib import Path
import json,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
shutil.copy2(W/'hold_static_mechanics.py',S/'code/hold_static_mechanics.py')
for name in ('fast_runtime.py','fast_task_ipc.py'):
 p=S/'code'/name;shutil.copy2(p,S/'versions'/('C7_'+name))
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('hold_endpoint_handoff'"," flags=flags+(('hold_static_mechanics',cfg.get('hold_static_mechanics',False)),)\n flags=flags+(('hold_endpoint_handoff'",1)
needle=" if cfg.get('native_backend'):"
t=t.replace(needle," if cfg.get('hold_static_mechanics') and cfg['execution_mode']!='SCIENTIFIC_SIMULATION':\n  import os\n  os.environ['FAST_HOLD_STATIC_MECHANICS']='C8'\n"+needle,1);p.write_text(t)
p=S/'code/fast_task_ipc.py';t=p.read_text()
t=t.replace(" packet(sock,0,ready)\n", " if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':\n  import hold_static_mechanics\n  hold_static_mechanics.install()\n packet(sock,0,ready)\n",1)
t=t.replace("  try:packet(sock,identity,result)","  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':result['hold_static_mechanics']=hold_static_mechanics.evidence()\n  try:packet(sock,identity,result)",1)
t=t.replace(" sock.close()\nclass ReadyFuture", "  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8' and 'value' in result:\n   hold_static_mechanics.prepare(payload,result['value'])\n sock.close()\nclass ReadyFuture",1)
t=t.replace("  if self.value.get('fault_injection'):ROWS[-1]['fault_injection']=self.value['fault_injection']", "  if self.value.get('hold_static_mechanics'):ROWS[-1]['hold_static_mechanics']=self.value['hold_static_mechanics']\n  if self.value.get('fault_injection'):ROWS[-1]['fault_injection']=self.value['fault_injection']",1)
p.write_text(t)
for name,mode,base,diag in [('005_C8_science_nominal','SCIENTIFIC_SIMULATION','001_C7_science_nominal',False),('006_C8_science_deviation','SCIENTIFIC_SIMULATION','002_C7_science_deviation',False),('007_C8_host_nominal_diagnostic','REALTIME_CHARACTERIZATION','003_C7_host_nominal_diagnostic',True),('008_C8_host_deviation_diagnostic','REALTIME_CHARACTERIZATION','004_C7_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,execution_mode=mode,fast_version=cfg['fast_version']+'_C8',hold_static_mechanics=True,critical_trace=diag,dependencies=[],required_gates=['output/C8_LOCAL_EQUIVALENCE.json'])
 if mode!='SCIENTIFIC_SIMULATION':cfg.update(dependencies=['005_C8_science_nominal','006_C8_science_deviation'],required_gates=cfg['required_gates']+['versions/005_C8_science_nominal_SCI_GATE.json','versions/006_C8_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C8 registered. No physical dispatch.')
