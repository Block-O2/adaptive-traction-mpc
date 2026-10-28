"""Finite supplementary execution-mask counterfactual, registered before primary validation."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
import numpy as np
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix']-2700
def put(n,d):
 f=P/n;f.parent.mkdir(exist_ok=True,parents=True);tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(f)
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def wait(n):
 for _ in range(max(1,int(deadline-time.time())+1)):
  if time.time()>=deadline or (P/'STOP_REQUESTED').exists():raise TimeoutError('SUPPLEMENTAL_QUEUE_WAIT:'+n)
  f=P/n
  if f.exists():
   try:return json.loads(f.read_text())
   except json.JSONDecodeError:pass
  time.sleep(1)
 raise TimeoutError(n)
configs={g:sha(P/'experiments'/(g+'.json')) for g in ['PPOREPAIR01','PPOREPAIRVAL']}
put('owned/PPO_REPAIR_QUEUE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,maximum_extra_START=11,finite_configs=configs,source_sha256=sha(Path(__file__)),registered_before_any_primary_VAL=True,predecessor='owned/VALIDATION3_QUEUE_END.json'))
done=[];reason='FINITE_SUPPLEMENTAL_STUDY_COMPLETED'
def job(g):
 assert time.time()<deadline-1800,'NO_TIME_FOR_COMPLETE_SUPPLEMENTAL_JOB_AND_AUDIT'
 assert sha(P/'experiments'/(g+'.json'))==configs[g],'SUPPLEMENTAL_FROZEN_CONFIG_CHANGED'
 with (P/'logs'/(g+'_supplemental_supervisor.log')).open('w') as log:
  child=subprocess.Popen([sys.executable,'-B',str(P/'source/supervise_v2.py'),'experiments/'+g+'.json'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  put('owned/PPO_REPAIR_QUEUE_CURRENT.json',dict(pid=child.pid,group=g,deadline_unix=deadline));rc=child.wait(timeout=max(1,int(deadline-time.time())))
 assert rc==0,'SUPPLEMENTAL_PHYSICAL_JOB_FAILED:'+g
 done.append(g)
def score(i):
 d=wait('analysis/extended/'+i+'.json');b=wait('analysis/extended/HANDOFF01_BEST.json')
 return float(.65*np.linalg.norm(d['native_motion']['jerk_deg_s3']['rms'])/np.linalg.norm(b['native_motion']['jerk_deg_s3']['rms'])+.35*d['wrench']['force']['norm_rate']['rms']/b['wrench']['force']['norm_rate']['rms']+.004*(d['JF']-b['JF'])+.004*(d['JM']-b['JM']))
def accepted(i):
 r=wait('attempts/'+i+'_RESULT.json');return sum(e.get('modal',{}).get('status')=='ACCEPTED' for e in r['execution'])
try:
 end=wait('owned/VALIDATION3_QUEUE_END.json');assert end['reason']=='FINITE_LOCKED_VALIDATION_COMPLETED','PRIMARY_VALIDATION_NOT_CLOSED'
 original=wait('attempts/PPOCHECK_FROZEN_MEAN_RESULT.json');rejected=[e['modal'] for e in original['execution'] if e.get('modal',{}).get('phase')=='OUTBOUND' and e['modal']['status']=='REJECTED']
 assert len(rejected)>=2,'NO_REGISTERED_EXECUTION_MASK_GATE'
 job('PPOREPAIR01');old='PPOCHECK_FROZEN_PLUS_RULE';oldscore=score(old);oldaccept=accepted(old);ranking=[]
 for tag in ['TIME0','TIME0_RULE']:
  i='PPOREPAIR01_'+tag;r=wait('attempts/'+i+'_RESULT.json');ranking.append(dict(id=i,qualified=r['qualified'],S=score(i),accepted_modal_plans=accepted(i)))
 trigger=any(r['qualified'] and r['S']<oldscore-.005 and r['accepted_modal_plans']>oldaccept for r in ranking)
 put('analysis/PPO_REPAIR_GATE.json',dict(utc=utc(),reference_id=old,reference_S=oldscore,reference_accepted_modal_plans=oldaccept,rows=ranking,validation_triggered=trigger,rule='A qualified repair must improve preregistered S by at least .005 versus frozen PPO+speed rule and restore at least one accepted modal plan. Validation actions and condition were already frozen before primary VAL. No primary validation result consulted.'))
 if trigger:job('PPOREPAIRVAL')
 else:reason='SUPPLEMENTAL_DEV_COMPLETED_NO_GAIN_VALIDATION_NOT_RUN'
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/PPO_REPAIR_QUEUE_END.json',dict(pid=os.getpid(),utc=utc(),reason=reason,completed=done,required_next='Final closure must include this queue before END; no new research round.'))
