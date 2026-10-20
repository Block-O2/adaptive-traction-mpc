from pathlib import Path
import os,sys,json,time,subprocess,hashlib,fcntl
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_runtime_qualification_decoupling_v1')
sys.path.insert(0,str(S/'code'))
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def append(x):
 with (S/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
def main():
 lock=(S/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush()
 specs=json.loads(Path(sys.argv[1]).read_text())
 import runner
 for cfg in specs:
  assert time.time()<json.loads((S/'RUN_PLAN.json').read_text())['dispatch_cutoff_unix']
  ident=cfg['id'];assert not (S/'output'/(ident+'_RESULT.json')).exists()
  row=runner.sample(owner='MULTIRATE_DISPATCH');row['cpu_load']=os.getloadavg()
  while row['mem_available']<.35*2**30 or row['windows'].get('commit_headroom',2**40)<.35*2**30:
   save(S/'RESOURCE_PAUSE.json',dict(unix=time.time(),row=row));time.sleep(45);row=runner.sample(owner='PAUSE_NEW_DISPATCH')
  p=S/'inputs'/(ident+'.json');save(p,cfg)
  hashes={str(S/'code'/n):hashlib.sha256((S/'code'/n).read_bytes()).hexdigest() for n in ('multirate.py','run_one.py','campaign.py')}
  append(dict(event='START',id=ident,unix=time.time(),cfg=cfg,sources=hashes))
  print('START',ident,flush=True)
  with (S/'logs'/(ident+'.log')).open('w') as f:
   child=subprocess.Popen([sys.executable,'-u',str(S/'code/profile_run.py'),str(p)],stdout=f,stderr=subprocess.STDOUT)
   last=time.time()
   while child.poll() is None:
    if time.time()-last>=45:row=runner.sample(owner=child.pid);row['cpu_load']=os.getloadavg();last=time.time()
    time.sleep(.5)
   code=child.wait()
  result=S/'output'/(ident+'_RESULT.json');r=json.loads(result.read_text()) if result.exists() else dict(status='FAILED_NO_RESULT')
  append(dict(event='END',id=ident,unix=time.time(),returncode=code,status=r['status'],error=r.get('error')))
  print('END',ident,r['status'],r.get('error'),flush=True)
 runner.sample(owner='JOINED_CAMPAIGN')
 save(S/'CAMPAIGN_JOINED.json',dict(pid=os.getpid(),unix=time.time(),specs=[r['id'] for r in specs],children_joined=True))
if __name__=='__main__':main()
