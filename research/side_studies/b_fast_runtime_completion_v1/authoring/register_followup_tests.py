from pathlib import Path
import json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');base=json.loads((S/'queue/062_N13_S2_science_nominal.json').read_text());configs=[]
prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]}
science=base|dict(id='067_N13_S2_science_deviation',seed=2026100623,prefix=prefix,dependencies=['062_N13_S2_science_nominal'],required_gates=['versions/062_N13_S2_science_nominal_SCI_GATE.json'])
configs.append(science)
for n in (68,69):
 configs.append(base|dict(id=f'{n:03d}_N13_S2_legal_host',seed=2026100700+n,prefix=prefix,execution_mode='REALTIME_CHARACTERIZATION',dependencies=[science['id']],required_gates=['versions/067_N13_S2_science_deviation_SCI_GATE.json']))
faults=[(70,'COMMISSIONING','worker_delay',30),(71,'COMMISSIONING','expired_result',120),(72,'COMMISSIONING','explicit_native_rejection',None),(73,'TASK','worker_delay',30),(74,'TASK','expired_result',120),(75,'TASK','model_version_mismatch',None),(76,'TASK','explicit_native_rejection',None)]
for n,stage,kind,delay in faults:
 fault=dict(stage=stage,kind=kind,request_id=3 if stage=='COMMISSIONING' else 6)
 if stage=='TASK':fault['packet_identity']=1
 if delay is not None:fault['delay_ms']=delay
 configs.append(base|dict(id=f'{n:03d}_{stage}_{kind}',seed=2026100700+n,prefix={},execution_mode='REALTIME_CHARACTERIZATION',fault_injection=fault,dependencies=['062_N13_S2_science_nominal'],required_gates=['versions/062_N13_S2_science_nominal_SCI_GATE.json','output/FAULT_INJECTION_LOCAL_REGRESSION.json'],series='registered_bounded_fault_diagnostic'))
for cfg in configs:
 p=S/'queue'/(cfg['id']+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n')
out=dict(id='S2_LEGAL_AND_BOUNDED_FAULTS',registered_unix=time.time(),configs=[str(S/'queue'/(c['id']+'.json')) for c in configs],original_frozen_fault_protocol=str(S/'versions/RUNTIME_FUNCTIONAL_CHECKS.json'),commissioning_model_mismatch=dict(status='NOT_APPLICABLE_SOURCE_INTERFACE',request_id=3,reason='Original commissioning target selector carries no versioned worker mechanics-proof identity; cannot claim TASK-style model-key injection at this original ID. Retain original protocol and record this interface limitation; add separately named TASK6/packet1 test.'),TASK_request_mapping='Prospective original TASK request6 corresponds to DirectExecutor packet1; verify exact original request binding before dispatch, never retimestamp.',known_invalid_action_execution_allowed=False,no_live_model_mutation=True,thresholds_unchanged=True,no_new_fallback=True,no_Q_or_learning=True,expected_failures_must_remain_failed=True)
p=S/'versions/S2_FOLLOWUP_TEST_REGISTRATION.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print('REGISTERED',len(configs),'distinct trials')
