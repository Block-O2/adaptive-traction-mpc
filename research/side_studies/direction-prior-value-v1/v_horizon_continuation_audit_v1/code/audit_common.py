from pathlib import Path
import json,hashlib,shutil,subprocess,sys,time,os
sys.dont_write_bytecode=True
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1')
STUDY=OLD/'v_horizon_continuation_audit_v1'
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
LOCAL=Path(__file__).resolve().parent
START=1791263194
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def main_git():
 run=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True)
 return dict(branch=run('branch','--show-current').strip(),head=run('rev-parse','HEAD').strip(),status=run('status','--short'),index=sha(ROOT/'.git/index'),cached=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest())
