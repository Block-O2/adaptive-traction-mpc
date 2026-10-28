"""Wait for the owned first group, verify it, then execute the frozen dev matrix serially."""
from pathlib import Path
import sys,subprocess,time,json,os
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
plan=json.loads((P/'RUN_PLAN.json').read_text())
(P/'audit/CONTINUATION_OWNER.json').write_text(json.dumps(dict(pid=os.getpid(),start=time.time()))+'\n')
try:
    while not (P/'D01R_OWNER.json').exists():
        assert time.time()<plan['no_new_physics_after_unix'];time.sleep(10)
    assert json.loads((P/'D01R_OWNER.json').read_text())['returncode']==0,'FIRST_GROUP_FAILED'
    assert (P/'D01R_DONE.json').exists()
    subprocess.run([sys.executable,'-B',str(R/'analysis/check_reproduction.py')],check=True,cwd=P)
    subprocess.run([sys.executable,'-B',str(P/'control/run_development.py'),'D02','D03','D04','D05','D06','V01','V02'],check=True,cwd=P)
finally:
    (P/'audit/CONTINUATION_EXIT.json').write_text(json.dumps(dict(pid=os.getpid(),end=time.time()))+'\n')
