"""Freeze only needed source, never mutate the primary checkout."""
from pathlib import Path
import json, hashlib, shutil, subprocess, time, sys
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1')
STUDY=OLD.parent/'b_native_learning_matrix_v1'
LOCAL=Path(__file__).resolve().parent
START=1791273540
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def main():
 STUDY.mkdir(exist_ok=True)
 if (STUDY/'SOURCE.json').exists():print('ALREADY_FROZEN');return
 git=lambda *args:subprocess.check_output(['git','-C',str(ROOT),*args],text=True)
 save(STUDY/'GIT_BEFORE.json',dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),status=git('status','--short'),index_sha256=sha(ROOT/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--cached','--binary'])).hexdigest()))
 files={};origins={};diff=[]
 # Reuse the verified native and streaming source freeze, with no old results.
 for p in (OLD/'source/stages').rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  rel=p.relative_to(OLD/'source');dest=STUDY/'source'/rel
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);origins[str(p)]=sha(p)
  if dest.suffix=='.py':dest.write_text(dest.read_text().replace(str(OLD/'source'),str(STUDY/'source')))
  files[str(dest)]=sha(dest)
  primary=ROOT/rel
  if primary.exists() and sha(primary)!=sha(p):diff.append(dict(relative=str(rel),primary_sha256=sha(primary),frozen_sha256=sha(p)))
 for p in (OLD/'deps').iterdir():
  if not p.is_file():continue
  dest=STUDY/'deps'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);origins[str(p)]=sha(p)
  if dest.suffix=='.py':dest.write_text(dest.read_text().replace(str(OLD),str(STUDY)))
  files[str(dest)]=sha(dest)
 for name in ('SHARED_COORDINATION_ACTION_CONTRACT.json','OBSERVATION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json'):
  p=OLD/'output'/name;dest=STUDY/'output'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);origins[str(p)]=sha(p)
 for d in ('code','queue','logs','weights','reports'): (STUDY/d).mkdir(exist_ok=True)
 request=Path('/mnt/c/Users/HankL/.codex/attachments/db755dbc-a497-4f4c-9912-cdaf36ec7f22/已粘贴的文本.txt')
 shutil.copy2(request,STUDY/'USER_REQUEST.txt')
 save(STUDY/'SOURCE.json',dict(originals=origins,frozen_files=files,primary_vs_old_freeze_differences=diff,total_source_bytes=sum(Path(p).stat().st_size for p in files),snapshot_basis=str(OLD),primary_unchanged=True))
 save(STUDY/'RUN_PLAN.json',dict(version=1,start_unix=START,deadline_unix=START+9*3600,dispatch_cutoff_unix=START+8.25*3600,max_physics_attempts=240,development_cap=160,reserved_independent_attempts=80,physics_owners=1,max_new_bytes=12*2**30,development_iterations_max=2,information='B actual commissioned estimated belief only',Q_definition='remaining actual current-repetition J_F N s conditioned on causal native state and committed K3 suffix; native rejection/fallback stays active; no P performance replanning',continuation='native-certified-committed-K3-suffix-v1',models=dict(V=[128,128],G=[128,128],linear_V=True),split_rule='parent and all branches together; exact/near duplicates excluded across train/dev/test; shared initial states disclosed',methods=['M0 original B','M1 interface + reusable native S if defined else strong fixed developed policy','M2 ordinary candidates + Q','M3 G + same S only if S defined','M4 mixed ordinary/G candidates + Q'],candidate_budget=6,online='source-grounded deadline; retain legal carry when late; scientific and delayed replay separate',resources=dict(sample_s=45,backoff_s=[300,600,1200],max_recovery_s=3600),phase='B_QUALIFICATION'))
 save(STUDY/'CHECKPOINT.json',dict(phase='SOURCE_FROZEN',next='sync harness, inspect actual B native scoring/deadline, original and zero physical regressions',start_unix=START,attempts=0))
 (STUDY/'PROGRESS.md').write_text('Source frozen; B qualification next. All old scientific outcomes remain historical.\n')
 (STUDY/'ATTEMPTS.jsonl').touch();(STUDY/'COMPUTE_LEDGER.jsonl').touch()
 (STUDY/'RESUME.md').write_text('Read RUN_PLAN, CHECKPOINT, ATTEMPTS, TASK_LEDGER before restarting. Preserve original clock/caps. Never replay completed IDs. Use explicit retry IDs for incomplete attempts. One physics owner only.\n')
 print(json.dumps(dict(study=str(STUDY),files=len(files),bytes=sum(Path(p).stat().st_size for p in files),differences=len(diff))))
if __name__=='__main__':main()
