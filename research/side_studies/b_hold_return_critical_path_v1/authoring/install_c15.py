from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
assert json.loads((S/'output/C15_LOCAL_EQUIVALENCE.json').read_text())['status']=='PASS'
shutil.copy2(S/'code/hold_mapping_reuse.py',S/'versions/C14_hold_mapping_reuse.py')
shutil.copy2(W/'hold_mapping_reuse_c15.py',S/'code/hold_mapping_reuse.py')
# Record all runtime source/dependency inputs at future STARTs, excluding outputs.
for name in ('fast_dispatch.py','cohort_dispatch.py'):
 p=S/'code'/name;shutil.copy2(p,S/'versions'/('C14_'+name));t=p.read_text()
 t=t.replace("('code','native','build')", "('source','deps','code','native','build')")
 t=t.replace("and '__pycache__' not in p.parts}","and '__pycache__' not in p.parts and 'results' not in p.relative_to(S).parts}")
 ast.parse(t);p.write_text(t)
for name,base,host in [('043_C15_science_nominal','039_C14_science_nominal',False),('044_C15_science_deviation','040_C14_science_deviation',False),('045_C15_host_nominal_diagnostic','041_C14_host_nominal_diagnostic',True),('046_C15_host_deviation_diagnostic','042_C14_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C15_NUMERIC_MAPPING_KEY',dependencies=[],required_gates=['output/C15_LOCAL_EQUIVALENCE.json','output/C13_LOCAL_EQUIVALENCE.json'])
 if host:cfg.update(dependencies=['043_C15_science_nominal','044_C15_science_deviation'],required_gates=cfg['required_gates']+['versions/043_C15_science_nominal_SCI_GATE.json','versions/044_C15_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C15 registered: label-independent pure numerics, actual candidate identity and original validation retained; future START manifests include source/deps.')
