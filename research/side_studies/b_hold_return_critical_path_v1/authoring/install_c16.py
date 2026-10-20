from pathlib import Path
import json,shutil,ast
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
local=json.loads((S/'output/C16b_LOCAL_EQUIVALENCE.json').read_text());assert local['status']=='PASS'
assert all(r['reused_ms']<r['original_ms'] for r in local['rows']),'No local speed benefit; do not spend host attempts'
shutil.copy2(S/'code/fast_runtime.py',S/'versions/C15_fast_runtime.py');shutil.copy2(W/'hold_static_geometry.py',S/'code/hold_static_geometry.py')
p=S/'code/fast_runtime.py';t=p.read_text()
t=t.replace(" flags=flags+(('hold_mapping_reuse'", " flags=flags+(('hold_static_geometry',cfg.get('hold_static_geometry',False)),)\n flags=flags+(('hold_mapping_reuse'",1)
t=t.replace("  if cfg.get('hold_mapping_reuse'):","  if cfg.get('hold_static_geometry'):\n   import hold_static_geometry\n   hold_static_geometry.reset()\n  if cfg.get('hold_mapping_reuse'):",1)
t=t.replace(" if cfg.get('hold_mapping_reuse'):\n  import hold_mapping_reuse", " if cfg.get('hold_static_geometry'):\n  import hold_static_geometry\n  hold_static_geometry.install()\n  hold_static_geometry.reset()\n if cfg.get('hold_mapping_reuse'):\n  import hold_mapping_reuse",1)
t=t.replace(" if CFG.get('hold_mapping_reuse'):"," if CFG.get('hold_static_geometry'):\n  import hold_static_geometry\n  sc.save(ident+'_HOLD_STATIC_GEOMETRY.json',hold_static_geometry.evidence())\n if CFG.get('hold_mapping_reuse'):",1);ast.parse(t);p.write_text(t)
for name,base,host in [('047_C16_science_nominal','043_C15_science_nominal',False),('048_C16_science_deviation','044_C15_science_deviation',False),('049_C16_host_nominal_diagnostic','045_C15_host_nominal_diagnostic',True),('050_C16_host_deviation_diagnostic','046_C15_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C16b_STATIC_GEOMETRY_ONLY',hold_mapping_reuse=False,hold_static_geometry=True,dependencies=[],required_gates=['output/C16b_LOCAL_EQUIVALENCE.json','output/C13_LOCAL_EQUIVALENCE.json'])
 if host:cfg.update(dependencies=['047_C16_science_nominal','048_C16_science_deviation'],required_gates=cfg['required_gates']+['versions/047_C16_science_nominal_SCI_GATE.json','versions/048_C16_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C16 static geometry registered, complete original mapping and tiny reference velocities execute afresh.')
