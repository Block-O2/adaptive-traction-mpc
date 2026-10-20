"""Standalone autonomous evaluation: never opens teacher data or teacher actions."""
from common import *

def run(seed,tag='formal'):
    lock=check_lock(); spec=read('PREREGISTRATION.json'); offline=read('OFFLINE_RESULTS.json')
    assert len(offline)==3 and all(r['offline_pass'] for r in offline), 'OFFLINE_GATE_CLOSED'
    resource(f'EVAL_{seed}_{tag}')
    record=next(r for r in offline if r['seed']==seed); checkpoint=Path(record['checkpoint'])
    assert sha(checkpoint)==record['checkpoint_sha256']
    actor=make_actor(seed); ckpt=torch.load(checkpoint,map_location='cpu',weights_only=True)
    actor.load_state_dict(ckpt['state_dict']); actor.eval()
    assert ckpt['critic_exists'] is False and ckpt['inherited_weights'] is False
    case,options=load_case_options(); env=SACExpertEnv(O/f'eval_seed_{seed}_{tag}',case,options,.02,'NATIVE',True)
    observations=[];actions=[];phases=[];times=[];executed=[];statuses=[];latencies=[]
    try:
        obs,info=env.reset(seed=spec['initial_condition_seed'])
        assert env.model_hash==lock['frozen_model_hash']
        init=obs.copy(); initial={'estimated_state':obs[:4]*SCALES[:4],'reference':obs[4:6]*SCALES[4:6]}
        for i in range(1600):
            start=time.perf_counter_ns(); action,_=actor.predict(obs,deterministic=True)
            latencies.append((time.perf_counter_ns()-start)/1e6)
            assert np.isfinite(action).all() and action.shape==(2,)
            observations.append(obs.copy()); actions.append(action.copy());phases.append(info['phase']);times.append(info['physics_task_s'])
            obs,reward,term,trunc,info=env.step(action)
            executed.append(env.last_row['executed']);statuses.append(env.last_row['status'])
            if (i+1)%250==0: print(json.dumps(dict(seed=seed,tag=tag,steps=i+1,task_s=times[-1],phase=phases[-1])),flush=True)
            if term or trunc: break
        assert term or trunc, 'R2_GLOBAL_TIMEOUT_DID_NOT_TERMINATE'
        assert sum(t.name=='single-CPU-MuJoCo-owner' for t in __import__('threading').enumerate())<=1
        metric=r2.metric(env,f'BC_seed_{seed}_{tag}','NATIVE'); metric.pop('raw_actions')
        transitions=env.summary['task']['phase_transitions']
        with np.load(env.episode_dir/'trace.npz') as trace:
            mask=trace['stage']=='TASK'; tt=trace['time_s'][mask]; t0=float(tt[0])
            q=trace['estimated_human_state_rad_rad_s'][mask,:2]; dq=trace['estimated_human_state_rad_rad_s'][mask,2:4]
            ref=trace['reference_q_rad'][mask]; tracking=q-ref
            physical_q=trace['physical_human_state_rad_rad_s'][mask,:2] if 'physical_human_state_rad_rad_s' in trace.files else None
            phase_t={r['to']:float(r['time_s']-t0) for r in transitions}
            outbound=tt <= t0+phase_t.get('HOLD',1e9)
            progress=np.min(np.clip((q-np.radians([5,10]))/np.radians([115,110]),0,1),axis=1)
            goalbox=np.all(np.abs(np.degrees(q)-120)<=1,axis=1)
            velbox=np.all(np.abs(np.degrees(dq))<=2,axis=1)
            detail=dict(max_synchronized_progress=float(np.max(progress[outbound])),
                        goal_position_box_samples=int(np.sum(goalbox&outbound)),
                        goal_position_and_velocity_samples=int(np.sum(goalbox&velbox&outbound)),
                        settled_OUTBOUND_arrival='HOLD' in phase_t,HOLD_entry_s=phase_t.get('HOLD'),
                        HOLD_completed='RETURN' in phase_t,RETURN_entry_s=phase_t.get('RETURN'),
                        RETURN_completed='COMPLETE' in phase_t,COMPLETE_s=phase_t.get('COMPLETE'),
                        tracking_RMSE_deg=np.degrees(np.sqrt(np.mean(tracking**2,axis=0))),
                        tracking_max_abs_deg=np.degrees(np.max(np.abs(tracking),axis=0)),
                        final_q_deg=np.degrees(q[-1]),final_dq_deg_s=np.degrees(dq[-1]),
                        final_reference_q_deg=np.degrees(ref[-1]),
                        independent_VALID=bool(metric['valid']),termination_reason=env.summary.get('abort_reason') or env.summary['status'])
        arrays=dict(observations=np.array(observations,np.float32),raw_actions=np.array(actions,np.float32),
                    executed_actions=np.array(executed,np.float32),phase=np.array(phases),task_s=np.array(times),status=np.array(statuses))
        np.savez_compressed(env.episode_dir/'BC_POLICY_TRANSITIONS.npz',**arrays)
        np.savez_compressed(L/f'POLICY_seed_{seed}_{tag}.npz',**arrays)
        save(f'CLOSED_LOOP_seed_{seed}_{tag}.json',dict(seed=seed,tag=tag,checkpoint_sha256=sha(checkpoint),
             metric=metric,endpoints=detail,terminated=term,truncated=trunc,steps=len(actions),
             phase_transitions=transitions,initial=initial,initial_observation=init,
             actor_inference_ms=dict(mean=np.mean(latencies),p95=np.percentile(latencies,95),max=max(latencies)),
             teacher_access_count_during_rollout=0,teacher_override_count=0,deterministic=True,
             simulation_truth_actor_inputs=False,policy_period_s=.02,episode_dir=str(env.episode_dir),
             policy_transitions_sha256=sha(env.episode_dir/'BC_POLICY_TRANSITIONS.npz')))
        compact_archive(env)
        print(json.dumps(clean(dict(seed=seed,tag=tag,**detail))),flush=True)
    finally: env.close()

if __name__=='__main__': run(int(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else 'formal')
