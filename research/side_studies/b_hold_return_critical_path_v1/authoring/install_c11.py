from pathlib import Path
import json,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
p=S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py'
shutil.copy2(p,S/'versions/C10_runtime_coordination_residual_v2.py')
before=hashlib.sha256(p.read_bytes()).hexdigest();t=p.read_text()
old='''                else:
                    active_schedule = None
            if not online_timing and planning_wait is None'''
new='''                else:
                    active_schedule = None
                # Host-only orchestration. The helper cannot admit or execute a
                # result; the next original loop reads fresh current inputs.
                hold_collection_service = globals().get("_fast_hold_request_collection")
                if (not scientific and task_state.phase is TaskPhase.HOLD
                        and hold_collection_service is not None
                        and hold_collection_service(runtime, async_pending)):
                    continue
            if not online_timing and planning_wait is None'''
assert t.count(old)==1;t=t.replace(old,new);p.write_text(t)
(S/'versions/C11_SOURCE_CHANGE.json').write_text(json.dumps(dict(before_sha256=before,after_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),path=str(p),scope='One host-only bounded collection service after an actually issued original HOLD request; return to the unchanged original loop for fresh checks'),indent=2)+'\n')
for name in ('fast_runtime.py','fast_task_ipc.py'):shutil.copy2(S/'code'/name,S/'versions'/('C10_'+name))
shutil.copy2(W/'hold_request_collection.py',S/'code/hold_request_collection.py')
p=S/'code/fast_runtime.py';t=p.read_text();t=t.replace(" flags=flags+(('hold_compact_key'"," flags=flags+(('hold_request_collection',cfg.get('hold_request_collection',False)),)\n flags=flags+(('hold_compact_key'",1)
t=t.replace(" if cfg.get('hold_compact_key'):\n  import os"," if cfg.get('hold_request_collection'):\n  import hold_request_collection as collection,study_common as sc\n  collection.ROWS.clear()\n  sc.rt._fast_hold_request_collection=collection.observe if cfg['execution_mode']!='SCIENTIFIC_SIMULATION' else None\n if cfg.get('hold_compact_key'):\n  import os",1)
t=t.replace("  if cfg.get('hold_endpoint_handoff'):\n   import hold_endpoint_handoff", "  if cfg.get('hold_request_collection'):\n   import hold_request_collection\n   hold_request_collection.ROWS.clear()\n  if cfg.get('hold_endpoint_handoff'):\n   import hold_endpoint_handoff",1)
t=t.replace(" if CFG.get('hold_endpoint_handoff'):\n  import hold_endpoint_handoff"," if CFG.get('hold_request_collection'):\n  import hold_request_collection\n  sc.save(ident+'_HOLD_REQUEST_COLLECTION.json',dict(rows=hold_request_collection.ROWS,scientific_bypass=CFG['execution_mode']=='SCIENTIFIC_SIMULATION',original_guard_and_admission=True,no_result_authority_in_helper=True))\n if CFG.get('hold_endpoint_handoff'):\n  import hold_endpoint_handoff",1);p.write_text(t)
for name,base,diag in [('023_C11_science_nominal','019_C10_science_nominal',False),('024_C11_science_deviation','020_C10_science_deviation',False),('025_C11_host_nominal_diagnostic','021_C10_host_nominal_diagnostic',True),('026_C11_host_deviation_diagnostic','022_C10_host_deviation_diagnostic',True)]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=name,fast_version=cfg['fast_version']+'_C11',hold_request_collection=True,critical_trace=diag,dependencies=[],required_gates=['output/C11_LOCAL_EQUIVALENCE.json','output/C10_LOCAL_EQUIVALENCE.json'])
 if diag:cfg.update(dependencies=['023_C11_science_nominal','024_C11_science_deviation'],required_gates=cfg['required_gates']+['versions/023_C11_science_nominal_SCI_GATE.json','versions/024_C11_science_deviation_SCI_GATE.json'])
 p=S/'queue'/(name+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
print('C11 registered; no physics dispatched')
