from pathlib import Path
import json,hashlib,time,shutil,os,subprocess
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def load(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for block in iter(lambda:s.read(2**20),b''):h.update(block)
 return h.hexdigest()
def main():
 owner=load('control/OWNER.json');assert owner['joined'] and owner['returncode']==0;assert load('PARENT_FORK_GATE.json')['status']=='PASS';assert load('ANOMALY_REPEAT_GATE.json')['status']=='PASS';assert load('ATTEMPT_ACCOUNTING.json')['status']=='PASS';assert load('PROTECTION_AUDIT.json')['status']=='PASS';assert load('NATIVE_PROVENANCE_AUDIT.json')['status']=='PASS'
 ledger=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[x for x in ledger if x['event']=='START'];rows=[json.loads(x) for x in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()]
 manifest=load('EXECUTION_CODE_MANIFEST.json');changed=[n for n,s in manifest['files'].items() if sha(P/n)!=s];runtime_metadata=[n for n in changed if n=='control/OWNER.json'];diagnostic_changes=[n for n in changed if n=='control/diagnostics.py'];assert set(changed)<=set(runtime_metadata+diagnostic_changes),'ACTIVE_EXECUTION_CODE_CHANGED:'+str(changed)
 assert owner['start_unix']>=manifest['unix'] and all(owner['start_unix']<=r['unix']<=owner['end_unix'] for r in starts),'OWNER_LEDGER_TIME_SCOPE'
 required=['REPORT.md','NEXT_RESEARCH_DECISION.md','METRICS_CONTRACT.md','LITERATURE_POSITIONING.md','EXPLORATION_RESULTS.jsonl','SENSITIVITY_RESULTS.json','CANDIDATE_RESULTS.jsonl','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','REPRODUCTION.md']
 for n in required:assert (P/n).is_file(),n
 figures=['cumulative_force_vs_time.png','force_accumulation_vs_motion_variation.png','actual_vs_reference_velocity.png','cumulative_velocity_variation.png','curvature_and_curvature_variation.png','waypoint_density_vs_motion.png','waypoint_density_vs_JF.png','timing_vs_JF_motion.png','best_candidate_full_task.png','force_motion_tradeoff.png']
 for n in figures:assert (P/'figures'/n).is_file(),n
 phaseerrors=[abs(x['force_closure_error_N_s']) for x in load('NATIVE_PROVENANCE_AUDIT.json')['arms']];assert max(phaseerrors)<1e-8
 end=time.time();plan=load('RUN_PLAN.json');put('PHYSICS_STOP.json',dict(status='STOP',unix=end,reason='Frozen finite sensitivity group complete; repeatable downstream penalty and negligible feasible force signal. No next package.',physics_START=len(starts),no_automatic_resume=True))
 put('STATE.json',dict(status='STOP_COMPLETE',unix=end,physics_START=len(starts),elapsed_wall_s=end-plan['t0_unix'],next_allowed_action='read-only review; any new campaign requires separate authorization and output package'))
 verification=dict(status='PASS',terminal_status='STOP_COMPLETE',unix=end,physics_START=len(starts),physics_END=sum(x['event']=='END' for x in ledger),complete_candidate_count=sum(x['status']=='COMPLETE' for x in rows),all_owned_processes_joined=owner['joined'],source_protection='PASS',original_motion_contract_identical=True,full_native_receipt_coefficient_integral_audit='PASS',maximum_full_force_closure_error_N_s=max(phaseerrors),initial_state_match=load('NATIVE_PROVENANCE_AUDIT.json')['all_initial_states_equal'],parent_B_equivalence='PASS',anomaly_repeat='PASS',postfreeze_nonexecution_diagnostic_enrichment=diagnostic_changes,expected_runtime_metadata_updates=runtime_metadata,owner_covers_all_START_timestamps=True,host_clock_qualification='NOT_EVALUABLE; historical failures retained',level='PHYSICAL_LEVEL1 development',new_force_record=load('FROZEN_SELECTION.json')['status'],independent_paired_validation=load('VALIDATION_RESULTS.json')['status'],figures=figures,required_artifacts=required,clinical_thresholds=False,training_performed=False,production_git_mutation=False,no_next_package=True,elapsed_wall_s=end-plan['t0_unix'],within_wall_limit=end<=plan['hard_stop_unix'],physics_budget_limit=plan['physics_budget'],within_START_limit=len(starts)<=plan['physics_budget'],audit_independence='separate numerical/source recomputation by same agent; no independent reviewer claimed')
 assert verification['within_START_limit'] and verification['within_wall_limit'];put('PACKAGE_VERIFICATION.json',verification)
 # Include all raw evidence hashes; avoid following historical archive symlinks.
 files={}
 for root,dirs,names in os.walk(P,followlinks=False):
  dirs[:]=[d for d in dirs if d!='__pycache__' and not (Path(root)/d).is_symlink()]
  for n in names:
   f=Path(root)/n
   if n not in ['PACKAGE_MANIFEST.json'] and not f.is_symlink():files[str(f.relative_to(P))]=dict(bytes=f.stat().st_size,sha256=sha(f))
 put('PACKAGE_MANIFEST.json',dict(unix=end,canonical_package=str(P),files=files,external_archive_link=str(P/'key_traces'),bytes=sum(x['bytes'] for x in files.values())))
 for f in P.iterdir():
  if f.is_file() and f.suffix in ['.md','.json','.jsonl']:shutil.copy2(f,L/f.name)
 for d in ['figures','audit','tests']:
  shutil.copytree(P/d,L/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 # Export reproducible sources plus compact reports; keep massive native raw in WSL.
 for d in ['control','code','deps','weights']:
  shutil.copytree(P/d,L/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 rel='stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py';dest=L/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/'source'/rel,dest)
 (L/'reports').mkdir(exist_ok=True)
 for f in (P/'reports').glob('*'):
  if f.is_file() and ('MEASURED' in f.name or 'INDEPENDENT_AUDIT' in f.name or 'SNAPSHOT' in f.name or 'ERROR' in f.name):shutil.copy2(f,L/'reports'/f.name)
 (L/'RAW_DATA_LOCATION.md').write_text('# Full evidence location\n\n'+str(P)+'\n\nWindows is a light review copy. Full native raw, receipts, issued references, motion series and exact execution closure are retained in WSL. PACKAGE_MANIFEST hashes canonical contents; it is not a claim that all raw data were copied to Windows.\n')
 print(json.dumps(dict(status='STOP_COMPLETE',physics_START=len(starts),wall_min=(end-plan['t0_unix'])/60,canonical_bytes=sum(x['bytes'] for x in files.values()),review=str(L)),indent=2))
if __name__=='__main__':main()
