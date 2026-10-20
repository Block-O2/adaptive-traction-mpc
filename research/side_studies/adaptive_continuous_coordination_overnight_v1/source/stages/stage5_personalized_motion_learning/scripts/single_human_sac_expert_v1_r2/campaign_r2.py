"""Timing-only R2 orchestration; R1 sources, index, physical task and evidence stay immutable."""
from pathlib import Path
import sys,json,time,datetime,math,hashlib,subprocess,shutil,traceback,csv,os
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1/source');S=R/'stages/stage5_personalized_motion_learning'
D1=S/'docs/single_human_sac_expert_v1';P1=S/'scripts/single_human_sac_expert_v1'
D=D1/'r2';P=S/'scripts/single_human_sac_expert_v1_r2';O=S/'results/single_human_sac_expert_v1_r2'
sys.path.insert(0,str(P1))
import qualify as q
import final_qualification as f
from sac_env import *
BASE_METRIC=f.metric_record
NUMERIC_EPS=1e-9
PHASE_MIN={'OUTBOUND':9.,'HOLD':1.,'RETURN':9.}
# Physical dwell .5 s is unchanged. For MATCHED 1s the legacy stationary
# scheduler needs two certified .5s schedules, each one activation and one
# receipt-owned endpoint confirmation tick. All methods get the same allowance.
DECISION_ALLOWANCE=max(.02,math.ceil(1./.5)*(rt.CONTROL_DT_S+rt.CONTROL_DT_S))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(rt._jsonable(value),indent=2,sort_keys=True,allow_nan=False)+'\n')
def matched_eligible(times):return all(v-NUMERIC_EPS<=times[k]<=v+DECISION_ALLOWANCE+NUMERIC_EPS for k,v in PHASE_MIN.items())
def metric(env,name,scope):
 record=BASE_METRIC(env,name,scope)
 record['task_valid']=bool(record['physical_audit']['pass_'])
 record['matched_eligible']=matched_eligible(record['phase_durations'])
 record['matched_timing_valid']=scope!='MATCHED' or record['matched_eligible']
 record['valid']=record['task_valid'] and record['matched_timing_valid']
 record['timing_contract']='SAC_MATCHED_TIMING_CONTRACT_R2'
 return record
def configure():
 for module in (q,f):module.D=D;module.O=O
 f.metric_record=metric
def resource_check(tag):
 memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
 ps=subprocess.check_output(['ps','-eo','pid,ppid,pcpu,rss,args','--no-headers'],text=True)
 parents={int(x.split(None,2)[0]):int(x.split(None,2)[1]) for x in ps.splitlines()}
 def owned(pid):
  seen=set()
  while pid in parents and pid not in seen:
   if pid==os.getpid():return True
   seen.add(pid);pid=parents[pid]
  return False
 others=[]
 for line in ps.splitlines():
  parts=line.split(None,4)
  if len(parts)==5 and 'python' in parts[4] and 'unattended' not in parts[4] and 'conda shell' not in parts[4] and not owned(int(parts[0])) and (float(parts[2])>=20. or int(parts[3])>=256*1024):others.append(line)
 try:
  cmd=['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory']
  windows_kb=int(subprocess.check_output(cmd,text=True,timeout=15).strip())
 except Exception as e:windows_kb=None
 avail=int(memory['MemAvailable'].split()[0])*1024;swap_used=(int(memory['SwapTotal'].split()[0])-int(memory['SwapFree'].split()[0]))*1024
 safe=avail>=2*1024**3 and windows_kb is not None and windows_kb>=2*1024**2 and not others
 row=dict(utc=now(),tag=tag,safe=safe,side_study_active=bool(others),other_heavy_python=others,WSL_available_bytes=avail,windows_available_kb=windows_kb,swap_used_bytes=swap_used,load=Path('/proc/loadavg').read_text().strip(),gpu=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip(),processes=ps)
 rows=json.loads((D/'RESOURCE_SAMPLES_R2.json').read_text()) if (D/'RESOURCE_SAMPLES_R2.json').exists() else [];rows.append(row);write(D/'RESOURCE_SAMPLES_R2.json',rows)
 print(json.dumps({k:row[k] for k in ('tag','safe','side_study_active','WSL_available_bytes','windows_available_kb','swap_used_bytes','gpu')}),flush=True)
 if not safe:
  q.status('RESOURCE_WAIT',status='SAC_READY_WAITING_FOR_RESOURCES',next_action='STOP cleanly. Do not alter the other study or WSL resources. Resume only after resource evidence supports one SAC environment.')
 return safe
def prep():
 D.mkdir(exist_ok=False)
 for name in ('SAC_EXPERT_V1_CONTRACT.json','SAC_OBSERVATION_NORMALIZATION.json','SAC_REWARD_AUDIT.json','SAC_RESET_STRESS.json','SAC_TRAINING_CONFIG.json','SOURCE_FINGERPRINTS.json','GIT_PREFLIGHT.json','RUN_reference_20ms_NATIVE.json','RUN_final_reference_20ms_NATIVE.json','RUN_final_reference_20ms_MATCHED.json','CUDA_READINESS.json'):
  shutil.copy2(D1/name,D/name)
 write(D/'STATE.json',dict(status='R2_TIMING_QUALIFICATION',phase='R2_TIMING_FROZEN',started_unix=json.loads((D1/'GIT_PREFLIGHT_R2.json').read_text())['started_unix'],started_utc=now(),formal_training_started=False,training_steps=0,branch='codex/single-human-sac-expert-v1',hard_wall_hours=12,next_action='Affected timing gates only; retain R1 PASS observation/action/reward/reset/normalization/adaptation evidence.'))
 source_hashes={str(p.relative_to(R)):sha(p) for p in (P1/'sac_env.py',S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py',S/'src/traction_mpc_stage5/task.py',S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/activation_validation.py',S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/receipt_reference_governor.py',S/'configs/high_rom_v1/stage5_goal_task_120_v1.json')}
 diagnosis=dict(status='SOURCE_AND_TRANSPARENT_RUNTIME_CONFIRMED',classification=['scheduler/reference semantics','expected discrete execution ownership'],implementation_bug=False,physical_required_contiguous_valid_dwell_s=.5,matched_required_phase_clock_s=1.,hold_entry_s=19.05499999999997,first_valid_sample_s=19.059999999999995,first_credited_valid_interval_endpoint_s=19.06500000000002,original_dwell_first_satisfied_s=19.560000000002383,first_schedule_activation_s=19.059999999999995,first_endpoint_emitted_s=19.560000000002383,first_endpoint_recognized_s=19.565000000002406,second_schedule_activation_s=19.57000000000243,second_endpoint_emitted_s=20.070000000004818,exit_decision_s=20.07500000000484,actual_hold_s=1.0200000000048703,source_chain=['task.py hold_complete/transition_phase: .5 s minimum contiguous dwell','activation_validation.py SensorSupportedTaskClock: two valid contiguous post-entry captures; entry capture never credits pre-entry time','receipt_reference_governor.py is_complete: only committed emitted progress can be complete; select/commit happens after transition check','runtime_sac_expert_v1.py: control tick transition then plan/references; continuous_hold guards reference ownership; asynchronous worker activation needs one execution interval'],extra_seconds_formula='2 * (one 0.005s activation wait + one 0.005s receipt-owned endpoint recognition) = 0.020s',physics_dt_s=.0005,control_reference_sensor_transition_dt_s=.005,policy_dt_s=.02,old_controller_policy_cadence='event-driven planner requests at phase/segment boundaries; no 20ms SAC callback',time_measurement='HOLD = RETURN transition timestamp minus HOLD transition timestamp; costs include every physical waiting interval',source_hashes=source_hashes,probe=str((D1/'SAC_HOLD_PROBE_R2.json').relative_to(R)),probe_sha256=sha(D1/'SAC_HOLD_PROBE_R2.json'),diagnostic_failed_attempt='diagnosis_old_MATCHED worker startup failed because diagnostic harness omitted main guard; preserved; repaired harness only and independently reran attempt2')
 write(D1/'SAC_TIMING_BLOCKER_DIAGNOSIS.json',diagnosis)
 (D1/'SAC_TIMING_BLOCKER_DIAGNOSIS.md').write_text('# HOLD timing blocker diagnosis\n\nPhysical task HOLD requires at least 0.5 s of uninterrupted valid causal dwell, not exactly 1 s. The 1 s minimum is a MATCHED comparison clock. The old planner executes two stationary 0.5 s certified references while that clock waits. Each requires a 5 ms asynchronous activation interval and a 5 ms receipt-owned endpoint recognition interval: 2 × (5+5) ms = 20 ms. A phase transition is checked every 5 ms, before new reference progress is emitted/committed; the SAC callback period is 20 ms but is absent in the old controller.\n\nHOLD entry 19.055 s; first valid captured sample 19.060 s; first credited endpoint 19.065 s; original 0.5 s dwell proved at 19.560 s. First schedule activation/end emission/recognition 19.060/19.560/19.565 s. Second activation/end emission/recognition 19.570/20.070/20.075 s. Final HOLD-to-RETURN decision 20.075 s, so HOLD is 1.020 s. The transparent transition probe reproduces these values and the still-incomplete reference at 20.070 s. This is legitimate scheduler/reference ownership semantics, not a physical/task bug. No controller or task edit is made.\n\nThe first diagnostic harness startup failed because its multiprocessing main guard was missing; that attempt is preserved and the harness-only fix is recorded. Detailed trace, causal dwell, source hashes and calls are in JSON.\n')
 timing=dict(schema='SAC_MATCHED_TIMING_CONTRACT_R2',status='FROZEN_PROSPECTIVE_BEFORE_SAC',frozen_utc=now(),formal_training_steps_at_freeze=0,physical_task=dict(required_contiguous_valid_hold_s=.5,unchanged_task_config_sha256=source_hashes[str((S/'configs/high_rom_v1/stage5_goal_task_120_v1.json').relative_to(R))],original_angle_velocity_safety_phase_deadline_and_global_deadline_unchanged=True),matched_phase_minimum_s=PHASE_MIN,decision_allowance_s=DECISION_ALLOWANCE,numerical_epsilon_s=NUMERIC_EPS,allowance_formula='max(policy_period, ceil(T_matched_HOLD / T_physical_HOLD) * (control_activation_tick + control_receipt_confirmation_tick)) = max(.020, 2*(.005+.005)) = .020 s',eligibility_formula='for every phase p: T_min[p]-1e-9 <= actual T[p] <= T_min[p]+.020+1e-9 AND unchanged independent complete-task physical evaluator PASS',total_duration_bounds_s=[19.,19.+3*DECISION_ALLOWANCE],methods=['old_nominal','online_reference','fixed_hip_lead','cem_reference_transfer','future SAC'],fairness='identical physical task, commissioned Human, initial condition and common earliest phase clocks; identical upper timing allowance for all methods; no waypoint/segment imitation; actual waiting cost always included',native='original free-duration complete task; unchanged .5s contiguous valid physical HOLD minimum; never pooled with matched ranking',scope_limit='Matched clocks leave within-phase pacing and up to 60ms total residual duration variation. Do not infer pure coordination from native differences, or perfect timing isolation from eligibility alone.',preserve_R1=True)
 write(D1/'SAC_MATCHED_TIMING_CONTRACT_R2.json',timing);(D1/'SAC_MATCHED_TIMING_CONTRACT_R2.md').write_text('# Prospectively frozen discrete MATCHED timing R2\n\nOriginal physical continuous valid HOLD minimum remains 0.5 s. Common comparison phase minima are OUTBOUND 9 s, HOLD 1 s, RETURN 9 s. For every method and phase, eligibility requires `T_min - 1e-9 <= T_actual <= T_min + .020 + 1e-9`, plus the unchanged independent physical evaluator PASS. Total phase time is 19 to 19.060 s.\n\nThe .020 s allowance equals `max(.020 policy period, ceil(1/.5) × (.005 activation + .005 receipt endpoint confirmation))`. Source and transparent deterministic runtime establish both ticks; this is frozen at zero SAC training steps. No controller is changed to hit exact clock boundaries. Physical dwell, deadlines, safety, causal actor features/action/reward/scales and commissioning-only mode remain unchanged. Actual physical waiting contributes to J_F. Native and MATCHED-TIMING are separate scopes. Equal phase clocks do not equalize within-phase pacing; residual total timing differences must be reported.\n')
 contract=json.loads((D1/'SAC_EXPERT_V1_CONTRACT.json').read_text());contract.update(schema='SAC_EXPERT_V1_CONTRACT_R2',version=2,status='TIMING_FROZEN_QUALIFICATION_PENDING',timing_contract=timing,previous_contract_sha256=sha(D1/'SAC_EXPERT_V1_CONTRACT.json'),only_scientific_change='common timing eligibility bounds; original runtime earliest clocks unchanged',retained_pass_evidence={n:sha(D1/n) for n in ('SAC_OBSERVATION_NORMALIZATION.json','SAC_REWARD_AUDIT.json','SAC_RESET_STRESS.json','SAC_ACTION_PERIOD_QUALIFICATION.json','CUDA_READINESS.json')})
 contract['evaluation']['matched']='SAC_MATCHED_TIMING_CONTRACT_R2; physical .5s contiguous HOLD unchanged; common phase minima 9/1/9, upper slack .020s + 1e-9 per phase.'
 write(D/'SAC_EXPERT_V1_CONTRACT.json',contract);write(D1/'SAC_EXPERT_V1_CONTRACT_R2.json',contract)
 (D1/'SAC_EXPERT_V1_CONTRACT_R2.md').write_text('# Single-Human SAC Expert contract R2\n\nTiming eligibility is the only scientific revision from preserved blocked R1. Observation 55-D, independent 2-D absolute online target, fixed normalization, reward, .020s policy period, commissioned frozen Human, physical task/safety and protected runtime remain byte-identical. Full unchanged definitions and evidence hashes are in JSON. Timing rule is frozen before any SAC learning; all affected comparator/task gates must pass before throughput and formal training. Additional wall cap is 12 hours from R2 preflight, one active environment, Seed 1 priority with meaningful Seed 2 only if budget permits.\n')
 tests=[]
 for name,times,expected in [('lower',dict(OUTBOUND=9,HOLD=1,RETURN=9),True),('upper',dict(OUTBOUND=9.02,HOLD=1.02,RETURN=9.02),True),('early_hold',dict(OUTBOUND=9,HOLD=.999,RETURN=9),False),('late_hold',dict(OUTBOUND=9,HOLD=1.025,RETURN=9),False),('early_outbound',dict(OUTBOUND=8.999,HOLD=1,RETURN=9),False),('late_return',dict(OUTBOUND=9,HOLD=1,RETURN=9.025),False)]:
  actual=matched_eligible(times);assert actual==expected;tests.append(dict(name=name,expected=expected,actual=actual,pass_=True))
 write(D/'TIMING_RULE_REGRESSION.json',dict(status='PASS',cases=tests,termination_implementation_changed=False,original_timeout_truncation_reward_audit_sha256=sha(D1/'SAC_REWARD_AUDIT.json')))
 print(json.dumps(dict(phase='TIMING_R2_FROZEN',allowance_s=DECISION_ALLOWANCE,tests=len(tests),actor_and_physical_source_unchanged=True)),flush=True)
def rescore(row):
 row=json.loads(json.dumps(row));row['R1_valid']=row['valid'];row['task_valid']=bool(row['physical_audit']['pass_']);row['matched_eligible']=matched_eligible(row['phase_durations']);row['matched_timing_valid']=row['scope']!='MATCHED' or row['matched_eligible'];row['valid']=row['task_valid'] and row['matched_timing_valid'];row['timing_contract']='SAC_MATCHED_TIMING_CONTRACT_R2';row['evidence_route']='Rescore unchanged raw trace and previously unchanged independent physical evaluator; no controller/runtime/task change';assert sha(R/row['trace'])==row['trace_sha256'];return row
def comparator_table(rows,status):
 write(D/'SAC_COMPARATOR_TABLE.json',dict(status=status,rows=rows,historical_numbers_not_directly_ranked=True));write(D1/'SAC_COMPARATOR_REQUALIFICATION.json',dict(status=status,rows=rows,timing_contract_sha256=sha(D1/'SAC_MATCHED_TIMING_CONTRACT_R2.json')))
 compact=[{**{k:r.get(k) for k in ('name','scope','task_valid','matched_eligible','valid','J_F','force_peak','moment_peak','duration_s','clearance','physical_clearance','trace','trace_sha256')},**{p+'_s':r['phase_durations'][p] for p in PHASE_MIN}} for r in rows]
 q.table('SAC_COMPARATOR_TABLE.csv',compact);shutil.copy2(D/'SAC_COMPARATOR_TABLE.csv',D1/'SAC_COMPARATOR_REQUALIFICATION.csv')
def qualify_timing():
 assert json.loads((D1/'SAC_MATCHED_TIMING_CONTRACT_R2.json').read_text())['formal_training_steps_at_freeze']==0
 if not resource_check('before_comparator_qualification'):return
 rows=[rescore(r) for r in json.loads((D1/'SAC_COMPARATOR_TABLE.json').read_text())['rows']];comparator_table(rows,'RUNNING')
 for fn in (f.simple_comparator,f.cem_comparator):
  if not resource_check('before_'+fn.__name__):return
  record=fn('MATCHED');rows.append(record);comparator_table(rows,'RUNNING');print(json.dumps({k:record[k] for k in ('name','scope','task_valid','matched_eligible','valid','J_F','phase_durations')}),flush=True)
 baseline=rows[0]
 initial_same=all(np.allclose(r[k],baseline[k],atol=1e-12,rtol=0) for r in rows for k in ('model_beta','model_residual','initial_estimated_state'))
 gates=dict(comparator_initial_conditions=initial_same,all_required_comparators_valid=all(any(r['name']==n and r['scope']==scope and r['valid'] for r in rows) for n in ('old_nominal','online_reference','fixed_hip_lead','cem_reference_transfer') for scope in ('NATIVE','MATCHED')),timing_rule_regression=json.loads((D/'TIMING_RULE_REGRESSION.json').read_text())['status']=='PASS',original_physical_hold_task_unchanged=sha(S/'configs/high_rom_v1/stage5_goal_task_120_v1.json')==json.loads((D1/'SAC_MATCHED_TIMING_CONTRACT_R2.json').read_text())['physical_task']['unchanged_task_config_sha256'],retained_reward_audit=json.loads((D/'SAC_REWARD_AUDIT.json').read_text())['status']=='PASS',retained_reset_stress=json.loads((D/'SAC_RESET_STRESS.json').read_text())['status']=='PASS')
 write(D/'FINAL_QUALIFICATION_GATES.json',dict(status='PASS' if all(gates.values()) else 'FAIL',gates=gates,formal_steps=0))
 if not all(gates.values()):comparator_table(rows,'FAIL');q.status('QUALIFICATION_STOP',status='BLOCKED',blocker='R2_AFFECTED_TIMING_GATES_FAIL',next_action='Preserve failures, STOP without training.');return
 comparator_table(rows,'PASS');q.status('R2_TIMING_GATES_PASS',status='SAC_EXPERT_V1_R2_QUALIFIED',next_action='Resource-safe actual CUDA throughput then freeze formal configuration and train automatically.')
 contract=json.loads((D/'SAC_EXPERT_V1_CONTRACT.json').read_text());contract['status']='SAC_EXPERT_V1_R2_QUALIFIED';write(D/'SAC_EXPERT_V1_CONTRACT.json',contract);write(D1/'SAC_EXPERT_V1_CONTRACT_R2.json',contract)
 print('SAC_EXPERT_V1_R2_QUALIFIED',flush=True)
def benchmark():
 assert json.loads((D/'FINAL_QUALIFICATION_GATES.json').read_text())['status']=='PASS'
 if not resource_check('before_throughput'):return
 import throughput as t
 t.D=D;t.O=O
 t.main()
 # The prior mechanical benchmark intentionally starts updates at 32. Also
 # measure the actual formal 5000-step random-action warm-up configuration.
 if json.loads((D/'SAC_THROUGHPUT.json').read_text())['status']=='PASS':
  from stable_baselines3 import SAC
  import torch
  case,options=load_case_options();env=SACExpertEnv(O/'throughput/formal_config_collection',case,options,.02,retain_trace=False)
  config=json.loads((D/'SAC_TRAINING_CONFIG.json').read_text());kwargs={k:config[k] for k in ('learning_rate','batch_size','buffer_size','learning_starts','train_freq','gradient_steps','tau','ent_coef','target_entropy','replay_buffer_kwargs')}
  model=SAC('MlpPolicy',env,device='cuda',gamma=gamma_for(.02),policy_kwargs=dict(net_arch=config['network']),seed=config['seeds'][0],verbose=0,**kwargs)
  res=t.Resources();res.start();start=time.monotonic();cpu=time.process_time();callback=t.CollectionCallback()
  try:
   model.learn(total_timesteps=128,callback=callback)
   collection=t.summarize('Exact formal configuration collection warm-up; no optimization before learning_starts=5000',start,cpu,model.num_timesteps,callback.sim_s,res);collection.update(episodes=callback.episodes,learning_starts=model.learning_starts,gradient_updates=model._n_updates,formal=False,never_reused_for_formal=True)
   data=json.loads((D/'SAC_THROUGHPUT.json').read_text());data['formal_configuration_collection']=collection;rate=min(data['sac']['agent_steps_s'],collection['agent_steps_s']);data['conservative_budget_rate_steps_s']=rate
   data['estimates']={str(n):dict(hours=n/rate/3600,rate_steps_s=rate,uncertainty='Short benchmark includes reset costs and exact formal random-action warmup; learning changes failure/reset frequency. Hard additional wall cap controls actual execution.') for n in (100000,300000,500000,1000000,2000000)}
   write(D/'SAC_THROUGHPUT.json',data);print(json.dumps(dict(exact_formal_collection_rate=collection['agent_steps_s'],budget_rate=rate,estimates=data['estimates'])),flush=True)
  finally:env.close();res.close()
 for name in ('SAC_THROUGHPUT','SAC_RUNTIME_PROFILE'):
  for ext in ('.json','.md'):
   if (D/(name+ext)).exists():shutil.copy2(D/(name+ext),D1/(name+'_R2'+ext))
def lock_and_budget_r2():
 assert json.loads((D/'FINAL_QUALIFICATION_GATES.json').read_text())['status']=='PASS'
 assert json.loads((D/'STATE.json').read_text())['phase']=='ALL_QUALIFICATION_GATES_PASS'
 assert resource_check('before_formal_training')
 throughput=json.loads((D/'SAC_THROUGHPUT.json').read_text());assert throughput['status']=='PASS'
 rate=throughput['sac']['agent_steps_s'];warmup_rate=throughput['formal_configuration_collection']['agent_steps_s'];start=json.loads((D1/'GIT_PREFLIGHT_R2.json').read_text())['started_unix'];cutoff=start+12*3600;train_end=cutoff-45*60
 # Bound by measured resets + actual CUDA update throughput, reserve the
 # original independent evaluation cadence, and prioritize >=300k Seed 1.
 available=max(0.,train_end-time.time())-max(0.,5000/warmup_rate-5000/rate);feasible=int(rate*available);eval_s=max(180.,2*throughput['deterministic_evaluation']['wall_s'])
 for _ in range(3):feasible=max(0,int(rate*(available-math.ceil(feasible/25000)*eval_s)))
 if feasible>=1000000:targets=[500000,500000]
 elif feasible>=600000:targets=[500000,100000]
 elif feasible>=350000:targets=[min(500000,feasible-50000),50000]
 else:targets=[300000]
 config=json.loads((D/'SAC_TRAINING_CONFIG.json').read_text());config.update(status='FROZEN_FORMAL',gamma=gamma_for(.02),policy_period_s=.02,version='SB3_2.6.0_R2_timing_only',planned_steps=targets,seeds=config['seeds'][:len(targets)],hard_wall_cutoff_unix=cutoff,hard_wall_cutoff_utc=datetime.datetime.fromtimestamp(cutoff,datetime.timezone.utc).isoformat(),training_cutoff_utc=datetime.datetime.fromtimestamp(train_end,datetime.timezone.utc).isoformat(),seed2_reserved_wall_s=targets[1]/rate if len(targets)>1 else 0.,benchmark_rate=rate,benchmark_warmup_rate=warmup_rate,minimum_meaningful_seed1_steps=300000,measured_feasible_steps=feasible,partial_if_wall_cap_before_minimum=True)
 write(D/'SAC_TRAINING_CONFIG.json',config);write(D1/'SAC_TRAINING_CONFIG_R2.json',config)
 contract=json.loads((D/'SAC_EXPERT_V1_CONTRACT.json').read_text());contract.update(status='FROZEN_FORMAL',formal_frozen_utc=now(),training=config)
 ref=json.loads((D/'RUN_reference_20ms_NATIVE.json').read_text());matched=json.loads((D/'RUN_final_reference_20ms_MATCHED.json').read_text())
 contract['discount'].update(native_reference_decisions=ref['steps'],matched_reference_decisions=matched['steps'],selected_complete_task_weights=dict(native=float(gamma_for(.02)**ref['steps']),matched=float(gamma_for(.02)**matched['steps'])))
 contract['budget'].update(target_hours=[4,10],hard_additional_hours=12,planned_seed_steps=targets,minimum_seed1_steps=300000,selected_feasible_steps=feasible,checkpoint_interval_steps=25000,independent_confirmation_J_F_tolerance_n_s=1e-6,phase_policy='Fresh initialization, no benchmark replay/weights, no curriculum; Seed 1 priority; no second seed unless >=50k independent budget fits. Preserve ordinary failed episodes; partial if hard time/resource stop prevents minimum.')
 write(D/'SAC_EXPERT_V1_CONTRACT.json',contract);write(D1/'SAC_EXPERT_V1_CONTRACT_R2.json',contract)
 pre=json.loads((D1/'GIT_PREFLIGHT_R2.json').read_text());fingerprints=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text());files=fingerprints['protected_files'].copy()
 # The full original index/worktree inventory is checked at closeout. Frequent
 # locks cover executable/configuration and scientific-input sources, avoiding
 # repeatedly reading unrelated historical binary artifacts during learning.
 for p in (P1/'sac_env.py',P1/'qualify.py',P1/'final_qualification.py',P1/'throughput.py',S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py',D1/'SAC_REWARD_AUDIT.json',D1/'SAC_RESET_STRESS.json',D1/'SAC_OBSERVATION_NORMALIZATION.json'):files[str(p.relative_to(R))]=sha(p)
 for p in (P/'train_campaign_r2.py',P/'campaign_r2.py',D/'SAC_EXPERT_V1_CONTRACT.json',D/'SAC_TRAINING_CONFIG.json',D1/'SAC_MATCHED_TIMING_CONTRACT_R2.json',D/'SAC_OBSERVATION_NORMALIZATION.json'):files[str(p.relative_to(R))]=sha(p)
 lock=dict(files=files,contract_hash=sha(D/'SAC_EXPERT_V1_CONTRACT.json'),configuration_hash=sha(D/'SAC_TRAINING_CONFIG.json'),frozen_model_hash=ref['model_hash'],frozen_model=ref['frozen_model'],task_hash=sha(S/'configs/high_rom_v1/stage5_goal_task_120_v1.json'),condition_hash=sha(S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'),normalization_hash=sha(D/'SAC_OBSERVATION_NORMALIZATION.json'),user_request_hash=sha(D1/'USER_REQUEST_R2.txt'),source_head=pre['head'],branch=pre['branch'])
 write(D/'SAC_CONTRACT_LOCK.json',lock)
 print(json.dumps(dict(phase='FORMAL_CONFIG_FROZEN',steps=targets,measured_feasible_steps=feasible,budget_rate=rate,hard_cutoff_utc=config['hard_wall_cutoff_utc'])),flush=True)
 return config,lock,train_end
def train():
 assert json.loads((D/'STATE.json').read_text())['phase']=='ALL_QUALIFICATION_GATES_PASS'
 if not resource_check('formal_dispatch'):return
 sys.path.insert(0,str(P));import train_campaign_r2 as tc
 tc.metric_record=metric;tc.lock_and_budget=lock_and_budget_r2
 tc.run()
if __name__=='__main__':
 configure()
 try:
  {'prep':prep,'qualify':qualify_timing,'benchmark':benchmark,'train':train}[sys.argv[1]]()
 except Exception as error:
  if D.exists():write(D/'R2_EXCEPTION_'+sys.argv[1]+'.json',dict(error=str(error),traceback=traceback.format_exc(),utc=now()));q.status('R2_EXCEPTION_STOP',status='BLOCKED',blocker=str(error))
  raise
