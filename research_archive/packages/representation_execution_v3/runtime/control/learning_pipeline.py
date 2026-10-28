"""Bounded serial research progression after dev matrix; fail closed on any pipeline error."""
from pathlib import Path
import os,sys,json,subprocess,time,shutil,traceback
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
plan=json.loads((P/'RUN_PLAN.json').read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def run(path,*args):
    assert time.time()<plan['no_new_physics_after_unix']
    print('PIPELINE_STEP',str(path),*args,flush=True)
    subprocess.run([sys.executable,'-B',str(path),*args],check=True,cwd=P)
put('audit/LEARNING_PIPELINE_OWNER.json',dict(pid=os.getpid(),start=time.time()))
try:
    while not (P/'audit/CONTINUATION_EXIT.json').exists():
        assert time.time()<plan['no_new_physics_after_unix'];time.sleep(15)
    assert (P/'V02_DONE.json').exists(),'DEVELOPMENT_NOT_COMPLETE'
    assert json.loads((P/'V02_OWNER.json').read_text())['returncode']==0
    for f in (R/'learning').glob('*.py'):shutil.copy2(f,P/'learning'/f.name)
    groups=['D01R','D02','D03','D04','D05','D06','V01','V02']
    run(P/'learning/dataset.py','development',*groups)
    run(P/'learning/train_value.py')
    run(R/'control/prepare_test.py')
    for group in ['U01','U02','U03']:
        run(P/'control/owner_v3.py',group,'validation')
        assert (P/(group+'_DONE.json')).exists()
    run(P/'learning/dataset.py','all',*groups,'U01','U02','U03')
    run(P/'learning/evaluate_value.py')
    run(R/'analysis/prediction_study.py')
    run(R/'analysis/model_response.py','D03','D04','D05','D06')
    put('LEARNING_PIPELINE_DONE.json',dict(status='PASS',unix=time.time(),scope='execution completed, not a claim of scientific generalization'))
except BaseException as e:
    put('audit/LEARNING_PIPELINE_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('audit/LEARNING_PIPELINE_EXIT.json',dict(pid=os.getpid(),end=time.time()))
