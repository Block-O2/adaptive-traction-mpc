"""Rehydrate one already recorded actor rollout after compact retention, not a new formal evaluation."""
from common import *
import gzip
def guard():
    st=json.loads((D/'STATE.json').read_text());assert time.time()<st['hard_cutoff_unix']
    w=memory.windows();m=memory.memfile('/proc/meminfo');p=memory.processes()
    assert m['MemAvailable']>=1.5*2**30 and w['CommitLimit']-w['CommittedBytes']>=2*2**30
    assert m['SwapTotal']-m['SwapFree']<=16*2**20 and not p['other_heavy_python'] and not w['ExternalVideoRender']
def run():
    assert json.loads((D/'STATE.json').read_text())['status']=='PAIRED_50K_COMPLETE_STOP';guard();check_lock()
    record=json.loads((D/'EVALUATION_A_0050000_NATIVE_periodic.json').read_text());original=R/record['trace'];assert not original.exists()
    source=original.parent/'POLICY_TRANSITIONS.npz';data=np.load(source)
    folder=O/'important_failure_archive'/'A_0050000_NATIVE_periodic_rehydrated_v2';case,options=load_case_options()
    np.random.seed(SEED);random.seed(SEED);env=SACExpertEnv(folder,case,options,.02,'NATIVE',True)
    errors=dict(observation=0.,next_observation=0.,reward=0.);receipt=None
    try:
        obs,info=env.reset(seed=SEED)
        for i,action in enumerate(data['actions']):
            if i%100==0:guard()
            errors['observation']=max(errors['observation'],float(np.abs(obs-data['observations'][i]).max()))
            obs,reward,term,trunc,info=env.step(action)
            errors['next_observation']=max(errors['next_observation'],float(np.abs(obs-data['next_observations'][i]).max()))
            errors['reward']=max(errors['reward'],abs(reward-float(data['rewards'][i])))
            assert term==bool(data['terminated'][i]) and trunc==bool(data['truncated'][i])
        assert env.summary is not None and env.model_hash==check_lock()['frozen_model_hash']
        assert errors['observation']<=1e-7 and errors['next_observation']<=1e-7 and errors['reward']<=1e-8
        assert abs(env.force_integral-record['J_F'])<=1e-6 and abs(env.force_peak-record['force_peak'])<=1e-6 and abs(env.moment_peak-record['moment_peak'])<=1e-6
        assert env.summary['abort_reason']==record['termination_reason'] and not info['success']
        ep=env.episode_dir
        p=ep/'runtime_artifacts.json'
        if p.exists():
            target=ep/'runtime_artifacts.json.gz'
            with p.open('rb') as src,gzip.open(target,'wb') as dst:shutil.copyfileobj(src,dst)
            assert p.resolve().is_relative_to(folder.resolve());p.unlink()
        receipt=dict(status='VALIDATED_ARCHIVAL_REHYDRATION',original_rollout=record['rollout_id'],scope='NATIVE',original_periodic_training_step=50000,original_periodic_updates=44999,original_high_frequency_file_was_pruned=True,original_trace_sha256=record['trace_sha256'],source_actor_transitions=str(source),source_actor_transitions_sha256=sha(source),restored_episode_dir=str(ep),original_model_hash=env.model_hash,comparison_max_abs_error=errors,JF_difference=env.force_integral-record['J_F'],force_peak_difference=env.force_peak-record['force_peak'],moment_peak_difference=env.moment_peak-record['moment_peak'],original_termination_reproduced=True,not_a_new_formal_evaluation_row=True,new_online_steps=0,new_updates=0,teacher_actions_used=False,files={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in ep.iterdir() if p.is_file()},scope_limit='Native only. No new or inferred MATCHED result. The original recorded scope-specific evaluation rows remain unchanged.',hash_limit='Restored-file hashes identify the reconstructed artifacts, not an assertion of byte-identical deleted raw files.')
        save('IMPORTANT_FAILURE_REHYDRATION_V2.json',receipt)
        prose('IMPORTANT_FAILURE_REHYDRATION_V2.md','# Important A50k failure retention\n\nThe original compact-retention job pruned the A50k periodic high-frequency trace before the one-update positional discontinuity was selected as important. The stored actor actions and full policy-rate transitions were retained. A single Native archival replay recreates that already recorded trajectory and checks every observation, next observation, reward and done flag, plus force cost and force/moment peaks against the original evaluation. It adds zero training steps, zero updates and no new formal evaluation row. The original results remain unchanged. Full reconstructed physics artifacts are separately labeled and their own hashes are recorded; deleted original raw hashes are not presented as copies.\n')
        raw=json.loads((D/'RAW_DATA_MANIFEST.json').read_text())
        for p,v in receipt['files'].items():raw['entries'].append(dict(path=p,bytes=v['bytes'],sha256=v['sha256'],retained=True,reason='Important failure, validated archival replay of own stored actor actions; original pruning retained in prior entries.'))
        raw['retained_high_frequency_directories'].append(str(ep));raw['post_retention_rehydration']='IMPORTANT_FAILURE_REHYDRATION_V2.json';save('RAW_DATA_MANIFEST.json',raw)
        print(json.dumps(clean(receipt)),flush=True)
    finally:env.close()
    shutil.copy2(Path(__file__),P/Path(__file__).name)
if __name__=='__main__':run()
