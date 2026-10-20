"""Five short deterministic, frozen-R2 rollouts. No training/optimizer calls."""
from inventory_v1 import *
import time, shutil, traceback
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1'))
sys.path.insert(0,str(S/'scripts/single_human_sac_expert_v1_r2'))
import qualify as q, final_qualification as f, campaign_r2 as c
from sac_env import SACExpertEnv,load_case_options
import torch
from stable_baselines3 import SAC
torch.set_num_threads(1)
LOCK=json.loads((S/'docs/single_human_sac_expert_v1/r2/SAC_CONTRACT_LOCK.json').read_text())
def guard():
    spec=importlib.util.spec_from_file_location('m',W/'single_human_sac_memory/memory_test_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    mem=m.memfile('/proc/meminfo');win=m.windows();procs=m.processes()
    row=dict(unix=time.time(),wsl=mem,windows=win,processes=procs)
    with (D/'DIAGNOSTIC_RESOURCE_SAMPLES.jsonl').open('a') as h:h.write(json.dumps(row)+'\n')
    assert mem['MemAvailable']>=1.5*2**30 and win['CommitLimit']-win['CommittedBytes']>=2*2**30, 'memory risk'
    assert mem['SwapTotal']==mem['SwapFree'], 'swap used; stop diagnostic'
    assert not procs['other_heavy_python'] and not win['ExternalVideoRender'], 'other heavy experiment'
    for p,h in LOCK['files'].items():assert sha(R/p)==h, 'R2 source/contract changed:'+p
def rollout(name,scope,model=None):
    guard();case,options=load_case_options();env=SACExpertEnv(O/'diagnostic_rollouts'/f'{name}_{scope}',case,options,.02,scope,True)
    data=[];result=None;start=time.monotonic()
    try:
        obs,info=env.reset(seed=20261003);initial=obs.copy();assert env.model_hash==LOCK['frozen_model_hash']
        for i in range(1600):
            if i and i%100==0:guard()
            previous=obs.copy();previous_phase=info['phase'];previous_t=info['physics_task_s']
            if model is None:action=q.policy(name,env,obs,info)
            else:
                with torch.no_grad():action,_=model.predict(obs,deterministic=True)
            obs,reward,term,trunc,info=env.step(action)
            data.append(dict(obs=previous,next_obs=obs.copy(),action=np.asarray(action).copy(),reward=reward,terminated=term,truncated=trunc,phase=previous_phase,task_s=previous_t,parts=info['reward_decomposition']))
            if term or trunc:break
        assert env.summary is not None, 'No terminal outcome within immutable30s task'
        metric=c.metric(env,name,scope)
        result=dict(name=name,scope=scope,status=env.summary['status'],abort_reason=env.summary.get('abort_reason'),valid=metric['valid'],metric=metric,terminal_info=info,reward_total=env.reward_total,reward_totals=env.reward_parts,initial_observation=initial.tolist(),frozen_model_hash=env.model_hash,host_s=time.monotonic()-start,training_steps=0,optimizer_updates=0,wrapper='unmodified sac_env.SACExpertEnv .02s + campaign_r2.metric (same as formal tr.evaluate)',policy='unchanged qualify.policy fixed_hip_lead or diagnostic adversary' if model is None else 'exact saved300k periodic deterministic SAC',independent_physical_audit=metric['physical_audit'])
        np.savez_compressed(env.episode_dir/'DIAGNOSTIC_TRANSITIONS.npz',observations=np.asarray([r['obs'] for r in data]),next_observations=np.asarray([r['next_obs'] for r in data]),actions=np.asarray([r['action'] for r in data]),rewards=np.asarray([r['reward'] for r in data]),terminated=np.asarray([r['terminated'] for r in data]),truncated=np.asarray([r['truncated'] for r in data]),phase=np.asarray([r['phase'] for r in data]),task_s=np.asarray([r['task_s'] for r in data]),**{'reward_'+k:np.asarray([r['parts'][k] for r in data]) for k in ('force','shaping','completion','failure','rejection')})
        result['transition_archive']=str((env.episode_dir/'DIAGNOSTIC_TRANSITIONS.npz').relative_to(R))
        save(f'DIAGNOSTIC_{name}_{scope}.json',result)
        print(json.dumps({k:result[k] for k in ('name','scope','status','abort_reason','valid','reward_total','reward_totals','host_s')}),flush=True)
    finally:
        f.compact_archive(env);env.close()
    return result
def run():
    for module in (q,f):module.D=D;module.O=O
    save('DIAGNOSTIC_STATE.json',dict(status='DIAGNOSTIC_ROLLOUTS',training_steps=0,source_changes=[]))
    completed=[]
    for scope in ('NATIVE','MATCHED'):completed.append(rollout('fixed_hip_lead',scope))
    if not completed[0]['valid']:completed.append(rollout('reference','NATIVE'))
    cp=S/'results/single_human_sac_seed1_continuation_v2_guardfix_attempt3/seed_20261003/step_0300000.zip'
    guard();model=SAC.load(cp,device='cuda');model.policy.set_training_mode(False)
    updates=model._n_updates;before={k:sha(cp) for k in ['checkpoint']}
    r=rollout('SAC300k','NATIVE',model);completed.append(r)
    assert model._n_updates==updates and sha(cp)==before['checkpoint'];del model
    for name in ('early_failure','no_motion'):completed.append(rollout(name,'NATIVE'))
    assert len(completed)<=6
    save('DIAGNOSTIC_STATE.json',dict(status='ROLLOUTS_COMPLETE',completed=len(completed),training_steps=0,source_changes=[],optimizer_updates=0))
    shutil.copy2(Path(__file__),P/Path(__file__).name)
if __name__=='__main__':
    try:run()
    except Exception as e:
        save(f'DIAGNOSTIC_EXCEPTION_{time.time_ns()}.json',dict(error=str(e),traceback=traceback.format_exc(),training_steps=0));raise
