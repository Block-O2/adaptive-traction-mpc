"""Memory-only continuation: immutable R2, 12194 -> 30000, no capacity change."""
from pathlib import Path
import os,sys,time,json,hashlib,subprocess,base64,gc,threading,traceback,pickle,random
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1/source')
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/single_human_sac_memory_v1/attempt5'; O=S/'results/single_human_sac_memory_v1/attempt5'
OLD=S/'docs/single_human_sac_expert_v1/r2'
ORIGINAL=S/'results/single_human_sac_expert_v1_r2/seed_20261003'
START=S/'results/single_human_sac_memory_v1/attempt4/seed_20261003'
START_STEP=13169
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_memory/output/attempt5')
T0=time.monotonic();MODEL=None;ENV=None;CB=None;SAMPLES=[];SWAP0=None
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):
    text=json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n'
    (D/name).write_text(text);(LOCAL/name).write_text(text)
def memfile(path):
    return {k:int(v.split()[0])*1024 for k,v in (l.split(':',1) for l in Path(path).read_text().splitlines() if ':' in l) if v.strip().split()[0].isdigit()}
def processes():
    rows=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            st={k:v.strip() for k,v in (l.split(':',1) for l in (p/'status').read_text().splitlines())}
            rows.append(dict(pid=int(p.name),ppid=int(st['PPid']),name=st['Name'],state=st['State'],rss=int(st.get('VmRSS','0 kB').split()[0])*1024,cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    owned={os.getpid()}
    while True:
        new=owned|{r['pid'] for r in rows if r['ppid'] in owned}
        if new==owned:break
        owned=new
    ours=[]
    for row in rows:
        if row['pid'] in owned:
            try:row.update(memfile(f"/proc/{row['pid']}/smaps_rollup"))
            except (FileNotFoundError,ProcessLookupError,PermissionError):pass
            ours.append(row)
    others=[r for r in rows if r['pid'] not in owned and 'python' in r['cmd'] and r['rss']>=256*2**20 and 'conda shell' not in r['cmd']]
    ours.sort(key=lambda row:(row['pid']!=os.getpid(),row['pid']))
    return dict(owned=ours,owned_count=len(ours),system_count=len(rows),zombies=[r for r in rows if r['state'].startswith('Z')],other_heavy_python=others)
PS="""$ProgressPreference='SilentlyContinue'; $m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; $o=Get-CimInstance Win32_OperatingSystem; $v=Get-Process -Name vmmemWSL -ErrorAction SilentlyContinue; $r=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'manim|sac_video.*build.py'} | Select-Object ProcessId,CommandLine); [pscustomobject]@{AvailableBytes=[int64]$m.AvailableBytes;CommittedBytes=[int64]$m.CommittedBytes;CommitLimit=[int64]$m.CommitLimit;TotalRAMBytes=([int64]$o.TotalVisibleMemorySize*1024);VmmemWorkingSetBytes=[int64]$v.WorkingSet64;VmmemPrivateBytes=[int64]$v.PrivateMemorySize64;ProcessCount=(Get-Process).Count;ExternalVideoRender=$r} | ConvertTo-Json -Depth 4 -Compress"""
def windows():
    s=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(PS.encode('utf-16le')).decode()],text=True,timeout=30)
    return json.loads(s.strip())
def replay():
    if MODEL is None or MODEL.replay_buffer is None:return None
    b=MODEL.replay_buffer; arrays={k:dict(shape=list(v.shape),dtype=str(v.dtype),nbytes=v.nbytes) for k,v in vars(b).items() if hasattr(v,'nbytes') and hasattr(v,'shape')}
    allocated=sum(v['nbytes'] for v in arrays.values()); per=allocated/(b.buffer_size*b.n_envs)
    return dict(buffer_size=b.buffer_size,n_envs=b.n_envs,pos=b.pos,full=b.full,size=b.size(),optimize_memory_usage=b.optimize_memory_usage,handle_timeout_termination=b.handle_timeout_termination,arrays=arrays,allocated_array_bytes=allocated,used_payload_bytes=int(b.size()*b.n_envs*per),bytes_per_transition=per,theory={str(n):dict(uncapped_payload_bytes=int(n*per),current_capacity_payload_bytes=int(min(n,b.buffer_size*b.n_envs)*per),current_capacity_allocation_bytes=allocated) for n in (30000,100000,300000,500000,1000000)})
def sample(tag):
    global SWAP0
    w=windows();m=memfile('/proc/meminfo');p=processes();vm={k:int(v) for k,v in (l.split() for l in Path('/proc/vmstat').read_text().splitlines())}
    swap=m['SwapTotal']-m['SwapFree']
    if SWAP0 is None:SWAP0=swap
    gpu=None
    if 'torch' in sys.modules and sys.modules['torch'].cuda.is_initialized():
        t=sys.modules['torch'];gpu=dict(allocated=t.cuda.memory_allocated(),reserved=t.cuda.memory_reserved(),max_allocated=t.cuda.max_memory_allocated(),max_reserved=t.cuda.max_memory_reserved())
    reasons=[]
    if m['MemAvailable']<int(1.5*2**30):reasons.append('WSL_AVAILABLE_BELOW_1_5_GIB')
    if w['CommitLimit']-w['CommittedBytes']<2*2**30:reasons.append('WINDOWS_COMMIT_HEADROOM_BELOW_2_GIB')
    if swap-SWAP0>128*2**20:reasons.append('NEW_WSL_SWAP_OVER_128_MIB')
    if w['AvailableBytes']<256*2**20 and m['MemAvailable']<2*2**30:reasons.append('JOINT_HOST_GUEST_LOW_MEMORY')
    if p['other_heavy_python']:reasons.append('OTHER_HEAVY_PYTHON')
    row=dict(tag=tag,unix=time.time(),elapsed_s=time.monotonic()-T0,step=MODEL.num_timesteps if MODEL else None,updates=MODEL._n_updates if MODEL else None,windows=w,wsl=m,swap_used_bytes=swap,vmstat_swap_pages={k:vm[k] for k in ('pswpin','pswpout')},memory_pressure=Path('/proc/pressure/memory').read_text(),processes=p,torch_gpu=gpu,nvidia_smi=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),replay=replay(),thread_names=[t.name for t in threading.enumerate()],episodes=CB.episodes if CB else 0,training_resets=ENV.episode_index if ENV else 0,learning_log_rows=len(TR.LEARNING_ROWS) if 'TR' in globals() else 0,evaluation_rows=len(TR.EVAL_ROWS) if 'TR' in globals() else 0,safe=not reasons,stop_reasons=reasons)
    if CB:row.update(continuation_steps_s=(MODEL.num_timesteps-START_STEP)/(time.monotonic()-CB.begin),segment_steps_s=(MODEL.num_timesteps-CB.segment_step)/(time.monotonic()-CB.segment_start))
    row['gc']=dict(enabled=gc.isenabled(),counts=list(gc.get_count()),callbacks=len(gc.callbacks))
    if ENV:row['episode_retained_records']=dict(actions=len(ENV.action_records),runtime=len(ENV.runtime_records),capture_keys=list(ENV.capture))
    SAMPLES.append(row);write('MEMORY_SAMPLES.json',SAMPLES);write('LATEST.json',row)
    print(json.dumps(dict(tag=tag,step=row['step'],main_rss_mib=p['owned'][0].get('Rss',0)/2**20,main_pss_mib=p['owned'][0].get('Pss',0)/2**20,owned=p['owned_count'],episodes=row['episodes'],resets=row['training_resets'],windows_available_gib=w['AvailableBytes']/2**30,wsl_available_gib=m['MemAvailable']/2**30,commit_headroom_gib=(w['CommitLimit']-w['CommittedBytes'])/2**30,safe=row['safe'])),flush=True)
    return row
def optimizer_hash(model):
    import torch
    def digest(value,h):
        if isinstance(value,torch.Tensor):h.update(str((value.dtype,tuple(value.shape))).encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
        elif isinstance(value,dict):
            for k in sorted(value,key=str):h.update(str(k).encode());digest(value[k],h)
        elif isinstance(value,(list,tuple)):
            for v in value:digest(v,h)
        else:h.update(repr(value).encode())
    out={}
    for name,obj in [('actor',model.actor.optimizer),('critic',model.critic.optimizer),('entropy',model.ent_coef_optimizer)]:
        h=hashlib.sha256();digest(obj.state_dict(),h);out[name]=dict(sha256=h.hexdigest(),state_count=len(obj.state),steps=sorted(set(float(v['step']) for v in obj.state.values())))
    return out
def snapshot():
    index=subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0')
    dirty=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=R).decode().split('\0')
    files={p:sha(R/p) for p in tracked+dirty if p and (R/p).is_file()}
    for folder in (START,ORIGINAL):
        for path in folder.iterdir():
            if path.is_file():files[str(path.relative_to(R))]=sha(path)
    return dict(branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip(),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),status=subprocess.check_output(['git','status','--short'],cwd=R,text=True),index=index,files=files)
def run():
    global MODEL,ENV,CB,TR
    D.mkdir(parents=True,exist_ok=False);O.mkdir(parents=True,exist_ok=False);LOCAL.mkdir(parents=True,exist_ok=True)
    pre=snapshot();write('PRESERVATION_BEFORE.json',pre)
    write('STATE.json',dict(status='MEMORY_ACCOUNTING',start_step=START_STEP,original_start_step=12194,target_step=30000,started_unix=time.time()))
    policy=dict(version='SAC_MEMORY_POLICY_V1',scope='memory diagnostics only',buffer_capacity_change=False,scientific_changes=[],milestones=[15000,20000,25000,30000],guard=['WSL MemAvailable >=1.5 GiB','Windows commit headroom >=2 GiB','new WSL swap <=128 MiB','STOP joint Windows Available <256 MiB and WSL MemAvailable <2 GiB','no other heavy Python simulation'],startup_pressure='park before updates for at most60 seconds, 10-second rechecks, then preserve/STOP if still unsafe',windows_available_alone='warning, not a leak or pressure diagnosis',resource_configuration_unchanged=True,wall_cap_hours=6,evaluation='original deterministic NATIVE and MATCHED at25k plus final30k; learning frozen',stop_after_target=True)
    policy['version']='SAC_MEMORY_POLICY_V2'
    policy['external_workload_gate']='Wait for120 seconds without observed existing Windows video render and commit headroom>=5 GiB before CUDA warm-up; do not stop or modify unrelated workload.'
    policy['transient_pressure']='Park scientific simulation collection at a policy boundary without advancing physics, recheck10 seconds, at most120 seconds; require two safe samples before continuing. Stop immediately if commit headroom<512MiB, WSL available<1GiB, new swap>128MiB or another heavy simulation; preserve/STOP if pressure persists. No GPU cache dropping or RAM/swap expansion.'
    write('RESOURCE_POLICY_V1.json',policy)
    deadline=time.monotonic()+40*60;quiet_since=None
    while True:
        row=sample('waiting_external_host_load')
        if not row['windows']['ExternalVideoRender'] and row['windows']['CommitLimit']-row['windows']['CommittedBytes']>=5*2**30:
            if quiet_since is None:quiet_since=time.monotonic()
            if time.monotonic()-quiet_since>=120:break
        else:quiet_since=None
        if time.monotonic()>deadline:
            write('STATE.json',dict(status='RESOURCE_WAIT',step=START_STEP,reason='External video rendering / commit headroom',next='preserve state; no heavy simulation'));return
        time.sleep(30)
    sample('before_imports')
    sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'));sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1_r2'))
    import train_campaign_r2 as tr;TR=tr
    import campaign_r2 as c,qualify as q,final_qualification as f
    import torch,numpy as np
    from stable_baselines3 import SAC
    sample('after_torch_mujoco_imports')
    q.D=D;q.O=O;f.D=D;f.O=O;tr.D=D;tr.O=O;tr.metric_record=c.metric
    tr.CURRENT_LOCK=json.loads((OLD/'SAC_CONTRACT_LOCK.json').read_text());tr.check_lock()
    MODEL=SAC.load(START/f'step_{START_STEP:07d}.zip',device='cuda')
    sample('after_checkpoint_optimizer_load')
    assert MODEL.num_timesteps==START_STEP and MODEL._n_updates==8166
    original_optimizer=optimizer_hash(MODEL)
    MODEL.load_replay_buffer(START/'final_replay_buffer.pkl')
    assert MODEL.replay_buffer.size()==13166  # Three pressure-stop callback transitions were never committed; preserve exactly.
    rb=replay();assert rb['buffer_size']==100000 and rb['n_envs']==1 and rb['bytes_per_transition']==460
    write('REPLAY_ACCOUNTING.json',rb)
    sample('after_replay_load')
    case,options=tr.load_case_options();ENV=tr.SACExpertEnv(O/'seed_20261003/training',case,options,.02,retain_trace=False)
    MODEL.set_env(ENV,force_reset=True)
    assert optimizer_hash(MODEL)==original_optimizer
    write('RESUME_VERIFICATION.json',dict(start_step=MODEL.num_timesteps,start_updates=MODEL._n_updates,optimizers=original_optimizer,replay=rb,normalization='original immutable fixed physical scale vector',checkpoint_sha256=sha(START/f'step_{START_STEP:07d}.zip'),replay_sha256=sha(START/'final_replay_buffer.pkl'),fresh_physical_episode=True,reset_num_timesteps=False,rng_note='original checkpoint did not save RNG state; subsequent pressure stop RNG restored below; no claim of exact uninterrupted original trajectory'))
    with (START/'continuation_rng.pkl').open('rb') as h:rng=pickle.load(h)
    random.setstate(rng['random']);np.random.set_state(rng['numpy']);torch.set_rng_state(rng['torch'].cpu());torch.cuda.set_rng_state_all([v.cpu() for v in rng['cuda']])
    def guard(tag):
        row=sample(tag)
        if row['safe']:return True
        safe_count=0
        for i in range(12):
            severe=(row['windows']['CommitLimit']-row['windows']['CommittedBytes']<512*2**20 or row['wsl']['MemAvailable']<2**30 or row['swap_used_bytes']-SWAP0>128*2**20 or row['processes']['other_heavy_python'])
            if severe:return False
            time.sleep(10);row=sample(tag+'_parked_recheck_'+str(i));safe_count=safe_count+1 if row['safe'] else 0
            if safe_count>=2:return True
        return False
    tr.resource_check=guard
    class Callback(tr.CampaignCallback):
        def __init__(self):
            super().__init__(20261003,time.time()+6*3600,json.loads((OLD/'SAC_TRAINING_CONFIG.json').read_text()));self.segment_step=START_STEP;self.segment_start=time.monotonic()
        def _on_training_start(self):
            assert guard('after_initial_reset'),'unsafe startup resources'
        def _on_step(self):
            step=self.model.num_timesteps
            if step==25000:sample('before_periodic_evaluations_25000')
            ok=super()._on_step()
            if step in (12197,12198,15000,20000,25000,30000):
                row=sample(f'milestone_{step}');self.segment_step=step;self.segment_start=time.monotonic()
                if not row['safe'] and not guard('milestone_pressure_recheck_'+str(step)):self.stop_reason='MEMORY_POLICY_STOP';return False
            return ok
    CB=Callback();error=None
    try:MODEL.learn(total_timesteps=30000-START_STEP,reset_num_timesteps=False,callback=CB)
    except Exception as ex:error=dict(error=str(ex),traceback=traceback.format_exc());write('EXCEPTION.json',error);print(error['traceback'],flush=True)
    finally:
        MODEL.save(O/f'seed_20261003/step_{MODEL.num_timesteps:07d}');MODEL.save_replay_buffer(O/'seed_20261003/final_replay_buffer.pkl');ENV.close()
        sample('after_training_close')
    if error is None and MODEL.num_timesteps==30000:
        for scope in ('NATIVE','MATCHED'):
            sample('before_final_eval_'+scope);tr.evaluate(MODEL,20261003,30000,scope,'memory_final');sample('after_final_eval_'+scope)
    gc.collect();sample('after_gc_closed')
    with (O/'seed_20261003/continuation_rng.pkl').open('wb') as h:pickle.dump(dict(random=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state_all()),h)
    final=optimizer_hash(MODEL);write('FINAL_STATE.json',dict(step=MODEL.num_timesteps,updates=MODEL._n_updates,episodes=CB.episodes,resets=ENV.episode_index,stop_reason=CB.stop_reason or 'BOUNDED_30000_COMPLETE',error=error,optimizers=final,checkpoint=str(O/f'seed_20261003/step_{MODEL.num_timesteps:07d}.zip'),replay=str(O/'seed_20261003/final_replay_buffer.pkl'),wall_s=time.monotonic()-CB.begin))
    tr.check_lock();fail=[p for p,h in pre['files'].items() if not (R/p).exists() or sha(R/p)!=h]
    assert not fail,fail
    assert subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)==pre['index']
    write('PRESERVATION_AFTER.json',dict(pass_=True,preexisting_files_checked=len(pre['files']),index_unchanged=True,head_unchanged=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==pre['head'],scientific_lock_pass=True))
    write('STATE.json',dict(status='BOUNDED_TEST_COMPLETE_PENDING_ANALYSIS' if MODEL.num_timesteps==30000 and not error else 'BOUNDED_TEST_STOP',step=MODEL.num_timesteps,error=error,next='analyze memory; no300k'))
    print('MEMORY_TEST_SAVED_STOP',flush=True)
if __name__=='__main__':run()
