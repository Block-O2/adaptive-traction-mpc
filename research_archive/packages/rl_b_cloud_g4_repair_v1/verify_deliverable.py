"""Final saved-artifact cross-check; never imports or creates an environment."""
from pathlib import Path
import json,hashlib,datetime,os
from common import put,ROOT
from checkpoints import contract
required=['REPORT.md','ROOT_CAUSE_ANALYSIS.md','FORCE_INTEGRATION_REPAIR.md','G4_TERMINATION_REWARD_AUDIT.md','TASK_TIMING_AUDIT.md','RL_EXECUTION_PARITY_AUDIT.md','PPO_SMOKE_RESULTS.json','CHECKPOINT_RESUME_AUDIT.json','VALIDATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md']
def read(p):return json.loads(Path(p).read_text())
acc=read('ATTEMPT_ACCOUNTING.json');pkg=read('PACKAGE_VERIFICATION.json');v=read('VALIDATION_RESULTS.json');ready=read('READINESS.json');eps=read('audit/EPISODE_ACCOUNTING_SUMMARY.json');checks={}
checks['all_required_files']=all((ROOT/n).is_file() and (ROOT/n).stat().st_size>0 for n in required)
checks['START_END_closed']=acc['START_count']==acc['END_count']==10 and acc['all_closed']
checks['physical_budget']=acc['actual_episodes']==9 and acc['actual_episodes']<=10 and acc['physical_attempts']==8
checks['complete_partial_count']=acc['complete_episodes']==3 and acc['partial_episodes']==6 and acc['natural_episodes']==6 and acc['TEST_ONLY_physics_episodes']==3
checks['native_and_RL_counts']=sum(e['native_steps'] for e in eps)==acc['native_steps']==799020 and sum(e['RL_decisions'] for e in eps)==acc['RL_decisions']==106
checks['all_force_independent_pass']=all(e['independent_force_pass'] for e in eps) and all(read(Path(e['directory'])/'FORCE_INDEPENDENT_AUDIT.json')['pass'] for e in eps)
checks['all_observed_execution_core_pass']=all(e['independent_execution_core_pass'] for e in eps)
checks['parity_preserved']=all(read('audit/PARITY_'+k+'.json')['pass'] for k in ('slow','maximal','random'))
checks['random_frozen_regression_preserved_FAIL']=v['EXECUTION_PASS']=='FAIL' and read('RL_EXECUTION_VALIDATION.json')['random_TASK_s']>19.08
checks['G4_coverage_not_relabelled']=v['G4_PASS']=='FAIL' and not read('G4_PHYSICAL_VALIDATION.json')['all_key_real_failure_paths_closed']
checks['no_PPO_or_checkpoint_created']=read('PPO_SMOKE_RESULTS.json')['gradient_updates']==0 and read('CHECKPOINT_RESUME_AUDIT.json')['status']=='NOT_RUN' and not any((ROOT/'runs').rglob('checkpoints'))
checks['training_gate_blocks']=ready['RL_EXECUTION_CONTRACT_PASS']=='FAIL' and read('PPO_SMOKE_RESULTS.json')['negative_gate']['pass']
checks['original_history_protected']=pkg['status']=='PASS' and pkg['ZIP_payloads_passed']==450 and not pkg['historical_mismatches'] and not pkg['historical_missing']
checks['only_two_scientific_source_changes']=len(pkg['isolated_source_changes'])==2 and pkg['other_source_payloads_byte_unchanged']==412
checks['current_code_identity']=pkg['full_code_contract_sha256']==v['contract_sha256']==ready['contract_sha256']==contract()
checks['all_owned_processes_exited']=read('PROCESS_EXIT_AUDIT.json')['pass']
checks['resources']=read('RESOURCE_USAGE.json')['minimum_available_GiB']>=6 and read('RESOURCE_USAGE.json')['no_monitor_resource_failure_in_physics']
# Every saved physics end is before both actual stop and the hard final30min lockout.
cutoff=datetime.datetime.fromisoformat('2026-10-20T10:17:23+00:00').timestamp()
checks['no_physics_in_hard_final30min']=acc['last_physics_END_unix']<cutoff
active=[];task_scripts={'run_remaining.py','resource_guard.py','run_rollout.py','cloud_g4_cases.py','safety_TEST_ONLY.py','train.py'}
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:args=(p/'cmdline').read_bytes().split(b'\0')
 except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if args and b'python' in args[0] and any(Path(a.decode(errors='replace')).name in task_scripts for a in args[1:]):active.append({'pid':int(p.name),'args':[a.decode(errors='replace') for a in args if a]})
checks['no_simulation_or_train_processes']=not active
r={'category':'FINAL_ARTIFACT_INDEPENDENT_CROSS_CHECK','pass':all(checks.values()),'checks':checks,'active_owned_task_processes':active,'required_files':required,'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};put('FINAL_VERIFICATION.json',r)
print(json.dumps(r,indent=2));assert r['pass']
