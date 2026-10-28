from pathlib import Path
import hashlib,json,time,subprocess,platform,zipfile,shutil
R=Path(__file__).resolve().parent;B=R.parent;OLD=B/'rl_b_first_ppo_pilot_v1'
def put(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(4*1024**2),b''):h.update(x)
 return h.hexdigest()
state=json.loads((R/'STATE.json').read_text())
protocol={'study':R.name,'frozen_unix':time.time(),'question':'Does the exact pilot PPO task-learning signal replicate over three independently initialized training seeds?',
 'category':'BOUNDED_DEVELOPMENT_REPLICATION_NOT_FORMAL_QUALIFICATION','seed_rule':'first 8 hex digits of SHA256(package_name + :stage1: + index), modulo 2147483647; indices 0,1,2; generated only after this protocol is written',
 'stage1':{'stages':[20,50],'optional_extension':80,'episode_cap':240,'all_seeds_reported':True,'no_seed_specific_tuning':True,'extension_rule':'At 50 extend ALL three seeds to 80 only if at least two seeds have a higher last-10 than first-10 training completion rate, not all three have final repeated runtime success, at least 90 minutes remain before no-new-physics and >12M native steps remain. Frozen evaluation cannot choose seed/reward; no extension otherwise.'},
 'evaluation':{'episode_cap':24,'schedule':['initial deterministic once per seed','episode20 deterministic once per seed','episode50 deterministic twice per seed','if extension episode80 deterministic twice per seed','one fixed legal plus-one control explicitly not B/H150','if Stage2 final deterministic twice against its frozen Stage1 parent'],'nominal_only':True,'environment_seed':20261020,'physical_initial_state_rule':'Exact historical deterministic commissioning/recovery and nominal task state; environment seed does not randomize patient or physical parameters.','no_heldout_generalization_claim':True,'not_used_for_configuration_selection':True},
 'replication_pass_rule':'All three seeds improve from an initial deterministic runtime failure to repeated 2/2 runtime success at the final preregistered checkpoint. Otherwise report partial/not replicated, with every seed. Runtime success is not matched/full qualification.',
 'stage2':{'episode_cap':50,'planned_episodes':30,'parent_rule':'smallest numerical Stage1 seed, final preregistered checkpoint; never pick best force result','gate':'3/3 replication criterion, parent repeated 2/2 runtime complete, no observed hard safety/reward/ownership defect, >60 minutes until no-new-physics and sufficient native budget; full scorer missing permits non-promotion development only','reward_design':'Freeze a simple task/progress/completion + force + motion cost after Stage1 training-reward audit and before Stage2. No tuning on frozen evaluation; no reward revision branch planned.','checkpoints':[10,20,30],'stop_rule':'Stop on observed safety/reward/ownership defect, nonfinite values, or after a block of 10 with training completion rate more than 20 percentage points below the parent last20; final frozen task failure forbids improvement claim.'},
 'unchanged_scientific_variables':['41-dimensional causal observation allowlist','2 bounded continuous progress-fraction intents, no teacher','pilot_v3_failure_cost_floor reward and all PPO hyperparameters for Stage1','original robot/cuff/passive hip-knee Human physics','0.25ms native steps, 5ms controls','original planner/certificate/admission/governor/40ms bridge/100ms lifecycle/controller/allocator','original task, absolute safety and scorer thresholds'],
 'truth_firewall':'Actor uses current causal measured/estimated interface only. qpos/qvel/native and future truth are evaluation-only. No human future truth or teacher actions.',
 'qualification':{'runtime':'original COMPLETE, all OUTBOUND/HOLD/RETURN transitions and causal completion commit','matched':'all original frozen matched task conditions; timing alone insufficient','full':'original matched task+safety+motion/fairness+causal all passing; missing semantics means NOT_READY','host_realtime':'NOT_EVALUABLE in scientific mode; no strict55 claim'},
 'resources':{'t0_unix':state['t0_unix'],'hard_stop_unix':state['hard_stop_unix'],'no_new_physics_after_unix':state['no_new_physics_after_unix'],'native_steps_hard_cap':42000000,'rl_decisions_hard_cap':40000,'optimizer_steps_hard_cap':12000,'episode_decision_cap':128,'max_episode_wall_s':300,'min_available_ram_GiB':6,'min_free_disk_GiB':10,'max_output_GiB':35,'cpu_threads_per_environment':1,'maximum_physics_envs':1,'process_timeout_s':14400,'monitor_interval_s':15},
 'exclusions':'No task failure excluded. Infrastructure/resource interruption is PARTIAL_INFRASTRUCTURE and counts as a physical attempt, with actual completed steps, but is never relabeled a task failure or successful training episode.',
 'train_artifacts':'Every episode: compact PPO transition/rollout, terminal summary, reward parts, observed native/motion/safety/causal audit, action proposals/receipts, resources. Periodic checkpoints at initialization and every 5 completed episodes plus phase ends; complete raw for every frozen evaluation. Training native journal and large runtime raw are temporary, audited then pruned with SHA256 tombstones; failed/partial summaries and compact evidence remain.',
 'stop_boundary':'No final campaign, no next research package, no Git writes or instance changes.'}
put(R/'REPLICATION_PROTOCOL.json',protocol)
protocol_sha=sha(R/'REPLICATION_PROTOCOL.json')
seeds=[int(hashlib.sha256((R.name+':stage1:'+str(i)).encode()).hexdigest()[:8],16)%2147483647 for i in range(3)]
assert len(set(seeds))==3
cfg={**protocol['resources'],'study':R.name,'protocol_sha256':protocol_sha,'seeds':seeds,'environment_seed':20261020,'phase_caps':[20,50,80],'training_episode_cap':240,'stage2_episode_cap':50,'evaluation_episode_cap':24,'reward_version':'pilot_v3_failure_cost_floor','ppo':json.loads((OLD/'PPO_TRAINING_CONFIG.json').read_text())['ppo']}
put(R/'PPO_TRAINING_CONFIG.json',cfg)
put(R/'audit/SEED_GENERATION.json',{'protocol_sha256':protocol_sha,'generated_unix':time.time(),'rule':protocol['seed_rule'],'seeds':seeds,'excluded_seeds':[]})
protected={};protected_names=[]
for name in ['rl_b_first_ppo_pilot_v1','rl_b_g4_closure_ppo_readiness_v1','rl_b_cloud_g4_repair_v1','rl_b_cloud_v1']:
 for p in sorted((B/name).rglob('*')):
  if not p.is_file() or '.venv' in p.parts:continue
  protected[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size};protected_names.append(str(p))
for p in [*B.glob('*.zip'),Path('/home/hank/ihear_rl_b_cpu_cloud_v1.zip')]:
 protected[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
put(R/'audit/HISTORICAL_PROTECTION_BEFORE.json',{'unix':time.time(),'files':protected,'excluded':'.venv dependencies only; no history output/source/checkpoint excluded'})
source={str(p.relative_to(R/'source')):sha(p) for p in sorted((R/'source').rglob('*')) if p.is_file()}
original={str(p.relative_to(OLD/'source')):sha(p) for p in sorted((OLD/'source').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
assert source==original
put(R/'SOURCE_MANIFEST.json',{'source_path':str(OLD/'source'),'files':source,'source_files':len(source),'exact_copy':True})
put(R/'audit/ENVIRONMENT.json',{'python':subprocess.check_output([str(B/'rl_b_cloud_v1/.venv/bin/python'),'-V'],text=True).strip(),'platform':platform.platform(),'uname':platform.uname()._asdict(),'cpu_count':__import__('os').cpu_count(),'starting_git_state':state['git'],'git_mutations':False,'dependencies_unchanged':True})
print(json.dumps({'seeds':seeds,'protocol_sha256':protocol_sha,'protected_files':len(protected),'source_files':len(source)}))
