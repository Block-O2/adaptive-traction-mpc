"""Final arithmetic, reports and protection audit after the repaired pilot exits."""
from pathlib import Path
import os,sys,json,time,subprocess,traceback,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def run(name,*args):
    print('FINAL_RETRY_STEP',name,*args,flush=True)
    with (P/'logs'/('final_retry_'+name.removesuffix('.py')+'.log')).open('x') as log:
        subprocess.run([sys.executable,'-B',str(R/'analysis'/name),*args],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=P)
assert json.loads((P/'REPETITION_RETRY_OWNER.json').read_text())['joined']
put('audit/FINAL_RETRY_OWNER.json',dict(pid=os.getpid(),unix=time.time()))
try:
    missing=[]
    for folder in (P/'source/results').iterdir():
        f=folder/'summary.json'
        if not f.exists():continue
        trans=json.loads(f.read_text()).get('task',{}).get('phase_transitions',[])
        if trans and trans[-1]['to']=='COMPLETE' and not (P/'derived'/(folder.name+'_INDEPENDENT.json')).exists():missing.append('@'+folder.name)
    if missing:run('audit_raw.py',*missing)
    for n in ['summarize_science.py','final_figures.py','verify_science.py','write_final_reports.py','close_physics.py','final_history_audit.py']:run(n)
    for f in (P/'figures').glob('*.png'):shutil.copy2(f,R/'figures'/f.name)
    put('audit/FINAL_RETRY_DONE.json',dict(status='PASS',unix=time.time(),remaining='visual QA and seal_and_deliver'))
except BaseException as e:
    put('audit/FINAL_RETRY_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('audit/FINAL_RETRY_EXIT.json',dict(pid=os.getpid(),unix=time.time()))
