"""Foreground owner of one serial physical phase; bounded cleanup of owned group."""
from pathlib import Path
import os,sys,json,time,subprocess,signal
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
P=json.loads((S/'RUN_PLAN.json').read_text());mode=sys.argv[1]
assert time.time()<P['dispatch_cutoff_unix']-600
cmd=['/home/hank/envs/adaptive-online-rl-v1/bin/python','-B','-u',str(S/'code/overnight_runner.py'),mode]
record=dict(mode=mode,command=cmd,cwd=str(S),owner_pid=os.getpid(),start_unix=time.time())
path=S/'control'/('LAUNCH_'+mode+'.json')
with (S/'logs'/(mode+'.log')).open('w') as log:
    child=subprocess.Popen(cmd,cwd=S,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record['pid']=child.pid;path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    try:
        code=child.wait(timeout=max(1,P['physics_hard_stop_unix']-time.time()-30))
    except BaseException as error:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGINT)
            try:code=child.wait(timeout=25)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:code=child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=5)
        else:code=child.returncode
        record['owner_exception']=repr(error)
    record.update(returncode=code,end_unix=time.time(),outer_joined=True)
    path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
sys.exit(code if code>=0 else 1)
