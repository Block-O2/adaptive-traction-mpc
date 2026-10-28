"""Saved causal sensor interval dose by phase; original metric unchanged."""
from pathlib import Path
from collections import defaultdict
import json
import math
from research_common import ROOT, atomic, read, sha, now

HISTORY = ROOT.parent/'rl_b_autonomous_replication_v1'


def phase_dose(run, expected):
    path = run/'env/episode_0001/online_tick_evidence.jsonl'
    phases = defaultdict(lambda:dict(duration_s=0., J_F_N_s=0., J_M_Nm_s=0.))
    previous = None
    for s in path.read_text().splitlines():
        row = json.loads(s)
        if previous is not None:
            dt = row['task_s']-previous['task_s']
            assert dt >= 0
            phase = phases[previous['phase']]
            phase['duration_s'] += dt
            phase['J_F_N_s'] += math.sqrt(sum(v*v for v in previous['measured_force_world_n']))*dt
            phase['J_M_Nm_s'] += math.sqrt(sum(v*v for v in previous['measured_moment_world_nm']))*dt
        previous = row
    checks = dict(
        original_JF_sum=abs(sum(v['J_F_N_s'] for v in phases.values())-expected['JF'])<1e-7,
        original_JM_sum=abs(sum(v['J_M_Nm_s'] for v in phases.values())-expected['JM'])<1e-7,
        original_TASK_duration=abs(sum(v['duration_s'] for v in phases.values())-expected['task_s'])<1e-7)
    assert all(checks.values()),checks
    return dict(run=str(run), source=str(path), source_sha256=sha(path),
                phases=dict(phases), checks=checks, pass_=all(checks.values()))


def main():
    originals = [json.loads(s) for s in (HISTORY/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    parents = {}
    for seed in [1495656323,1630784693]:
        x = next(x for x in originals if x['training_seed']==seed and x['kind']=='checkpoint050_first')
        parents[seed] = phase_dose(HISTORY/x['run'],x)
    cases = []
    for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines():
        x = json.loads(s)
        if x['mode']!='evaluation':
            continue
        evidence = phase_dose(Path(x['run']),x)
        original = parents[x['seed']]
        comparable = x['success'] and x['policy_mode']=='deterministic'
        comparable &= all(abs(evidence['phases'].get(k,{}).get('duration_s',0)-v['duration_s'])<1e-7
                          for k,v in original['phases'].items())
        deltas = None
        if comparable:
            deltas = {k:{metric:evidence['phases'][k][metric]-v[metric]
                         for metric in ['duration_s','J_F_N_s','J_M_Nm_s']}
                      for k,v in original['phases'].items()}
        directory=Path(x['run']).parent
        cfg=read(directory/'EFFECTIVE_CONFIG.json') or read(directory/'START.json',{}).get('config',{})
        cases.append(dict(evaluation_split=cfg.get('evaluation_split','development'),evaluation_rng=cfg.get('evaluation_rng'),job_id=x['job_id'], branch=x['branch'], seed=x['seed'],
            endpoint=x['index']-1, mode=x['policy_mode'], success=x['success'],
            task_s=x['task_s'], integral_scope=x['integral_scope'],
            same_parent_complete_phase_duration_comparable=bool(comparable),
            difference_from_parent= deltas, evidence=evidence))
    atomic(ROOT/'audit/PHASE_DOSE_ATTRIBUTION.json',dict(time_utc=now(),
        source_sha256=sha(Path(__file__)), category='READ_ONLY_SAVED_CAUSAL_INTERVAL_INTEGRATION',
        parent_references=parents, cases=cases,
        definition='Original 5ms observed force/moment norms, left quadrature over actual executed interval duration; zero-duration notifications own zero dose. This is not a new 0.25ms force quadrature or a modified formal scorer.',
        restriction='Per-phase differences locate the descriptive dose tradeoff on complete equal-duration nominal mean tasks; they do not establish a unique optimizer cause or original B/H150 live matched qualification.'))
    print('phase-attributed frozen trajectories',len(cases),'all sums match original metrics; new physics=0 Adam=0')


if __name__=='__main__':
    main()
