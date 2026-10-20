from pathlib import Path
import sys,subprocess,json,time,os,fcntl
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1')
sys.path.insert(0,str(S/'code'))
def main():
 lock=(S/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush()
 import runner
 def sample(owner):
  row=runner.sample(owner=owner)
  with (S/'output/CPU_LOG.jsonl').open('a') as f:f.write(json.dumps(dict(unix=row['unix'],load=os.getloadavg(),owner=owner))+'\n')
 sample('BEFORE_CONSECUTIVE')
 start=time.time()
 with (S/'logs/R3_CONSECUTIVE_SESSION.log').open('w') as log:
  child=subprocess.Popen([sys.executable,'-u',str(S/'code/session_worker.py'),sys.argv[1]],stdout=log,stderr=subprocess.STDOUT)
  last=time.time()
  while child.poll() is None:
   if time.time()-last>=45:sample(child.pid);last=time.time()
   time.sleep(.5)
  code=child.wait()
 sample('AFTER_CONSECUTIVE_JOIN')
 (S/'SESSION_CAMPAIGN_JOINED.json').write_text(json.dumps(dict(pid=os.getpid(),returncode=code,child_pid=child.pid,unix=time.time(),wall_s=time.time()-start,joined=True),indent=2)+'\n')
 print('SESSION_JOINED',code,flush=True)
if __name__=='__main__':main()
