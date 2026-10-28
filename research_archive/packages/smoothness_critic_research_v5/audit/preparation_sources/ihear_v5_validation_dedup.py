from pathlib import Path
import os,sys,json,time,signal,subprocess,datetime,hashlib
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
assert not (P/'analysis/LOCKED_VALIDATION_SELECTION.json').exists(),'VALIDATION_ALREADY_FROZEN'
assert not (P/'owned/VALIDATION2_QUEUE_CURRENT.json').exists(),'VALIDATION_QUEUE_HAS_CHILD'
assert not any(json.loads(s).get('group','').startswith('VAL') for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()),'VALIDATION_ALREADY_STARTED'
src=(P/'source/v5_validation_queue_v2.py').read_text().replace('VALIDATION2_QUEUE_','VALIDATION3_QUEUE_')
needle="  put(f'experiments/{group}.json',cfg);"
addition="""  # Identical frozen controller actions share one actual validation; aliases are not extra trials.
  requested_labels=[r['tag'] for r in cfg['actions']];unique=[];seen={};aliases={}
  for entry in cfg['actions']:
   key=json.dumps(entry['action'],sort_keys=True,separators=(',',':'))
   if key not in seen:seen[key]=entry['tag'];unique.append(entry)
   aliases[entry['tag']]=seen[key]
  cfg['actions']=unique;cfg['validation_method_aliases']=aliases;cfg['requested_method_labels']=requested_labels
"""
assert src.count(needle)==1;src=src.replace(needle,addition+needle)
src=src.replace("actions=[r['tag'] for r in cfg['actions']],condition=condition", "actions=[r['tag'] for r in cfg['actions']],method_aliases=aliases,requested_method_labels=requested_labels,condition=condition")
src=src.replace("same_Human_not_cross_patient=True))","same_Human_not_cross_patient=True,exact_action_aliases_share_one_actual_trial=True,no_alias_is_counted_as_a_new_physical_attempt=True))")
compile(src,str(P/'source/v5_validation_queue_v3.py'),'exec');(P/'source/v5_validation_queue_v3.py').write_text(src)
old=json.loads((P/'owned/VALIDATION2_QUEUE_START.json').read_text());pid=old['pid'];cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode();assert 'v5_validation_queue_v2.py' in cmd
os.kill(pid,signal.SIGINT)
for _ in range(80):
 if (P/'owned/VALIDATION2_QUEUE_END.json').exists():break
 time.sleep(.1)
else:raise RuntimeError('WAITING_OLD_QUEUE_DID_NOT_END')
end=json.loads((P/'owned/VALIDATION2_QUEUE_END.json').read_text());assert not end['completed']
with (P/'logs/VALIDATION3_QUEUE.log').open('w') as log:
 child=subprocess.Popen(['/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python','-B',str(P/'source/v5_validation_queue_v3.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hypothesis='Two methods can freeze exactly the same action; repeating it under a second method name adds no deterministic information.',experiment='Before any VAL START or candidate freeze, canonicalize only exact JSON-equivalent controller actions; retain method-to-actual-ID aliases.',result='FINITE_VALIDATION3_QUEUE_REGISTERED',diagnosis='Primary PATTERN/BO 12-trial budgets remain untouched. Actual validation reuses identical actions without inventing extra raw, evidence or physical attempts.',decision='Continue same finite phase-composition and locked-prefix protocol, same original T0/deadline, with aliases frozen before first VAL START.',evidence=['source/v5_validation_queue_v3.py','owned/VALIDATION2_QUEUE_END.json'],new_queue_pid=child.pid)
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
print('VALIDATION3_PID',child.pid,'OLD_WAITING_QUEUE_DONE_WITHOUT_PHYSICS')
