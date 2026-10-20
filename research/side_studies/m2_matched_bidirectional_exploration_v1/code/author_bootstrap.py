from pathlib import Path
import os, json, time, hashlib, shutil, subprocess, datetime
OLD=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1')
S=OLD.parent/'m2_matched_bidirectional_exploration_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_runtime_qualification_decoupling_v1')
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
T0=datetime.datetime.fromisoformat('2026-10-07T18:34:42+00:00').timestamp()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def git_snapshot():
 def git(*args):
  r=subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True);assert r.returncode==0,r.stderr;return r.stdout
 return dict(branch=git('branch','--show-current').decode(),HEAD=git('rev-parse','HEAD').decode(),status=git('status','--porcelain=v1').decode(),index_sha256=sha(ROOT/'.git/index'),staged_diff_sha256=hashlib.sha256(git('diff','--cached','--binary')).hexdigest())
def main():
 assert not S.exists(),'Resume existing package; never reset clock'
 assert (OLD/'PACKAGE_CLOSED.json').exists()
 S.mkdir()
 for d in ('reports','preservation','queue','logs','output','inputs','versions','checkpoints'):(S/d).mkdir()
 hard=min(T0+4*3600,datetime.datetime.fromisoformat('2026-10-08T07:30:00+08:00').timestamp())
 save(S/'RUN_PLAN.json',dict(t0_unix=T0,start_unix=T0,hard_stop_unix=hard,dispatch_cutoff_unix=hard-1800,physics_budget=50,max_physics_budget=50,bytes_target=4*2**30,threads=1,physical_dt_s=.00025,control_dt_s=.005,no_training=True,Q='frozen only',G=False,historical_read_only=True,single_physics_owner=True,no_auto_resume=True))
 protocol=json.loads((OLD/'versions/RUNTIME_FUNCTIONAL_CHECKS.json').read_text())['required']
 runtime={k:v for k,v in protocol.items() if k!='original_R2'}
 checks=['complete_physical_task_and_OUTBOUND_and_RETURN','meaningful_B_plans_actual_native_execution','FAST_feedback_continuous_and_bounded_backlog','command_write_and_physical_step_causality','no_stale_or_expired_write','current_state_admission_safety_mechanics','tracking_clearance_force_moment_native_physical_audit','legal_prior_control_continues_on_late_reject','HOLD_complete_controlled_original_dwell_minimum_completion','original_timestamps_no_backdate_no_free_physics_pause','source_and_config_identity']
 contract=dict(schema='B_RUNTIME_MOTION_QUALIFICATION_v1',registered_unix=time.time(),scope='Tested nominal and legal-deviation full host-clock MuJoCo simulation; no hardware or generalized claim',axes=dict(B_RUNTIME_MOTION_QUALIFIED=dict(all_required=checks,numerical_runtime_requirements=runtime,HOLD_upper_bound_is_not_gate=True),LEGACY_R2_MATCHED=dict(unchanged_original_evaluator=True,HOLD_upper_s=1.020000001,OUTBOUND_RETURN_original_timing_reported=True),LEGACY_STRICT55=dict(unchanged_original_qualification=True,activation_age_ms='strictly <55',not_sole_M2_gate=True)),frozen_science=dict(dwell_s=.5,HOLD_minimum_s=1.,completion_tolerance_s=1e-12,expiry_ms=100,control_dt_s=.005,native_dt_s=.00025,K3='unchanged',targets_physics_safety_controller='unchanged'),stages=['Read-only raw 047/048 evidence review under this contract','One nominal and one legal B host confirmation; fill only genuine evidence gaps','Freeze exact B source/config/runner/contract','Audit and version strict55-derived M2 research guard separately','Offline 120D feature/Q/count/carry/authority replay','Two actual host M2 smoke','If actual nonzero learning execution, two nominal plus two legal B/M2 pairs','Optional persistent repetition only if existing interface supports it and >=45min remain'],pairing=dict(conditions='same seed/prefix/commission information',baseline='same frozen B',candidate_budget=6,Q_sha256='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9',guard='same registered version within pair'),comparison=dict(primary='OUTBOUND+RETURN J_F with durations and phase mean force',raw_full_J_F='always retained',full_task_coordination_attribution_only_if_HOLD_difference_s_le=.005,no_HOLD_cut_or_fabrication=True,moment='integral and peak tradeoff reported'),M2_host_promising='Consistent direction force-cost benefit nominal and legal, actual nonzero execution, no added physical/safety/causal failure; no generalized/personalized learning claim',failure_policy='Retain all failures; no Q refit; at most one minimal M2 integration repair version; 4/2-candidate only if sole compute bottleneck',budget=dict(t0_unix=T0,hard_stop_unix=hard,dispatch_cutoff_unix=hard-1800,attempts=50),inputs='Original deployable observations/commissioned belief/current task reference/history only; evaluation truth never enters selection',split='Existing evidence is retrospective under new contract, new confirmations/smoke/paired timing repeats prospective; not fresh held-out Human families',exclusions='None; cold/replay/retry/fail/pair all new physics starts count',prohibited=['B control law changes','Human/physics/safety/task mathematics','timestamp rewrite','Q/G training','online adaptation','legacy result edits','main Git mutation'])
 save(S/'QUALIFICATION_CONTRACT.json',contract);shutil.copy2(S/'QUALIFICATION_CONTRACT.json',W/'QUALIFICATION_CONTRACT.json');shutil.copy2(S/'RUN_PLAN.json',W/'RUN_PLAN.json')
 save(S/'preservation/GIT_BEFORE.json',git_snapshot())
 protected={}
 for name in ('b_hold_return_critical_path_v1','b_fast_runtime_completion_v1','b_native_q_realtime_integration_v1','b_native_learning_matrix_v1'):
  folder=OLD.parent/name
  for rel in ('REPORT.md','PACKAGE_CLOSED.json','FULL_PACKAGE_MANIFEST.json','FINAL_CODE_MANIFEST.json','RUN_PLAN.json','TASK_LEDGER.json','ATTEMPTS.jsonl'):
   p=folder/rel
   if p.is_file():protected[str(p)]=sha(p)
 q=OLD.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz';protected[str(q)]=sha(q);assert protected[str(q)]==contract['pairing']['Q_sha256']
 save(S/'preservation/PROTECTED_BEFORE.json',protected)
 manifest=json.loads((OLD/'FINAL_CODE_MANIFEST.json').read_text());verified=[]
 for rel,value in manifest.items():
  if rel.split('/')[0] in ('source','deps','code','native','build'):
   expected=value.get('sha256') if isinstance(value,dict) else value
   assert sha(OLD/rel)==expected,rel;verified.append(rel)
 save(S/'preservation/C13_SOURCE_VERIFICATION.json',dict(status='PASS',verified_files=len(verified),fast_runtime_sha256=sha(OLD/'code/fast_runtime.py'),C13_version_sha256=sha(OLD/'versions/C13_fast_runtime.py'),runtime_exact_C13=sha(OLD/'code/fast_runtime.py')==sha(OLD/'versions/C13_fast_runtime.py')))
 for d in ('source','deps','code','native','build'):
  shutil.copytree(OLD/d,S/d,ignore=shutil.ignore_patterns('results','__pycache__','temp.*'))
 (S/'source/results').mkdir(exist_ok=True)
 relocated=[]
 for d in ('source','deps','code'):
  for p in (S/d).rglob('*.py'):
   t=p.read_text();new=t.replace(str(OLD),str(S)).replace('"b_hold_return_critical_path_v1"','"m2_matched_bidirectional_exploration_v1"').replace("'b_hold_return_critical_path_v1'","'m2_matched_bidirectional_exploration_v1'")
   if t!=new:
    before=sha(p);p.write_text(new);relocated.append(dict(path=str(p.relative_to(S)),before=before,after=sha(p)))
 save(S/'preservation/SOURCE_RELOCATION.json',relocated)
 for rel in ('RUNTIME_FUNCTIONAL_CHECKS.json','035_C13_science_nominal_SCI_GATE.json','036_C13_science_deviation_SCI_GATE.json'):shutil.copy2(OLD/'versions'/rel,S/'versions'/rel)
 for rel in ('C13_LOCAL_EQUIVALENCE.json','C12_LOCAL_EQUIVALENCE.json'):shutil.copy2(OLD/'output'/rel,S/'output'/rel)
 shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/95d2573d-d006-4536-b4de-bc974c622963/已粘贴的文本.txt',S/'USER_REQUEST.txt')
 shutil.copy2(W/'bootstrap.py',S/'code/bootstrap.py')
 save(S/'TASK_LEDGER.json',{});(S/'ATTEMPTS.jsonl').touch();(S/'PROGRESS.md').write_text('t0 2026-10-08 02:34:42 +08; hard stop 06:34:42; heavy cutoff 06:04:42.\n')
 for idx,(base,label) in enumerate([('047_C13_host_nominal_quiet','nominal'),('048_C13_host_deviation_quiet','deviation')],1):
  cfg=json.loads((OLD/'queue'/(base+'.json')).read_text());cfg.update(id=f'{idx:03d}_B_confirm_{label}',dependencies=[],required_gates=['output/C13_LOCAL_EQUIVALENCE.json','output/C12_LOCAL_EQUIVALENCE.json','versions/035_C13_science_nominal_SCI_GATE.json','versions/036_C13_science_deviation_SCI_GATE.json'],qualification_group='prospective_runtime_confirmation',legacy_guard_version='B_native_original')
  save(S/'queue'/(cfg['id']+'.json'),cfg)
 save(S/'STATE.json',dict(status='ACTIVE',phase='EXISTING_EVIDENCE',active=[],t0_unix=T0,hard_stop_unix=hard,physics_attempts=0,B_RUNTIME_FROZEN=False))
 print(json.dumps(dict(status='INITIALIZED',study=str(S),verified_C13_files=len(verified),relocations=len(relocated),elapsed_s=time.time()-T0)))
if __name__=='__main__':main()
