from pathlib import Path
import hashlib,json,subprocess,time,shutil,os

OLD=Path('/home/hank/ihear-lab/representation_execution_v3/runtime')
NEW=OLD.parent/'m2_comprehensive_coordination_search_v1'
WIN=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_multirate_realtime_v1')
ROOT=Path('/home/hank/ihear-lab/representation_execution_v3/runtime/source')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def git():
 def run(*args):return subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True).stdout
 return dict(branch=run('branch','--show-current'),HEAD=run('rev-parse','HEAD'),status=run('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=run('diff','--cached','--binary'))
def main():
 assert not NEW.exists(),'Existing package must not be overwritten'
 NEW.mkdir()
 for d in ('code','output','reports','versions','logs','inputs','preservation'): (NEW/d).mkdir()
 shutil.copy2(WIN/'initialize.py',NEW/'code/initialize.py')
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/a5845084-9428-43bc-93b1-0f88a9227674/已粘贴的文本.txt',NEW/'USER_REQUEST.txt')
 save(NEW/'GIT_BEFORE.json',git())
 start=time.time()
 save(NEW/'RUN_PLAN.json',dict(start_unix=start,preferred_closeout_unix=start+5.25*3600,dispatch_cutoff_unix=start+7.25*3600,hard_stop_unix=start+8*3600,max_revisions=3,Q=False,G=False,learning=False,M2_gate='B_HOST_QUALIFIED and remaining time >=5400s',regression_tolerance=1e-10,regression_exact_preferred=True,asynchronous_host_differences='Timing diagnostics may differ. No post-hoc numeric tolerance relaxation. Physical scientific traces, references, decisions and phases must match original scientific mode within 1e-10.',cold_seeds=[2026100711,2026100712,2026100713,2026100714],session_seeds=[2026100721,2026100722,2026100723,2026100724],development_seed=2026100610))
 protected={}
 for name in ('b_native_learning_matrix_v1','b_native_q_realtime_integration_v1','coordination_residual_realization_v2'):
  d=OLD.parent/name
  if d.exists():
   for p in d.rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:protected[str(p)]=sha(p)
 save(NEW/'preservation/HISTORICAL_BEFORE.json',protected)
 print('Protected historical files',len(protected),flush=True)
 for d in ('source','deps','code'):
  shutil.copytree(OLD/d,NEW/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','results'))
 (NEW/'source/results').mkdir(exist_ok=True)
 relocation=[]
 for d in ('code','deps','source'):
  for p in (NEW/d).rglob('*.py'):
   text=p.read_text()
   if str(OLD) in text:
    h=sha(p);p.write_text(text.replace(str(OLD),str(NEW)));relocation.append(dict(path=str(p),before_sha256=h,after_sha256=sha(p)))
 save(NEW/'SOURCE_RELOCATION.json',relocation)
 save(NEW/'SOURCE_MANIFEST.json',{str(p):sha(p) for d in ('source','deps','code') for p in (NEW/d).rglob('*') if p.is_file()})
 save(NEW/'preservation/CONTROL_BEFORE.json',{str(p):sha(p) for p in (NEW/'source').rglob('*') if p.is_file()})
 shutil.copy2(OLD/'output/HISTORICAL_K3_DESIGN_REFERENCE.json',NEW/'output/HISTORICAL_K3_DESIGN_REFERENCE.json')
 shutil.copy2(WIN/'initialize.py',NEW/'code/initialize.py')
 print('Initialized',NEW, 'elapsed',time.time()-start,flush=True)
if __name__=='__main__':main()
