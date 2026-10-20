from pathlib import Path
import json,time,shutil,py_compile
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
shutil.copy2(W/'handoff_budget.py',S/'code/handoff_budget.py')
py_compile.compile(str(S/'code/handoff_budget.py'),doraise=True)
base=json.loads((S/'queue/099_N13_S2_D2_C6_host_nominal.json').read_text());configs=[]
for n,science in ((102,True),(103,False)):
 ident=f'{n:03d}_N13_S2_D2_C6_handoff_'+('science' if science else 'host')
 cfg=base|dict(id=ident,seed=2026100700+n,attribution=True,front_attribution=True,handoff_exclusive_attribution=True,series='attribution_not_qualification',dependencies=['098_N13_S2_D2_C6_science_nominal'],required_gates=[],execution_mode='SCIENTIFIC_SIMULATION' if science else 'REALTIME_CHARACTERIZATION')
 if not science:cfg['dependencies']=['102_N13_S2_D2_C6_handoff_science'];cfg['required_gates']=['versions/102_N13_S2_D2_C6_handoff_science_SCI_GATE.json']
 p=S/'queue'/(ident+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');configs.append(str(p))
(S/'versions/HOLD_HANDOFF_ATTRIBUTION_PROTOCOL.json').write_text(json.dumps(dict(unix=time.time(),configs=configs,purpose='Resolve remaining attribution gap: simultaneous actual-cycle exclusive budgets and original sensor dwell proposal versus original reference-ready deferral. Original callable values unchanged; measured execution remains attribution-only, never used to qualify B.',Q=False,no_planner_authority_change=True),indent=2)+'\n')
print('HANDOFF_ATTRIBUTION_REGISTERED')
