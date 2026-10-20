"""Prospective qualification only. Never starts formal learning before ALL gates pass."""
from pathlib import Path
import sys,json,time,traceback,shutil,hashlib,csv,resource,subprocess,gzip
import numpy as np
from types import SimpleNamespace
from sac_env import *
D=S/'docs/single_human_sac_expert_v1';O=S/'results/single_human_sac_expert_v1';P=S/'scripts/single_human_sac_expert_v1'
class Process:
    def memory_info(self):return SimpleNamespace(rss=int(Path('/proc/self/statm').read_text().split()[1])*4096)
    def io_counters(self):
        row=dict(line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines());return SimpleNamespace(write_bytes=int(row['write_bytes']))
def save(name,value):
    p=D/name;p.write_text(json.dumps(rt._jsonable(value),indent=2,sort_keys=True,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(name,rows):
    if not rows:return
    keys=sorted(set().union(*(r.keys() for r in rows)))
    with (D/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,keys);writer.writeheader();writer.writerows([{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows])
def status(phase,**extra):
    state=json.loads((D/'STATE.json').read_text());state.update(phase=phase,**extra);save('STATE.json',state)
def freeze_development():
    case,options=load_case_options()
    contract=dict(schema='single_human_sac_expert_v1',version=1,status='DEVELOPMENT_QUALIFICATION_NOT_FORMAL_FROZEN',Human='high_rom_nominal_sync_120_v1',task=dict(start_deg=[5,10],goal_deg=[120,120],hold_s=.5,phase_timeout_s=10,global_timeout_s=30),adaptation='commissioning_only; deterministic cold reset + identical commissioning each episode; no task updates; hash beta/residual/estimated geometry every decision',observation=feature_spec(),action=dict(dimensions=2,range=[-1,1],mapping='absolute independent joint target: q_min + (a+1)/2*(q_max-q_min)',reason='Development Gym repair: terminal +/-0.05 rad smoke mapping cannot express no/minimal motion or full lead/lag. Same certified acceleration-aware target interface, no plant/torque/state changes.',safety='unchanged online_reference.py realization and full continuation certification, then unchanged CR12 receipt/physical safety'),period_candidates_s=[.01,.02,.05],chosen_period_s=None,normalization=dict(mode='fixed physical scales; no clipping, no evaluation statistics; finite/outlier audit',statistics_updates=False),reward=dict(force='negative measured 5ms left quadrature /100 N s',shaping='5*(gamma*Phi_next-Phi_current), Phi in [0,3], absorbing terminal Phi=0',completion=500,failure=-1000,rejection=-.2,early_bonus=0,moment_weight=0,phase_potential='OUTBOUND normalized mean q progress; HOLD 1+valid dwell fraction; RETURN 2+return progress',deadline_replay='handle_timeout_termination=False: finite-horizon task failure has no bootstrap; Gym truncated=True remains explicit'),termination=dict(success='unchanged causal physical/task state machine; independent unchanged scientific evaluator gates promotion',failure='existing physical/task/safety abort',truncation='TIMEOUT failure; no success; absorbing observation'),reset='fresh single physics owner/plant/observer/updater/reference queues; repeated commissioning then frozen task; no prior session context',safety_limits=dict(force_n=200,moment_nm=60,ROM_deg=[[0,125],[0,125]],source='frozen config + scientific evaluator',no_oracle_actor=True),evaluation=dict(native='natural complete OUTBOUND/HOLD/RETURN',matched='prospective earliest OUTBOUND->HOLD at 9 s; earliest RETURN->COMPLETE at 9 s phase elapsed; valid arrival/dwell still required; late arrival >9.010 s invalid for matched ranking; reference and physics keep running; no equal-segment constraint',deterministic=True,normalization_frozen=True,interval_steps=25000,holdout='none; fixed previously exposed development Human only'),model_selection='valid deterministic independently replayed complete-task J_F; native and matched rankings separate; never training return; no global optimum',discount=dict(time_constant_s=150,candidates={str(p):{str(g):float(g**(18.5/p)) for g in (.99,.995,.999,.9995,.9999,gamma_for(p))} for p in (.01,.02,.05)},chosen_gamma=None),budget=dict(target_hours=[6,10],hard_hours=12,workers=1,desired_seed1_steps=[300000,500000,1000000],max_steps=2000000,seed2='independent meaningful run or comparable if measured time permits',seeds=[20261003,20261004],minimum_seed2_steps=50000,throughput_time_estimates_steps=[100000,300000,500000,1000000,2000000]),gates=['source integrity','causal observation/normalization','action authority and 10/20/50 ms physics','reward adversaries','20 sequential resets','independent complete-task physical evaluator','CUDA','final throughput incl CUDA collection/optimization','prospective timing comparator validity'],stop_before_training='Any unresolved qualification gate fails. Preserve negative evidence and STOP without training.',training=None)
    save('SAC_EXPERT_V1_CONTRACT.json',contract)
    (D/'SAC_EXPERT_V1_CONTRACT.md').write_text('# Single-Human Direct SAC Expert v1\n\nDevelopment qualification contract; formal training is prohibited until every gate passes and the selected period, discount, configuration and all source hashes are frozen. See JSON for machine-readable A–K definitions.\n\nThe fixed high-ROM nominal Human uses fresh deterministic physical commissioning and a frozen commissioned model during each episode. Hidden Human truth is excluded from the policy. A 55-D causal observation extends the validated 47-D vector with phase/dwell clocks, preceding proposed/executed action, rejection and remaining task time. Fixed physical scales never update or clip.\n\nThe old smoke mapping was only a terminal offset and is not a valid broad direct-policy contract. This version explicitly repairs the Gym mapping to absolute independent joint targets over the existing ROM; the acceleration-aware reference, physical plant, safety limits and evaluator remain unchanged.\n\nNative evaluation permits natural valid timing. Matched evaluation prospectively requires 9-second OUTBOUND and RETURN clocks plus the original valid HOLD; early arrival physically waits while cuff cost continues. Any late unmatched repetition is ineligible. No old segment-count semantics or trajectory imitation. All results are development evidence on one exposed Human.\n')
    save('SAC_OBSERVATION_NORMALIZATION.json',dict(status='PROSPECTIVELY_SPECIFIED',features=feature_spec(),dimension=55,causal_only=True,no_clipping=True,no_running_statistics=True,near_zero_scale=False))
    (D/'SAC_OBSERVATION_NORMALIZATION.md').write_text('# Observation and normalization\n\nAll 55 feature names, causal sources and exact scale values are in JSON. Angle scales use 125-degree ROM; per-joint velocity and acceleration scales use frozen task limits; measured force uses 200 N, moment uses 20 Nm, effective-model beta uses 10 coefficient units, residual uses 20 Nm, geometry uses 1 m; clocks use task/phase/HOLD duration. No clipping or future/evaluation statistics. Coefficient-specific interpretation is effective dynamics rather than anatomical truth. Outliers are measured before formal freeze.\n')
    save('SAC_TRAINING_CONFIG.json',dict(status='PROPOSED_NOT_TRAINED',algorithm='Stable-Baselines3 SAC',device='cuda',learning_rate=.0003,batch_size=256,buffer_size=100000,learning_starts=5000,train_freq=1,gradient_steps=1,gamma=None,tau=.005,ent_coef='auto',target_entropy='auto',network=[256,256],activation='ReLU',optimizer='Adam',seeds=[20261003,20261004],action_scaling='Box[-1,1]^2 to absolute existing-ROM target',observation_normalization='fixed 55-element scale vector',replay_buffer_kwargs=dict(handle_timeout_termination=False),torch_num_threads=1,version=None,policy_period_s=None))
    import torch,stable_baselines3,inspect
    ready=torch.cuda.is_available() and torch.cuda.get_device_name(0)=='NVIDIA GeForce RTX 4060 Laptop GPU'
    save('CUDA_READINESS.json',dict(pass_=ready,torch_version=torch.__version__,torch_cuda=torch.version.cuda,cuda_available=torch.cuda.is_available(),device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,sb3_version=stable_baselines3.__version__,sac_signature=str(inspect.signature(stable_baselines3.SAC)),physics='CPU MuJoCo unchanged',formal_training_steps=0))
    save('METHOD_SOURCES.json',dict(source='https://stable-baselines3.readthedocs.io/en/v2.6.0/modules/sac.html',claim='Use official SB3 SAC mature continuous-control implementation; parameters checked against installed 2.6.0 signature.',scope='implementation guidance only; physical claims from local evidence'))
    status('ACTION_AND_PERIOD_QUALIFICATION')
def policy(name,env,obs,info):
    phase=info['phase'];t=info['physics_task_s'];target=env.soft_target.copy();owned=env.owned.q_rad
    if name=='reference':pass
    elif name=='no_motion':target=owned.copy()
    elif name=='minimal_motion':target=owned+np.array([.0001,.0001])*(1 if phase!='RETURN' else -1)
    elif name in ('early_failure','repeated_rejection'):target=np.array([0.,ROM])
    elif name=='repeated_rejection_after_prefix' and t>=.1:target=np.array([0.,ROM])
    elif name=='timeout':target=np.radians([45.,45.])
    elif name=='skip_hold' and phase=='HOLD':target=np.radians([5.,10.])
    elif name=='incomplete_return' and phase=='RETURN':target=np.radians([60.,60.])
    elif name=='alternating_extreme':target=np.array([ROM,0.]) if int(t/env.period_s)%2 else np.array([0.,ROM])
    elif name=='alternating_extreme_after_prefix' and t>=.1:target=np.array([ROM,0.]) if int(t/env.period_s)%2 else np.array([0.,ROM])
    elif name=='force_moment_tradeoff':target=target+np.array([.04,-.04]) if .5<t<2.5 else target
    elif name=='rapid_completion':pass
    elif name=='stalling' and t<3.:target=owned.copy()
    elif name=='authority':
        sign=-1 if phase=='RETURN' else 1
        if .5<t<.7:target=owned+sign*np.array([.03,.005])
        elif .7<=t<.9:target=owned+sign*np.array([.005,.03])
        elif .9<=t<1.1:target=owned+sign*np.array([.003,.003])
    elif name=='fixed_hip_lead':
        if phase=='OUTBOUND' and t<1.5:target[1]=min(target[1],owned[1]+.02)
    return target_to_action(target,env.spec).astype(np.float32)
def physical_audit(env):
    sys.path.insert(0,str(S/'scripts/high_rom_v1'))
    from evaluate_execution_mode import evaluate
    scoring=json.loads((S/'docs/high_rom_v1/PHASE_B_MATRIX.json').read_text())['scoring']
    p=env.episode_dir;case_path=S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json'
    if not (p/'runtime_artifacts.json').exists() and (p/'runtime_artifacts.json.gz').exists() and (p/'SAC_PHYSICAL_AUDIT.json').exists():
        return json.loads((p/'SAC_PHYSICAL_AUDIT.json').read_text())
    (p/'HIGH_ROM_CASE_RESULT.json').write_text(json.dumps(dict(status=env.summary['status'],abort_reason=env.summary.get('abort_reason'),case_sha256=sha(case_path),elapsed_host_s=time.monotonic()-env.host_start,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_ms=0.)))
    mode=evaluate(p,dict(case_key=env.case['case_key'],physical_variant=env.case['cell']['family'],candidate=env.case['coordination_candidate'],path=str(case_path.relative_to(R)),sha256=sha(case_path)),scoring,goal_deg=[120,120],start_deg=[5,10])
    records=env.summary['online_reference_records'];accepted=[x for x in records if x.get('status')=='ACCEPTED']
    certs=(not records) or (bool(accepted) and all(x['activation_validation']['feasible'] and x['activation_validation']['C2'] and not x['activation_validation']['truth_consumed'] for x in accepted))
    result=dict(pass_=mode['overall_result_for_mode']=='PASS' and certs,unchanged_evaluator=mode,online_certificates_valid=certs)
    (p/'SAC_PHYSICAL_AUDIT.json').write_text(json.dumps(rt._jsonable(result),indent=2));return result
def rollout(name,period=.05,scope='NATIVE',limit=None):
    case,options=load_case_options();out=O/'qualification'/f'{name}_{int(period*1000)}ms_{scope}'
    env=SACExpertEnv(out,case,options,period,scope,retain_trace=True);start=time.monotonic();proc=Process();before=proc.io_counters();rss_before=proc.memory_info().rss
    record=dict(name=name,period_s=period,scope=scope,status='RUNNING',seed=20261003,formal_training=False)
    try:
        obs,info=env.reset(seed=20261003);record['initial_observation']=obs.tolist();record['model_hash']=env.model_hash;record['frozen_model']=env.model_record
        for k in range(5000 if limit is None else limit):
            action=policy(name,env,obs,info);obs,reward,terminated,truncated,info=env.step(action)
            assert np.all(np.isfinite(obs)) and np.isfinite(reward)
            if terminated or truncated:break
        record.update(result=info,steps=env.step_count,terminated=terminated,truncated=truncated,reward_totals=env.reward_parts,normalization_max_abs=(env.raw_max/SCALES).tolist(),action_modification_fraction=env.rejections/max(1,env.step_count),action_records=env.action_records,runtime_realization_ms=env.runtime_records)
        if terminated or truncated:
            record['physical_audit']=physical_audit(env)
            z=np.load(env.episode_dir/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
            jf=float(f[:-1]@np.diff(t));record['trace_J_F']=jf;record['reward_J_F_error']=env.force_integral-jf
            record['force_mean']=float(np.mean(f));record['force_rms']=float(np.sqrt(np.mean(f*f)));record['trace_force_peak']=float(np.max(f));record['trace_moment_peak']=float(np.max(m));record['trace_moment_integral']=float(m[:-1]@np.diff(t));record['phase_transitions']=env.summary['task']['phase_transitions']
            record['model_updates_task']=env.summary['task']['continual_adaptation_update_count']
            record['physical_success']=record['physical_audit']['pass_']
            record['status']='COMPLETE' if info.get('success') else 'EXPECTED_TASK_FAILURE'
        else:record['status']='SHORT_ROLLOUT'
    except Exception as error:record.update(status='EXCEPTION',error=str(error),traceback=traceback.format_exc())
    finally:
        env.close();record['host_s']=time.monotonic()-start;record['rss_before_bytes']=rss_before;record['rss_after_bytes']=proc.memory_info().rss;record['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;record['disk_written_bytes']=max(0,proc.io_counters().write_bytes-before.write_bytes)
    # Preserve new qualification traces losslessly, with both byte hashes inventoried.
    archives=[]
    for path in out.rglob('runtime_artifacts.json'):
        item=dict(original=str(path.relative_to(R)),original_sha256=sha(path),original_bytes=path.stat().st_size)
        compressed=Path(str(path)+'.gz')
        with path.open('rb') as source,gzip.open(compressed,'wb',compresslevel=3) as dest:shutil.copyfileobj(source,dest)
        item.update(archive=str(compressed.relative_to(R)),archive_sha256=sha(compressed),archive_bytes=compressed.stat().st_size)
        path.unlink();archives.append(item)
    record['lossless_archives']=archives
    save(f'RUN_{name}_{int(period*1000)}ms_{scope}.json',record)
    print(json.dumps(dict(name=name,period=period,scope=scope,status=record['status'],steps=record.get('steps'),host_s=record['host_s'],physical_success=record.get('physical_success'),J_F=record.get('trace_J_F'),reward_J_F_error=record.get('reward_J_F_error'),error=record.get('error'))),flush=True)
    return record
def main():
    command=sys.argv[1]
    if command=='freeze':freeze_development()
    elif command=='run':rollout(sys.argv[2],float(sys.argv[3]) if len(sys.argv)>3 else .05,sys.argv[4] if len(sys.argv)>4 else 'NATIVE')
    else:raise ValueError(command)
if __name__=='__main__':main()
