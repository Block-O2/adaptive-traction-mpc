"""仅真实主审批准后以外部 timeout 60s 调用；当前 SOURCE_ONLY，未执行。"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    args=argparse.ArgumentParser();args.add_argument('--package',required=True);args.add_argument('--approval',required=True);a=args.parse_args()
    P=Path(a.package).resolve();here=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('_approved_exact_terminal_runner_v7',here/'run_candidate.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    _,approval,contract=runner.bindings(P,a.approval)
    assert Path(sys.executable).absolute()==Path(contract['interpreter']['invoked_python'])
    assert os.environ.get('PYTHONDONTWRITEBYTECODE')=='1' and sys.dont_write_bytecode
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        assert os.environ.get(key)=='1','THREADS1_REQUIRED:'+key
    scope=here.parent;initial=resource.getrusage(resource.RUSAGE_SELF);started=time.time()
    save(scope/'EXECUTION_ATTEMPT_V1.json',{'status':'STARTED_NO_RETRY','PID':os.getpid(),'start_wall_unix':started,
         'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_initial_KiB':initial.ru_maxrss,
         'python_invoked':sys.executable,'python_binary':str(Path(sys.executable).resolve()),'python_binary_sha256':sha(Path(sys.executable).resolve()),
         'python_version':sys.version,'approval_sha256':sha(P/a.approval),'contract_sha256':approval['contract_sha256'],'new_physics':0})
    error=None;identity={}
    try:
        resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
        import numpy
        identity={'numpy_version':numpy.__version__,'numpy_file':str(Path(numpy.__file__).resolve()),'numpy_file_sha256':sha(numpy.__file__),
                  'scipy':'NOT_IMPORTED_OR_USED'}
        assert numpy.__version__==contract['interpreter']['numpy_version']
        assert sha(numpy.__file__)==contract['interpreter']['numpy_module_sha256']
        save(scope/'ACTUAL_INTERPRETER_IDENTITY_V1.json',identity)
        runner.run(P,a.approval)
    except BaseException as exc:
        error=repr(exc);raise
    finally:
        final=resource.getrusage(resource.RUSAGE_SELF)
        save(scope/'EXECUTION_INITIAL_FINAL_RESOURCE_V1.json',{'status':'FAILED_NO_RETRY' if error else 'COMPLETED','error':error,
             'initial_wall_unix':started,'final_wall_unix':time.time(),'wall_s':time.time()-started,
             'CPU_user_s':final.ru_utime-initial.ru_utime,'CPU_system_s':final.ru_stime-initial.ru_stime,
             'RSS_peak_KiB':final.ru_maxrss,'identity':identity,'new_physics':0,'auto_retry':False})


if __name__=='__main__':main()
