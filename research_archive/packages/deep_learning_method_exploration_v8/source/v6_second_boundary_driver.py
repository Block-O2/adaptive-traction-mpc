"""Last local boundary test, frozen after negative challenge; no subsequent search."""
from pathlib import Path
import os,sys,json,time,subprocess,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
start=time.time();status='WAITING';reason=None;deadline=read('ACTIVATION.json')['hard_stop_unix']
put('owned/SECOND_BOUNDARY_DRIVER_START.json',dict(pid=os.getpid(),started_unix=start,source_sha256=sha(Path(__file__)),deadline_unix=deadline))
try:
 while not (P/'owned/PHASE_RULE_FOLLOWUP_END.json').exists():
  assert time.time()<deadline-2400,'CLOSEOUT_RESERVE'
  time.sleep(5)
 phase=read('analysis/FIXED_PHASE_RULE_RESULTS.json');assert phase['status'] in ['NOT_RUN','COMPLETED_TWO_PAIRED_CONFIRMATIONS']
 n=sum(json.loads(s)['event']=='START' for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines())
 if n+4>150 or deadline-time.time()<3300:
  status='NOT_RUN';reason='Insufficient four-attempt/time budget with40min closure reserve.'
 else:
  protocol=read('freeze/SECOND_LOCAL_BOUNDARY_CHALLENGE.json');g='LEGACY_BOUNDARY_O3';cfg=read('experiments/'+g+'.json')
  assert sha(P/'experiments'/f'{g}.json')==protocol['config_sha256']
  assert sha(P/cfg['frozen_bundle'])==protocol['model_sha256']
  assert sha(P/'source/v6_selection.py')==protocol['selection_source_sha256']
  with (P/'logs'/f'{g}_second_boundary_supervisor.log').open('w') as log:
   rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),f'experiments/{g}.json'],env=dict(os.environ,ACL2_PACKAGE=str(P)),stdout=log,stderr=subprocess.STDOUT,timeout=max(1,deadline-time.time()-2400)).returncode
  assert rc==0,'SECOND_BOUNDARY_PHYSICS_ERROR'
  with (P/'logs'/f'{g}_frozen_evaluation.log').open('w') as log:
   rc=subprocess.run([sys.executable,'-B',str(P/'source/v6_evaluate.py'),g,cfg['frozen_bundle'],'legacy'],env=dict(os.environ,ACL2_PACKAGE=str(P)),stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
  assert rc==0,'SECOND_BOUNDARY_EVALUATION_ERROR'
  status='COMPLETED_FROZEN_LOCAL_CHALLENGE'
 put('analysis/SECOND_LOCAL_BOUNDARY_RESULT.json',dict(status=status,reason=reason,ended_unix=time.time(),no_more_boundary_search=True))
except BaseException as e:
 status='REVIEW_REQUIRED';reason=str(e);put('jobs/SECOND_BOUNDARY_ERROR.json',dict(error=str(e),unix=time.time()));raise
finally:
 put('owned/SECOND_BOUNDARY_DRIVER_END.json',dict(pid=os.getpid(),ended_unix=time.time(),status=status,reason=reason))
 print('SECOND_BOUNDARY',status,reason,flush=True)
