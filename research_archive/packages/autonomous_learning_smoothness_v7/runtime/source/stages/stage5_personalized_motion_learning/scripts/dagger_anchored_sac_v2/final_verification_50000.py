"""Training has stopped: cold final strategy/reference replays, evaluation-only ledger."""
from common import *
from operational_memory_v3 import phase,evidence,descendants
import gc,traceback
def dispatch(script,req):
 guard();rp=O/'evaluation_requests'/('final_'+req['result']+'.json');rp.write_text(json.dumps(req));phase('EVALUATION_START');evidence('FINAL_BEFORE_CHILD',request=str(rp))
 child=subprocess.Popen([sys.executable,str(P/script),str(rp)],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'});rc=child.wait();assert rc==0,f'FINAL_CHILD_EXIT_{rc}';assert not Path(f'/proc/{child.pid}').exists()
 children=descendants(os.getpid());assert not any('multiprocessing.spawn' in x['cmd'] for x in children),'FINAL_PLANNER_NOT_RELEASED';gc.collect();phase('POST_EVALUATION_RELEASE');evidence('FINAL_AFTER_CHILD_RELEASE',child_pid=child.pid,child_reaped=True,descendants=children)
 return read(req['result'])
def run():
 status=read('FINAL_STATUS.json');assert status['total_online_steps']==50000 and status['status'] in ('COMPLETE_BUDGET','RESCUE_ABILITY_LOST');result=read('RESULTS.json');lastcp=result['checkpoints'][-1];best=result['best']['NATIVE'];assert lastcp['total_online_steps']==50000
 state('COMPLETE_BUDGET_FINAL_REPLAYS_PENDING',total_online_steps=50000,resumable_checkpoint=str(O/'checkpoints/final_attempt_state'),error=None,next_action='Training stopped; perform authorized evaluation-only final cold replays')
 root=O/'final_verification_50000';root.mkdir(exist_ok=True);pi0=root/'frozen_student.pt';torch.save(torch.load(V/'qualified_actor.pt',map_location='cpu',weights_only=False)['state_dict'],pi0)
 strategies=[dict(name='frozen_DAgger_student',actor=str(pi0)),dict(name='confirmed_best',actor=str(Path(best['checkpoint'])/'actor.pt')),dict(name='final_50000',actor=str(O/'checkpoints/final_attempt_state/actor.pt'))]
 # Preserve/evaluate every other intermediate complete VALID candidate better than final.
 ledger=[json.loads(x) for x in (L/'EVALUATIONS.jsonl').read_text().splitlines()]
 finalrow=next(r for r in ledger if r['name']==f"legacy_predict_revision/checkpoint/a{lastcp['attempt']}_p{lastcp['point']}_NATIVE_1")
 if finalrow['valid']:
  for cp in result['checkpoints']:
   if cp['checkpoint'] in (best['checkpoint'],lastcp['checkpoint']) or cp['native_valid']!=2:continue
   n=next(r for r in ledger if r['name']==f"legacy_predict_revision/checkpoint/a{cp['attempt']}_p{cp['point']}_NATIVE_1")
   if n['valid'] and n['J_F']<finalrow['J_F']-1e-6:strategies.append(dict(name=f"intermediate_a{cp['attempt']}_p{cp['point']}",actor=str(Path(cp['checkpoint'])/'actor.pt')))
 for strategy in strategies:strategy['actor_sha256']=sha(strategy['actor'])
 save('FINAL_VERIFICATION_PLAN_50000.json',dict(total_collection_steps=50000,strategy_plan=strategies,repeats_per_scope=2,scopes=['NATIVE','MATCHED'],stochastic_native_per_learner=1,comparators=['original_controller','CEM','fixed_hip_leading'],evaluation_only=True,training_updates=0,scientific_changes=[]))
 monitor=None;rows=[]
 try:
  monitor=subprocess.Popen([sys.executable,'-u',str(P/'resource_policy_v2.py'),str(os.getpid())],stdout=(L/'RESOURCE_MONITOR_FINAL.log').open('a'),stderr=subprocess.STDOUT)
  for strategy in strategies:
   for scope in ['NATIVE','MATCHED']:
    for j in range(2):
     name=f'final_verification_50000/{strategy["name"]}_{scope}_{j+1}';req=dict(name=name,scope=scope,actor=strategy['actor'],seed=read('PREREGISTRATION.json')['seed']+7919*(1000+len(rows)),initial_condition_seed=read('PREREGISTRATION.json')['initial_condition_seed'],stochastic=False,result='FINAL_EVAL_'+name.split('/')[-1]+'.json')
     row=read(req['result']) if (L/req['result']).exists() else dispatch('evaluate_operational_v3.py',req);row.update(strategy=strategy['name'],final_verification=True,collection_steps_used=0);rows.append(row);log('FINAL_VERIFICATION_50000.jsonl',row);save('FINAL_VERIFICATION_50000.json',dict(status='RUNNING',rows=rows,total_collection_steps=50000,evaluation_only_steps=sum(x.get('steps',0) for x in rows)))
   if strategy['name']!='frozen_DAgger_student':
    name=f'final_verification_50000/{strategy["name"]}_NATIVE_STOCHASTIC';req=dict(name=name,scope='NATIVE',actor=strategy['actor'],seed=read('PREREGISTRATION.json')['seed']+7919*(1000+len(rows)),initial_condition_seed=read('PREREGISTRATION.json')['initial_condition_seed'],stochastic=True,result='FINAL_EVAL_'+name.split('/')[-1]+'.json');row=read(req['result']) if (L/req['result']).exists() else dispatch('evaluate_operational_v3.py',req);row.update(strategy=strategy['name'],final_verification=True,collection_steps_used=0);rows.append(row);log('FINAL_VERIFICATION_50000.jsonl',row)
  for kind in ['original_controller','CEM','fixed_hip_leading']:
   for scope in ['NATIVE','MATCHED']:
    req=dict(kind=kind,scope=scope,result=f'FINAL_COMPARATOR_{kind}_{scope}.json');row=read(req['result']) if (L/req['result']).exists() else dispatch('final_comparator_v3.py',req);rows.append(row);log('FINAL_VERIFICATION_50000.jsonl',row);save('FINAL_VERIFICATION_50000.json',dict(status='RUNNING',rows=rows,total_collection_steps=50000,evaluation_only_steps=sum(x.get('steps',0) for x in rows)))
  save('FINAL_VERIFICATION_50000.json',dict(status='COMPLETE',rows=rows,total_collection_steps=50000,evaluation_only_steps=sum(x.get('steps',0) for x in rows),comparators_without_policy_steps='original controller runs complete physics directly; trace duration preserved',training_updates=0,cold_processes_reaped=True));state('COMPLETE_BUDGET_FINAL_VERIFIED',total_online_steps=50000,error=None,final_verification='COMPLETE',next_action='STOP; report only; no extension beyond50000')
 except BaseException as e:save('FINAL_VERIFICATION_EXCEPTION.json',dict(error=str(e),traceback=traceback.format_exc(),rows=rows,training_already_stopped=True,total_collection_steps=50000));raise
 finally:
  if monitor is not None:monitor.terminate();monitor.wait(timeout=15)
  phase('FINAL_VERIFICATION_EXIT');evidence('FINAL_VERIFICATION_EXIT')
if __name__=='__main__':run()
