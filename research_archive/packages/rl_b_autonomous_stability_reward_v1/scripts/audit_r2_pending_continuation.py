"""Check real preserved complete episodes enter the resumed PPO update exactly."""
from pathlib import Path
import json
from research_common import ROOT, read, atomic, now, sha


def audit():
    seed=1630784693
    base=ROOT/f'runtime/jobs/REWARD_R2_seed{seed}_to010/checkpoints/episode_010'
    job=f'REWARD_R2_seed{seed}_to030'
    out=ROOT/'runtime/jobs'/job
    meta=read(base.with_suffix('.json'))
    rows=[json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    completed=[x for x in rows if x['job_id']==job and x['mode']=='training']
    updated=[x for x in completed if x['update']]
    result=dict(time_utc=now(),source_sha256=sha(Path(__file__)),job=job,
                parent=str(base),physics_attempts=0,Adam_updates=0)
    if not updated:
        result.update(status='AWAITING_REAL_RESUMED_UPDATE',pass_=None,
                      completed_new_episodes=len(completed),
                      required_parent_pending=meta['pending_complete_transitions'])
    else:
        first=min(updated,key=lambda x:x['index'])
        consumed=sorted((x for x in completed if x['index']<=first['index']),key=lambda x:x['index'])
        pending_path=Path(meta['pending_complete_rollout_path'])
        pending=read(pending_path)
        expected=list(pending)
        paths=[pending_path]
        for row in consumed:
            path=Path(row['run'])/'RESEARCH_TRANSITIONS.json'
            expected+=read(path);paths.append(path)
        batch_path=Path(first['run'])/'COMPLETE_UPDATE_INPUT.json'
        actual=read(batch_path)
        resume=read(out/'RESUME_AUDIT.json');pending_resume=read(out/'PENDING_RESUME_AUDIT.json')
        before=read(Path(first['run'])/'before_update_checkpoint.json')
        checks=dict(
            parent_pending_checksum=sha(pending_path)==meta['pending_complete_rollout_sha256'],
            full_start_policy_Adam_RNG_counter_restore=resume['pass_'] and all(resume['checks'].values()),
            restored_pending_count=pending_resume['restored_transitions']==len(pending),
            actual_pending_prefix_exact=actual[:len(pending)]==pending,
            complete_update_input_exact=actual==expected,
            batch_size_matches=len(actual)==first['update']['transitions'],
            complete_episode_count_matches=sum(bool(x['episode_start']) for x in expected)==first['update']['complete_episodes'],
            unupdated_generating_policy=before['policy_sha256']==meta['pending_generated_under_policy_sha256'],
            optimizer_unchanged_before_first_update=before['state_snapshot']['optimizer']==meta['state_snapshot']['optimizer'],
            new_indices_follow_parent=[x['index'] for x in consumed]==list(range(11,first['index']+1)),
            new_episode_starts_after_complete_pending=bool(actual[len(pending)]['episode_start']))
        result.update(status='PASS' if all(checks.values()) else 'FAIL',pass_=all(checks.values()),
            checks=checks,parent_pending_transitions=len(pending),
            parent_pending_complete_episodes=meta['pending_complete_episodes'],
            new_episodes=[x['index'] for x in consumed],
            new_transitions=sum(x['rl_decisions'] for x in consumed),
            first_update_transitions=len(actual),first_update_index=first['index'],
            first_update_actual_Adam=first['gradient_updates'],
            sources_sha256={str(p):sha(p) for p in [*paths,batch_path,base.with_suffix('.json'),out/'RESUME_AUDIT.json',out/'PENDING_RESUME_AUDIT.json']},
            interpretation='Exact ordered equality proves the preserved pending and all new completed episodes enter this real update once, with no omitted/duplicated transition; it is not a no-physics training replay or a task-success claim.')
    atomic(ROOT/'audit/R2_REAL_PENDING_CONTINUATION_AUDIT.json',result)
    return result


if __name__=='__main__':
    result=audit()
    print(json.dumps({k:result[k] for k in ['status','pass_','job']}))
    raise SystemExit(1 if result['pass_'] is False else 0)
