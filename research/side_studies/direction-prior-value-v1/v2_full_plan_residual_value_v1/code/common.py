from pathlib import Path
import json,hashlib,sys,os,time,subprocess,shutil
sys.dont_write_bytecode=True
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1')
AUDIT=OLD/'v_horizon_continuation_audit_v1'
NEW=OLD/'v2_full_plan_residual_value_v1'
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
LOCAL=Path(__file__).resolve().parent
START=1791269812
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def main_git():
 run=lambda *a:subprocess.check_output(['git','-C',str(ROOT),*a],text=True)
 return dict(branch=run('branch','--show-current').strip(),head=run('rev-parse','HEAD').strip(),status=run('status','--short'),index=sha(ROOT/'.git/index'),cached=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest())
def hostpath(s):
 if len(s)>2 and s[1]==':':return Path('/mnt/'+s[0].lower()+'/'+s[3:].replace('\\','/'))
 return Path(s)
