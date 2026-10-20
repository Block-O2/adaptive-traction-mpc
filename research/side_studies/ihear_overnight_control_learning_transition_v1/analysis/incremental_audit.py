"""Read-only arithmetic on completed groups; never launches physics."""
from pathlib import Path
import sys, os, json, time, subprocess, traceback
R=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
put('audit/INCREMENTAL_AUDIT_OWNER.json',dict(pid=os.getpid(),start=time.time()))
done=[]
try:
    for g in ['D02','D03','D04','D05','D06','V01','V02','U01','U02','U03']:
        while not (P/(g+'_DONE.json')).exists():
            if (P/'STOP_ANALYSIS.json').exists():raise RuntimeError('STOP_REQUESTED')
            if (P/'audit/LEARNING_PIPELINE_ERROR.json').exists():raise RuntimeError('PIPELINE_STOPPED')
            time.sleep(15)
        with (P/'logs'/('audit_'+g+'.log')).open('x') as log:
            subprocess.run([sys.executable,'-B',str(R/'analysis/audit_raw.py'),g],stdout=log,stderr=subprocess.STDOUT,check=True)
        done.append(g);put('audit/INCREMENTAL_AUDIT_PROGRESS.json',dict(groups=done,unix=time.time()))
        print('INDEPENDENT_GROUP_AUDITED',g,flush=True)
    put('audit/INCREMENTAL_AUDIT_DONE.json',dict(status='PASS',groups=done,unix=time.time()))
except BaseException as e:
    put('audit/INCREMENTAL_AUDIT_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),groups=done,unix=time.time()));raise
finally:put('audit/INCREMENTAL_AUDIT_EXIT.json',dict(pid=os.getpid(),unix=time.time()))
