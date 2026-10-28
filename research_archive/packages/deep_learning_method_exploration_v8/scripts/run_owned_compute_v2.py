"""Finite, single-child non-physics computation with durable resource records."""
from pathlib import Path
import argparse,hashlib,json,os,resource,subprocess,sys,time,traceback
P=Path(__file__).resolve().parents[1]
def write_new(p,obj):
    with p.open('x') as stream:json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--timeout',type=float,required=True);parser.add_argument('command',nargs=argparse.REMAINDER);args=parser.parse_args()
    import re
    assert re.fullmatch(r'[A-Za-z0-9_]{1,100}',args.label)
    command=args.command[1:] if args.command and args.command[0]=='--' else args.command
    script=(P/command[0]).resolve();assert script.is_relative_to(P) and script.suffix=='.py'
    activation=json.loads((P/'ACTIVATION.json').read_text());remaining=activation['hard_stop_unix']-time.time();assert remaining>0 and 0<args.timeout<=600
    command=[sys.executable,'-B',str(script),*command[1:]];started=time.time();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    start=P/'owned'/(args.label+'_START.json');end=P/'owned'/(args.label+'_END.json')
    assert not start.exists() and not end.exists()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',ACL2_PACKAGE=str(P))
    record={'label':args.label,'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':started,'activation':activation['activation_id'],'global_hard_deadline_unix':activation['hard_stop_unix'],'timeout_s':min(args.timeout,remaining),'command':command,'script_sha256':sha(script),'wrapper_sha256':sha(__file__),'python_binary_sha256':sha(Path(sys.executable).resolve()),'physics_dispatch_authorized_by_this_wrapper':False}
    write_new(start,record);code=None;error=None
    try:
        with (P/'logs'/(args.label+'.log')).open('x') as stream:
            process=subprocess.Popen(command,cwd=P,env=env,stdout=stream,stderr=subprocess.STDOUT)
            try:
                try:child_ticks=int((Path('/proc')/str(process.pid)/'stat').read_text().rsplit(')',1)[1].split()[19])
                except FileNotFoundError:child_ticks=None
                write_new(P/'owned'/(args.label+'_CHILD.json'),{'pid':process.pid,'start_ticks':child_ticks,'identity_capture':'PROC_STAT' if child_ticks is not None else 'EXITED_BEFORE_PROC_CAPTURE_WAITED_BY_POPEN_HANDLE','parent_pid':os.getpid(),'started_unix':time.time()})
                code=process.wait(timeout=min(args.timeout,remaining))
            except BaseException:
                process.kill();process.wait();raise
        assert code==0,'OWNED_COMPUTE_CHILD_FAILED:'+str(code)
    except BaseException as exc:error=type(exc).__name__+':'+str(exc);raise
    finally:
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        write_new(end,{**record,'ended_unix':time.time(),'wall_s':time.time()-started,'status':'PASS' if error is None else 'FAILED_PRESERVED','returncode':code,'error':error,'child_CPU_user_s':after.ru_utime-before.ru_utime,'child_CPU_system_s':after.ru_stime-before.ru_stime,'child_max_RSS_KiB':after.ru_maxrss,'child_joined':True,'resource_scope':'one owned direct child and its waited computation; peak RSS is RUSAGE_CHILDREN high water in this fresh wrapper process'})
    print(args.label,'COMPUTE_PASS','wall_s',time.time()-started)
if __name__=='__main__':main()
