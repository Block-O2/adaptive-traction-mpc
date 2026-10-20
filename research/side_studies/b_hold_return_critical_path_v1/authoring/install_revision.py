from pathlib import Path
import json,shutil,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
O=S.parent/'b_fast_runtime_completion_v1'
for n in ('hold_endpoint_handoff.py','critical_trace.py','reconstruct.py','inspect_evidence.py'):shutil.copy2(W/n,S/'code'/n)
p=S/'code/fast_runtime.py';t=p.read_text()
assert 'hold_endpoint_handoff' not in t
t=t.replace(" flags=flags+(('handoff_exclusive_attribution'", " flags=flags+(('hold_endpoint_handoff',cfg.get('hold_endpoint_handoff',False)),('critical_trace',cfg.get('critical_trace',False)))\n flags=flags+(('handoff_exclusive_attribution'")
t=t.replace("  if cfg.get('committed_endpoint_service'):","  if cfg.get('hold_endpoint_handoff'):\n   import hold_endpoint_handoff\n   hold_endpoint_handoff.ROWS.clear()\n  if cfg.get('critical_trace'):\n   import critical_trace\n   critical_trace.ROWS.clear()\n  if cfg.get('committed_endpoint_service'):",1)
needle=" if cfg.get('capture_controller_full'):\n  import full_controller_replay"
t=t.replace(needle," if cfg.get('hold_endpoint_handoff') and cfg['execution_mode']!='SCIENTIFIC_SIMULATION':\n  import hold_endpoint_handoff\n  hold_endpoint_handoff.install()\n if cfg.get('critical_trace'):\n  import critical_trace\n  critical_trace.install()\n"+needle)
t=t.replace(" if CFG.get('handoff_exclusive_attribution'):"," if CFG.get('hold_endpoint_handoff'):\n  import hold_endpoint_handoff\n  sc.save(ident+'_HOLD_ENDPOINT_HANDOFF.json',dict(rows=hold_endpoint_handoff.ROWS,scientific_bypass=CFG['execution_mode']=='SCIENTIFIC_SIMULATION',original_completion_and_minimum_unchanged=True))\n if CFG.get('critical_trace'):\n  import critical_trace\n  critical_trace.finish(ident)\n if CFG.get('handoff_exclusive_attribution'):",1)
p.write_text(t)
nom=json.loads((O/'queue/099_N13_S2_D2_C6_host_nominal.json').read_text())
dev=json.loads((O/'queue/101_N13_S2_D2_C6_host_deviation.json').read_text())
for name,mode,base,diag in [('001_C7_science_nominal','SCIENTIFIC_SIMULATION',nom,False),('002_C7_science_deviation','SCIENTIFIC_SIMULATION',dev,False),('003_C7_host_nominal_diagnostic','REALTIME_CHARACTERIZATION',nom,True),('004_C7_host_deviation_diagnostic','REALTIME_CHARACTERIZATION',dev,True)]:
 cfg=dict(base,id=name,execution_mode=mode,fast_version=base['fast_version']+'_C7',dependencies=[],required_gates=[],hold_endpoint_handoff=True,critical_trace=diag)
 if mode!='SCIENTIFIC_SIMULATION':cfg.update(dependencies=['001_C7_science_nominal','002_C7_science_deviation'],required_gates=['output/C7_LOCAL_EQUIVALENCE.json','versions/001_C7_science_nominal_SCI_GATE.json','versions/002_C7_science_deviation_SCI_GATE.json'])
 else:cfg['required_gates']=['output/C7_LOCAL_EQUIVALENCE.json']
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('Installed C7, four preregistered inputs. No physics yet.')
