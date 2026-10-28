"""Fail-closed CPU resource guard; no power/memory configuration changes."""
from pathlib import Path
import ctypes,json,os,shutil,subprocess,sys,time,threading
R=Path(__file__).resolve().parent
GiB=1024**3
def sample():
 if os.name=='nt':
  from ctypes import wintypes
  class Memory(ctypes.Structure):
   _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
  m=Memory();m.length=ctypes.sizeof(m)
  if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise OSError('MEMORY_MONITOR_FAILED')
  avail=m.available;total=m.total
  class PageInfo(ctypes.Structure):
   _fields_=[('cb',wintypes.DWORD),('reserved',wintypes.DWORD),('total',ctypes.c_size_t),('used',ctypes.c_size_t),('peak',ctypes.c_size_t)]
  used=[];callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,ctypes.c_void_p,ctypes.POINTER(PageInfo),wintypes.LPCWSTR)
  def collect(context,info,name):used.append(info.contents.used);return True
  callback=callback_type(collect);psapi=ctypes.WinDLL('psapi',use_last_error=True);psapi.EnumPageFilesW.argtypes=[callback_type,ctypes.c_void_p];psapi.EnumPageFilesW.restype=wintypes.BOOL
  if not psapi.EnumPageFilesW(callback,None):raise OSError('PAGEFILE_MONITOR_FAILED')
  import mmap
  swap=sum(used)*mmap.PAGESIZE
 else:
  info={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
  avail=info['MemAvailable'];total=info['MemTotal'];swap=info['SwapTotal']-info['SwapFree']
 return {'unix':time.time(),'available_bytes':avail,'total_bytes':total,'swap_used_bytes':swap,'disk_free_bytes':shutil.disk_usage(R).free}
class ResourceStop(RuntimeError):pass
class Guard:
 def __init__(self,out,seconds=600,min_available_gib=6.,min_disk_gib=5.,max_output_gib=2.):
  self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True);self.seconds=seconds;self.min_available=min_available_gib*GiB;self.min_disk=min_disk_gib*GiB;self.max_output=max_output_gib*GiB
  self.started=time.monotonic();self.event=threading.Event();self.failure=None;self.thread=None;self.samples=[];self.initial_swap=None;self.swap_bad=0
 def poll(self,admission=False):
  try:
   row=sample();elapsed=time.monotonic()-self.started;row['elapsed_s']=elapsed
   self.samples.append(row)
   with (self.out/'resources.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
   if row['available_bytes']<self.min_available+(1.25*GiB if admission else 0):raise ResourceStop('AVAILABLE_MEMORY_RESERVE')
   if row['disk_free_bytes']<self.min_disk:raise ResourceStop('DISK_RESERVE')
   if elapsed>self.seconds:raise ResourceStop('WALL_DEADLINE')
   swap=row['swap_used_bytes']
   if swap is not None:
    if self.initial_swap is None:self.initial_swap=swap
    self.swap_bad=self.swap_bad+1 if swap>self.initial_swap+128*1024**2 else 0
    if self.swap_bad>=5:raise ResourceStop('SUSTAINED_SWAP_GROWTH')
   if int(elapsed)%5==0:
    size=sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())
    if size>self.max_output:raise ResourceStop('OUTPUT_DISK_BUDGET')
   if (R/'RESOURCE_STOP').exists():raise ResourceStop('EXPLICIT_RESOURCE_STOP')
  except BaseException as e:
   self.failure=f'{type(e).__name__}:{e}';raise ResourceStop(self.failure)
  return row
 def check(self):
  if self.failure:raise ResourceStop(self.failure)
  if self.thread is not None and not self.thread.is_alive():raise ResourceStop('MONITOR_THREAD_DIED')
 def start(self):
  self.poll(admission=True)
  def monitor():
   while not self.event.wait(.5):
    try:self.poll()
    except BaseException:return
  self.thread=threading.Thread(target=monitor,name='owned-resource-monitor',daemon=True);self.thread.start();return self
 def close(self):
  self.event.set()
  if self.thread:self.thread.join(3)
  record={'samples':len(self.samples),'minimum_available_GiB':min((s['available_bytes']/GiB for s in self.samples),default=None),'wall_s':time.monotonic()-self.started,'failure':self.failure,'monitor_joined':self.thread is None or not self.thread.is_alive()}
  (self.out/'RESOURCE_RESULT.json').write_text(json.dumps(record,indent=2));return record
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=float,default=600);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
 if a.command and a.command[0]=='--':a.command=a.command[1:]
 if not a.command:raise ValueError('COMMAND_REQUIRED')
 g=Guard(a.out,a.seconds);proc=None;error=None;rc=None;job=None
 (a.out).mkdir(parents=True,exist_ok=True)
 if (a.out/'START.json').exists():raise RuntimeError('ATTEMPT_ALREADY_EXISTS')
 from checkpoints import contract
 start={'unix':time.time(),'command':a.command,'pid':os.getpid(),'category':'GUARDED_CPU_ATTEMPT','contract_sha256':contract(),'environment':{k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},'physics_envs':1,'wall_cap_s':a.seconds};(a.out/'START.json').write_text(json.dumps(start,indent=2))
 try:
  # Admission occurs before launching/importing physics or Torch.
  g.poll(admission=True)
  env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','IHEAR_RUN_DIR':str(a.out.resolve()),'IHEAR_GUARDED':'1'}
  with (a.out/'stdout.log').open('w') as out,(a.out/'stderr.log').open('w') as err:
   command=a.command if os.name=='nt' else ['nice','-n','10',*a.command]
   proc=subprocess.Popen(command,cwd=R,env=env,stdout=out,stderr=err,start_new_session=os.name!='nt',creationflags=4 if os.name=='nt' else 0)
   if os.name=='nt':
    from windows_process import OwnedJob
    job=OwnedJob(proc);job.resume()
   else:
    os.sched_setaffinity(proc.pid,{min(os.sched_getaffinity(0))})
   while proc.poll() is None:
    g.poll()
    if job:
     with (a.out/'owned_processes.jsonl').open('a') as f:f.write(json.dumps(job.stats())+'\n')
    time.sleep(.5)
   rc=proc.returncode
 except BaseException as e:error=f'{type(e).__name__}:{e}'
 finally:
  if job:job.close()
  if proc is not None and proc.poll() is None:
   if os.name=='nt' and job is None:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
   else:
    import signal
    os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:
    if os.name!='nt':os.killpg(proc.pid,signal.SIGKILL)
    proc.wait(timeout=5)
  if proc is not None and os.name!='nt':
   import signal
   try:os.killpg(proc.pid,signal.SIGTERM)
   except ProcessLookupError:pass
  result=g.close();end={'unix':time.time(),'returncode':rc,'error':error,'child_pid':None if proc is None else proc.pid,'child_joined':proc is None or proc.poll() is not None,'resources':result}
  (a.out/'END.json').write_text(json.dumps(end,indent=2));print(json.dumps(end))
 if rc!=0 or error:raise SystemExit(1)
if __name__=='__main__':main()
