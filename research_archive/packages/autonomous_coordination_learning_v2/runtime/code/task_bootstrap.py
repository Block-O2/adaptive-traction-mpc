from pathlib import Path
import json,hashlib,shutil,time,sys,subprocess
ROOT=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source')
BASE=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
STUDY=BASE.parent/'m2_comprehensive_coordination_search_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
