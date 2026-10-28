"""Run one registered offline entry point with PID identity and bounded deadline."""
from pathlib import Path
import os,sys,json,time,signal,runpy,hashlib
P=Path(__file__).resolve().parents[1];script=P/'source'/sys.argv[1];args=sys.argv[2:];job='OFFLINE_'+script.stem+'_'+str(time.time_ns());start=time.time();stat=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();identity={'pid':os.getpid(),'start_ticks':int(stat[19]),'started_unix':start,'script':str(script.relative_to(P)),'source_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'arguments':args,'branch':'EVALUATION_AND_RAW_RECOMPUTE'}
def put(n,d):
 f=P/n;q=f.with_name(f.name+'.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(f)
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OFFLINE_LOCAL_OR_GLOBAL_DEADLINE')));signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(SystemExit('OFFLINE_TERMINATED_PRESERVED')));a=json.loads((P/'ACTIVATION.json').read_text());signal.alarm(max(1,int(min(900,a['deadline_unix']-start))));os.environ.update(ACL2_PACKAGE=str(P),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:6])
put('owned/'+job+'_START.json',identity)
try:
 sys.argv=[str(script),*args];sys.path.insert(0,str(P/'source'));runpy.run_path(str(script),run_name='__main__');put('owned/'+job+'_END.json',dict(status='PASS',ended_unix=time.time(),wall_s=time.time()-start,**identity))
except BaseException as e:
 put('owned/'+job+'_END.json',dict(status='FAILED_PRESERVED',ended_unix=time.time(),error=str(e),**identity));raise
