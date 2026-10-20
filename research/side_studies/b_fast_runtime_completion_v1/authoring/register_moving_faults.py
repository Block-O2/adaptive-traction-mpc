from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
base=json.loads((S/'queue/073_TASK_worker_delay.json').read_text());paths=[]
for n,kind,delay in ((85,'worker_delay',30),(86,'expired_result',120)):
 ident=f'{n:03d}_TASK7_moving_{kind}'
 cfg=base|dict(id=ident,seed=2026100700+n,series='moving_committed_prefix_bounded_fault',fault_injection=dict(stage='TASK',kind=kind,request_id=7,packet_identity=2,delay_ms=delay),committed_endpoint_service=False,readiness_service=False,required_gates=['versions/081_N13_S2_C5_science_nominal_SCI_GATE.json','output/FAULT_INJECTION_LOCAL_REGRESSION.json'])
 p=S/'queue'/(ident+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');paths.append(str(p))
out=dict(id='MOVING_TASK7_DIAGNOSTICS',registered_unix=time.time(),configs=paths,original_fault_protocol_preserved=True,addition='First TASK6 fault waits used an existing stationary handoff reference. TASK7/packet2 tests original moving committed prefix, finite delay/expiry, source age, executable horizon and original fallback authority.',exact_request_packet_mapping_required=True,known_invalid_action_write=False,new_fallback=False,no_Q_or_training=True,stop_each_run_on_original_native_safety_failure=True,run_next_after_BRAKE_INFEASIBLE_requires_root_cause=True,physics_budget=120)
p=S/'versions/MOVING_TASK7_FAULT_PROTOCOL.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print('MOVING_FAULTS_REGISTERED',len(paths))
