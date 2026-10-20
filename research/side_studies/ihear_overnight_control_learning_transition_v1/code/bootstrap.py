from pathlib import Path
import os,sys,json,time,datetime,hashlib,shutil,subprocess
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1')
OLD=S.parent/'b_runtime_qualification_decoupling_v1'
H=S.parent/'b_hold_return_critical_path_v1'
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
T0=datetime.datetime.fromisoformat('2026-10-08T04:56:02+00:00').timestamp()
QHASH='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(2**20):h.update(b)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def git_snapshot():
 def git(*args):
  r=subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,check=True);return r.stdout
 return dict(branch=git('branch','--show-current').decode(),HEAD=git('rev-parse','HEAD').decode(),status=git('status','--porcelain=v1').decode(),index_sha256=sha(ROOT/'.git/index'),staged_diff_sha256=hashlib.sha256(git('diff','--cached','--binary')).hexdigest())
def main():
 assert not S.exists(),'Never reset an existing package'
 S.mkdir()
 for d in ('reports','preservation','queue','logs','output','inputs','versions','checkpoints','weights'):(S/d).mkdir()
 plan=dict(t0_unix=T0,t0_basis='first observed UTC clock at task entry',hard_stop_unix=T0+10800,dispatch_cutoff_unix=T0+9600,physics_budget=20,max_physics_budget=20,physical_dt_s=.00025,control_dt_s=.005,threads=1,bytes_target=4*2**30,single_physics_owner=True,no_auto_resume=True)
 prior=json.loads((OLD/'QUALIFICATION_CONTRACT.json').read_text())
 numerical=prior['axes']['B_RUNTIME_MOTION_QUALIFIED']['numerical_runtime_requirements']
 contract=dict(schema='B_FAST_JITTER_M2_HOST_v1',registered_unix=time.time(),budget=plan,tracks_independent=True,label='RESEARCH_HOST_EXPERIMENT / RUNTIME_NOT_QUALIFIED',science=prior['frozen_science'],axes=dict(PHYSICAL_TASK_VALID=['original physical scorer PASS','full task or preregistered legal segment','controlled original HOLD','no native execution failure'],HOST_EXECUTION_CAUSAL_VALID=['every physical step owner reconstructed','no expired actual write','original current admission and fallback','original timestamps and native permission'],FAST_RUNTIME_ENGINEERING_QUALIFIED=numerical,LEGACY_R2_MATCHED=prior['axes']['LEGACY_R2_MATCHED'],LEGACY_STRICT55=prior['axes']['LEGACY_STRICT55']),Q_sha256=QHASH,Q_training=0,Q_online_updates=0,G=False,P_full_repetition_optimizer=False,adaptive_Q=False,Human_matrix_expansion=False,allowed_inputs=prior['inputs'],truth_firewall='evaluation truth used only after execution, never selection',hypotheses=['Historical FAST slowdown source is unknown; compare exact implementation, measurement and within-run conditions before attributing','Frozen M2 can physically execute nonzero native coordination with unchanged safety, irrespective of FAST engineering qualification','Paired raw force changes require separate phase-duration and moment attribution'],setup='Existing nominal and legal prefix conditions; development smoke and bounded matched pairs, no new held-out/generalized claim',seeds=[2026100801,2026100802],pair_plan=['nominal pair1 B then M2','nominal pair2 M2 then B','deviation pair1 B then M2','deviation pair2 M2 then B'],candidate_budget=6,issued_count_semantics='modifiable issued proposals, never silently committed count',K3=[.1,.4,.7],zero_residual='original B',guard_policy='guard-on min(40,55-36)=19ms; guard-off retains 40ms physical bridge deadline and original 100ms lifecycle/current admission/ownership; classify before changing',repair_policy='one evidence-based M2 adapter repair; no controller/physics/safety/planner or Q changes',phase_attribution='raw complete task integrals, no trimming; symmetric duration and mean-force decomposition, moment integral/peak retained',exclusions='none; all failures retained; incomplete pairs not valid pairs',stop_policy='stop individual run for actual safety/causality/native permission failure; FAST engineering alone does not stop Track B; heavy dispatch stops final20min',prohibited=prior['prohibited'])
 save(S/'RUN_PLAN.json',plan);save(S/'EXPERIMENT_CONTRACT.json',contract);save(S/'QUALIFICATION_CONTRACT.json',contract)
 save(S/'preservation/GIT_BEFORE.json',git_snapshot())
 protected={}
 for name in ('b_runtime_qualification_decoupling_v1','b_hold_return_critical_path_v1','b_fast_runtime_completion_v1','b_native_q_realtime_integration_v1','b_native_learning_matrix_v1'):
  folder=S.parent/name
  for rel in ('REPORT.md','PACKAGE_CLOSED.json','FULL_PACKAGE_MANIFEST.json','FINAL_CODE_MANIFEST.json','RUN_PLAN.json','TASK_LEDGER.json','ATTEMPTS.jsonl'):
   p=folder/rel
   if p.is_file():protected[str(p)]=sha(p)
 q=S.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1'
 assert sha(q/'weights.npz')==QHASH
 for p in q.iterdir():
  if p.is_file():protected[str(p)]=sha(p)
 manifest=json.loads((OLD/'FINAL_CODE_MANIFEST.json').read_text());verified=[]
 for rel,value in manifest.items():
  if rel.split('/')[0] in ('source','deps','code','native','build') and 'results' not in Path(rel).parts:
   expected=value.get('sha256') if isinstance(value,dict) else value
   assert sha(OLD/rel)==expected,rel;verified.append(rel);protected[str(OLD/rel)]=expected
 save(S/'preservation/PROTECTED_BEFORE.json',protected)
 save(S/'preservation/C13_SOURCE_VERIFICATION.json',dict(status='PASS',verified_files=len(verified),manifest=str(OLD/'FINAL_CODE_MANIFEST.json'),native_binary={str(p):sha(p) for p in (OLD/'build').rglob('*.so')}))
 for d in ('source','deps','code','native','build'):
  shutil.copytree(OLD/d,S/d,ignore=shutil.ignore_patterns('results','__pycache__','temp.*'))
 (S/'source/results').mkdir(exist_ok=True)
 relocation=[]
 for d in ('source','deps','code'):
  for p in (S/d).rglob('*.py'):
   text=p.read_text();new=text.replace(str(OLD),str(S)).replace('"b_runtime_qualification_decoupling_v1"','"m2_comprehensive_coordination_search_v1"').replace("'b_runtime_qualification_decoupling_v1'","'m2_comprehensive_coordination_search_v1'")
   if text!=new:
    before=sha(p);p.write_text(new);relocation.append(dict(path=str(p.relative_to(S)),before=before,after=sha(p)))
 save(S/'preservation/SOURCE_RELOCATION.json',relocation)
 for p in (OLD/'versions').iterdir():
  if p.is_file():shutil.copy2(p,S/'versions'/p.name)
 for rel in ('C13_LOCAL_EQUIVALENCE.json','C12_LOCAL_EQUIVALENCE.json'):shutil.copy2(OLD/'output'/rel,S/'output'/rel)
 shutil.copytree(q,S/'weights/frozen_Q_v1')
 timing=S.parent/'b_native_q_realtime_integration_v1/TIMING_BASELINE.json'
 shutil.copy2(timing,S/'TIMING_BASELINE.json')
 # The saved shared-action contract is a mandatory input, not optional code.
 for p in (OLD/'source').rglob('*action*contract*.json'):
  dest=S/'source'/p.relative_to(OLD/'source');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 save(S/'TASK_LEDGER.json',{});(S/'ATTEMPTS.jsonl').touch()
 save(S/'STATE.json',dict(status='ACTIVE',phase='PREFLIGHT',active=[],t0_unix=T0,physics_attempts=0))
 for p in W.glob('*.py'):shutil.copy2(p,S/'code'/p.name)
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/417c53f1-437a-43f5-b6c9-36dd9a0757b9/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 for rel in ('EXPERIMENT_CONTRACT.json','QUALIFICATION_CONTRACT.json','RUN_PLAN.json'):shutil.copy2(S/rel,W/rel)
 print(json.dumps(dict(status='INITIALIZED',path=str(S),verified_C13_files=len(verified),source_relocations=len(relocation),elapsed_s=time.time()-T0)))
if __name__=='__main__':main()
