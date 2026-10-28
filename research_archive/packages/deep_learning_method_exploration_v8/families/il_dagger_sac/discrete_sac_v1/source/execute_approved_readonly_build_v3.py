"""主审批准的一次只读builder资源wrapper；不含模型调用。"""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time
import traceback
sys.dont_write_bytecode=True
P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8');R=P/'families/il_dagger_sac/discrete_sac_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,value):
 with Path(p).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
 approval=R/'MAIN_APPROVAL_READONLY_BUILD_V3.json';a=load(approval)
 assert a['status']=='APPROVED_BY_MAIN_AGENT_FOR_READ_ONLY_DATA_BUILD'
 contract=P/a['proposed_contract_path'];assert sha(contract)==a['proposed_contract_sha256']=='d89404a459dee77080fb3f57480954b9e78850e70ed6466ddf94a64f7eebda7d'
 builder=P/a['builder_path'];assert sha(builder)==a['builder_sha256']=='12f8dfc93cdfd72c8e94a963f8bb444ebb9f830ec913da60f5cfcc691fc4e17c'
 assert sha(P/a['source_manifest_path'])==a['build_source_manifest_sha256']=='e64a86974b2e0d48e8bf61edd9057f6435406d5f4b44705da9035fe9f59f400b'
 assert sha(Path(__file__))==a['execution_wrapper_sha256']
 assert str(Path(sys.executable).resolve())==a['actual_interpreter']['resolved_binary'] and sha(Path(sys.executable).resolve())==a['actual_interpreter']['binary_sha256'] and sys.version==a['actual_interpreter']['sys_version']
 out=P/a['output_scope'];assert out.is_relative_to(R) and not out.exists(),'REFUSE_RETRY_OR_OVERWRITE';out.mkdir(parents=True)
 allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(allowed)})
 resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(600,600))
 initial=resource.getrusage(resource.RUSAGE_SELF);started=time.time();error=None;status='STARTED'
 write(out/'OWNER_START.json',{'started_unix':started,'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_KiB':initial.ru_maxrss,'PID':os.getpid(),'affinity':sorted(os.sched_getaffinity(0)),'approval_sha256':sha(approval),'wrapper_sha256':sha(__file__),'actual_interpreter':a['actual_interpreter'],'external_finite_timeout_s':600,'real_learner_init_forward_fit_physics':0})
 print('READONLY_BUILD_STARTED',started,flush=True)
 try:
  spec=importlib.util.spec_from_file_location('_approved_readonly_sac_dataset_builder_v3',builder);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  dataset,manifest=m.build(P,approval,P/a['source_manifest_path'])
  write(out/'SAC_OFFPOLICY_DATASET_V3.json',dataset);write(out/'SAC_OFFPOLICY_DATASET_MANIFEST_V3.json',manifest)
  counts={}
  for name,rows in dataset['cohorts'].items():
   counts[name]={'actual_rows':len(rows),'case_SHA_count':len({r['split_case_sha256_evaluation_only'] for r in rows}),'parent_fingerprint_count':len({r['parent_fingerprint_evaluation_only'] for r in rows}),'causal_feature_fingerprint_count':len({r['causal_features_sha256'] for r in rows}),'action_counts':dict(collections.Counter(dataset['action_contracts'][r['action_index']]['action']['family']+':'+str(r['action_index']) for r in rows)),'qualified_count':sum(r['original_qualified'] for r in rows),'complete_original_motion_failure_count':sum(not r['original_qualified'] for r in rows),'negative_failure_return_count':sum(r['canonical_terminal_return']==-1. for r in rows),'low_JF_failed_never_positive':all(r['canonical_terminal_return']==-1. for r in rows if not r['original_qualified']),'parameter_and_geometry_fingerprints':'See independent history_learning evaluation-only audit; never actor inputs'}
  write(out/'ACTUAL_COHORT_COUNTS_V3.json',{'cohorts':counts,'original_dataset_audit':dataset['audit'],'all_development_only':True,'sealed_reads':0,'real_model_calls':0,'new_physics':0})
  status='COMPLETED'
  print('READONLY_BUILD_COMPLETED',json.dumps({'dataset_sha256':sha(out/'SAC_OFFPOLICY_DATASET_V3.json'),'manifest_sha256':sha(out/'SAC_OFFPOLICY_DATASET_MANIFEST_V3.json'),'actual_counts':counts},ensure_ascii=False),flush=True)
 except BaseException as exc:
  error={'error':str(exc),'traceback':traceback.format_exc()};status='FAILED_NO_AUTOMATIC_RETRY';print('READONLY_BUILD_FAILED',str(exc),flush=True);raise
 finally:
  final=resource.getrusage(resource.RUSAGE_SELF)
  write(out/'BUILD_RESOURCE_AND_STATUS_V3.json',{'status':status,'error':error,'initial':{'wall_unix':started,'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_KiB':initial.ru_maxrss},'final':{'wall_unix':time.time(),'CPU_user_s':final.ru_utime,'CPU_system_s':final.ru_stime,'RSS_peak_KiB':final.ru_maxrss},'wall_s':time.time()-started,'CPU_user_s':final.ru_utime-initial.ru_utime,'CPU_system_s':final.ru_stime-initial.ru_stime,'real_learner_initializations':0,'model_forward':0,'model_fit':0,'new_physics':0,'automatic_retry':False,'mutable_CURRENT_or_active_H2_read':False,'sealed_reads':0})
if __name__=='__main__':main()
