from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
for name in ('commissioning_owner.py','fast_runtime.py'):shutil.copy2(S/'code'/name,S/'versions'/('C11_STARTUP_FAILED_'+name))
p=S/'code/fast_runtime.py';t=p.read_text();old=" if cfg.get('hold_request_collection'):\n  import hold_request_collection as collection,study_common as sc";new=" if cfg.get('hold_request_collection'):\n  import os\n  os.environ['FAST_RUNTIME_SOURCE_VERSION']='C11a'\n  import hold_request_collection as collection,study_common as sc";assert t.count(old)==1;t=t.replace(old,new);ast.parse(t);p.write_text(t)
p=S/'code/commissioning_owner.py';t=p.read_text();old=" p=sc.STUDY/'versions'/(revision+'_INSTALLED_RUNTIME.py')";new=" import os\n source_version=os.environ.get('FAST_RUNTIME_SOURCE_VERSION','')\n p=sc.STUDY/'versions'/(revision+('_'+source_version if source_version else '')+'_INSTALLED_RUNTIME.py')";assert t.count(old)==1;t=t.replace(old,new);ast.parse(t);p.write_text(t)
gate=json.loads((S/'output/C11_LOCAL_EQUIVALENCE.json').read_text());gate.update(version='C11a',source_registration='Versioned generated runtime path; existing consistency check retained',physics_steps=0,model_API_calls=0)
(S/'output/C11a_LOCAL_EQUIVALENCE.json').write_text(json.dumps(gate,indent=2)+'\n')
for name,base,diag in [('027_C11a_science_nominal','023_C11_science_nominal',False),('028_C11a_science_deviation','024_C11_science_deviation',False),('029_C11a_host_nominal_diagnostic','025_C11_host_nominal_diagnostic',True),('030_C11a_host_deviation_diagnostic','026_C11_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C11a_SOURCE_REGISTRATION',dependencies=[],required_gates=['output/C11a_LOCAL_EQUIVALENCE.json','output/C10_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['027_C11a_science_nominal','028_C11a_science_deviation'],required_gates=cfg['required_gates']+['versions/027_C11a_science_nominal_SCI_GATE.json','versions/028_C11a_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C11a source registration repaired; previous startup failure retained')
