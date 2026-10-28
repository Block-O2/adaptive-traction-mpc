"""Read-only 2/4/6h branch snapshots, owned by the active finite campaign."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,time,signal,collections
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));os.environ['IHEAR_RESEARCH_ROOT']=str(R)
from research_common import read,atomic,append,now,pid_identity,HARD_STOP,resources
stop=False

def end_signal(*a):
 global stop
 stop=True
signal.signal(signal.SIGTERM,end_signal);signal.signal(signal.SIGINT,end_signal)
t0=datetime.fromisoformat(read(R/'ACTIVATION.json')['activation_utc']).timestamp();owner=R/'owned/PROGRESS_STAGE_REPORTER.json'
atomic(R/'STAGE_REPORTER_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),source='analysis_tools/stage_reporter.py',new_physics=0))
try:
 while not stop and time.time()<HARD_STOP-30 and not (R/'STOP_REQUESTED').exists() and not (R/'END.json').exists():
  elapsed=time.time()-t0
  for hour in [2,4,6]:
   p=R/f'STAGE_REPORT_{hour}H_DETAILED.json'
   if elapsed<hour*3600 or p.exists():continue
   ledger=read(R/'LEDGER.json',{});rows=[json.loads(s) for s in (R/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (R/'ALL_ATTEMPTS.jsonl').exists() else []
   branches=collections.defaultdict(list)
   for r in rows:branches[(r['branch'],r['seed'],r['mode'],r['policy_mode'])].append(r)
   summaries=[dict(branch=k[0],seed=k[1],mode=k[2],policy_mode=k[3],attempts=len(v),complete=sum(r['success'] for r in v),optimizer_steps=sum(r['gradient_updates'] for r in v),failures=[dict(run=r['run'],reason=r['abort_reason'],JF=r['JF'],JM=r['JM'],scope=r['integral_scope']) for r in v if not r['success']]) for k,v in branches.items()]
   active=[a for a in ledger.get('attempts',[]) if not a['settled']]
   report=dict(time_utc=now(),activation_elapsed_hours=elapsed/3600,training_episodes=sum(r['mode']=='training' for r in rows),optimizer_steps=ledger.get('optimizer_steps',0),native_steps=ledger.get('native_steps',0),branches=summaries,active=active,resources=resources(),remaining=dict(training=160-ledger.get('training_attempts',0),evaluation=36-ledger.get('evaluation_attempts',0),native=33000000-ledger.get('native_steps',0),wall_s=HARD_STOP-time.time()),method_selection=read(R/'TRAINING_METHOD_SELECTION.json'),reward_lock=read(R/'REWARD_EXPERIMENT_LOCK.json'),next_decision='Continue fixed authorized branches and evidence-based gates; no stop at this report; final candidate lock before reserved streams',scope='Nominal development only')
   atomic(p,report)
   text=[f'# ACTIVATION + {hour}h 阶段报告','',f'UTC：{report["time_utc"]}；实际elapsed {elapsed/3600:.4f}h。', '', f'训练完成 {report["training_episodes"]} 集；Adam {report["optimizer_steps"]} steps；native {report["native_steps"]:,}。','', '|分支|父seed|模式|完整/已完成|Adam steps|','|---|---|---|---|---|']
   text += [f'|{s["branch"]}|{s["seed"]}|{s["policy_mode"]}|{s["complete"]}/{s["attempts"]}|{s["optimizer_steps"]}|' for s in summaries]
   text+=['',f'当前任务：{[a["job"] for a in active]}。剩余预算：{report["remaining"]}。','', '失败 partial 原样保留，单分支失败继续其他有界假设；正式 G4/live matched/Stage2/Campaign 均未获资格。本报告不是STOP信号；继续已授权有限队列，最终候选先锁SHA再打开预留流。']
   (R/f'STAGE_REPORT_{hour}H.md').write_text('\n'.join(text)+'\n')
  time.sleep(10)
finally:
 atomic(R/'STAGE_REPORTER_END.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),new_physics=0))
 record=read(owner,{})
 if record:record['ended']=dict(time_utc=now(),normal=True);atomic(owner,record)
