"""Read-only physics reproduction of the archived 593 transitions; no learning."""
from common import *
from final_qualification import compact_archive
def run():
    lock=check_lock();z=np.load(O/'NATIVE_DEMO.npz');case,options=load_case_options()
    env=SACExpertEnv(O/'teacher_audit_reproduction',case,options,.02,'NATIVE',True)
    try:
        obs,info=env.reset(seed=SEED);assert env.model_hash==lock['frozen_model_hash']
        errors=[]
        for i,action in enumerate(z['actions']):
            np.testing.assert_allclose(obs,z['observations'][i],atol=1e-7,rtol=0)
            assert info['phase']==z['phase'][i]
            obs,reward,term,trunc,info=env.step(action)
            np.testing.assert_allclose(obs,z['next_observations'][i],atol=1e-7,rtol=0)
            assert abs(reward-z['rewards'][i])<1e-8
            assert term==z['terminated'][i] and trunc==z['truncated'][i]
            assert np.max(np.abs(env.last_row['executed']-action))<2e-7
            errors.append(dict(index=i,max_obs_error=float(np.max(np.abs(obs-z['next_observations'][i]))),reward_error=abs(reward-z['rewards'][i]),flags_match=True,executed_target_match=True))
        record=r2.metric(env,'teacher_audit_reproduction','NATIVE');assert record['valid']
        save('TEACHER_EXACT_REPRODUCTION.json',dict(status='PASS',count=len(errors),rows=errors,independent_metric={k:v for k,v in record.items() if k!='raw_actions'},training_steps=0,optimizer_updates=0))
        audit=json.loads((D/'DEMO_DATA_AUDIT.json').read_text());audit['exact_same_wrapper_reproduction']='PASS all 593 observations/actions/rewards/next states/flags/phase; independent VALID';save('DEMO_DATA_AUDIT.json',audit)
        compact_archive(env)
        print(json.dumps(dict(status='TEACHER_REPRODUCTION_PASS',count=len(errors),valid=record['valid'],J_F=record['J_F'])),flush=True)
    finally:env.close()
if __name__=='__main__':run()
