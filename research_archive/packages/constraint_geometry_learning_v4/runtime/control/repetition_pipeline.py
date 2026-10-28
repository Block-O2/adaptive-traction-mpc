from pathlib import Path
import os,sys,time,json,subprocess,traceback
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
plan=json.loads((P/'RUN_PLAN.json').read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
put('audit/REPETITION_PIPELINE_OWNER.json',dict(pid=os.getpid(),start=time.time(),source='preregistered before primary test outcomes'))
try:
    while not (P/'audit/LEARNING_PIPELINE_EXIT.json').exists():
        assert time.time()<plan['no_new_physics_after_unix']-1800;time.sleep(15)
    assert (P/'LEARNING_PIPELINE_DONE.json').exists(),'MAIN_LEARNING_PIPELINE_DID_NOT_COMPLETE'
    records=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
    assert sum(r['event']=='START' for r in records)+6<=100
    subprocess.run([sys.executable,'-B',str(R/'control/prepare_repetition.py')],check=True,cwd=P)
    subprocess.run([sys.executable,'-B',str(P/'control/repetition_owner.py')],check=True,cwd=P)
    subprocess.run([sys.executable,'-B',str(R/'analysis/audit_raw.py'),'@REP_FIRST','REP'],check=True,cwd=P)
    put('REPETITION_PIPELINE_DONE.json',dict(status='PASS',unix=time.time(),scope='pilot execution and raw arithmetic complete; scientific gain still requires evaluation'))
except BaseException as e:
    put('audit/REPETITION_PIPELINE_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('audit/REPETITION_PIPELINE_EXIT.json',dict(pid=os.getpid(),end=time.time()))
