"""Autonomous diagnostic replay. No teacher dataset opened in this process."""
from common import *
import gzip, shutil
def run(seed):
    lock();resources('REPLAY_'+str(seed));checkpoint=W/'bc_reproduction_gate_v1/output'/f'actor_seed_{seed}.pt'
    a=actor(seed);ck=torch.load(checkpoint,map_location='cpu',weights_only=True);a.load_state_dict(ck['state_dict']);a.eval()
    native=S/'results'/NAME
    if not native.exists():native.symlink_to(O,target_is_directory=True)
    case,options=load_case_options();env=SACExpertEnv(native/f'diagnostic_seed_{seed}',case,options,.02,'NATIVE',True)
    obslist=[];actions=[];executed=[];times=[];phases=[];statuses=[]
    try:
        obs,info=env.reset(seed=20261003)
        for i in range(1600):
            act,_=a.predict(obs,deterministic=True)
            obslist.append(obs.copy());actions.append(act.copy());times.append(info['physics_task_s']);phases.append(info['phase'])
            obs,reward,term,trunc,info=env.step(act);executed.append(env.last_row['executed']);statuses.append(env.last_row['status'])
            if (i+1)%250==0:print(json.dumps(dict(seed=seed,steps=i+1,task_s=times[-1],phase=phases[-1])),flush=True)
            if term or trunc:break
        assert term or trunc
        np.savez_compressed(O/f'POLICY_seed_{seed}.npz',observations=np.array(obslist),raw_actions=np.array(actions),executed_actions=np.array(executed),task_s=np.array(times),phase=np.array(phases),status=np.array(statuses))
        metric=r2.metric(env,f'DIAGNOSTIC_BC_{seed}','NATIVE');metric.pop('raw_actions')
        t=task_trace(env.episode_dir);q=t['estimated_human_state_rad_rad_s'][:,:2];dq=t['estimated_human_state_rad_rad_s'][:,2:];start=t['time_s'][0]
        transitions=env.summary['task']['phase_transitions'];pt={r['to']:r['time_s']-start for r in transitions};out=t['time_s']<=start+pt.get('HOLD',1e9)
        progress=np.min(np.clip((q-np.radians([5,10]))/np.radians([115,110]),0,1),axis=1)
        detail=dict(max_synchronized_progress=np.max(progress[out]),settled_arrival='HOLD' in pt,HOLD_entry_s=pt.get('HOLD'),HOLD_completed='RETURN' in pt,RETURN_entry_s=pt.get('RETURN'),RETURN_completed='COMPLETE' in pt,COMPLETE_s=pt.get('COMPLETE'),VALID=metric['valid'],termination=env.summary.get('abort_reason') or env.summary['status'],final_q_deg=np.degrees(q[-1]),final_dq_deg_s=np.degrees(dq[-1]))
        save(f'CLOSED_LOOP_seed_{seed}.json',dict(seed=seed,category='DIAGNOSTIC_NOT_OLD_GATE',metric=metric,endpoints=detail,checkpoint_sha256=sha(checkpoint),steps=len(actions),terminated=term,truncated=trunc,episode_dir=env.episode_dir,teacher_reads_during_rollout=0,teacher_overrides=0,truth_actor_inputs=False))
        path=env.episode_dir/'runtime_artifacts.json'
        if path.exists():
            h=sha(path)
            with path.open('rb') as src,gzip.open(str(path)+'.gz','wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
            with gzip.open(str(path)+'.gz','rb') as f:assert hashlib.sha256(f.read()).hexdigest()==h
            path.unlink()
        lock();print(json.dumps(clean(dict(seed=seed,**detail))),flush=True)
    finally:env.close()
if __name__=='__main__':run(int(sys.argv[1]))
