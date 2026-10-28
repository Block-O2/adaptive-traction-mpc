"""Freeze one two-parent pair before the sole eight-stream final evaluation."""
from pathlib import Path
import json
from research_common import ROOT, read, atomic, sha, now, same_pid, decision
from followup_queue import inspect_plan
SEEDS=[1495656323,1630784693]
RNGS=[2026102191,2026102192,2026102193,2026102194]

def vector(result):
    out=[]
    fields=['tracking_RMS_deg','velocity_RMS_deg_s','velocity_peak_deg_s',
            'acceleration_RMS_deg_s2','acceleration_peak_deg_s2','jerk_RMS_deg_s3',
            'jerk_peak_deg_s3','terminal_return_absolute_error_deg',
            'RETURN_overshoot_below_goal_deg','OUTBOUND_overshoot_above_goal_deg']
    for seed in SEEDS:
        case=next(x for x in result['seed_results'] if x['seed']==seed)
        row=next(x for x in case['evaluations'] if x['policy_mode']=='deterministic')
        assert row['success'] and row['independent_audit_pass'] and abs(row['task_s']-19.03)<1e-7
        out.extend([row['JF'],row['JM']])
        for key in fields: out.extend(row['motion'][key])
    return out

def dominates(a,b):return all(x<=y for x,y in zip(a,b)) and any(x<y for x,y in zip(a,b))

def main():
    lock=ROOT/'FINAL_FROZEN_SELECTION.json'
    assert not lock.exists(),'FINAL_PAIR_ALREADY_LOCKED_DO_NOT_RESELECT'
    assert not (ROOT/'STOP_REQUESTED').exists()
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    assert not any(x.get('evaluation_split')=='heldout_action_stream' or '_final_rng' in x['job_id'] for x in rows)
    registry=read(ROOT/'ADDITIONAL_REWARD_STUDIES.json')
    assert all(x['status']=='COMPLETE' and sha(ROOT/x['result_path'])==x['result_sha256'] for x in registry['studies'])
    results={b:read(ROOT/f'{b}_RESULTS.json') for b in ['RETENTION_H2','RETENTION_R1']}
    for b,d in results.items():
        assert d['status']=='COMPLETE_BOUNDED_RETENTION_COHORT'
        assert d['cumulative_continuation_endpoint']==60 and {x['seed'] for x in d['seed_results']}==set(SEEDS)
        queue='H2_RETENTION_TO060_v1' if b=='RETENTION_H2' else 'R1_RETENTION_TO060_v1'
        q=ROOT/'followup_queues'/queue
        assert read(q/'END.json')['completed'] and not same_pid(read(q/'START.json')['identity'])
        assert all(x['training']['all_independent_audits_pass'] and x['full_restore_pass'] for x in d['seed_results'])
        assert all(e['independent_audit_pass'] for x in d['seed_results'] for e in x['evaluations'])
    eligible=[b for b,d in results.items() if d['all_tested_lineage_means_retained'] and d['all_latest_mean_success']]
    assert eligible,'NO_LONG_FAMILY_RETAINED_REQUIRES_EXPLICIT_FALLBACK_REVIEW'
    if len(eligible)==1:
        selected=eligible[0];reason='Only this longer family retains both parents at every tested mean endpoint'
    else:
        modes=[b for b in eligible if results[b]['all_latest_sample_success']]
        if len(modes)==1:
            selected=modes[0];reason='Both families retain mean; only selected family completes both latest development sample tasks'
        else:
            choices=modes or eligible
            a,b=choices;va,vb=vector(results[a]),vector(results[b])
            if dominates(va,vb):selected=a;reason='Same task/retention tier; selected family Pareto-dominates all listed complete equal-duration dose and native motion metrics'
            elif dominates(vb,va):selected=b;reason='Same task/retention tier; selected family Pareto-dominates all listed complete equal-duration dose and native motion metrics'
            else:selected='RETENTION_R1';reason='Same task/retention/latest-mode tier with dose/motion tradeoffs; precommitted R1 diagnostic preference, not universal superiority'
    seen=[]
    for p in sorted((ROOT/'jobs').glob('*/START.json')):
        s=read(p);cfg=read(Path(s['config']));assert sha(Path(s['config']))==s['config_sha256']
        if cfg['mode']=='evaluation':
            assert cfg['evaluation_rng'] not in RNGS,'FINAL_ACTION_RNG_ALREADY_USED'
            seen.append(dict(job=cfg['job_id'],rng=cfg['evaluation_rng'],split=cfg.get('evaluation_split','development'),config_sha256=s['config_sha256']))
    assert len(seen)==44,'FINAL_MUST_FOLLOW_EXACTLY_44_DEVELOPMENT_ATTEMPTS'
    pair=[];jobs=[]
    for case in results[selected]['seed_results']:
        cp=Path(case['checkpoint']);meta=read(cp.with_suffix('.json'))
        files={str(p.relative_to(ROOT)):sha(p) for p in [cp.with_suffix('.zip'),cp.with_suffix('.rng.pt'),cp.with_suffix('.json')]}
        assert files[str(cp.with_suffix('.zip').relative_to(ROOT))]==meta['model_sha256']
        assert files[str(cp.with_suffix('.rng.pt').relative_to(ROOT))]==meta['rng_sha256']
        assert meta['pending_complete_transitions']==0
        pair.append(dict(seed=case['seed'],checkpoint=str(cp),files=files,state_snapshot=meta['state_snapshot'],parent_checkpoint=meta['parent'],method=meta['research_config'],contract_sha256=meta['contract_sha256']))
        for rng in RNGS:
            job=f"{selected}_seed{case['seed']}_ep060_final_rng{rng}"
            cfg=dict(job_id=job,branch=selected,seed=case['seed'],parent_checkpoint=str(cp),
                start_episode=60,episodes=1,mode='evaluation',learning_rate=0.0003,rollout='aggregate64',
                reward='R0',target_kl=None,policy_mode='stochastic',evaluation_rng=rng,
                evaluation_split='heldout_action_stream')
            p=ROOT/'configs'/f'{job}.json';assert not p.exists();atomic(p,cfg)
            jobs.append(dict(config=str(p),sha256=sha(p)))
    plan=ROOT/'configs/FINAL_ACTION_STREAMS8_PLAN_v1.json'
    assert not plan.exists()
    atomic(plan,dict(version='FINITE_FOLLOWUP_QUEUE_v1',queue_id='FINAL_ACTION_STREAMS8_v1',phase='FINAL_VERIFICATION',
        purpose='One preselected frozen pair, four unseen action RNGs each; no training or adaptive candidate swaps',
        required_sources={n:sha(ROOT/'scripts'/n) for n in ['worker.py','rewards.py','research_common.py']},jobs=jobs))
    _,_,inspection=inspect_plan(plan);assert inspection['ready_to_start'],inspection
    atomic(lock,dict(time_utc=now(),status='LOCKED_BEFORE_ANY_FINAL_STREAM',selected_branch=selected,
        reward=results[selected].get('reward','R0'),reason=reason,selection_protocol_sha256=sha(ROOT/'FINAL_SELECTION_PROTOCOL.md'),
        selection_script_sha256=sha(__file__),retention_results={b:sha(ROOT/f'{b}_RESULTS.json') for b in results},
        checkpoint_pair=pair,unseen_rngs=RNGS,prior_development_evaluations=seen,plan=str(plan),plan_sha256=sha(plan),
        admission=inspection,post_final_rule='No more training, Reward/PPO/std changes or candidate replacement after any final result',
        scope='Same nominal physical initial state; action-stream holdout only; not patient or initial-state generalization'))
    decision('FINAL_FROZEN_PAIR_LOCKED',dict(selection_file=str(lock),sha256=sha(lock),branch=selected,reason=reason,plan=str(plan)),
        'Execute this sole fixed eight-stream evaluation, then offline scientific review and closure; no tuning or new candidate')
    print(json.dumps(dict(selected_branch=selected,reason=reason,lock_sha256=sha(lock),plan=str(plan),inspection=inspection)))
if __name__=='__main__':main()
