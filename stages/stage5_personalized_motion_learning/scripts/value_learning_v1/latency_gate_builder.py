"""Prospective simulation-pilot computation gate from actual measured evidence.

This never declares hardware/real-time qualification. Marginal percentiles are
never added and called a measured end-to-end percentile. First stationary
pattern selection uses the strict source-age ceiling; moving continuation has
the tighter certified bridge-fork opportunity. Missing evidence stays pending.
"""
import argparse
import hashlib
import json
from pathlib import Path
from evidence_io import read_json,file_sha


def _row(replays,*,first,legacy_limit,count):
    for replay in replays:
        is_first=(replay.get('captured_phase')=='OUTBOUND' and replay.get('captured_path_index')==0
                  and not replay.get('captured_continuation_committed'))
        if is_first!=first:continue
        if first and not replay.get('captured_reference_stationary'):continue
        for row in replay.get('rows',[]):
            observed=row.get('observed_research_candidate_count',[])
            if row.get('legacy_candidate_limit')==legacy_limit and row.get('requested_research_candidate_count')==count:
                if observed and all(x==count for x in observed):return row
    return None


def _inside(row,ceiling):
    if not row or row.get('failed_count') or not row.get('admitted_completed_count'):return False
    measured=row.get('algorithm_through_original_epoch_reference_validation_ms',{})
    return measured.get('maximum') is not None and measured['maximum']<ceiling


def build_gate(cpu,offline,replays,*,legacy_limit=1,first_count=4,normal_profile=None,normal_run=None):
    first=_row(replays,first=True,legacy_limit=legacy_limit,count=first_count)
    continuation=_row(replays,first=False,legacy_limit=legacy_limit,count=1)
    # These derive from the existing registered architecture, not a new 5 ms rule.
    budgets={'strict_original_source_age_ceiling_ms':100.,'moving_bridge_duration_ms':40.,
             'observed_certified_moving_fork_progress_ms':35.,
             'first_stationary_pattern_selection_ceiling_ms':100.,
             'moving_continuation_opportunity_ms':35.}
    ranking=offline.get('ranking_gate')=='PASS'
    cpu_measured=all(cpu.get('models',{}).get(k) for k in ('ridge_full','mlp_full'))
    algorithm_fits=_inside(first,100.) and _inside(continuation,35.)
    benchmark_hashes=set(cpu.get('model_file_sha256',{}).values())
    replay_hashes={replay.get('model_file_sha256') for replay in replays}
    model_match=bool(len(replay_hashes)==1 and None not in replay_hashes and replay_hashes<=benchmark_hashes)
    clean=bool(normal_profile and normal_run and normal_run.get('status')=='VALID'
               and normal_run.get('active_model_file_immutable_during_rep')
               and not (normal_run.get('pattern') or {}).get('capture_snapshot_dir')
               and normal_profile.get('source_complete')
               and normal_profile.get('snapshot_capture_extra_io_source_count')==0)
    normal_model=(normal_run or {}).get('model_sha256_at_start')
    if clean and (normal_model not in benchmark_hashes or normal_model not in replay_hashes):clean=False
    config=(normal_run or {}).get('pattern') or {}
    if clean and (config.get('mode')!='VALUE_PATTERN' or config.get('legacy_candidate_limit')!=legacy_limit
                  or len(config.get('proposal_descriptors',[]))!=first_count):clean=False
    roles=(normal_profile or {}).get('clean_role_timings_ms',{})
    first_live=roles.get('first_pattern_selection',{}).get('capture_to_activation_ms',{})
    moving_live=roles.get('moving_continuation',{}).get('capture_to_activation_ms',{})
    live_measured=bool(first_live.get('count') and moving_live.get('count'))
    observed_live_fits=bool(clean and live_measured and first_live['maximum']<100. and moving_live['maximum']<35.)
    ready=bool(ranking and cpu_measured and model_match and algorithm_fits and clean)
    if not (first and continuation and cpu_measured):status='PENDING_ACTUAL_COMPUTATION_EVIDENCE'
    elif not ranking:status='OFFLINE_RANKING_GATE_FAILED'
    elif not model_match:status='MODEL_PROVENANCE_MISMATCH'
    elif not algorithm_fits:status='ALGORITHM_PROFILE_EXCEEDS_PRELIMINARY_OPPORTUNITY'
    elif not clean:status='PENDING_CLEAN_NORMAL_MODEL_RUN'
    elif observed_live_fits:status='SCIENTIFIC_PILOT_COMPUTATION_PLAUSIBLE_OBSERVED_HOST_SPANS_WITHIN_OPPORTUNITY'
    else:status='SCIENTIFIC_PILOT_COMPUTATION_PLAUSIBLE_WALL_BUDGET_UNDEMONSTRATED'
    return dict(schema='value_learning_prospective_computation_gate_v1',status=status,
        ready_for_small_scientific_pilot=ready,architecture_budget_ms=budgets,
        selected_configuration=dict(legacy_candidate_limit=legacy_limit,first_pattern_candidate_count=first_count,
                                    committed_continuation_candidate_count=1),
        offline_ranking_gate=offline.get('ranking_gate'),actual_cpu_models_measured=cpu_measured,
        immutable_model_hashes_match=model_match,algorithm_profile_within_preliminary_ceilings=algorithm_fits,
        clean_normal_model_rollout_validated=clean,clean_normal_model_run_id=(normal_run or {}).get('run_id'),
        first_pattern_algorithm_profile=first,continuation_algorithm_profile=continuation,
        measured_clean_role_timings_ms=roles,observed_full_host_spans_within_architecture_opportunity=observed_live_fits,
        first_decision_context='stationary initial OUTBOUND boundary; moving-first use must be reevaluated against its actual fork',
        model_scope='MATCHED timing-context Q under declared continuation; native absolute-objective extension excluded from fitting',
        hardware_realtime_qualified=False,
        runtime_assurance_status='RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS',
        limitations=['Offline replay includes original-epoch activation validation, excludes live queue, fresh-state handoff checks and command write',
                     'Algorithm opportunity is plausible-path evidence, not full latency deadline compliance',
                     'Scientific Simulation freezes producer epoch; host profile cannot establish wall-causal execution',
                     'No marginal p95/p99 sums are reported as observed end-to-end quantiles',
                     'A late ranking result must be dropped and existing baseline/fallback architecture remains authoritative',
                     'No actor/distillation need is inferred from model-only timing; inspect full candidate scheduling first'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cpu',type=Path,required=True)
    parser.add_argument('--offline',type=Path,required=True);parser.add_argument('--replay',type=Path,action='append',required=True)
    parser.add_argument('--normal-profile',type=Path);parser.add_argument('--normal-run',type=Path)
    parser.add_argument('--legacy-limit',default='1');parser.add_argument('--first-count',type=int,default=4)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    normal_profile=read_json(args.normal_profile) if args.normal_profile else None
    normal_run=read_json(args.normal_run/'rollout_result.json' if args.normal_run.is_dir() else args.normal_run) if args.normal_run else None
    limit=None if args.legacy_limit=='default' else int(args.legacy_limit)
    result=build_gate(read_json(args.cpu),read_json(args.offline),[read_json(p) for p in args.replay],
                      legacy_limit=limit,first_count=args.first_count,normal_profile=normal_profile,normal_run=normal_run)
    paths=[args.cpu,args.offline,*args.replay]+([args.normal_profile] if args.normal_profile else [])
    if args.normal_run:paths.append(args.normal_run/'rollout_result.json' if args.normal_run.is_dir() else args.normal_run)
    result['source_original_content_sha256']={str(p):file_sha(p) for p in paths}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status','ready_for_small_scientific_pilot','observed_full_host_spans_within_architecture_opportunity')},indent=2))


if __name__=='__main__':main()
