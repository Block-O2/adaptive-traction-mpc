"""One registered fit, bounded to 600s and original activation deadline."""
from pathlib import Path
import os,sys,time,json,signal,hashlib
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
from acl2_shared import put,sha,read
job=sys.argv[2];started=time.time();identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':started,'branch':'LOCAL_RESPONSE_SURROGATE_CAPABILITY_V1','source_sha256':sha(Path(__file__)),'model_source_sha256':sha(P/'source/v7_local_surrogate_v3.py'),'model_id':job}
assert read('ACTIVATION.json')['deadline_unix']-started>60
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('MODEL_FIT_LOCAL_OR_GLOBAL_DEADLINE')))
signal.alarm(max(1,int(min(600,read('ACTIVATION.json')['deadline_unix']-started))))
put('owned/'+job+'_FIT_START.json',identity)
try:
 from v7_local_surrogate_v3 import run
 run(sys.argv[1],job)
 put('owned/'+job+'_FIT_END.json',dict(status='PASS',ended_unix=time.time(),wall_s=time.time()-started,**identity))
except BaseException as e:
 put('owned/'+job+'_FIT_END.json',dict(status='FAILED_PRESERVED',error=str(e),ended_unix=time.time(),wall_s=time.time()-started,**identity));raise
