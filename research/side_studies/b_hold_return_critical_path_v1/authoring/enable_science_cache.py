"""Version C8a: exercise the new pure cache in BOTH scientific gates."""
from pathlib import Path
import json,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values()),'Do not mutate active runtime sources'
for name in ('fast_runtime.py','fast_task_ipc.py','hold_static_mechanics.py'):shutil.copy2(S/'code'/name,S/'versions'/('C8_BYPASS_SCI_'+name))
p=S/'code/fast_runtime.py';t=p.read_text();old=" if cfg.get('hold_static_mechanics') and cfg['execution_mode']!='SCIENTIFIC_SIMULATION':";assert old in t;t=t.replace(old," if cfg.get('hold_static_mechanics'):",1);p.write_text(t)
p=S/'code/fast_task_ipc.py';t=p.read_text().replace("hold_static_mechanics.prepare(payload,result['value'])","hold_static_mechanics.prepare_guarded(payload,result['value'])");p.write_text(t)
shutil.copy2(W/'hold_static_mechanics.py',S/'code/hold_static_mechanics.py')
for name,base,diag in [('009_C8a_science_nominal','005_C8_science_nominal',False),('010_C8a_science_deviation','006_C8_science_deviation',False),('011_C8a_host_nominal_diagnostic','007_C8_host_nominal_diagnostic',True),('012_C8a_host_deviation_diagnostic','008_C8_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C8a_CACHE_ACTIVE_SCI',critical_trace=diag)
 if diag:cfg.update(dependencies=['009_C8a_science_nominal','010_C8a_science_deviation'],required_gates=['output/C8a_LOCAL_EQUIVALENCE.json','versions/009_C8a_science_nominal_SCI_GATE.json','versions/010_C8a_science_deviation_SCI_GATE.json'])
 else:cfg.update(dependencies=[],required_gates=['output/C8a_LOCAL_EQUIVALENCE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
(S/'versions/C8_SCI_BYPASS_DISCLOSURE.json').write_text(json.dumps(dict(status='SUPPLEMENT_REQUIRED',prior_ids=['005_C8_science_nominal','006_C8_science_deviation'],reason='The pure mechanics cache was disabled in scientific mode. Prior gates prove unchanged scheduling path but do not fully exercise cache. New009/010 enable cache while keeping C7 host-only; no host dispatch until active scientific gates pass.',never_promote_prior_bypass_as_cache_validation=True),indent=2)+'\n')
print('C8a cache active scientific registration complete')
