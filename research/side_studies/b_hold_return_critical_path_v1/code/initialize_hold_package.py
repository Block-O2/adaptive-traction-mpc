from pathlib import Path
import hashlib,json,shutil,time,subprocess,os
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
S=OLD.parent/'b_hold_return_critical_path_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_hold_return_critical_path_v1')
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
T0=1791385530.0 # 2026-10-07 15:05:30 UTC; first actual request clock, never reset
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 p=S/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert not S.exists(),'Already initialized: resume only'
 assert (OLD/'PACKAGE_CLOSED.json').exists()
 S.mkdir()
 for d in ('code','native','build','output','inputs','reports','versions','preservation','queue','logs','checkpoints'):(S/d).mkdir()
 save('RUN_PLAN.json',dict(t0_unix=T0,start_unix=T0,dispatch_cutoff_unix=T0+4.5*3600,hard_stop_unix=T0+5*3600,physics_budget=80,max_physics_budget=80,bytes_target=4*2**30,threads=1,no_training=True,Q=False,G=False,physical_dt_s=.00025,control_dt_s=.005,regression_atol=1e-10,legacy_strict55_preserved=True,source=str(OLD),historical_read_only=True,power_mode='Unchanged ordinary/quiet mode'))
 save('EXPERIMENT_CONTRACT.json',dict(question='What delays the actual scored HOLD boundary, and can authorized implementation changes eliminate the excess?',required_original_conditions=dict(sensor_dwell_s=.5,shared_HOLD_minimum_s=1.,R2_HOLD_upper_s=1.020000001,completion_tolerance_s=1e-12,control_dt_s=.005,native_dt_s=.00025,K3='unchanged',planner_authority='unchanged',truth_firewall='unchanged'),stages=['Read-only same-transition reconstruction >=4 nominal +2 legal +slow tail','A/B/C dependency classification and saved-input equivalence','Each substantive version full SCI nominal and legal before host','Development two-run host smoke; expand only if justified','Qualification >=4 cold +4 reused interpreter +2 legal; each fresh plant/commission','Transition delay/stale/current-mismatch/reject only after nominal PASS','Freeze only all required gates, otherwise NOT_FROZEN'],split='Prior traces are development evidence; all new trials preregistered by immutable queue inputs; no held-out claim for development smoke',inputs='Original deployable B inputs only; no future state, no truth injected',seeds='Original nominal/deviation seeds preserved; cold/reused are timing replicates, not new Human families',exclusions='No failed attempt is removed; failed export is distinct from physical completion',stop='Five hours or 80 new physical starts or required forbidden scientific change or full freeze'))
 def git(*args):
  r=subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,text=True);assert r.returncode==0,r.stderr;return r.stdout
 save('GIT_BEFORE.json',dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),status=git('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=git('diff','--cached','--binary')))
 keys=[OLD/n for n in ('REPORT.md','STATE.json','PACKAGE_CLOSED.json','FULL_PACKAGE_MANIFEST.json','FINAL_CODE_MANIFEST.json','RUN_PLAN.json','TASK_LEDGER.json','ATTEMPTS.jsonl','preservation/FINAL_PRESERVATION.json','reports/FULL_PACKAGE_VERIFICATION.json')]
 keys += [OLD.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz']
 save('preservation/PROTECTED_BEFORE.json',{str(p):sha(p) for p in keys})
 for d in ('source','deps','code','native','build'):
  shutil.copytree(OLD/d,S/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('results','__pycache__','temp.*'))
 (S/'source/results').mkdir(exist_ok=True)
 relocated=[]
 for d in ('source','deps','code'):
  for p in (S/d).rglob('*.py'):
   original=p.read_text();new=original.replace(str(OLD),str(S)).replace('"b_fast_runtime_completion_v1"','"b_hold_return_critical_path_v1"').replace("'b_fast_runtime_completion_v1'","'b_hold_return_critical_path_v1'")
   if new!=original:
    before=sha(p);p.write_text(new);relocated.append(dict(path=str(p.relative_to(S)),before=before,after=sha(p)))
 save('SOURCE_RELOCATION.json',relocated)
 for name in ('SHARED_COORDINATION_ACTION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json'):shutil.copy2(OLD/'output'/name,S/'output'/name)
 for name in ('RUNTIME_FUNCTIONAL_CHECKS.json','R3_SCIENTIFIC_GATE.json'):
  if (OLD/'versions'/name).exists():shutil.copy2(OLD/'versions'/name,S/'versions'/name)
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/ef4746fd-fa82-4196-99ae-dfe6ebd0379b/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 shutil.copy2(W/'initialize.py',S/'code/initialize_hold_package.py')
 save('SOURCE_BEFORE.json',{str(p.relative_to(S)):sha(p) for d in ('source','deps','code','native','build') for p in (S/d).rglob('*') if p.is_file()})
 save('TASK_LEDGER.json',{});(S/'ATTEMPTS.jsonl').touch()
 save('STATE.json',dict(status='ACTIVE',phase='READ_ONLY_CRITICAL_PATH',t0_unix=T0,hard_stop_unix=T0+5*3600,physics_attempts=0,active=[],next_action='Reconstruct >=4 nominal and >=2 legal old transitions; classify exact dependencies before changes'))
 (S/'PROGRESS.md').write_text('New scope t0=2026-10-07 15:05:30 UTC; hard stop=20:05:30 UTC; max80 new starts. Prior package remains sealed.\n')
 print(json.dumps(dict(study=str(S),elapsed_s=time.time()-T0,source_files=len(json.loads((S/'SOURCE_BEFORE.json').read_text())))))
if __name__=='__main__':main()
