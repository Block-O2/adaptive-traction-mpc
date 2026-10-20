"""Post-run teacher comparison only, with no physical owner or action selection."""
from common import *

def diagnose(record):
    import threading
    assert not any(t.name=='single-CPU-MuJoCo-owner' for t in threading.enumerate())
    z=np.load(DEMO); teacher_obs=z['observations']; teacher_actions=z['actions'];teacher_phase=z['phase'];teacher_time=z['task_s']
    a=np.load(Path(record['episode_dir'])/'BC_POLICY_TRANSITIONS.npz');obs=a['observations'];actions=a['raw_actions'];phases=a['phase'];times=a['task_s']
    aligned=np.argmin(np.abs(times[:,None]-teacher_time[None,:]),axis=1)
    same=phases==teacher_phase[aligned]
    obs_l2=np.linalg.norm(obs-teacher_obs[aligned],axis=1)
    act_l2=np.linalg.norm(actions-teacher_actions[aligned],axis=1)
    nearest=[];near_distance=[]
    for o,p in zip(obs,phases):
        ids=np.flatnonzero(teacher_phase==p);distance=np.linalg.norm(teacher_obs[ids]-o,axis=1)
        j=int(np.argmin(distance));nearest.append(ids[j]);near_distance.append(distance[j])
    nearest=np.array(nearest);near_action=np.linalg.norm(actions-teacher_actions[nearest],axis=1)
    # Additional distances remove existing phase/time/history fields for interpretation only.
    causal_state_l2=np.linalg.norm(obs[:,:41]-teacher_obs[aligned,:41],axis=1)
    first=None
    for i in range(len(obs)-4):
        if np.all(obs_l2[i:i+5]>.25):
            t=float(times[i]);p=str(phases[i])
            region=('early OUTBOUND' if t<1.5 else 'goal approach / settling') if p=='OUTBOUND' else p
            first=dict(index=i,task_s=t,phase=p,region=region,observation_L2=float(obs_l2[i]),phase_aligned=bool(same[i]),rule='5 consecutive samples above preregistered .25 normalized L2')
            break
    arrays=dict(task_s=times,phase=phases,teacher_time_aligned_index=aligned,time_aligned_phase_matches=same,
                observation_L2_time_aligned=obs_l2,action_L2_time_aligned=act_l2,
                nearest_same_phase_teacher_index=nearest,nearest_observation_L2=np.array(near_distance),
                action_L2_nearest_comparable=near_action,causal_state_L2_time_aligned=causal_state_l2,
                teacher_time_delta_s=times-teacher_time[aligned])
    path=Path(record['episode_dir'])/'BC_DEVIATION.npz';np.savez_compressed(path,**arrays)
    shutil.copy2(path,L/f'DEVIATION_seed_{record["seed"]}_{record["tag"]}.npz')
    initial=np.array(record['initial_observation']);np.testing.assert_allclose(initial,teacher_obs[0],atol=1e-7,rtol=0)
    def stats(x):return dict(mean=float(np.mean(x)),RMSE=float(np.sqrt(np.mean(x*x))),max=float(np.max(x)),p95=float(np.percentile(x,95)))
    checkpoints=[]
    for target in (0.,.5,1.,1.5,2.,3.,4.,5.,6.,8.,10.,12.):
        if target>times[-1]+.01: continue
        i=int(np.argmin(np.abs(times-target)))
        checkpoints.append(dict(task_s=float(times[i]),phase=str(phases[i]),observation_L2=float(obs_l2[i]),
                               action_L2_time_aligned=float(act_l2[i]),nearest_observation_L2=float(near_distance[i]),
                               action_L2_nearest_comparable=float(near_action[i]),phase_aligned=bool(same[i])))
    result=dict(seed=record['seed'],tag=record['tag'],first_significant_deviation=first,
                observation_L2_time_aligned=stats(obs_l2),action_L2_time_aligned=stats(act_l2),
                nearest_observation_L2=stats(np.array(near_distance)),action_L2_nearest_comparable=stats(near_action),
                time_aligned_phase_match_rate=float(np.mean(same)),initial_condition_matches_teacher=True,
                per_phase={p:dict(count=int(np.sum(phases==p)),observation_L2_time_aligned=stats(obs_l2[phases==p]),action_L2_nearest_comparable=stats(near_action[phases==p])) for p in np.unique(phases)},
                checkpoints=checkpoints,arrays=str(path),arrays_sha256=sha(path),
                limitation='Nearest recorded teacher state is a finite-data geometric comparator, not a counterfactual teacher policy at off-trajectory states. Time-aligned phase mismatch and teacher end extrapolation are explicit. These diagnostics do not prove partial observability or absolute-target causation.')
    save(f'DIAGNOSIS_seed_{record["seed"]}_{record["tag"]}.json',result);return result

if __name__=='__main__':
    spec=read('PREREGISTRATION.json')
    if len(read('OFFLINE_RESULTS.json'))==3 and all(r['offline_pass'] for r in read('OFFLINE_RESULTS.json')):
        rows=[read(f'CLOSED_LOOP_seed_{seed}_formal.json') for seed in spec['seeds']]
        for row in rows:diagnose(row)
        valid=[r for r in rows if r['endpoints']['independent_VALID']]
        best=min(valid,key=lambda r:(r['metric']['J_F'],r['seed'])) if valid else max(rows,key=lambda r:(r['endpoints']['max_synchronized_progress'],-r['seed']))
        save('BEST_SELECTION.json',dict(seed=best['seed'],tag='formal',valid=bool(valid),replay_required=bool(valid),rule=spec['best_selection']))
        print(json.dumps(dict(best_seed=best['seed'],valid_count=len(valid),independent_replay_required=bool(valid))),flush=True)
