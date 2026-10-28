from pathlib import Path
import sys,os,json,signal,subprocess,time
from research_common import ROOT,read,atomic,append,sha,now,HARD_STOP,pid_identity
from run_job import run_job
p=ROOT/'configs/STD_PLAN_v3.json';plan=read(p);phase=sys.argv[1];run_tag=phase if phase!='pilot' else 'pilot_interfacefix2';assert phase in ['pilot','identity','preregistered']
if phase!='pilot':assert read(ROOT/'audit/PILOT_ACCEPTANCE.json',{}).get('pass_'),'PILOT_NOT_ACCEPTED'
if phase=='preregistered':assert read(ROOT/'audit/IDENTITY_REGRESSION.json',{}).get('pass_'),'MEAN_IDENTITY_REGRESSION_NOT_ACCEPTED'
start=ROOT/f'{run_tag.upper()}_QUEUE_START.json';assert not start.exists()
atomic(start,dict(time_utc=now(),identity=pid_identity(os.getpid()),plan_sha256=sha(p),sources={str(x.relative_to(ROOT)):sha(x) for x in (ROOT/'scripts').glob('*.py')}))
watch=None
if not (ROOT/'WATCHDOG_START.json').exists():
 with (ROOT/'watchdog.stdout.log').open('w') as out,(ROOT/'watchdog.stderr.log').open('w') as err:
  watch=subprocess.Popen([sys.executable,str(ROOT/'scripts/watchdog.py')],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},cwd=ROOT,stdout=out,stderr=err,start_new_session=True)
atomic(ROOT/'RESEARCH_STATE.json',dict(status='RUNNING',phase=phase,time_utc=now()))
results=[];error=None
try:
 for item in plan['plans']:
  if item['split']!=phase:continue
  assert sha(item['config'])==item['sha256'],'FROZEN_CONFIG_CHANGED'
  result=run_job(item['config']);results.append(result)
  append(ROOT/f'{run_tag.upper()}_QUEUE_RESULTS.jsonl',result)
  print(json.dumps(dict(job=result['job'],infrastructure_success=result['success'],wall_s=result['wall_s'])),flush=True)
  if not result['success']:raise RuntimeError('INTEGRITY_OR_INFRASTRUCTURE_FAILURE: inspect before new physics')
finally:
 atomic(ROOT/f'{run_tag.upper()}_QUEUE_END.json',dict(time_utc=now(),results=results,complete=len(results)==sum(x['split']==phase for x in plan['plans']) and all(x['success'] for x in results)))
 atomic(ROOT/'RESEARCH_STATE.json',dict(status='AWAITING_REVIEW',phase=phase,time_utc=now()))
