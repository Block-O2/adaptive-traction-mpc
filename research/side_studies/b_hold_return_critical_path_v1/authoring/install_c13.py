from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
for name in ('fast_task_owner.py','fast_runtime.py'):shutil.copy2(S/'code'/name,S/'versions'/('C12_'+name))
shutil.copy2(W/'task_decode_once.py',S/'code/task_decode_once.py')
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('hold_request_collection'"," flags=flags+(('task_decode_once',cfg.get('task_decode_once',False)),)\n flags=flags+(('hold_request_collection'",1)
t=t.replace(" if cfg.get('hold_request_collection'):\n  import os"," if cfg.get('task_decode_once'):\n  import os\n  os.environ['FAST_TASK_DECODE_ONCE']='C13'\n if cfg.get('hold_request_collection'):\n  import os",1);ast.parse(t);p.write_text(t)
p=S/'code/fast_task_owner.py';t=p.read_text();old=" ready.update(fast_task_owner='W1_EXACT_REQUEST_PROOF_REUSE'";new=" if os.environ.get('FAST_TASK_DECODE_ONCE')=='C13':\n  import task_decode_once\n  task_decode_once.install()\n ready.update(fast_task_owner='W1_EXACT_REQUEST_PROOF_REUSE'";assert t.count(old)==1;t=t.replace(old,new)
old="   value=op.execute_task_snapshot(payload);result={'value':value};native_finish=time.monotonic_ns()\n   result['multirate_mechanics_certificates']=admission_certificates.prepare(payload,value)"
new="   decoded=pickle.loads(payload) if os.environ.get('FAST_TASK_DECODE_ONCE')=='C13' else None\n   if decoded is not None:\n    import task_decode_once\n    value=task_decode_once.EXECUTE(decoded)\n   else:value=op.execute_task_snapshot(payload)\n   result={'value':value};native_finish=time.monotonic_ns()\n   result['multirate_mechanics_certificates']=(task_decode_once.PREPARE(decoded,value) if decoded is not None else admission_certificates.prepare(payload,value))\n   if decoded is not None:result['decode_once_evidence']=task_decode_once.EVIDENCE"
assert t.count(old)==1;t=t.replace(old,new);ast.parse(t);p.write_text(t)
for name,base,diag in [('035_C13_science_nominal','031_C12_science_nominal',False),('036_C13_science_deviation','032_C12_science_deviation',False),('037_C13_host_nominal_diagnostic','033_C12_host_nominal_diagnostic',True),('038_C13_host_deviation_diagnostic','034_C12_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C13_DECODE_ONCE',task_decode_once=True,dependencies=[],required_gates=['output/C13_LOCAL_EQUIVALENCE.json','output/C12_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['035_C13_science_nominal','036_C13_science_deviation'],required_gates=cfg['required_gates']+['versions/035_C13_science_nominal_SCI_GATE.json','versions/036_C13_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C13 registered; original bodies with only redundant decode replaced')
