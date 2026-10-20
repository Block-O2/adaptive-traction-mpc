"""Prospective Seed 1 continuation, 30000 -> 300000; immutable SAC/R2 science."""
from pathlib import Path
import sys,os,json,time,threading,pickle,random,traceback,subprocess,shutil,gc
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')
sys.path.insert(0,str(W/'single_human_sac_memory'))
import memory_test_v1 as m
R=m.R;S=m.S;NAME='single_human_sac_seed1_continuation_v1_attempt2'
D=S/'docs'/NAME;O=S/'results'/NAME;P=S/'scripts'/NAME
LOCAL=W/'single_human_sac_seed1_continuation/output_attempt2'
START=S/'results/single_human_sac_memory_v1/attempt5/seed_20261003'
OLD=S/'docs/single_human_sac_expert_v1/r2'
TARGET=300000;START_STEP=30000;SEED=20261003
MODEL=None;ENV=None;CB=None;TR=None;WATCH=None
WATCH_END=threading.Event();WATCH_LOCK=threading.Lock();PRESSURE=None;PHASE='startup'
CONFIRMED={};FULL_SAMPLES=0;MAX_TREE=0;ERROR=None;T0=time.monotonic()

def write(name,data):
    value=json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n'
    for folder in (D,LOCAL):
        tmp=folder/(name+'.tmp');tmp.write_text(value);tmp.replace(folder/name)

def memory_write(name,data):
    global FULL_SAMPLES
    if name=='MEMORY_SAMPLES.json':
        row=data[-1];FULL_SAMPLES+=1
        for folder in (D,LOCAL):
            with (folder/'MEMORY_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
    else:write(name,data)

def full_sample(tag):
    m.MODEL=MODEL;m.ENV=ENV;m.CB=CB
    if TR is not None:m.TR=TR
    row=m.sample(tag);m.SAMPLES.clear();return row

def reasons(w,mem,procs,swap):
    out=[]
    if mem['MemAvailable']<1.5*2**30:out.append('WSL_AVAILABLE_BELOW_1_5_GIB')
    if w['CommitLimit']-w['CommittedBytes']<2*2**30:out.append('WINDOWS_COMMIT_HEADROOM_BELOW_2_GIB')
    if swap-m.SWAP0>16*2**20:out.append('NEW_SWAP_OVER_16_MIB')
    if w['AvailableBytes']<256*2**20 and mem['MemAvailable']<2*2**30:out.append('JOINT_LOW_MEMORY')
    if procs['other_heavy_python']:out.append('OTHER_HEAVY_PYTHON')
    if w['ExternalVideoRender']:out.append('EXTERNAL_VIDEO_RENDER')
    return out

def watch():
    global PRESSURE,MAX_TREE
    swap_increments=[];trend=[];baseline=None;latest_hour=None;growth_hits=0
    while not WATCH_END.is_set():
        try:
            w=m.windows();mem=m.memfile('/proc/meminfo');procs=m.processes()
            swap=mem['SwapTotal']-mem['SwapFree'];tree=sum(x.get('Pss',0) for x in procs['owned']);MAX_TREE=max(MAX_TREE,tree)
            vm={k:int(v) for k,v in (x.split() for x in Path('/proc/vmstat').read_text().splitlines())}
            now=time.monotonic();rs=reasons(w,mem,procs,swap)
            swap_increments.append((now,swap,vm['pswpout']));swap_increments=swap_increments[-6:]
            if len(swap_increments)>=4 and all(b[1]>a[1] or b[2]>a[2] for a,b in zip(swap_increments[-4:],swap_increments[-3:])):rs.append('SUSTAINED_SWAP_ACTIVITY')
            if PHASE=='training' and MODEL is not None and MODEL.num_timesteps>=55000:
                anon=procs['owned'][0].get('Pss_Anon',0);trend.append((now,anon));trend=[x for x in trend if now-x[0]<=4*3600]
                if baseline is None:baseline=anon;latest_hour=now
                if now-latest_hour>=3600:
                    past=[v for t,v in trend if now-t>=3500];recent=[v for t,v in trend if now-t<300]
                    hourly=(sum(recent)/len(recent)-sum(past)/len(past)) if past and recent else 0
                    growth_hits=growth_hits+1 if hourly>128*2**20 else 0;latest_hour=now
                    if growth_hits>=3 and anon-baseline>512*2**20:rs.append('SUSTAINED_ANONYMOUS_MEMORY_GROWTH')
                if tree>4.5*2**30:rs.append('PERSISTENT_TRAINING_TREE_OVER_4_5_GIB')
            row=dict(unix=time.time(),elapsed_s=now-T0,phase=PHASE,step=MODEL.num_timesteps if MODEL else START_STEP,windows=w,wsl=mem,swap_used_bytes=swap,vmstat_swap_pages={k:vm[k] for k in ('pswpin','pswpout')},memory_pressure=Path('/proc/pressure/memory').read_text(),processes=procs,tree_pss_bytes=tree,stop_reasons=rs)
            with (D/'RESOURCE_WATCH.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            with WATCH_LOCK:PRESSURE=row
        except Exception as ex:
            with WATCH_LOCK:PRESSURE=dict(stop_reasons=['RESOURCE_MONITOR_FAILED'],error=str(ex))
        WATCH_END.wait(20 if PHASE=='evaluation' else 30)

class ResourceStop(RuntimeError):pass

def guard(tag):
    row=full_sample(tag)
    with WATCH_LOCK:current=PRESSURE
    rs=reasons(row['windows'],row['wsl'],row['processes'],row['swap_used_bytes'])
    persistent={'SUSTAINED_SWAP_ACTIVITY','SUSTAINED_ANONYMOUS_MEMORY_GROWTH','PERSISTENT_TRAINING_TREE_OVER_4_5_GIB','RESOURCE_MONITOR_FAILED'}
    if current:rs+=list(persistent.intersection(current['stop_reasons']))
    if not rs:return True
    write('RESOURCE_PRESSURE.json',dict(tag=tag,reasons=rs,sample=row,watch=current))
    severe=row['windows']['CommitLimit']-row['windows']['CommittedBytes']<512*2**20 or row['wsl']['MemAvailable']<2**30 or row['swap_used_bytes']-m.SWAP0>16*2**20 or row['processes']['other_heavy_python'] or persistent.intersection(rs)
    if severe:return False
    healthy=0
    for k in range(12):
        time.sleep(10);row=full_sample(tag+'_park_'+str(k))
        rs=reasons(row['windows'],row['wsl'],row['processes'],row['swap_used_bytes']);healthy=healthy+1 if not rs else 0
        if healthy>=2:return True
        if row['swap_used_bytes']-m.SWAP0>16*2**20 or row['wsl']['MemAvailable']<2**30:return False
    return False

def rng():return dict(random=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all())
def restore(state):
    random.setstate(state['random']);np.random.set_state(state['numpy']);torch.set_rng_state(state['torch'].cpu());torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda']])

def bundle(tag):
    TR.check_lock();folder=O/f'seed_{SEED}';folder.mkdir(parents=True,exist_ok=True);step=MODEL.num_timesteps
    cp=folder/(f'step_{step:07d}_final.zip' if tag=='final' else f'step_{step:07d}.zip');MODEL.save(cp);MODEL.save_replay_buffer(folder/'final_replay_buffer.pkl')
    with (folder/'continuation_rng.pkl').open('wb') as f:pickle.dump(rng(),f)
    write('SAVED_BUNDLE.json',dict(tag=tag,step=step,updates=MODEL._n_updates,replay_size=MODEL.replay_buffer.size(),files={str(x):m.sha(x) for x in (cp,folder/'final_replay_buffer.pkl',folder/'continuation_rng.pkl')},optimizers=m.optimizer_hash(MODEL),callback_before_store=tag=='periodic',remaining_target_steps=TARGET-step))
    return cp

def path_artifact(record):
    trace=R/record['trace'];out=trace.parent/'hip_knee_path.npz'
    with np.load(trace) as z:
        keys=[k for k in z.files if k in ('time_s','stage','reference_q_rad','estimated_human_state_rad_rad_s','human_q_rad','physical_human_q_rad')]
        np.savez_compressed(out,**{k:z[k] for k in keys})
    record['hip_knee_path']=str(out.relative_to(R));record['hip_knee_path_sha256']=m.sha(out)
    write(f"PATH_step_{record['training_step']:07d}_{record['scope']}_{record['tag']}.json",dict(trace=record['trace'],trace_sha256=record['trace_sha256'],hip_knee_path=record['hip_knee_path'],hip_knee_path_sha256=record['hip_knee_path_sha256'],path_keys=keys))

def evaluate(model,step,scope,tag):
    global PHASE
    if not guard('before_'+tag+'_'+scope):raise ResourceStop('Unsafe before evaluation')
    saved_rng=rng();PHASE='evaluation'
    try:
        record=TR.evaluate(model,SEED,step,scope,tag);path_artifact(record);return record
    finally:restore(saved_rng);PHASE='training';gc.collect();full_sample('after_'+tag+'_'+scope)

def milestone(step):
    cp=bundle('periodic');write('STATE.json',dict(status='DETERMINISTIC_EVALUATION',step=step,target=TARGET))
    selected=[]
    for scope in ('NATIVE','MATCHED'):
        old=TR.BEST.get(scope);row=evaluate(MODEL,step,scope,'periodic')
        if row['valid'] and (old is None or row['J_F']<old['J_F']):selected.append((scope,row))
    for scope,row in selected:
        state=rng();opt=m.optimizer_hash(MODEL);size=MODEL.replay_buffer.size();updates=MODEL._n_updates
        try:
            independent=SAC.load(cp,device='cuda')
            from stable_baselines3.common.buffers import ReplayBuffer
            independent.replay_buffer=ReplayBuffer(1,independent.observation_space,independent.action_space,device='cuda',handle_timeout_termination=False)
            records=[evaluate(independent,step,scope,f'confirmation_{i+1}') for i in range(2)]
            passed=all(r['valid'] and abs(r['J_F']-row['J_F'])<=1e-6 and abs(r['force_peak']-row['force_peak'])<=1e-6 and abs(r['moment_peak']-row['moment_peak'])<=1e-6 and abs(r['duration_s']-row['duration_s'])<=1e-9 for r in records)
            confirmation=dict(pass_=passed,selected=row,replays=records,J_F_tolerance=1e-6,independent_checkpoint_reload=True)
            write(f'CONFIRMATION_step_{step:07d}_{scope}.json',confirmation)
            if passed and (scope not in CONFIRMED or row['J_F']<CONFIRMED[scope]['selected']['J_F']):CONFIRMED[scope]=confirmation
            write('BEST_CONFIRMED.json',CONFIRMED)
            del independent;gc.collect()
        finally:restore(state)
        assert m.optimizer_hash(MODEL)==opt and MODEL.replay_buffer.size()==size and MODEL._n_updates==updates
    if not guard('after_milestone_'+str(step)):raise ResourceStop('Resource pressure after evaluation')
    report('TRAINING')

def report(status):
    wall=time.monotonic()-T0;step=MODEL.num_timesteps if MODEL else START_STEP
    summary=dict(status=status,memory_qualification='SAC_MEMORY_QUALIFIED',start_step=START_STEP,total_steps=step,target_steps=TARGET,wall_s=wall,steps_s=(step-START_STEP)/max(wall,1),episodes=CB.episodes if CB else 0,resets=ENV.episode_index if ENV else 0,stop_reason=CB.stop_reason if CB else None,error=ERROR,best_confirmed=CONFIRMED,max_tree_pss_bytes=MAX_TREE,scientific_changes=[],side_study_started=False,planned_evaluations=list(range(50000,TARGET+1,25000)))
    write('CONTINUATION_RESULT.json',summary)
    rows=[] if TR is None else TR.EVAL_ROWS
    lines=['# SAC Seed 1 continuation v1','',f'Status: {status}. Total steps: {step}; continuation wall {wall/3600:.3f} h; effective {summary["steps_s"]:.3f} steps/s.','', 'Memory qualification passed at 30k: startup and evaluation high-water allocations, no sustained leak/swap; replay stays 100000 transitions (46,000,000 bytes). Windows Available alone is not a leak indicator. Long-run observations are in RESOURCE_WATCH.jsonl and MEMORY_SAMPLES.jsonl. Resources take priority; no RAM/swap expansion or other heavy experiment.','', 'Same checkpoint, replay, Adam optimizer, entropy state, fixed normalization and RNG restored. Cold physical reset only. R2 scientific contract and source hashes remain unchanged. The latest user instruction extends orchestration to 300k total, superseding the earlier stop-at-30k and historical orchestration wall budget; no seed 2 and no automatic steps beyond 300k.','',f'Stop reason: {summary["stop_reason"]}; error: {ERROR}.','', '|Step|Scope|Tag|VALID|J_F|F peak|M peak|Duration|Interventions|','|---:|---|---|---|---:|---:|---:|---:|---:|']
    for r in rows:lines.append(f'|{r["training_step"]}|{r["scope"]}|{r["tag"]}|{r["valid"]}|{r["J_F"]:.6f}|{r["force_peak"]:.6f}|{r["moment_peak"]:.6f}|{r["duration_s"]:.6f}|{r["rejections"]}|')
    lines+=['','Only VALID and independently replay-confirmed candidates can be ranked. Invalid timeout costs never enter best-candidate comparisons. Deterministic repeats are reproducibility evidence, not human-population robustness. Every evaluation retains full physics trace, raw actions and hip/knee path. Training episodes retain compact action evidence and learning curve.','', 'Prior comparator values and memory accounting remain in the preserved R2 and SAC_MEMORY_REPORT_V1 reports. No reward, action, observation, normalization, safety, physical task, policy period, training hyperparameter or buffer-capacity change. No Git stage/commit/push.','', 'Next: continue the same state only if stopped for a temporary resource condition and separately authorized; at 300k report learning trend and recommend any extension, never run it automatically.']
    for folder in (D,LOCAL):(folder/'SAC_SEED1_CONTINUATION_REPORT_V1.md').write_text('\n'.join(lines)+'\n')

def run():
    global MODEL,ENV,CB,TR,WATCH,ERROR,PHASE,np,torch,SAC
    D.mkdir(parents=True,exist_ok=False);O.mkdir(parents=True,exist_ok=False);P.mkdir(parents=True,exist_ok=False);LOCAL.mkdir(parents=True,exist_ok=True)
    m.D=D;m.O=O;m.LOCAL=LOCAL;m.START=START;m.START_STEP=START_STEP;m.T0=T0;m.write=memory_write
    pre=m.snapshot();write('PRESERVATION_BEFORE.json',pre)
    shutil.copy2(Path(__file__),P/'continue_seed1_v1.py')
    manifest=json.loads((W/'single_human_sac_memory/output/SAVED_BUNDLE_VERIFICATION.json').read_text())
    for name,h in manifest['bundle_sha256'].items():assert m.sha(START/name)==h,(name,'changed')
    qualification=json.loads((W/'single_human_sac_memory/output/SAC_MEMORY_RESULT.json').read_text());assert qualification['status']=='SAC_MEMORY_QUALIFIED' and not qualification['leak_observed']
    plan=dict(version=NAME,authorized_target=TARGET,seed=SEED,start_step=START_STEP,start_updates=24997,start_replay_size=29997,scientific_contract='R2 unchanged',milestones=list(range(50000,TARGET+1,25000)),independent_best_confirmation_replays=2,resource_priority=True,no_side_study=True,no_seed2=True,no_steps_beyond_target=True,guard=dict(wsl_available_gib=1.5,windows_commit_headroom_gib=2,new_swap_stop_mib=16,sustained_swap_samples=4,persistent_training_tree_budget_gib=4.5,growth_detection='After55k: >128MiB/hour for three hourly checks AND >512MiB cumulative anonymous growth; preserve and stop'),logging='append resource rows; bounded trend retention; no full training physics trace retention',historical_wall_budget='Latest explicit300k instruction supersedes prior orchestration budget; scientific contract files remain byte-identical')
    write('CONTINUATION_PLAN.json',plan);write('STATE.json',dict(status='STARTUP_RESOURCE_GATE',step=START_STEP,target=TARGET))
    for name in ('SAC_CONTRACT_LOCK.json','SAC_EXPERT_V1_CONTRACT.json','SAC_OBSERVATION_NORMALIZATION.json','SAC_TRAINING_CONFIG.json'):
        shutil.copy2(START/name,D/name)
    quiet=None;deadline=time.monotonic()+600
    while True:
        row=full_sample('startup_host_gate')
        healthy=row['safe'] and not row['windows']['ExternalVideoRender'] and row['windows']['CommitLimit']-row['windows']['CommittedBytes']>=5*2**30 and row['windows']['AvailableBytes']>=2*2**30 and row['swap_used_bytes']==0
        if healthy:
            if quiet is None:quiet=time.monotonic()
            if time.monotonic()-quiet>=120:break
        else:quiet=None
        if time.monotonic()>deadline:write('STATE.json',dict(status='RESOURCE_STOP_BEFORE_TRAINING',step=START_STEP));report('RESOURCE_STOP_BEFORE_TRAINING');return
        time.sleep(30)
    sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'));sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1_r2'))
    import train_campaign_r2 as tr;TR=tr
    import campaign_r2 as c,qualify as q,final_qualification as f
    import numpy as np
    import torch
    from stable_baselines3 import SAC
    for module in (q,f,tr):module.D=D;module.O=O
    tr.metric_record=c.metric;tr.CURRENT_LOCK=json.loads((OLD/'SAC_CONTRACT_LOCK.json').read_text());tr.check_lock()
    original_env=tr.SACExpertEnv
    class EvaluationEnv(original_env):
        def step(self,action):
            with WATCH_LOCK:pressure=PRESSURE
            if pressure and pressure['stop_reasons']:raise ResourceStop('Evaluation resource pressure: '+str(pressure['stop_reasons']))
            return super().step(action)
    tr.SACExpertEnv=EvaluationEnv
    MODEL=SAC.load(START/'step_0030000.zip',device='cuda');assert MODEL.num_timesteps==30000 and MODEL._n_updates==24997
    expected=json.loads((W/'single_human_sac_memory/output/attempt5/FINAL_STATE.json').read_text())['optimizers'];assert m.optimizer_hash(MODEL)==expected
    MODEL.load_replay_buffer(START/'final_replay_buffer.pkl');assert MODEL.replay_buffer.size()==29997
    m.MODEL=MODEL;rb=m.replay();assert rb['allocated_array_bytes']==46000000 and rb['buffer_size']==100000 and rb['bytes_per_transition']==460
    write('REPLAY_ACCOUNTING.json',rb)
    case,options=tr.load_case_options();ENV=original_env(O/f'seed_{SEED}/training',case,options,.02,retain_trace=False);MODEL.set_env(ENV,force_reset=True)
    assert m.optimizer_hash(MODEL)==expected
    with (START/'continuation_rng.pkl').open('rb') as h:restore(pickle.load(h))
    write('RESUME_VERIFICATION.json',dict(step=MODEL.num_timesteps,updates=MODEL._n_updates,replay_size=MODEL.replay_buffer.size(),optimizers=expected,rng_restored=True,reset_num_timesteps=False,normalization_sha256=m.sha(D/'SAC_OBSERVATION_NORMALIZATION.json'),source_lock_pass=True))
    folder=O/f'seed_{SEED}';folder.mkdir(parents=True,exist_ok=True)
    for name in ('SAC_CONTRACT_LOCK.json','SAC_EXPERT_V1_CONTRACT.json','SAC_OBSERVATION_NORMALIZATION.json','SAC_TRAINING_CONFIG.json'):shutil.copy2(START/name,folder/name)
    class Callback(tr.BaseCallback):
        def __init__(self):
            super().__init__();self.begin=time.monotonic();self.segment_step=START_STEP;self.segment_start=self.begin;self.episodes=0;self.stop_reason=None;self.last_probe=self.begin;self.last_state=START_STEP
        def _on_training_start(self):
            if not guard('after_initial_reset'):raise ResourceStop('Startup after reset')
        def _on_step(self):
            step=self.model.num_timesteps;info=self.locals['infos'][0];elapsed=time.monotonic()-self.begin
            assert info.get('model_hash')==tr.CURRENT_LOCK['frozen_model_hash']
            with WATCH_LOCK:pressure=PRESSURE
            if time.monotonic()-self.last_probe>=60 or (pressure and pressure['stop_reasons']):
                self.last_probe=time.monotonic()
                if not guard('formal_resource_guard'):self.stop_reason='RESOURCE_RISK';return False
            if self.locals['dones'][0]:
                self.episodes+=1
                keys=('success','status','abort_reason','J_F','reward_total','force_peak','moment_peak','duration_s','rejections','steps','host_s','minimum_clearance_m','physical_rom_violation_steps_evaluation_only','physical_contact_steps_evaluation_only','fallbacks','action_evidence','reward_totals','physical_success_rank')
                row={k:info.get(k) for k in keys};row.update(seed=SEED,training_step=step,episode=self.episodes,wall_s=elapsed,steps_s=(step-START_STEP)/max(elapsed,1),independent_physical_rank=False)
                tr.LEARNING_ROWS.append(row);tr.table('SAC_LEARNING_CURVE.csv',tr.LEARNING_ROWS)
            if step-self.last_state>=500:
                self.last_state=step;tr.check_lock();losses={k:float(v) for k,v in self.model.logger.name_to_value.items() if k.startswith('train/') and np.isscalar(v)}
                if any(not np.isfinite(v) for v in losses.values()) or any(not torch.isfinite(p).all().item() for p in self.model.policy.parameters()):self.stop_reason='NAN_OR_NONFINITE_PARAMETERS';return False
                write('STATE.json',dict(status='FORMAL_SEED1_TRAINING',step=step,target=TARGET,elapsed_s=elapsed,steps_s=(step-START_STEP)/elapsed,episodes=self.episodes,losses=losses))
                print(json.dumps(dict(status='TRAINING',step=step,steps_s=(step-START_STEP)/elapsed,episodes=self.episodes)),flush=True)
            if step in range(50000,TARGET+1,25000):milestone(step)
            return True
    CB=Callback();m.CB=CB;m.MODEL=MODEL;m.ENV=ENV;m.TR=tr
    WATCH=threading.Thread(target=watch,name='resource_observer',daemon=True);WATCH.start();PHASE='training'
    try:MODEL.learn(total_timesteps=TARGET-START_STEP,reset_num_timesteps=False,callback=CB)
    except ResourceStop as ex:CB.stop_reason='RESOURCE_RISK';ERROR=dict(error=str(ex),traceback=traceback.format_exc());write('RESOURCE_STOP_EXCEPTION.json',ERROR)
    except Exception as ex:CB.stop_reason='EXCEPTION';ERROR=dict(error=str(ex),traceback=traceback.format_exc());write('EXCEPTION.json',ERROR)
    finally:
        PHASE='saving';bundle('final');ENV.close();WATCH_END.set();WATCH.join(timeout=35);gc.collect();full_sample('closed_final')
    tr.check_lock();fail=[p for p,h in pre['files'].items() if not (R/p).exists() or m.sha(R/p)!=h];assert not fail,fail
    assert subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)==pre['index']
    write('PRESERVATION_AFTER.json',dict(pass_=True,files_checked=len(pre['files']),head_unchanged=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pre['head'],index_unchanged=True,scientific_lock_pass=True))
    terminal='SAC_SEED1_300K_COMPLETE' if MODEL.num_timesteps==TARGET and CB.stop_reason is None else 'SAC_SEED1_SAVED_STOP'
    write('STATE.json',dict(status=terminal,step=MODEL.num_timesteps,target=TARGET,stop_reason=CB.stop_reason,error=ERROR));report(terminal)
    print(terminal,flush=True)

if __name__=='__main__':run()
