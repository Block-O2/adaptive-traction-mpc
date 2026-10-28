from common import *
from expert import CausalHipLeadingExpert
def progress(ob):
    q=ob[:2]*SCALES[:2]
    return float(np.min((q-np.radians([5,10]))/np.radians([115,110])))
def run():
    check();resource('EXPERT_GATE');config=read('PREREGISTRATION.json');expert=CausalHipLeadingExpert(config['expert'],SCALES)
    results=[]
    cases=[dict(seed=None,index=0)]+config['expert']['gate_prefixes']
    for case in cases:
        seed,index=case['seed'],case['index'];name='nominal' if seed is None else f'bc_{seed}_prefix_{index}'
        z=None if seed is None else np.load(BC/f'POLICY_seed_{seed}.npz')
        phys,options=load_case_options();env=SACExpertEnv(O/'expert_gate'/name,phys,options,.02,'NATIVE',True)
        records=[];observations=[];actions=[];next_obs=[];rewards=[];terms=[];truncs=[];phases=[]
        try:
            obs,info=env.reset(seed=config['initial_condition_seed'])
            for i in range(index):
                np.testing.assert_allclose(obs,z['observations'][i],atol=1e-7,rtol=0)
                obs,reward,term,trunc,info=env.step(z['raw_actions'][i]);assert not(term or trunc),'PREFIX_ALREADY_TERMINAL'
            if z is not None:np.testing.assert_allclose(obs,z['observations'][index],atol=1e-7,rtol=0)
            initial=obs.copy();p0=progress(obs);first_status=None;short=None
            for i in range(1600):
                action,detail=expert.query(obs);assert env.action_space.contains(action)
                observations.append(obs.copy());actions.append(action.copy());phases.append(info['phase'])
                obs,reward,term,trunc,info=env.step(action)
                next_obs.append(obs.copy());rewards.append(reward);terms.append(term);truncs.append(trunc)
                records.append(dict(**detail,action=action,executed=env.last_row['executed'],status=env.last_row['status']))
                if first_status is None:first_status=env.last_row['status']
                if i==99:short=dict(seconds=2.,before_progress=p0,after_progress=progress(obs),phase=info.get('phase'),advance=progress(obs)-p0)
                if term or trunc:break
            assert term or trunc,'UNFINISHED_GATE'
            row=metric(env,'EXPERT_'+name,'NATIVE')
            positive=(short is not None and short['advance']>0) or (row['valid'] and p0>=.99)
            passed=row['valid'] and first_status in ('ACCEPTED','IDENTICAL_CONTINUATION') and (seed is None or positive)
            result=dict(name=name,seed=seed,prefix_index=index,prefix_exact=True,reset_to_teacher=False,
                        input_state=initial,short_continuation=short,first_action_status=first_status,metric=row,pass_=passed,
                        query_count=len(actions),legal_query_count=len(actions),source_bc_sha256=sha(BC/f'POLICY_seed_{seed}.npz') if seed else None)
            np.savez_compressed(O/'expert_gate'/f'{name}_transitions.npz',observations=observations,actions=actions,
                next_observations=next_obs,rewards=rewards,terminated=terms,truncated=truncs,phase=phases)
            save('EXPERT_QUERY_'+name+'.json',records);results.append(result)
            save('EXPERT_GATE.json',dict(status='RUNNING',results=results))
            compact_archive(env);check()
            print(json.dumps(clean(dict(name=name,valid=row['valid'],pass_=passed,J_F=row['J_F'],short=short,termination=row.get('status')))),flush=True)
        finally:env.close()
        resource('AFTER_'+name)
    passed=all(r['pass_'] for r in results)
    save('EXPERT_GATE.json',dict(status='PASS' if passed else 'EXPERT_QUERY_INTERFACE_BLOCKED',queryable=passed,
         results=results,hidden_inputs=False,trajectory_replay_expert=False,nominal_demo_used_during_query=False))
    state('EXPERT_GATE_PASS' if passed else 'EXPERT_QUERY_INTERFACE_BLOCKED',next_action='Initialize phase-balanced DAgger; continue fixed schedule.' if passed else 'Preserve expert recovery failures; STOP, no DAgger or SAC.')
if __name__=='__main__':run()
