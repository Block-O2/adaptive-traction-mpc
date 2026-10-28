from common import *

def run():
    lock=check_lock(); resource('TEACHER'); z=np.load(DEMO); case,options=load_case_options()
    env=SACExpertEnv(O/'teacher_reference',case,options,.02,'NATIVE',True)
    errors=[]
    try:
        obs,info=env.reset(seed=read('PREREGISTRATION.json')['initial_condition_seed'])
        assert env.model_hash==lock['frozen_model_hash']
        for i,action in enumerate(z['actions']):
            before=float(np.max(np.abs(obs-z['observations'][i])))
            np.testing.assert_allclose(obs,z['observations'][i],atol=1e-7,rtol=0)
            assert info['phase']==z['phase'][i]
            obs,reward,term,trunc,info=env.step(action)
            after=float(np.max(np.abs(obs-z['next_observations'][i])))
            np.testing.assert_allclose(obs,z['next_observations'][i],atol=1e-7,rtol=0)
            assert abs(reward-z['rewards'][i])<1e-8
            assert term==z['terminated'][i] and trunc==z['truncated'][i]
            assert np.max(np.abs(np.array(env.last_row['executed'])-action))<2e-7
            errors.append(dict(index=i,obs_error=before,next_obs_error=after,reward_error=abs(reward-z['rewards'][i])))
        metric=r2.metric(env,'teacher_reference','NATIVE'); metric.pop('raw_actions')
        assert metric['valid'] and metric['physical_audit']['pass_']
        save('TEACHER_REPRODUCTION.json',dict(status='PASS',count=len(errors),errors=errors,metric=metric,
                                           unchanged_scientific_evaluator=True,new_learning_updates=0))
        compact_archive(env); state('TEACHER_SAME_WRAPPER_VALID_TRAINING_NEXT',count=593,valid=True)
    finally: env.close()

if __name__=='__main__': run()
