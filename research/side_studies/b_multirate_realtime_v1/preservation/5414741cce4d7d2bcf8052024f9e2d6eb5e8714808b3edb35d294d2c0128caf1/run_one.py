import os,sys,time,json,traceback,random
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_multirate_realtime_v1')
sys.path.insert(0,str(S/'code'))
def main():
 cfg=json.loads(Path(sys.argv[1]).read_text());ident=cfg['id'];start=time.time()
 import lean_instrumentation
 lean_instrumentation.prime()
 import study_common as sc
 import numpy as np
 random.seed(cfg['seed']);np.random.seed(cfg['seed'])
 import multirate
 multirate.install(cfg['revision'],cfg['execution_mode'])
 from native_method import PrefixBInterface
 interface=PrefixBInterface(dict(method='M0',prefix=cfg.get('prefix',{}),execution_mode=cfg['execution_mode']))
 try:
  metric=sc.run(ident,interface,original=False,execution_mode=cfg['execution_mode'])
  result=dict(id=ident,status='COMPLETE',metric=metric,wall_seconds=time.time()-start,inputs=cfg)
 except BaseException as e:
  result=dict(id=ident,status='FAILED',error=str(e),traceback=traceback.format_exc(),wall_seconds=time.time()-start,inputs=cfg)
 finally:
  sc.save(ident+'_MULTIRATE.json',multirate.evidence())
  sc.save(ident+'_RESULT.json',result)
  sc.save(ident+'_IMPORTED_SOURCES.json',{str(m.__file__):sc.sha(Path(m.__file__)) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and str(m.__file__).startswith(str(S)) and Path(m.__file__).is_file()})
 print(json.dumps({k:result.get(k) for k in ('id','status','error','wall_seconds')}),flush=True)
if __name__=='__main__':main()
