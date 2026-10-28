"""Summarize saved proposal/admission/application evidence; never runs physics."""
from pathlib import Path
from collections import Counter
import json
import numpy as np
from research_common import ROOT, atomic, read, sha, now

HISTORY = ROOT.parent / 'rl_b_autonomous_replication_v1'


def event_counts(value):
    if isinstance(value, int):
        return dict(historical_scalar_total=value)
    return dict(Counter(e['event'] for e in value))


def vector_stats(values):
    if not values:
        return None
    a = np.asarray(values, dtype=float)
    assert a.ndim == 2 and a.shape[1] == 2 and np.isfinite(a).all()
    return dict(count=len(a), mean=a.mean(0).tolist(),
                minimum=a.min(0).tolist(), maximum=a.max(0).tolist(),
                rms=np.sqrt(np.mean(a*a, 0)).tolist())


def summarize(run, identity):
    summary_path = run / 'env/episode_0001/summary.json'
    summary = read(summary_path)
    episode_paths = list(run.glob('episode_*.json'))
    assert len(episode_paths) == 1
    episode = read(episode_paths[0])
    ds = summary['decisions']
    phases = {}
    for phase in ['OUTBOUND', 'HOLD', 'RETURN']:
        selected = [d for d in ds if d['phase'] == phase]
        proposed = [d['proposed_action_delta_q_rad'] for d in selected
                    if d.get('proposed_action_delta_q_rad') is not None]
        executed = [d['executed_action_delta_q_rad'] for d in selected
                    if d.get('executed_action_delta_q_rad') is not None]
        pairs = [(d['proposed_action_delta_q_rad'], d['executed_action_delta_q_rad'])
                 for d in selected if d.get('proposed_action_delta_q_rad') is not None
                 and d.get('executed_action_delta_q_rad') is not None]
        reasons = [d.get('activation_rejected_reason') or d.get('planning_exception')
                   for d in selected if d.get('activation_outcome') != 'ACTIVATED']
        phases[phase] = dict(
            planner_decisions=len(selected),
            outcomes=dict(Counter(d['activation_outcome'] for d in selected)),
            plan_activated=sum(bool(d.get('plan_activated')) for d in selected),
            deadline_misses=sum(bool(d.get('deadline_miss')) for d in selected),
            proposed_delta_q_rad=vector_stats(proposed),
            executed_delta_q_rad=vector_stats(executed),
            proposed_executed_pairs=len(pairs),
            max_abs_proposed_executed_delta_q_difference_rad=(
                float(np.max(np.abs(np.asarray([p[0] for p in pairs]) -
                                    np.asarray([p[1] for p in pairs])))) if pairs else None),
            rejection_or_failure_reasons=[x for x in reasons if x])
    research_path = run / 'RESEARCH_TRANSITIONS.json'
    policy = None
    if research_path.exists():
        ts = read(research_path)
        raw = np.asarray([t['raw_action'] for t in ts], dtype=float)
        clipped = np.asarray([t['action'] for t in ts], dtype=float)
        policy = dict(
            transitions=len(ts), raw_gaussian=vector_stats(raw.tolist()),
            clipped_proposals=vector_stats(clipped.tolist()),
            clipped_components=int(np.sum(np.abs(raw) > 1)),
            total_components=int(raw.size),
            clipped_component_fraction=float(np.mean(np.abs(raw) > 1)),
            clip_mapping_max_abs_error=float(np.max(np.abs(np.clip(raw, -1, 1)-clipped))),
            mean_std=np.mean([t['std'] for t in ts], axis=0).tolist())
    return dict(**identity, run=str(run), sources={str(summary_path):sha(summary_path),
                str(episode_paths[0]):sha(episode_paths[0]),
                **({str(research_path):sha(research_path)} if research_path.exists() else {})},
                RL_decisions=episode['rl_decisions'],
                planner_decisions=len(ds), accepted=episode['accepted'],
                rejected=episode['rejections'], applied_receipts=episode['applied_receipts'],
                safety_mode_counts=summary['safety_mode_counts'], phases=phases,
                policy_proposals=policy)


def main():
    cases = []
    originals = [json.loads(s) for s in (HISTORY/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    for seed in [1495656323, 1630784693]:
        x = next(x for x in originals if x['training_seed'] == seed and x['kind'] == 'checkpoint050_first')
        cases.append(summarize(HISTORY/x['run'], dict(
            branch='ORIGINAL_050', seed=seed, continuation_endpoint=0,
            policy_mode='deterministic', success=x['success'], task_s=x['task_s'],
            source_category='HISTORICAL_READ_ONLY_REFERENCE',
            fallback_event_counts=event_counts(x['fallback_events']))))
    rows = [json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    for x in rows:
        if x['mode'] != 'evaluation':
            continue
        directory=Path(x['run']).parent
        cfg=read(directory/'EFFECTIVE_CONFIG.json') or read(directory/'START.json',{}).get('config',{})
        split=cfg.get('evaluation_split','development')
        cases.append(summarize(Path(x['run']), dict(
            evaluation_split=split,evaluation_rng=cfg.get('evaluation_rng'),
            job_id=x['job_id'], branch=x['branch'], seed=x['seed'],
            continuation_endpoint=x['index']-1, policy_mode=x['policy_mode'],
            success=x['success'], task_s=x['task_s'],
            source_category='NEW_FROZEN_DEVELOPMENT_EVALUATION' if split=='development' else 'FINAL_HELDOUT_ACTION_STREAM_EVALUATION',
            fallback_event_counts=event_counts(x['fallback_events']))))
    atomic(ROOT/'audit/SAVED_ACTION_EXECUTION_DIAGNOSIS.json', dict(
        time_utc=now(), category='READ_ONLY_SAVED_EVIDENCE_NO_PHYSICS_NO_ADAM',
        source_sha256=sha(Path(__file__)), cases=cases,
        limitations=[
            'Proposal vectors are coordination requests, not torque commands; native/receipt audits independently establish actual physics execution.',
            'Statistics describe each realized trajectory, whose observations and decision count differ; they are not common-state causal parameter estimates.',
            'ESCAPE_ADMITTED is preserved verbatim as an audited event label, not reclassified as a safety failure.',
            'A failed planner request and an activation-validator rejection are different outcomes; neither demonstrates an executed collision.']))
    lines = ['# 保存轨迹上的动作与执行诊断', '',
             '只读原始和本轮冻结证据，零新增物理/Adam。完整准入结果、每phase的提议/执行向量与source SHA见同名JSON。协调动作不是torque；实际应用仍由既有native/receipt审计证明。', '',
             '|branch|seed|续训端点|mode|split/RNG|任务完成|RL决策|planner决策|接受/拒绝|applied receipts|raw分量clip比例|RETURN结果|',
             '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for x in cases:
        pc = x['policy_proposals']
        fraction = f"{pc['clipped_component_fraction']:.4f}" if pc else '旧轨迹无raw Gaussian'
        lines.append(f"|{x['branch']}|{x['seed']}|{x['continuation_endpoint']}|{x['policy_mode']}|{x.get('evaluation_split','historical')}/{x.get('evaluation_rng','—')}|{x['success']}|{x['RL_decisions']}|{x['planner_decisions']}|{x['accepted']}/{x['rejected']}|{x['applied_receipts']}|{fraction}|{x['phases']['RETURN']['outcomes']}|")
    lines += ['', '每条轨迹的访问状态及决策数不同，以上统计不等于相同状态下的策略参数效应。失败planner请求和activation-validator拒绝分别保留；ESCAPE_ADMITTED按原审计事件名保存，不把该标签直接判为安全失败。']
    (ROOT/'audit/SAVED_ACTION_EXECUTION_DIAGNOSIS.md').write_text('\n'.join(lines)+'\n')
    print('saved execution cases',len(cases),'new physics=0 Adam=0')


if __name__ == '__main__':
    main()
