from pathlib import Path
import os,sys,json,time,hashlib,shutil,subprocess
sys.dont_write_bytecode=True
BASE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
S=BASE/'m2_comprehensive_coordination_search_v1'
OLD=BASE/'m2_coordination_space_exploration_v1'
WIN=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_comprehensive_coordination_search_v1')
ROOT=Path('/home/hank/ihear-lab/smoothness_critic_integration_v6/runtime/source')
T0=1791483504.
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def git():
 def g(*a):return subprocess.check_output(['git','-C',str(ROOT),*a],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode()
 return dict(branch=g('branch','--show-current'),HEAD=g('rev-parse','HEAD'),status=g('status','--porcelain=v1'),index=sha(ROOT/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest())
def main():
 assert not S.exists(),'NO_OVERWRITE'
 S.mkdir()
 for d in ['code','reports','logs','preservation','output','motion_series','queue']:(S/d).mkdir()
 save(S/'preservation/GIT_BEFORE.json',git())
 names=['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1','m2_neural_q_motion_v1','m2_motion_counterfactual_ranking_v1','m2_coordination_space_exploration_v1','b_native_learning_matrix_v1','b_native_q_realtime_integration_v1']
 protected={}
 for name in names:
  for p in (BASE/name).rglob('*'):
   if p.is_file():protected[str(p)]=dict(bytes=p.stat().st_size,sha256=sha(p))
 save(S/'preservation/PROTECTED_BEFORE.json',protected)
 for d in ['source','deps','code','native','build','weights']:
  shutil.copytree(OLD/d,S/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
 (S/'source/results').mkdir()
 relocated=[]
 for d in ['source','deps','code']:
  for p in (S/d).rglob('*.py'):
   old=p.read_text();new=old.replace(str(OLD),str(S)).replace('"m2_coordination_space_exploration_v1"','"m2_comprehensive_coordination_search_v1"').replace("'m2_coordination_space_exploration_v1'","'m2_comprehensive_coordination_search_v1'")
   if new!=old:
    before=sha(p);p.write_text(new);relocated.append(dict(path=str(p.relative_to(S)),before=before,after=sha(p)))
 save(S/'preservation/RELOCATION.json',relocated)
 for p in (WIN/'code').glob('*.py'):shutil.copy2(p,S/'code'/p.name)
 shutil.copy2(OLD/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',S/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
 shutil.copy2(OLD/'MOTION_ACCEPTANCE_PROTOCOL.json',S/'MOTION_ACCEPTANCE_PROTOCOL.json')
 shutil.copy2(OLD/'TIMING_BASELINE.json',S/'TIMING_BASELINE.json')
 save(S/'RUN_PLAN.json',dict(t0_unix=T0,hard_stop_unix=T0+10800,dispatch_cutoff_unix=T0+9600,physics_budget=18,single_physics_owner=True))
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/ae0885be-cbdd-4fa8-9541-0c2570d40d00/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 save(S/'INITIALIZED.json',dict(unix=time.time(),protected_files=len(protected),relocations=len(relocated),source='current frozen B copy, path relocation only',physics_attempts=0))
 print(json.dumps(dict(initialized=str(S),protected_files=len(protected),elapsed=time.time()-T0)),flush=True)
if __name__=='__main__':main()
