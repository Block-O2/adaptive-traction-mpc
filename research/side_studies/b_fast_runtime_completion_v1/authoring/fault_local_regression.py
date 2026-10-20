from pathlib import Path
import sys,json,pickle,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import fault_injection as f
sleeps=[];old_sleep=f.time.sleep;f.time.sleep=sleeps.append
try:
 raw=dict(value='original',worker_start_ns=10,compute_finish_ns=20,research_model_invocations=21,multirate_mechanics_certificates=dict(proofs={'k':{'feasible':True}},model_sequence=353))
 for kind,delay in [('worker_delay',30),('expired_result',120)]:
  cfg=dict(kind=kind,stage='TASK',request_id=6,packet_identity=1,delay_ms=delay)
  assert f.task_result(raw,2,cfg) is raw
  out=f.task_result(raw,1,cfg);assert out['value']==raw['value'] and out['research_model_invocations']==21 and out['compute_finish_ns']>=out['fault_injection']['actual_finish_ns']
 assert sleeps==[.03,.12]
 cfg=dict(kind='model_version_mismatch',stage='TASK',request_id=6,packet_identity=1)
 out=f.task_result(raw,1,cfg);assert out['value']==raw['value'] and out['multirate_mechanics_certificates']['model_sequence']==354
 assert raw['multirate_mechanics_certificates']['model_sequence']==353 and 'k' in raw['multirate_mechanics_certificates']['proofs']
 assert 'k' not in out['multirate_mechanics_certificates']['proofs']
 raw=dict(payload=pickle.dumps((dict(feasible=True,attempts=[]),('original',),{})),worker_start_ns=10,proposal_ready_ns=20)
 out=f.altered_result(raw,dict(kind='explicit_native_rejection',stage='COMMISSIONING',request_id=3))
 value,args,kwargs=pickle.loads(out['payload']);assert not value['feasible'] and args==('original',)
 assert pickle.loads(raw['payload'])[0]['feasible']
 assert f.task_result(raw,1,None) is raw
finally:f.time.sleep=old_sleep
out=dict(status='PASS',cases=7,no_physics=True,source_unchanged=True,original_decision_unchanged_for_delay_model_fault=True,finite_delay_ms=[30,120],original_model_call_count_preserved=True,nonmatching_packet_untouched=True)
(S/'output/FAULT_INJECTION_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
