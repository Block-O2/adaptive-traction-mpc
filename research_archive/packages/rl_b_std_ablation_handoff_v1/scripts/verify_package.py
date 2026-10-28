"""Independent fresh-process manifest coverage/hash and finalizer exit observation."""
from pathlib import Path
import os,json,time
from research_common import ROOT,read,atomic,sha,now,pid_identity,same_pid

def main():
 m=read(ROOT/'OUTPUT_MANIFEST.json');v=read(ROOT/'PACKAGE_VERIFICATION.json');bad=[];start=time.time()
 for x in m['files']:
  p=ROOT/x['path']
  if not p.is_file() or p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:bad.append(x['path'])
 expected={x['path'] for x in m['files']};actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()}-set(m['excluded'])
 assert not bad and expected==actual,dict(hash_mismatches=bad,missing=sorted(expected-actual),extra=sorted(actual-expected))
 assert sha(ROOT/'OUTPUT_MANIFEST.json')==v['manifest_sha256']
 assert not same_pid(v['finalizer_identity']),'FINALIZER_NOT_EXITED'
 l=read(ROOT/'LEDGER.json');assert all(x['settled'] for x in l['attempts']) and l['training_attempts']==0 and l['optimizer_steps']==0
 process=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   exe=(p/'exe').resolve();cwd=(p/'cwd').resolve();argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if 'python' in exe.name.lower() and same_pid(pid_identity(int(p.name))) and (str(ROOT) in argv or cwd.is_relative_to(ROOT)):process.append(dict(pid=int(p.name),argv=argv))
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 assert not process,process
 before_deadline=time.time()<__import__('datetime').datetime.fromisoformat(v['hard_stop_utc']).timestamp();assert before_deadline
 v.update(independent_final_verification_pending=False,independent_final_verification_pass=True,independent_final_verification=dict(time_utc=now(),verifier=pid_identity(os.getpid()),source_sha256=sha(Path(__file__)),files_verified=len(expected),bytes_verified=sum(x['bytes'] for x in m['files']),exact_filesystem_coverage=True,hash_mismatches=bad,all_owned_workers_watchdog_and_finalizer_exited=True,unregistered_compute=process,wall_s=time.time()-start,before_hard_deadline=before_deadline),final_state='STOP')
 atomic(ROOT/'PACKAGE_VERIFICATION.json',v);print(json.dumps(dict(pass_=True,files=len(expected),bytes=sum(x['bytes'] for x in m['files']),wall_s=time.time()-start,finalizer_exited=True)))
if __name__=='__main__':main()
