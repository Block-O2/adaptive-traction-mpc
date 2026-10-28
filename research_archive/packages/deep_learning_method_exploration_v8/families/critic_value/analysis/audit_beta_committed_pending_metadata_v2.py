"""仅JSON/源码元数据审计：0learner import/init/forward/update、0raw/trace。"""
from pathlib import Path
import hashlib,json,os,resource,signal,sys,time

P=Path(__file__).resolve().parents[3]
D=Path(__file__).resolve().parent/'beta_committed_pending_metadata_v2'
assert not D.exists();D.mkdir()
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('METADATA_AUDIT60S')))
signal.alarm(59)
start=time.time();ru=resource.getrusage(resource.RUSAGE_SELF)
usage0={'unix':start,'CPU':ru.ru_utime+ru.ru_stime,'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])}
files={};checks=[]
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sha_bytes(p.read_bytes())
def objsha(x):return sha_bytes(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True).encode())
def load(p):
 b=p.read_bytes();files[str(p.relative_to(P))]=sha_bytes(b);return json.loads(b)
def save(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def check(name,value):checks.append({'check':name,'PASS':bool(value)})
R=P/'families/ppo_reward/continuous_scale_v1/real_runs/GENUINE_BETA_V1'
arms=['BETA_RF_RAW','BETA_PPO_RAW','BETA_RF_SCALED','BETA_PPO_SCALED']
currentbytes=(R/'CURRENT.json').read_bytes();current=load(R/'CURRENT.json')
(D/'CURRENT_OBSERVED_ORIGINAL_BYTES.json').write_bytes(currentbytes)
generations={};snapshots={}
for n in [0,1]:
 g=R/f'GENERATION_{n:04d}';tx=load(g/'TRANSACTION.json');co=load(R/f'TRANSACTION_COMPUTATION_{n:04d}.json');it=load(R/f'TRANSACTION_ATTEMPT_{n:04d}.json');seal=load(R/f'TRANSACTION_COMPUTATION_SEAL_{n:04d}.json')
 check(f'G{n}.transaction_computation_file_SHA',tx['computation_sha256']==sha(R/f'TRANSACTION_COMPUTATION_{n:04d}.json'))
 check(f'G{n}.computation_intent_file_SHA',co['intent_sha256']==sha(R/f'TRANSACTION_ATTEMPT_{n:04d}.json'))
 check(f'G{n}.seal_computation_intent',seal['computation_sha256']==tx['computation_sha256'] and seal['intent_sha256']==co['intent_sha256'])
 check(f'G{n}.previous_pointer_canonical_SHA',tx['previous_pointer_sha256']==objsha(co['previous_pointer']))
 check(f'G{n}.intent_previous_pointer',it['previous_pointer']==co['previous_pointer'])
 check(f'G{n}.prepared_object_SHA',tx['prepared_object_sha256']==objsha(it['prepared']))
 ss={}
 for arm in arms:
  f=g/(arm+'.json');b=f.read_bytes();x=load(f);ss[arm]=x
  ce=co['checkpoint_bytes_utf8'][arm];binding=tx['checkpoints'][arm]
  check(f'G{n}.{arm}.exact_computed_bytes',b==ce['utf8'].encode())
  check(f'G{n}.{arm}.file_SHA',sha_bytes(b)==ce['sha256']==binding['sha256']==seal['checkpoint_file_sha256'][arm])
  check(f'G{n}.{arm}.object_SHA',objsha(x)==ce['object_sha256']==binding['object_sha256'])
  check(f'G{n}.{arm}.no_pending',x['pending']==[])
 snapshots[n]=ss
 generations[n]={'transaction_file_sha256':sha(g/'TRANSACTION.json'),'computation_file_sha256':tx['computation_sha256'],'status':tx['status'],'operation':tx['operation'],'all_four_published_together':tx['all_four_published_together'],'optimizer_calls_on_recovery':tx['optimizer_calls_on_recovery'],'computation_accounting':tx['result_accounting'].get('accounting'),'created_unix':tx['created_unix'],'closed_jobs':it['prepared'].get('proof',{}).get('closed_jobs')}
 if n==1:
  initial_pointer=co['previous_pointer'];check('G1.previous_pointer_references_G0',initial_pointer['generation_index']==0 and initial_pointer['transaction_sha256']==generations[0]['transaction_file_sha256'])
  for arm in arms:check('G1.previous_pointer.'+arm,initial_pointer['checkpoints'][arm]['sha256']==sha(R/'GENERATION_0000'/(arm+'.json')))
check('CURRENT.G1',current['generation_index']==1 and current['transaction_sha256']==generations[1]['transaction_file_sha256'])
for arm in arms:check('CURRENT.checkpoint.'+arm,current['checkpoints'][arm]['sha256']==sha(R/'GENERATION_0001'/(arm+'.json')))
batch1={}
for arm in arms:
 a=snapshots[0][arm];b=snapshots[1][arm];fb=b['finished_batches'][0]
 receipts=[x['physical_receipt'] if isinstance(x.get('physical_receipt'),dict) else x for x in fb['full_physical_receipts']]
 batch1[arm]={'weights_G0_equals_G1':a['policy']['weights']==b['policy']['weights'],'G0_policy_parameter_steps':a['policy']['counters']['parameter_updates'],'G1_policy_parameter_steps':b['policy']['counters']['parameter_updates'],'G0_optimizer_steps':a['optimizer']['completed_parameter_steps'],'G1_optimizer_steps':b['optimizer']['completed_parameter_steps'],'finished_batch_count':len(b['finished_batches']),'original_finished_batch_fields':{k:fb.get(k) for k in ['batch_id','algorithm','gain','all_rewards_equal_in_this_batch','advantages','advantage_baseline','weights_changed','total_parameter_delta_norm','new_training_forward','new_manual_score_evaluations','new_parameter_steps']},'receipt_count':len(receipts),'qualified_count':sum(x['original_qualified'] is True for x in receipts),'all_hardFalse':all(x['true_hard_safety_violation'] is False for x in receipts),'feedback_reward': [x['reward'] for x in fb['feedback_components']]}
groups={};prior=snapshots[1]
for group in ['V8BETA02H','V8BETA02L']:
 folder=R/'sampling'/group;bundle=load(folder/'PENDING_CHECKPOINTS.json');config=load(P/'experiments'/(group+'.json'));spec=config['onpolicy_sampling'];now={};summ={}
 for arm in arms:
  f=folder/(arm+'_PENDING.json');x=load(f);now[arm]=x
  check(group+'.bundle_snapshot_exact.'+arm,x==bundle['snapshots'][arm])
  item=next(q for q in spec['arm_inputs'] if q['arm_id']==arm);inputpath=P/item['snapshot_path'];inputdoc=load(inputpath)
  check(group+'.config_input_file_SHA.'+arm,sha(inputpath)==item['snapshot_sha256']==bundle['source_inputs'][arm]['input_snapshot_sha256'])
  check(group+'.input_equals_previous.'+arm,inputdoc==prior[arm])
  check(group+'.weights_unchanged.'+arm,x['policy']['weights']==snapshots[1][arm]['policy']['weights'])
  check(group+'.policy_version_unchanged.'+arm,x['policy']['version']==snapshots[1][arm]['policy']['version'])
  check(group+'.optimizer_exact.'+arm,x['optimizer']==snapshots[1][arm]['optimizer'])
  check(group+'.finished_batches_exact.'+arm,x['finished_batches']==snapshots[1][arm]['finished_batches'])
  check(group+'.parameter_steps_unchanged.'+arm,x['policy']['counters']['parameter_updates']==snapshots[1][arm]['policy']['counters']['parameter_updates'])
  check(group+'.pending_prefix_exact.'+arm,x['pending'][:len(prior[arm]['pending'])]==prior[arm]['pending'])
  check(group+'.seen_prefix_exact.'+arm,x['seen_attempt_ids'][:len(prior[arm]['seen_attempt_ids'])]==prior[arm]['seen_attempt_ids'])
  rows=[]
  for row in x['pending']:
   rec=row['physical_receipt'];sample=row['sample']
   rows.append({'attempt_id':row['attempt_id'],'lambda':sample['lambda_sample'],'original_qualified':rec['original_qualified'],'complete':rec['complete'],'engineering_complete':rec['engineering_complete'],'protected_task_failure':rec['protected_task_failure'],'true_hard_safety_violation':rec['true_hard_safety_violation'],'actual_new_native_steps':rec['actual_new_native_steps'],'JF':rec['JF_N_s'],'JM':rec['JM_Nm_s'],'source_receipt_object_sha256':objsha(rec)})
  summ[arm]={'pending':rows,'pending_count':len(rows),'new_rows_this_job':len(rows)-len(prior[arm]['pending']),'policy_counters':x['policy']['counters'],'optimizer_steps':x['optimizer']['completed_parameter_steps'],'weights_sha256':objsha(x['policy']['weights']),'rng_sha256':objsha(x['rng']),'G1_rng_equal':x['rng']==snapshots[1][arm]['rng']}
 stop=load(P/'owned'/(group+'_SUPERVISOR_END.json'))
 groups[group]={'stage':bundle['stage'],'source_inputs':bundle['source_inputs'],'parameter_updates_in_this_job':bundle['parameter_updates_in_this_job'],'owner_pid':bundle['owner_pid'],'owner_start_ticks':bundle['owner_start_ticks'],'supervisor_state':stop['state'],'worker_exit_code':stop['worker_exit_code'],'survivors':stop['survivors'],'arms':summ,'total_pending_rows':sum(q['pending_count'] for q in summ.values())}
 check(group+'.closed',stop['state']=='STOP' and stop['survivors']==[])
 check(group+'.zero_job_parameter_updates',bundle['parameter_updates_in_this_job']==0)
 prior=now
check('CURRENT.bytes_unchanged_during_audit',(R/'CURRENT.json').read_bytes()==currentbytes)
check('no_G2_commit_files',not any((R/q).exists() for q in ['GENERATION_0002','TRANSACTION_ATTEMPT_0002.json','TRANSACTION_COMPUTATION_0002.json','TRANSACTION_COMPUTATION_SEAL_0002.json']))
allrows=[row for arm in arms for row in groups['V8BETA02L']['arms'][arm]['pending']]
check('batch2.unique9pending',len(allrows)==len({x['attempt_id'] for x in allrows})==9)
check('batch2.all9known_hardFalse',all(x['true_hard_safety_violation'] is False for x in allrows))
ru=resource.getrusage(resource.RUSAGE_SELF)
result={'status':'METADATA_CHAIN_PASS_NO_SECOND_BATCH_UPDATE' if all(x['PASS'] for x in checks) else 'METADATA_CHAIN_HAS_FAILURES','CURRENT_original_sha256':sha_bytes(currentbytes),'CURRENT_generation':current['generation_index'],'generations':generations,'batch1':batch1,'batch2':groups,'checks':checks,'failed_checks':[x for x in checks if not x['PASS']],'batch2_summary':{'unique_pending':len(allrows),'qualified':sum(x['original_qualified'] is True for x in allrows),'complete':sum(x['complete'] is True for x in allrows),'engineering_complete':sum(x['engineering_complete'] is True for x in allrows),'protected_task_failure':sum(x['protected_task_failure'] is True for x in allrows),'all9hardFalse':all(x['true_hard_safety_violation'] is False for x in allrows),'not_cancelled_not_published':True,'parent_prefix_global_hardFalse':None,'parent_prefix_review':'families/critic_value/analysis/beta02l_prefix_trace_v1/PREFIX_TRACE_REVIEW_V1.json'},'scope_limits':['JSON哈希/metadata核验，不重跑scorer，不重读raw/trace，不证明未记录的工作不存在','没有取消/发布/回滚RNG，9pending保持外部隔离状态，由root后续批准处置','原partial工程/接口失败，不能混作完整合格训练样本','首批已支付update steps不等于非零weight变化，全部零advantage诊断保留'],'evidence_files_sha256':files,'resource':{**usage0,'END_unix':time.time(),'wall_s':time.time()-start,'CPU_s':ru.ru_utime+ru.ru_stime-usage0['CPU'],'RSS_peak_KiB':ru.ru_maxrss,'affinity':sorted(os.sched_getaffinity(0)),'AS_bytes':1024**3,'python':sys.executable,'python_binary_sha256':sha(Path(sys.executable).resolve()),'model_init_forward_fit_physics':0,'raw_trace_reads':0,'actual_run_writes':0}}
save(D/'RESULT.json',result)
save(D/'EVIDENCE_SHA_MANIFEST.json',{'files':files,'audit_source_sha256':sha(Path(__file__)),'result_sha256':sha(D/'RESULT.json')})
signal.alarm(0)
print(json.dumps({'status':result['status'],'failed_checks':result['failed_checks'],'result_sha256':sha(D/'RESULT.json'),'batch1_parameter_steps':sum(x['G1_optimizer_steps']-x['G0_optimizer_steps'] for x in batch1.values()),'batch1_all_weights_unchanged':all(x['weights_G0_equals_G1'] for x in batch1.values()),'batch2':result['batch2_summary'],'resource':result['resource']},ensure_ascii=False,indent=2))
