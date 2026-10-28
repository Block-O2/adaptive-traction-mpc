"""Summarize observed reward credit and frozen outcomes, without new training."""
from pathlib import Path
from collections import defaultdict
import json
import statistics
from research_common import ROOT, atomic, read, sha, now


def stats(xs):
    return dict(n=len(xs), minimum=min(xs), mean=statistics.mean(xs), maximum=max(xs)) if xs else None


def main():
    rows = [json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    groups = defaultdict(list)
    for x in rows:
        if x['mode'] == 'training' and x['branch'].startswith('REWARD_'):
            groups[(x['branch'], x['seed'], 10 if x['index'] <= 10 else 30)].append(x)
    result = []
    for (branch, seed, screen), xs in sorted(groups.items()):
        episodes = []
        sources = {}
        for x in xs:
            run = Path(x['run'])
            path = run/'RESEARCH_TRANSITIONS.json'
            transitions = read(path)
            totals = defaultdict(float)
            for t in transitions:
                for key, value in t['reward_parts'].items():
                    totals[key] += value
            cost = -sum(totals.get(k,0) for k in ['force','moment','variation'])
            before = transitions[0]['reward_before']
            after = transitions[-1]['reward_after']
            sources[str(path)] = sha(path)
            episodes.append(dict(index=x['index'], success=x['success'], task_s=x['task_s'],
                training_reward=x['training_reward'], baseline_reward=x['baseline_reward'],
                reward_parts=dict(totals), realized_weighted_cost=cost,
                initial_potential=before['phi'], final_observed_potential=after['phi'],
                JF=x['JF'], JM=x['JM'], online_acceleration_proxy_integral=after['variation'],
                RL_decisions=x['rl_decisions'], actual_Adam=x['gradient_updates'],
                raw_clipped_component_fraction=x['raw_clipped_fraction'],
                pending_complete_transitions=x['pending_complete_transitions'],
                saved_transition_reward_sum_matches=abs(sum(t['reward'] for t in transitions)-x['training_reward'])<1e-7,
                reward_audit_pass=read(run/'RESEARCH_REWARD_AUDIT.json')['pass_']))
        successes = [x for x in episodes if x['success']]
        failures = [x for x in episodes if not x['success']]
        updates = [x['update'] for x in xs if x['update']]
        losskeys = ['train/approx_kl','train/clip_fraction','train/value_loss',
                    'train/explained_variance','train/policy_gradient_loss','train/std']
        latest = max(xs,key=lambda x:x['index'])
        frozen = [dict(job_id=x['job_id'], endpoint=x['index']-1, mode=x['policy_mode'],
                       success=x['success'], task_s=x['task_s'], JF=x['JF'], JM=x['JM'],
                       abort_reason=x['abort_reason'], reward_arithmetic=x['reward_version'])
                  for x in rows if x['mode']=='evaluation' and x['branch']==branch and x['seed']==seed]
        result.append(dict(branch=branch, seed=seed, nominal_segment='001–010' if screen==10 else '011–030',
            observed_episode_indices=[x['index'] for x in episodes], episodes=len(episodes),
            training_successes=len(successes), actual_Adam=sum(x['actual_Adam'] for x in episodes),
            RL_decisions=sum(x['RL_decisions'] for x in episodes),
            native_steps=sum(x['native_steps'] for x in xs),
            failure_returns=stats([x['training_reward'] for x in failures]),
            success_returns=stats([x['training_reward'] for x in successes]),
            failed_partial_weighted_cost=stats([x['realized_weighted_cost'] for x in failures]),
            complete_weighted_cost=stats([x['realized_weighted_cost'] for x in successes]),
            successful_reward_component_ranges={k:stats([x['reward_parts'].get(k,0) for x in successes])
                                                for k in ['progress','completion','force','moment','variation']},
            final_pending_complete_transitions=latest['pending_complete_transitions'],
            update_diagnostics={k:stats([u['losses'][k] for u in updates if k in u['losses']]) for k in losskeys},
            all_saved_reward_checks_pass=all(x['saved_transition_reward_sum_matches'] and x['reward_audit_pass'] for x in episodes),
            frozen_development_results=frozen, training_episode_details=episodes,
            sources_sha256=sources))
    atomic(ROOT/'audit/REWARD_REFLECTION_EVIDENCE.json', dict(time_utc=now(),
        category='SAVED_DEVELOPMENT_REWARD_CREDIT_NO_NEW_PHYSICS_NO_ADAM',
        source_sha256=sha(Path(__file__)), groups=result,
        limitations=[
            'On-policy training success counts describe changing sampled policies, not independent frozen completion rates.',
            'Return scales differ between reward versions and cannot rank policy quality.',
            'Failed partial JF/JM and different task durations cannot establish dose improvement.',
            'An identical negative failure total under the declared cost floor is intentional, not evidence that every failed action receives identical transition credit.',
            'Frozen evaluations retain original R0 arithmetic; their trained reward identity comes from the checkpoint metadata.',
            'Only already observed development action streams appear here; this analysis does not open final unseen streams or independent initial states.']))
    print('observed reward segments',len(result),'episodes',sum(x['episodes'] for x in result),
          'all reward sums/audits pass',all(x['all_saved_reward_checks_pass'] for x in result))


if __name__=='__main__':
    main()
