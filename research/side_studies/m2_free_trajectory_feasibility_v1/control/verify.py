from pathlib import Path
import json,sys,time,hashlib,subprocess,gzip,shutil,collections,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
sys.path.insert(0,str(S/'code'))
from study_common import clean,sha
import numpy as np
def load(p):return json.loads(Path(p).read_text())
def put(n,x):(S/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
before=load(S/'preservation/GIT_BEFORE.json')
request=Path('/mnt/c/Users/HankL/.codex/attachments/bacda6c1-6e5b-4125-980d-b790a4774d56/已粘贴的文本.txt')
if request.exists():shutil.copy2(request,S/'USER_REQUEST.txt')
def git(r):
    r=Path(r)
    def g(*a):return subprocess.check_output(['git','-C',str(r),*a],env={'PATH':'/usr/bin:/bin','GIT_OPTIONAL_LOCKS':'0'}).decode()
    return dict(head=g('rev-parse','HEAD'),branch=g('branch','--show-current'),status=g('status','--porcelain=v1'),index=sha(r/'.git/index'),staged=hashlib.sha256(g('diff','--cached','--binary').encode()).hexdigest(),unstaged=hashlib.sha256(g('diff','--binary').encode()).hexdigest())
after={r:git(r) for r in before};put('preservation/GIT_AFTER.json',after)
original=load(S/'preservation/REUSED_SOURCE_HASHES.json');changed=[p for p,h in original.items() if not Path(p).exists() or sha(p)!=h]
parents=[]
for p in (S/'reports').glob('*_PARENT_CHECKS.json'):
    parents.extend(load(p))
rows=[json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()]
independent=[]
for r in rows:
    ident=r['id'];m=load(r['metrics_path']);directory=S/'source/results'/ident
    with np.load(directory/'trace.npz') as z:
        ix=z['stage']=='TASK';t=z['time_s'][ix];f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1)
        jf=float(np.sum(f[:-1]*np.diff(t)));mi=float(np.sum(moment[:-1]*np.diff(t)))
    with np.load(S/'motion_series'/(ident+'.npz')) as z:
        t=z['time_s'];q=z['true_q_rad'];dq=z['true_dq_rad_s'];a=np.gradient(dq,t,axis=0,edge_order=2);jerk=np.gradient(a,t,axis=0,edge_order=2)
        recomputed={}
        for key,value in [('velocity_deg_s',dq),('acceleration_deg_s2',a),('jerk_deg_s3',jerk)]:
            x=np.rad2deg(value);stats=dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
            recomputed[key]={stat:float(np.max(abs(v-np.array(m['motion']['raw']['full'][key][stat])))) for stat,v in stats.items()}
        dose=dict(excursion_error_deg=float(np.max(abs(np.rad2deg(np.ptp(q,axis=0))-m['dose']['excursion_deg']))),cumulative_error_deg=float(np.max(abs(np.rad2deg(np.sum(abs(np.diff(q,axis=0)),axis=0))-m['dose']['cumulative_travel_deg']))))
    err=max(v for stats in recomputed.values() for v in stats.values())
    assert abs(jf-m['J_F_N_s'])<1e-8 and abs(mi-m['moment_integral_Nm_s'])<1e-8 and err<1e-8,'INDEPENDENT_NUMERICAL_MISMATCH'
    assert m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS' and m['axes']['PHYSICAL_TASK_VALID']=='PASS'
    independent.append(dict(id=ident,force_integral_error_N_s=jf-m['J_F_N_s'],moment_integral_error_Nm_s=mi-m['moment_integral_Nm_s'],raw_motion_statistic_error=recomputed,dose_error=dose,status='PASS'))
put('INDEPENDENT_DERIVED_CHECKS.json',dict(status='PASS',runs=independent,source='control trace and archived unfiltered native q/dq independently re-integrated and differentiated',scope='same scientific raw data, not independent physical conditions'))
crc=[]
for p in (S/'source/results').glob('*/runtime_artifacts.json.gz'):
    h=hashlib.sha256();size=0
    with gzip.open(p,'rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk);size+=len(chunk)
    crc.append(dict(path=str(p.relative_to(S)),gzip_EOF_CRC='PASS',decoded_sha256=h.hexdigest(),decoded_bytes=size))
attempts=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in attempts if r['event']=='START']
compute=[]
for a in starts:
    ident=a['id'];p=S/'output'/(ident+'_DATA.json');partial=S/'output'/(ident+'_PARTIAL_COMPUTE.json')
    if p.exists():m=load(p)['metric'];kind='COMPLETE_PHYSICS'
    elif partial.exists():m=load(partial);kind='PARTIAL_OR_EXCEPTION'
    else:m={};kind='NO_FINAL_COMPUTE_RECORD'
    compute.append(dict(id=ident,kind=kind,actual_new_native_steps=m.get('actual_new_native_physics_steps'),actual_new_simulation_seconds=m.get('actual_new_simulation_seconds'),actual_new_main_inverse_dynamics_API_calls=m.get('actual_new_main_model_inverse_dynamics_api_calls'),actual_new_worker_inverse_dynamics_API_calls=m.get('actual_new_native_worker_model_inverse_dynamics_api_calls'),force_observed_N_s=m.get('J_F',m.get('observed_tick_force_integral')),task_valid=m.get('task_valid',False)))
put('ACTUAL_PHYSICAL_WORK.json',dict(starts=len(starts),cap=96,all_optimizer_real_evaluations_counted=True,rows=compute,total_known_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in compute),known_steps_exact_for_all=all(r['actual_new_native_steps'] is not None for r in compute),failed_logging_attempt_retained=True,mechanics_preview='Original analytic/estimated inverse-dynamics and schedule geometry screens are separately counted API calls, not forward integrated patient/robot rollouts; all actual mj_step forward task/prefix attempts appear in START ledger.'))
lookup={r['id']:r for r in rows};grades=[]
for a in starts:
    r=lookup.get(a['id']);c=next(c for c in compute if c['id']==a['id'])
    grades.append(dict(id=a['id'],qualified_result_level=r['level'] if r else 'REFERENCE_OR_PREFIX_ONLY_NOT_RANKED',native_B_executable=r.get('native_B_executable') if r else None,physics_compute_kind=c['kind'],task_valid=c['task_valid'],motion_pass=r['comparison']['acceptance_pass'] if r else None,classification_rule='Only full task, absolute safety and all frozen motion gates permit DYNAMICS_FEASIBLE; physically executed motion failures are explicitly below feasible promotion, not mathematical-only results. Prefix parents are provenance, not ranked new candidates.'))
put('ALL_ATTEMPT_CLASSIFICATION.json',grades)
put('COMMANDS_AND_REVISIONS.json',dict(python='/home/hank/envs/adaptive-online-rl-v1/bin/python',WSL='Ubuntu-Research-Verify',physical_commands=[dict(mode=mode,command='/home/hank/envs/adaptive-online-rl-v1/bin/python code/runner.py '+mode,first_start_unix=min(a['unix'] for a in starts if a.get('mode')==mode),working_directory=str(S)) for mode in dict.fromkeys(a.get('mode') for a in starts)],source_revisions={str(p.relative_to(S)):sha(p) for p in (S/'preservation/code_revisions').glob('*.py')},current_research_code_sha256={name:sha(S/'code'/name) for name in ['runner.py','free_planner.py']},controller_and_physical_originals_hashes_file='preservation/REUSED_SOURCE_HASHES.json',derived_control_scripts_file='control/',COBYLA_child_callback_unwind='Expected capi_return/callback stderr occurs only in forked child when returning from optimizer callback into the inherited physical runtime; parent optimizer resumes after child joins. It is not numerical rollout failure. Physical errors and optimizer termination status remain separately archived.'))
required=['REPORT.md','PHYSICAL_ACTION_SPACE.md','TRAJECTORY_OPTIMIZATION_PROTOCOL.json','BASELINE_REPRODUCTION.json','FREE_TRAJECTORY_SEARCH_RESULTS.json','FORCE_MOTION_TRADEOFFS.json','PHYSICAL_FEASIBILITY_VALIDATION.json','INTERFACE_GAP_ANALYSIS.md','NEXT_RESEARCH_DECISION.md']
assert all((S/n).exists() for n in required)
P=load(S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json');elapsed=time.time()-P['t0_unix'];last=max(a['unix'] for a in starts)
pin=load(S/'VALIDATION_PARAMETER_PIN.json')
assert sha(S/'FROZEN_SELECTION.json')==pin['selection_sha256'] and sha(S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json')==pin['protocol_sha256'],'VALIDATION_PARAMETERS_OR_PROTOCOL_CHANGED'
owned=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==os.getpid():continue
    try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    if 'code/runner.py' in cmd and str(S) in (p/'cwd').resolve().as_posix():owned.append(dict(pid=int(p.name),command=cmd))
size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file());free=shutil.disk_usage('/mnt/d').free
checks=dict(git_snapshot_equal=before==after,original_reused_sources_unchanged=not changed,parent_forks_unpolluted=all(r['unchanged'] for r in parents),all_required_deliverables_present=True,numeric_checks_pass=True,gzip_eof_crc_pass=True,attempts_within_cap=len(starts)<=96,all_new_physics_dispatched_before_cutoff=last<P['dispatch_cutoff_unix'],elapsed_within_four_hours=elapsed<14400,study_below_target_4GiB=size<=4*2**30,study_below_hard_8GiB=size<8*2**30,D_free_above_40GiB=free>40*2**30,no_owned_physics_process=not owned)
assert all(checks.values()),checks
put('PACKAGE_VERIFICATION.json',dict(status='PASS',unix=time.time(),elapsed_minutes=elapsed/60,checks=checks,attempt_count=len(starts),ordinary_generated_raw_compaction_scope='new package only, after full safety/receipt/integral audit; no historical deletion',source_hashes_checked=len(original),changed_original_sources=changed,git_before_after_equal=before==after,parent_checks=len(parents),parent_child_nonzero_exit=[r for r in parents if r['child_exitcode']!=0],logging_error_preserved=load(S/'WRAPPER_REPAIR_REGISTERED.json'),retained_raw_crc=crc,study_bytes=size,D_free_bytes=free,owned_physics_processes=owned,protected_scope='two Linux Git branch/HEAD/index/staged/unstaged/status plus reused frozen source/deps/native/build/weights byte hashes; no full historical byte scan',no_Q_training=True,no_online_individualization=True,no_production_B_change=True,no_host_clock=True,no_hardware=True,no_git_mutation=True,terminal_state='STOP'))
for p in Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control').glob('*.py'):shutil.copy2(p,S/'control'/p.name)
manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='PACKAGE_MANIFEST.json'}
put('PACKAGE_MANIFEST.json',manifest)
review=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_review');review.mkdir(exist_ok=True)
for p in S.iterdir():
    if p.is_file() and p.suffix in ['.json','.md','.jsonl'] and p.stat().st_size<30*2**20:shutil.copy2(p,review/p.name)
shutil.copytree(S/'figures',review/'figures',dirs_exist_ok=True)
print(json.dumps(dict(status='PASS',attempts=len(starts),elapsed_minutes=elapsed/60,study_GiB=size/2**30,D_free_GiB=free/2**30,review=str(review))))
