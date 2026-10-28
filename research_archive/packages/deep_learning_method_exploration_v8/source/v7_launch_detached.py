"""Detach exactly one already frozen bounded job; never an autonomous future queue."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,fcntl
P=Path(__file__).resolve().parents[1];relative=sys.argv[1];cfg=P/relative;c=json.loads(cfg.read_text());g=c['group']
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def info(pid):
 try:
  s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'start_ticks':int(s[19]),'state':s[0]}
 except (FileNotFoundError,ProcessLookupError):return None
def alive(old):
 x=info(old['pid']);return bool(x and x['start_ticks']==old['start_ticks'] and x['state']!='Z')
mutex=(P/'owned/LAUNCH_MUTEX.lock').open('a');fcntl.flock(mutex,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert time.time()<json.loads((P/'ACTIVATION.json').read_text())['deadline_unix']-600,'NO_DISPATCH_AFTER_DEADLINE_RESERVE'
assert json.loads((P/'audit'/(g+'_PRELAUNCH.json')).read_text())['config_sha256']==sha(cfg),'PRELAUNCH_NOT_BOUND'
assert (P/'runtime'/(g+'_TEST_PLAN.json')).read_bytes()==cfg.read_bytes(),'RUNTIME_PLAN_DIFFERS'
for f in (P/'owned').glob('*_SUPERVISOR.json'):
 row=json.loads(f.read_text());assert not alive(row['identity']),'ANOTHER_PHYSICAL_SUPERVISOR_STILL_ALIVE:'+f.name
for f in (P/'owned').glob('*_DETACHED_LAUNCH.json'):
 row=json.loads(f.read_text());assert not alive(row['supervisor']),'DETACHED_JOB_STILL_ALIVE:'+f.name
assert not (P/'owned'/(g+'_SUPERVISOR.json')).exists(),'UNIQUE_GROUP_REQUIRED'
out=P/'owned'/(g+'_DETACHED_LAUNCH.json');assert not out.exists()
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:6])
env=dict(os.environ,ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
log=(P/'logs'/(g+'_supervisor.log')).open('x')
proc=subprocess.Popen([sys.executable,'-B',str(P/'source/v7_supervise_v3.py'),relative],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True,close_fds=True)
identity=info(proc.pid);assert identity
row={'group':g,'created_unix':time.time(),'launcher':info(os.getpid()),'supervisor':identity,'config_sha256':sha(cfg),'launcher_source_sha256':sha(Path(__file__)),'supervisor_source_sha256':sha(P/'source/v7_supervise_v3.py'),'deadline_unix':json.loads((P/'ACTIVATION.json').read_text())['deadline_unix'],'job_wall_cap_s':c['job_wall_cap_s'],'only_this_registered_job':True,'subsequent_jobs_automatic':False,'terminal_and_pipe_independent':True,'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None}
tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(row,indent=2)+'\n');tmp.replace(out)
print('DETACHED_REGISTERED_JOB',g,identity,flush=True)
