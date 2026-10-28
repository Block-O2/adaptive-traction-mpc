"""Verify and describe the sole prelocked eight-stream final batch, no learning."""
from pathlib import Path
from datetime import datetime
import json
from research_common import ROOT,read,atomic,sha,now,same_pid,decision

def main():
    lockpath=ROOT/'FINAL_FROZEN_SELECTION.json';lock=read(lockpath)
    assert lock['status']=='LOCKED_BEFORE_ANY_FINAL_STREAM'
    planpath=Path(lock['plan']);assert sha(planpath)==lock['plan_sha256']
    plan=read(planpath);q=ROOT/'followup_queues'/plan['queue_id']
    assert read(q/'END.json')['completed'] and not same_pid(read(q/'START.json')['identity'])
    for name,expected in plan['required_sources'].items():assert sha(ROOT/'scripts'/name)==expected
    for case in lock['checkpoint_pair']:
        assert all(sha(ROOT/p)==expected for p,expected in case['files'].items()),'FROZEN_CHECKPOINT_CHANGED'
    allrows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    ledger=read(ROOT/'LEDGER.json')
    stamp=datetime.fromisoformat(lock['time_utc'])
    assert not any(a['kind']=='training' and datetime.fromisoformat(a['start_utc'])>=stamp for a in ledger['attempts']),'TRAINING_AFTER_FINAL_LOCK'
    rows=[]
    for item in plan['jobs']:
        cfgpath=Path(item['config']);assert sha(cfgpath)==item['sha256'];cfg=read(cfgpath)
        row=next(x for x in allrows if x['job_id']==cfg['job_id']);directory=Path(row['run']).parent
        assert cfg==read(directory/'EFFECTIVE_CONFIG.json')
        assert cfg['evaluation_split']=='heldout_action_stream' and cfg['mode']=='evaluation' and cfg['policy_mode']=='stochastic'
        assert row['parent']==cfg['parent_checkpoint'] and row['seed']==cfg['seed'] and row['index']==61
        assert row['gradient_updates']==0 and row['update'] is None and row['independent_audit_pass']
        cp=next(x for x in lock['checkpoint_pair'] if x['seed']==row['seed'])
        assert row['policy_before']==row['policy_after']==cp['state_snapshot']['policy']
        resume=read(directory/'RESUME_AUDIT.json');assert resume['pass_'] and all(resume['checks'].values())
        end=read(ROOT/'jobs'/cfg['job_id']/'END.json');assert end['success'] and end['child_joined']
        start=read(ROOT/'jobs'/cfg['job_id']/'START.json');assert datetime.fromisoformat(start['time_utc'])>stamp
        motion=read(Path(row['run'])/'COMMON_MOTION_METRICS.json');assert motion,'FINAL_MOTION_PENDING'
        rows.append(dict(job_id=cfg['job_id'],seed=cfg['seed'],evaluation_rng=cfg['evaluation_rng'],
            checkpoint=row['parent'],policy_sha256=row['policy_before'],success=row['success'],status=row['status'],
            abort_reason=row['abort_reason'],task_s=row['task_s'],JF=row['JF'],JM=row['JM'],integral_scope=row['integral_scope'],
            native_steps=row['native_steps'],rl_decisions=row['rl_decisions'],accepted=row['accepted'],rejections=row['rejections'],
            motion=motion,run=row['run'],config_sha256=item['sha256'],full_parent_restore=True,zero_Adam=True))
    assert len(rows)==8 and {(x['seed'],x['evaluation_rng']) for x in rows}=={(c['seed'],rng) for c in lock['checkpoint_pair'] for rng in lock['unseen_rngs']}
    prior_ids={x['job'] for x in lock['prior_development_evaluations']}
    assert {x['job_id'] for x in allrows if x['mode']=='evaluation'}==prior_ids|{x['job_id'] for x in rows},'UNPLANNED_FROZEN_EVALUATION'
    groups=[]
    for c in lock['checkpoint_pair']:
        xs=[x for x in rows if x['seed']==c['seed']]
        groups.append(dict(seed=c['seed'],checkpoint=c['checkpoint'],completed=sum(x['success'] for x in xs),attempts=4,
            duration_s=[x['task_s'] for x in xs],failed_job_ids=[x['job_id'] for x in xs if not x['success']],
            complete_JF=[x['JF'] for x in xs if x['success']],complete_JM=[x['JM'] for x in xs if x['success']]))
    result=dict(time_utc=now(),status='COMPLETE_FIXED_FINAL_ACTION_STREAM_BATCH',selected_branch=lock['selected_branch'],
        selection_sha256=sha(lockpath),selection_reason=lock['reason'],plan_sha256=sha(planpath),
        evaluations=rows,seed_results=groups,all8_complete=all(x['success'] for x in rows),
        no_training_after_selection=True,all_checkpoints_unchanged=True,all_evaluations_frozen=True,
        original_nominal_physics_only=True,independent_initial_state_generalization='NOT_ESTABLISHED_BLOCKED_INTERFACE',
        interpretation='Four descriptive unseen action streams per fixed checkpoint; do not pool across checkpoints into a robustness or patient-generalization rate. All partial failures retained. Different task durations preclude direct dose-benefit percentages.',
        source_sha256=sha(__file__),new_physics=0,new_Adam=0)
    atomic(ROOT/'FINAL_ACTION_STREAM_RESULTS.json',result)
    decision('FINAL_FIXED_ACTION_STREAM_BATCH_REVIEWED',dict(result='FINAL_ACTION_STREAM_RESULTS.json',sha256=sha(ROOT/'FINAL_ACTION_STREAM_RESULTS.json'),
        selected_branch=lock['selected_branch'],per_parent=[dict(seed=x['seed'],completed=x['completed'],attempts=4) for x in groups]),
        'No further tuning, training or candidate swap; complete saved-evidence audits, twenty-question review and bounded closure')
    print(json.dumps({k:result[k] for k in ['status','selected_branch','all8_complete','no_training_after_selection','all_checkpoints_unchanged']}))
if __name__=='__main__':main()
