"""Summarize complete two-parent30-to60 evidence; never infer unrun endpoints."""
from pathlib import Path
import argparse,json
from research_common import ROOT,read,atomic,sha,now
from stability_lineages import resolve,retained
SEEDS=[1495656323,1630784693]

def main(branch):
    mapping=read(ROOT/'STABILITY_LINEAGES.json')['branch_to_lineage'];lineage=mapping[branch]
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    xs=[x for x in rows if x['branch']==branch]
    tr=[x for x in xs if x['mode']=='training'];ev=[x for x in xs if x['mode']=='evaluation']
    assert len(tr)==60 and len(ev)==4,'RETENTION_COHORT_INCOMPLETE'
    assert {(x['seed'],x['index']-1,x['policy_mode']) for x in ev}=={(s,60,m) for s in SEEDS for m in ['deterministic','stochastic']},'RETENTION_EVALUATIONS_INCOMPLETE'
    ancestry=resolve(rows,mapping);assert ancestry['status']=='PASS',ancestry['errors']
    historical=[json.loads(l) for l in (ROOT.parent/'rl_b_autonomous_replication_v1/ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    parents={x['training_seed']:x for x in historical if x['kind']=='checkpoint050_first' and x['training_seed'] in SEEDS}
    cases=[]
    for seed in SEEDS:
        train=sorted((x for x in tr if x['seed']==seed),key=lambda x:x['index']);assert [x['index'] for x in train]==list(range(31,61))
        updates=[x['update'] for x in train if x['update']]
        jobdir=ROOT/f'runtime/jobs/{branch}_seed{seed}_to060';cp=jobdir/'checkpoints/episode_060';meta=read(cp.with_suffix('.json'))
        assert meta['continuation_episodes']==60 and meta['training_episodes']==110 and sha(cp.with_suffix('.zip'))==meta['model_sha256']
        parent=Path(meta['parent']);pm=read(parent.with_suffix('.json'));assert pm['branch']==lineage and pm['continuation_episodes']==30
        resume=read(jobdir/'RESUME_AUDIT.json');assert resume['pass_'] and all(resume['checks'].values())
        assert read(jobdir/'EFFECTIVE_CONFIG.json')['rollout_terminal_episode']==60
        sampled=sum(x['rl_decisions'] for x in train);optimized=sum(x['transitions'] for x in updates)
        assert train[-1]['pending_complete_transitions']==0 and sampled==optimized,'TERMINAL_EXPOSURE_MISMATCH'
        frozen=[]
        for x in ev:
            if x['seed']!=seed:continue
            motion=read(Path(x['run'])/'COMMON_MOTION_METRICS.json');assert motion,'MOTION_ANALYSIS_PENDING'
            refs=[]
            ref30=next(z for z in rows if z['branch']==lineage and z['mode']=='evaluation' and z['seed']==seed and z['index']==31 and z['policy_mode']==x['policy_mode'])
            for name,reference in [('ORIGINAL_050_MEAN',parents[seed]),('SAME_FAMILY_030_SAME_MODE',ref30)]:
                same_mode=(x['policy_mode']=='deterministic') if name=='ORIGINAL_050_MEAN' else True
                ok=same_mode and x['success'] and reference['success'] and abs(x['task_s']-reference['task_s'])<1e-7
                refs.append(dict(reference=name,complete_equal_duration_same_mode=ok,JF_percent=(x['JF']/reference['JF']-1)*100 if ok else None,JM_percent=(x['JM']/reference['JM']-1)*100 if ok else None,reference_JF=reference['JF'],reference_JM=reference['JM'],reference_task_s=reference['task_s']))
            frozen.append(dict(job_id=x['job_id'],policy_mode=x['policy_mode'],success=x['success'],status=x['status'],abort_reason=x['abort_reason'],task_s=x['task_s'],JF=x['JF'],JM=x['JM'],integral_scope=x['integral_scope'],comparisons=refs,motion=motion,independent_audit_pass=x['independent_audit_pass'],run=x['run']))
        cases.append(dict(seed=seed,parent_checkpoint=str(parent),parent_model_sha256=sha(parent.with_suffix('.zip')),checkpoint=str(cp),model_sha256=sha(cp.with_suffix('.zip')),metadata_sha256=sha(cp.with_suffix('.json')),full_restore_pass=resume['pass_'],research_config=meta['research_config'],worker_source_sha256=meta['research_source_sha256'],reward_source_sha256=meta['reward_source_sha256'],training=dict(episodes=30,successes=sum(x['success'] for x in train),sampled_transitions=sampled,optimized_transitions=optimized,actual_Adam=sum(x['gradient_updates'] for x in train),PPO_train=len(updates),epochs=sum(x['epochs'] for x in updates),singleton_minibatches=sum(x['singleton_minibatches'] for x in updates),terminal_pending=0,native_steps=sum(x['native_steps'] for x in train),all_independent_audits_pass=all(x['independent_audit_pass'] for x in train)),evaluations=frozen))
    result=dict(time_utc=now(),status='COMPLETE_BOUNDED_RETENTION_COHORT',branch=branch,lineage=lineage,reward=cases[0]['research_config']['reward'],cumulative_continuation_endpoint=60,original_training_episode=110,seed_results=cases,all_latest_mean_success=all(x['success'] for x in ev if x['policy_mode']=='deterministic'),all_latest_sample_success=all(x['success'] for x in ev if x['policy_mode']=='stochastic'),all_tested_lineage_means_retained=lineage in retained(ancestry['groups'],SEEDS),lineage_audit='audit/STABILITY_LINEAGE_AUDIT.json',source_sha256=sha(Path(__file__)),new_physics=0,new_Adam=0,scope='Continue the actual saved030 state for30 more episodes. The legal030 terminal flush already happened; this is not the same update schedule as uninterrupted60 from050. Nominal selected-parent development, no independent initial-state or B/H150 matched qualification.')
    atomic(ROOT/f'{branch}_RESULTS.json',result);print(json.dumps({k:v for k,v in result.items() if k!='seed_results'}));return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('branch');a=p.parse_args();main(a.branch)
