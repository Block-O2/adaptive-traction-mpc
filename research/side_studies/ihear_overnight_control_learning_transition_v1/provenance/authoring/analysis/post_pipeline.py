"""Finish audits and reports after experiment ownership closes; no new physics."""
from pathlib import Path
import os,sys,json,time,subprocess,traceback
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def run(name,*args):
    print('POST_STEP',name,*args,flush=True)
    with (P/'logs'/('post_'+name.removesuffix('.py')+'.log')).open('x') as log:
        subprocess.run([sys.executable,'-B',str(R/'analysis'/name),*args],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=P)
put('audit/POST_PIPELINE_OWNER.json',dict(pid=os.getpid(),start=time.time()))
try:
    while not (P/'audit/REPETITION_PIPELINE_EXIT.json').exists():time.sleep(15)
    assert (P/'LEARNING_PIPELINE_DONE.json').exists(),'PRIMARY_PIPELINE_NOT_COMPLETE'
    while not (P/'audit/INCREMENTAL_AUDIT_EXIT.json').exists():time.sleep(15)
    assert (P/'audit/INCREMENTAL_AUDIT_DONE.json').exists(),'RAW_AUDIT_NOT_COMPLETE'
    remaining=[]
    for folder in (P/'source/results').iterdir():
        if not (folder/'summary.json').exists():continue
        s=json.loads((folder/'summary.json').read_text());trans=s.get('task',{}).get('phase_transitions',[])
        if trans and trans[-1]['to']=='COMPLETE' and not (P/'derived'/(folder.name+'_INDEPENDENT.json')).exists():remaining.append('@'+folder.name)
    if remaining:run('audit_raw.py',*remaining)
    run('summarize_science.py')
    run('coupled_contrasts.py','D01R','D02','D03','D04','D05','D06','V01','V02','U01','U02','U03')
    run('final_figures.py')
    run('verify_science.py')
    run('write_final_reports.py')
    run('close_physics.py')
    run('final_history_audit.py')
    for f in (P/'figures').glob('*.png'):
        import shutil
        shutil.copy2(f,R/'figures'/f.name)
    put('audit/POST_PIPELINE_DONE.json',dict(status='PASS',unix=time.time(),remaining='visual QA and final manifest/delivery sealing'))
except BaseException as e:
    put('audit/POST_PIPELINE_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('audit/POST_PIPELINE_EXIT.json',dict(pid=os.getpid(),unix=time.time()))
