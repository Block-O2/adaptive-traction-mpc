"""Evidence-only cohort summary; refuse incomplete training or frozen windows."""
from pathlib import Path
import argparse,json
from research_common import ROOT,read,atomic,sha,now
SEEDS=[1495656323,1630784693]
def summarize(reward,endpoint):
    branch='REWARD_'+reward
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    tr=[x for x in rows if x['branch']==branch and x['mode']=='training' and x['index']<=endpoint]
    ev=[x for x in rows if x['branch']==branch and x['mode']=='evaluation' and x['index']<=endpoint+1]
    windows=[10,30] if endpoint==30 else [endpoint]
    assert len(tr)==endpoint*len(SEEDS),'TRAINING_COHORT_INCOMPLETE'
    assert {(x['seed'],x['index']-1,x['policy_mode']) for x in ev}=={(s,n,m) for s in SEEDS for n in windows for m in ['deterministic','stochastic']},'FROZEN_WINDOWS_INCOMPLETE'
    historical=[json.loads(l) for l in (ROOT.parent/'rl_b_autonomous_replication_v1/ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    parents={x['training_seed']:x for x in historical if x['kind']=='checkpoint050_first' and x['training_seed'] in SEEDS}
    seeds=[]
    for seed in SEEDS:
        xs=sorted((x for x in tr if x['seed']==seed),key=lambda x:x['index']);assert [x['index'] for x in xs]==list(range(1,endpoint+1))
        updates=[x['update'] for x in xs if x['update']]
        cp=ROOT/f'runtime/jobs/{branch}_seed{seed}_to{endpoint:03d}/checkpoints/episode_{endpoint:03d}'
        meta=read(cp.with_suffix('.json'));assert meta and sha(cp.with_suffix('.zip'))==meta['model_sha256']
        frozen=[]
        for x in ev:
            if x['seed']!=seed:continue
            motion=read(Path(x['run'])/'COMMON_MOTION_METRICS.json');assert motion,'MOTION_ANALYSIS_PENDING'
            p=parents[seed];ok=x['success'] and p['success'] and x['policy_mode']=='deterministic' and abs(x['task_s']-p['task_s'])<1e-7
            frozen.append(dict(job_id=x['job_id'],endpoint=x['index']-1,policy_mode=x['policy_mode'],success=x['success'],status=x['status'],abort_reason=x['abort_reason'],task_s=x['task_s'],JF=x['JF'],JM=x['JM'],integral_scope=x['integral_scope'],parent_equal_duration_complete_mean=ok,JF_percent=(x['JF']/p['JF']-1)*100 if ok else None,JM_percent=(x['JM']/p['JM']-1)*100 if ok else None,motion=motion,run=x['run'],independent_audit_pass=x['independent_audit_pass']))
        seeds.append(dict(seed=seed,checkpoint=str(cp),model_sha256=sha(cp.with_suffix('.zip')),metadata_sha256=sha(cp.with_suffix('.json')),research_config=meta['research_config'],worker_source_sha256=meta['research_source_sha256'],reward_source_sha256=meta['reward_source_sha256'],training=dict(episodes=len(xs),successes=sum(x['success'] for x in xs),sampled_transitions=sum(x['rl_decisions'] for x in xs),optimized_transitions=sum(x['transitions'] for x in updates),actual_Adam=sum(x['gradient_updates'] for x in xs),PPO_train=len(updates),epochs=sum(x['epochs'] for x in updates),native_steps=sum(x['native_steps'] for x in xs),terminal_pending=xs[-1]['pending_complete_transitions'],singleton_minibatches=sum(x['singleton_minibatches'] for x in updates),all_independent_audits_pass=all(x['independent_audit_pass'] for x in xs)),evaluations=frozen))
    result=dict(time_utc=now(),status='COMPLETE_BOUNDED_DEVELOPMENT_COHORT',reward=reward,branch=branch,endpoint=endpoint,tested_windows=windows,seed_results=seeds,all_tested_mean_success=all(x['success'] for x in ev if x['policy_mode']=='deterministic'),all_tested_sample_success=all(x['success'] for x in ev if x['policy_mode']=='stochastic'),reward_manifest_sha256=sha(ROOT/'REWARD_VERSION_MANIFEST.json'),source_sha256=sha(Path(__file__)),scope='Two selected successful parents; nominal development only. Distinct checkpoints/modes are not independent completion-rate trials. No formal matched or independent initial-state qualification.',new_physics=0,new_Adam=0)
    atomic(ROOT/f'{reward}_REWARD_RESULTS.json',result)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reward');p.add_argument('--endpoint',type=int,default=30);a=p.parse_args();r=summarize(a.reward,a.endpoint);print(json.dumps({k:v for k,v in r.items() if k!='seed_results'}))
