from pathlib import Path
import json,time,hashlib,subprocess,shutil,os
OLD=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime')
S=OLD.parent/'m2_comprehensive_coordination_search_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
ROOT=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime/source')
T0=1791352438.
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(n,x):(S/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert not S.exists(),'New package exists: resume, never reinitialize'
 S.mkdir()
 for d in ('code','native','build','output','inputs','reports','versions','preservation','queue','logs','checkpoints'): (S/d).mkdir()
 save('RUN_PLAN.json',dict(t0_unix=T0,start_unix=T0,dispatch_cutoff_unix=T0+9.25*3600,hard_stop_unix=T0+10*3600,physics_budget=120,max_physics_budget=240,bytes_target=10*2**30,threads=1,no_training=True,Q_initially=False,G=False,no_three_revision_limit=True,physical_dt_s=.00025,control_dt_s=.005,regression_atol=1e-10,legacy_strict55_preserved=True,power_mode='User ordinary/quiet mode preserved; Windows active power scheme balanced (381b4222-f694-41f0-9685-ff5bb260df2e).',source=OLD.as_posix()))
 def git(*a):
  p=subprocess.run(['git','-C',str(ROOT),*a],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,text=True);assert p.returncode==0,p.stderr;return p.stdout
 save('GIT_BEFORE.json',dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),status=git('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=git('diff','--cached','--binary')))
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/404888bf-06b0-4701-be4d-60e70aa4e4d0/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 keys=[OLD/'REPORT.md',OLD/'FULL_PACKAGE_MANIFEST.json',OLD/'FINAL_CODE_MANIFEST.json',OLD/'preservation/FINAL_PRESERVATION.json',OLD/'versions/R3_SCIENTIFIC_GATE.json',OLD/'versions/R3_INSTALLED_RUNTIME.py',OLD/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',OLD/'output/HISTORICAL_K3_DESIGN_REFERENCE.json',OLD.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz']
 keys += [OLD/'code'/n for n in ('multirate.py','commissioning_owner.py','slow_owner.py','admission_certificates.py','run_one.py','native_method.py','q_first_method.py','study_common.py','task_bootstrap.py')]
 for p in keys:assert p.is_file(),str(p)
 protected={str(p):sha(p) for p in keys};save('preservation/HISTORICAL_KEY_BEFORE.json',protected)
 save('preservation/PRIOR_MANIFEST_AUTHORITY.json',dict(prior_full=str(OLD/'FULL_PACKAGE_MANIFEST.json'),sha256=sha(OLD/'FULL_PACKAGE_MANIFEST.json'),historical_authority=str(OLD/'preservation/HISTORICAL_BEFORE.json'),historical_authority_sha256=sha(OLD/'preservation/HISTORICAL_BEFORE.json'),policy='No full historical raw library copy or repeated whole-history hash scans. Key files and reused source are verified.'))
 for d in ('source','deps','code'):
  shutil.copytree(OLD/d,S/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('results','__pycache__'))
 (S/'source/results').mkdir(exist_ok=True)
 relocation=[]
 for d in ('code','deps','source'):
  for p in (S/d).rglob('*.py'):
   original=p.read_text();text=original.replace(str(OLD),str(S)).replace('"b_multirate_realtime_v1"','"m2_comprehensive_coordination_search_v1"')
   if text!=original:
    relocation.append(dict(path=str(p.relative_to(S)),old_sha256=sha(p)));p.write_text(text);relocation[-1]['new_sha256']=sha(p)
 save('SOURCE_RELOCATION.json',relocation)
 for n in ('SHARED_COORDINATION_ACTION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json'):shutil.copy2(OLD/'output'/n,S/'output'/n)
 shutil.copy2(W/'initialize.py',S/'code/initialize_fast_package.py')
 save('SOURCE_BEFORE.json',{str(p.relative_to(S)):sha(p) for d in ('source','deps','code') for p in (S/d).rglob('*') if p.is_file() and 'results' not in p.parts})
 save('STATE.json',dict(status='PREFLIGHT',phase='SETUP',t0_unix=T0,updated_unix=time.time(),physics_attempts=0,next_action='Preflight entry, freeze functional criteria, low-overhead cycle/controller/plant attribution; then implement hottest 1–3 paths and causal ceil-grid command ownership.',completed=[],active=[]))
 save('TASK_LEDGER.json',{})
 (S/'ATTEMPTS.jsonl').touch()
 (S/'PROGRESS.md').write_text('SETUP: t0=2026-10-07 05:53:58 UTC, immutable 10-hour cap; 120 initial /240 absolute attempts. No physics dispatched.\n')
 print('INITIALIZED',S,'elapsed_s',time.time()-T0)
if __name__=='__main__':main()
