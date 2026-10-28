"""Final accounting and content seal. No simulations, learning, or historical writes."""
from pathlib import Path
import os,json,time,hashlib,datetime,subprocess,collections,shutil,sys,re
r=Path(__file__).resolve().parents[1];start=json.loads((r/'audit/STUDY_START.json').read_text());t0=datetime.datetime.fromisoformat(start['T0']).timestamp();now=time.time();zone=datetime.timezone(datetime.timedelta(hours=8))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def put(n,o):(r/n).write_text(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(p):return json.loads(Path(p).read_text())
put('audit/FINALIZATION_START.json',{'unix':now,'pid':os.getpid(),'scope':'ACCOUNTING_AND_HASH_SEAL_ONLY'})
physical=read(r/'PHYSICAL_EVALUATION_RESULTS.json');cases=physical['evaluations'];jobs=[];tracked_pids=set()
for p in sorted((r/'audit/jobs').iterdir()):
 a=read(p/'START.json');b=read(p/'END.json');jobs.append({'job':p.name,'start':a,'end':b});tracked_pids.update(x for x in [a.get('pid'),a.get('child_pid'),b.get('child_pid')] if x)
attempts=[]
for x in cases:
 d=r/x['run_path'];s=read(d/'START.json');e=read(d/'END.json');ps=read(d/'PHYSICS_START.json');pe=read(d/'PHYSICS_END.json');es=read(d/'env/episode_0001/EPISODE_START.json');ee=read(d/'env/episode_0001/EPISODE_END.json');tracked_pids.add(s['pid'])
 attempts.append({'id':x['case']['id'],'start':s,'end':e,'physics_start':ps,'physics_end':pe,'episode_start':es,'episode_end':ee,'terminal_runtime_status':x['status'],'success':x['success'],'native_steps':x['native_steps'],'RL_decisions':x['rl_decisions'],'gradient_updates':x['gradient_updates'],'independent_audits_pass':x['independent_audit_pass'] and x['force_audit_pass']})
monitor=read(r/'audit/MONITOR_PID.json');monend=read(r/'audit/MONITOR_END.json');tracked_pids.add(monitor['pid']);alive=[];pidchecks=[]
for pid in sorted(tracked_pids):
 p=Path(f'/proc/{pid}');exists=p.exists();cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace') if exists else None
 owned_active=exists and str(r) in (cmd or '') and pid!=os.getpid()
 pidchecks.append({'pid':pid,'exists':exists,'cmdline_if_reused_or_live':cmd,'owned_study_process_active':owned_active})
 if owned_active:alive.append(pid)
put('PROCESS_EXIT_AUDIT.json',{'unix':time.time(),'tracked_owned_pids':pidchecks,'owned_study_processes_still_active':alive,'all_owned_scientific_and_monitor_processes_exited':not alive,'all_physics_owner_joined':all(x['end']['owner_joined'] and x['physics_end']['owner_joined'] and x['episode_end']['owner_joined'] for x in attempts),'monitor_end':monend,'current_sealer_excluded_pid':os.getpid(),'current_sealer_scope':'This short-lived sealing command exits immediately after writing its final result; all simulation, worker, guard and sampler processes have already exited.'})
failed=[x for x in jobs if x['end']['exit_code']!=0]
put('ATTEMPT_ACCOUNTING.json',{'study_T0':start['T0'],'program_jobs':jobs,'program_START_count':len(jobs)+len(attempts),'program_END_count':len(jobs)+len(attempts),'program_ledger_scope':'Only actual study-owned audit/jobs and frozen evaluator programs; historical fixture START/END and imported archived logs are not counted as new attempts.','failed_program_jobs':[x['job'] for x in failed],'failure_resolution':'postrun_checks failed only while serializing NumPy bool; failed source/log retained; postrun_checks_fixed succeeds. No extra physics or training was run to repair it.','new_physical_attempts':attempts,'PHYSICS_START_count':len(attempts),'PHYSICS_END_count':len(attempts),'EPISODE_START_count':len(attempts),'EPISODE_END_count':len(attempts),'new_training_episodes':0,'new_gradient_updates':0,'new_native_steps':sum(x['native_steps'] for x in attempts),'new_RL_decisions':sum(x['RL_decisions'] for x in attempts),'max_new_physical_evaluations':8,'all_owned_ledgers_closed':all(x['end']['completed'] and x['end']['error'] is None for x in attempts) and all((r/'audit/jobs'/x['job']/'END.json').exists() for x in jobs),'engineering_failures':'audit/ENGINEERING_ATTEMPTS.json','Stage2':'NOT_RUN','full_fork_replay':'NOT_RUN','new_live_matched_evaluation':'NOT_RUN'})
samples=[json.loads(s) for s in (r/'audit/RESOURCE_SAMPLES.jsonl').read_text().splitlines()]
def ticks(row):
 a=[int(x) for x in row['cpu_ticks'].split()[1:9]];return sum(a),a[3]+a[4]
a,b=ticks(samples[0]),ticks(samples[-1]);total=b[0]-a[0];idle=b[1]-a[1];busy=total-idle;clock_ticks=os.sysconf('SC_CLK_TCK');ncpus=os.cpu_count()
rawbytes=sum(p.stat().st_size for p in (r/'physical/runtime/evaluations').rglob('*') if p.is_file());rawstreams=read(r/'audit/LOSSLESS_RAW_FINAL_VERIFICATION.json')
put('RESOURCE_USAGE.json',{'T0':start['T0'],'recorded_at':datetime.datetime.now(zone).isoformat(),'elapsed_minutes':(time.time()-t0)/60,'hard_limit_minutes':300,'last45min_rule_complied':all(x['physics_start']['unix']<datetime.datetime.fromisoformat(start['no_new_long_physics_after']).timestamp() for x in attempts),'cpus_visible':ncpus,'cpu_only':True,'numerical_threads_per_environment':1,'max_parallel_physics_environments':1,'minimum_available_ram_GiB':min(x['available_ram_bytes'] for x in samples)/1024**3,'minimum_free_disk_GiB':min(x['disk_free_bytes'] for x in samples)/1024**3,'physical_episode_minimum_available_ram_GiB':min(x['resources']['minimum_available_GiB'] for x in cases),'minimum_ram_required_GiB':6,'resource_stop_triggered':(r/'audit/RESOURCE_STOP').exists(),'host_cpu_observation':{'interval_seconds':samples[-1]['unix']-samples[0]['unix'],'busy_CPU_seconds':busy/clock_ticks,'mean_total_host_utilization_fraction':busy/total if total else 0,'mean_busy_logical_cpus':busy/total*ncpus if total else 0,'maximum_loadavg_1min':max(x['loadavg'][0] for x in samples),'attribution':'Host /proc/stat observation includes VSCode and other host work; it is not a fabricated exact study-only CPU charge.'},'resource_sample_count':len(samples),'per_episode_resources':[{'id':x['case']['id'],**x['resources']} for x in cases],'sum_episode_guard_wall_seconds':sum(x['resources']['wall_s'] for x in cases),'frozen_evaluation_job_wall_seconds':next(x['end']['wall_s'] for x in jobs if x['job']=='bounded_frozen_physics'),'physical_evidence_retained_bytes':rawbytes,'lossless_compressed_native_and_runtime_streams':rawstreams['count'],'uncompressed_native_and_runtime_bytes':sum(x['uncompressed_bytes'] for x in rawstreams['streams']),'native_steps':physical['native_steps'],'task_native_steps':physical['task_native_steps'],'RL_decisions':physical['RL_decisions'],'gradient_updates':0,'Hetzner_purchase_or_resize':False,'recovered_checkout_and_envs_are_separate_from_raw':True})
checks={
 'github_fixed_commit_clean':read(r/'audit/GITHUB_FINAL_IDENTITY.json')['clean'] and read(r/'audit/GITHUB_FINAL_IDENTITY.json')['head_matches'],
 'repository_source_identity':read(r/'audit/REPOSITORY_VERIFICATION.json')['status']=='PASS',
 'fixture_scorer_contract_model_identity':read(r/'audit/FIXTURE_CONTRACT_VERIFICATION.json')['status']=='PASS',
 'original_offline_scorer':read(r/'scorer/original-001/OFFLINE_SCORER_RESULT.json')['status']=='PASS',
 'original_scorer_outputs_manifest':read(r/'audit/SCORER_OUTPUT_MANIFEST_VERIFICATION.json')['pass'],
 'models_compile_no_steps':read(r/'audit/MODEL_VERIFICATION.json')['status']=='PASS' and read(r/'audit/MODEL_VERIFICATION.json')['physics_steps']==0,
 'sealed_rlb_original_import_unit_checks':read(r/'audit/rlb-check-001/RL_B_ENVIRONMENT_CHECK.json')['status']=='PASS',
 'identity_failure_tests':next(x['end']['exit_code']==0 for x in jobs if x['job']=='identity_guard_tests'),
 'actual_offline_access_guard_probes':read(r/'audit/ACCESS_GUARD_PROBES.json')['pass'],
 'cloud_source_diff_actual_contract':read(r/'source_diff/FILE_SHA256_COMPARISON.json')['all_frozen_contract_files_match'],
 'vendor_assets':all(x['pass'] for x in read(r/'source_diff/CODE_LINEAGE_AND_CONFIG.json')['vendor_checks']),
 'shared_ppo_config_values_explicit':all(x['identical'] for x in read(r/'source_diff/CLOUD_CONFIG_SEMANTIC_DIFF.json')['shared_ppo_scalars'].values()),
 'all_51_checkpoint_identities':read(r/'CHECKPOINT_050_080_COMPARISON.json')['checks']['all_checkpoint_identity_pass'],
 'all_240_GAE':read(r/'stability/TRAINING_OPTIMIZATION_AUDIT.json')['checks']['all_GAE_recomputed'],
 'all_240_reward_recomputations':read(r/'stability/REWARD_CREDIT_AUDIT.json')['all_pass'],
 'historical_PPO_frozen_forward':read(r/'stability/FROZEN_ACTION_EXECUTION_AUDIT.json')['checks']['all_eval_policy_recomputed'],
 'fixed_legal_baseline':read(r/'audit/PHYSICAL_RUNTIME_IDENTITY_END.json')['fixed_plus_one_baseline_actions_verified'],
 'six_original_native_trajectory_audits':read(r/'stability/HISTORICAL_NATIVE_EXECUTION_AUDIT.json')['all_accounting_pass'],
 'eight_new_attempts_only':len(cases)==8,
 'new_physics_all_audits_pass':all(x['independent_audit_pass'] and x['force_audit_pass'] for x in cases),
 'no_training_no_gradient_updates':all(x['gradient_updates']==0 and x['frozen_state_unchanged'] for x in cases),
 'copied_execution_contract_unchanged':read(r/'audit/PHYSICAL_RUNTIME_IDENTITY_END.json')['all_pass'],
 'common_rng_pairs_verified':read(r/'stability/COMMON_RANDOM_NUMBERS_AUDIT.json')['all_pass'],
 'lossless_raw_preserved':read(r/'audit/LOSSLESS_RAW_FINAL_VERIFICATION.json')['all_pass'],
 'historical_13683_files_preserved':read(r/'audit/HISTORICAL_PROTECTION_END.json')['pass'],
 'all_owned_processes_exited':not alive,
 'all_ledgers_closed':read(r/'ATTEMPT_ACCOUNTING.json')['all_owned_ledgers_closed'],
 'ram_reserve':read(r/'RESOURCE_USAGE.json')['minimum_available_ram_GiB']>=6,
 'hard_time_limit':time.time()<datetime.datetime.fromisoformat(start['hard_deadline']).timestamp(),
 'stage2_campaign_and_new_live_matched_not_run':read(r/'STATUS.json')['Stage2']=='NOT_RUN' and read(r/'STATUS.json')['final_campaign']=='NOT_RUN',
 'only_known_checker_failure_and_recovered':len(failed)==1 and failed[0]['job']=='postrun_checks' and next(x['end']['exit_code']==0 for x in jobs if x['job']=='postrun_checks_fixed'),
}
required=['REPORT.md','GITHUB_RECOVERY_AUDIT.md','FROZEN_SCORER_VALIDATION.md','HISTORICAL_MATCHED_REPRODUCTION.json','CLOUD_GITHUB_SOURCE_DIFF.md','CLOUD_CODE_RETURN_PLAN.md','PPO_STABILITY_DIAGNOSIS.md','CHECKPOINT_050_080_COMPARISON.json','TRAIN_EVAL_SEMANTICS_AUDIT.md','PHYSICAL_EVALUATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','RESOURCE_USAGE.json','NEXT_RESEARCH_DECISION.md','STATUS.json']
checks['required_deliverables_present']=all((r/n).is_file() and (r/n).stat().st_size>0 for n in required)
checks['report_images_present']=all((r/n).is_file() for n in ['stability/PPO_STABILITY.png','stability/PPO_STABILITY.pdf','stability/RETURN_REGRESSION.png','stability/RETURN_REGRESSION.pdf'])
put('VALIDATION_RESULTS.json',{'checks':checks,'check_count':len(checks),'failed_checks':[k for k,v in checks.items() if not v],'pass':all(checks.values()),'checker_failure_retained':'audit/jobs/postrun_checks; repaired serialization only; all final checks above are separately evaluated.'})
assert all(checks.values()),[k for k,v in checks.items() if not v]
state=read(r/'audit/WORK_STATE.json');state.update(phase='STOP',remaining_work=[],completed_at=datetime.datetime.now(zone).isoformat());put('audit/WORK_STATE.json',state)
put('STOP.json',{'state':'STOP','unix':time.time(),'timestamp':datetime.datetime.now(zone).isoformat(),'all_authorized_work_completed':True,'new_training_episodes':0,'new_gradient_updates':0,'new_physical_attempts':8,'Stage2':'NOT_RUN','final_campaign':'NOT_RUN','no_automatic_next_study':True,'next_step':'Review package, then separately authorize bounded H1 study if desired; no automatic continuation.'})
put('audit/FINALIZATION_END.json',{'unix':time.time(),'pid':os.getpid(),'scope':'Accounting complete; immediate content-seal calculation follows, no further research','pass':True})
# Mutable caches and reproducible virtual environments are documented exclusions.
excluded_dirs={'.git','offline-env','cpu-env'};excluded_names={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}
entries={}
for p in sorted(r.rglob('*')):
 rel=p.relative_to(r)
 if any(x in excluded_dirs for x in rel.parts):continue
 if not p.is_file() or rel.as_posix() in excluded_names:continue
 entries[rel.as_posix()]={'bytes':p.stat().st_size,'sha256':sha(p)}
put('OUTPUT_MANIFEST.json',{'schema':'ihear.matched_recovery_stability.content.v1','files':entries,'exclusions':{'directories':sorted(excluded_dirs),'root_seal_metadata':sorted(excluded_names),'reason':'Git object database and reproducible CPU virtual environments are installation state; their commits, locks, actual versions and install logs are included. OUTPUT_MANIFEST and PACKAGE_VERIFICATION are excluded from their own payload to avoid self-reference; external seal hashes both.'},'coverage':'All reports, scripts, audits, failed attempts, exact diffs, full lossless physical evidence, native model caches, copied execution closure, and complete Git working tree are included.'})
mismatches=[]
for rel,e in entries.items():
 p=r/rel
 if p.stat().st_size!=e['bytes'] or sha(p)!=e['sha256']:mismatches.append(rel)
assert not mismatches,mismatches
verification={'status':'PASS','verified_at':datetime.datetime.now(zone).isoformat(),'checks_passed':len(checks),'failed_checks':[],'payload_files':len(entries),'payload_bytes':sum(x['bytes'] for x in entries.values()),'payload_mismatches':mismatches,'output_manifest_sha256':sha(r/'OUTPUT_MANIFEST.json'),'historical_protected_files':read(r/'audit/HISTORICAL_PROTECTION_END.json')['files_verified'],'historical_mismatches':[],'fixed_github_commit':start['requested_commit'],'github_clean':True,'new_training_episodes':0,'new_gradient_updates':0,'new_physical_episodes':8,'program_START_END':{'START':len(jobs)+len(attempts),'END':len(jobs)+len(attempts)},'physics_START_END':{'START':8,'END':8},'episode_START_END':{'START':8,'END':8},'owned_scientific_processes_exited':True,'scorer_output_manifest_files_verified':53,'raw_lossless_streams_verified':rawstreams['count'],'known_failed_checker_retained':True,'final_state':'STOP','archive_created':False,'package_is_directory_with_manifest':True}
put('PACKAGE_VERIFICATION.json',verification)
external=r.parent/(r.name+'_SEAL_VERIFICATION.json');external.write_text(json.dumps({'package':str(r),'sealed_at':datetime.datetime.now(zone).isoformat(),'PACKAGE_VERIFICATION_sha256':sha(r/'PACKAGE_VERIFICATION.json'),'OUTPUT_MANIFEST_sha256':sha(r/'OUTPUT_MANIFEST.json'),'payload_files':len(entries),'status':'PASS','state':'STOP'},indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':len(checks),'files':len(entries),'payload_GiB':sum(x['bytes'] for x in entries.values())/1024**3,'elapsed_minutes':(time.time()-t0)/60,'package_verification':str(r/'PACKAGE_VERIFICATION.json'),'external_seal':str(external)},ensure_ascii=False))
