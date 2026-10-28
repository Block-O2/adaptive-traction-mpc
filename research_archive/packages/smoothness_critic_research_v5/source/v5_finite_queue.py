"""Runs only explicitly listed finite jobs; survives SSH, never invents work."""
from pathlib import Path
import datetime,hashlib,json,os,signal,subprocess,sys,time
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');a=json.loads((P/'ACTIVATION.json').read_text());queue=sys.argv[1];cfg=json.loads((P/'queue'/(queue+'.json')).read_text());python='/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python'
def put(n,x):
 f=P/n;f.parent.mkdir(exist_ok=True,parents=True);tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(f)
started=time.time();limit=min(cfg.get('deadline_unix',a['hard_stop_unix']-2700),a['hard_stop_unix']-2700)
put('owned/'+queue+'_QUEUE_START.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),activation=a['id'],finite_configs=cfg['configs'],deadline_unix=limit))
done=[];reason='FINITE_QUEUE_COMPLETED'
try:
 pred=cfg.get('predecessor')
 if pred:
  for _ in range(max(1,int(limit-time.time()))):
   f=P/'owned'/(pred+'_SUPERVISOR_END.json')
   if f.exists():
    assert json.loads(f.read_text())['worker_exit_code']==0,'PREDECESSOR_FAILED';break
   if time.time()>=limit or (P/'STOP_REQUESTED').exists():raise TimeoutError('QUEUE_CUTOFF')
   time.sleep(1)
  else:raise TimeoutError('PREDECESSOR_NOT_DONE')
 for config in cfg['configs']:
  if time.time()>=limit-900 or (P/'STOP_REQUESTED').exists():reason='INSUFFICIENT_TIME_OR_STOP';break
  command=[python,'-B',str(P/'source/supervise_v2.py'),config]
  with (P/'logs'/(queue+'_'+Path(config).stem+'_supervisor.log')).open('w') as log:
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
   put('owned/'+queue+'_CURRENT.json',dict(pid=child.pid,command=command,deadline_unix=limit))
   rc=child.wait(timeout=max(1,int(limit-time.time())))
  done.append(dict(config=config,exit_code=rc));assert rc==0,'FINITE_WORKER_FAILED:'+config
except BaseException as e:
 reason=type(e).__name__+':'+str(e);raise
finally:put('owned/'+queue+'_QUEUE_END.json',dict(pid=os.getpid(),reason=reason,completed=done,wall_s=time.time()-started,activation=a['id']))
