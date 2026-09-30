"""Read-only latency and schedule opportunity analysis of actual artifacts."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from latency_tools import distribution

COMPONENTS=('acquisition_to_request_ms','snapshot_ms','queue_ms','queue_and_snapshot_ms',
            'compute_ms','worker_to_main_scheduling_ms','validation_scheduling_ms',
            'validation_and_command_construction_ms','validation_to_activation_ms')
RESEARCH_COMPONENTS=('legacy_planner_ms','proposal_ms','feasibility_scheduling_ms','feature_ms',
                     'inference_ms','selection_ms','inference_selection_ms','decision_total_ms')


def analyze_artifacts(paths):
    requests=[];decisions=[];bridges=[];sources=[];instrumented=[]
    for path in paths:
        path=Path(path)
        if path.is_dir(): path=path/'runtime_artifacts.json'
        artifact=json.loads(path.read_text())
        task=[dict(row,source_path=str(path)) for row in artifact.get('requests',[]) if row.get('stage')=='TASK']
        requests.extend(task)
        lookup={row['request_id']:row for row in task}
        task_decisions=artifact.get('task_decisions',[])
        if not task_decisions and (path.parent/'summary.json').exists():
            task_decisions=json.loads((path.parent/'summary.json').read_text()).get('decisions',[])
        decisions.extend(task_decisions)
        bridges.extend(artifact.get('future_handoff_bridges',[]))
        for decision in task_decisions:
            for candidate in decision.get('evaluations',[]):
                if candidate.get('label')!=decision.get('executed_label'):continue
                research=candidate.get('execution_screen',{}).get('research_latency')
                if research:
                    instrumented.append(dict(research,request_id=decision.get('timing_request_id'),
                        source_path=str(path),request_timing=lookup.get(decision.get('timing_request_id'))))
        sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            execution_mode=artifact.get('execution_mode'),task_requests=len(task)))
    activated=[row for row in requests if row.get('outcome')=='ACTIVATED']
    intervals=[];durations=[];counts=[]
    for decision in decisions:
        for candidate in decision.get('evaluations',[]):
            if candidate.get('label')==decision.get('executed_label'):
                schedule=candidate.get('schedule') or {}
                duration=schedule.get('duration_s')
                if duration is not None:durations.append(duration)
        counts.append(decision.get('candidate_count',0))
    for path in sorted({row['source_path'] for row in requests}):
        group=[row for row in requests if row['source_path']==path]
        for a,b in zip(group,group[1:]):
            delta=b['source_sample_time_s']-a['source_sample_time_s']
            if delta>0:intervals.append(delta)
    scaling={}
    for count in sorted({r.get('candidate_count') for r in instrumented if r.get('candidate_count') is not None}):
        # Each instrumented row was joined within its source run above. Local
        # request ids must never be cross-joined between different artifacts.
        rows=[]
        for research in instrumented:
            if research.get('candidate_count')!=count:continue
            timing=research['request_timing']
            if timing and timing.get('activation_age_ms') is not None:rows.append(timing['activation_age_ms'])
        scaling[str(count)]={'joined_full_age_ms':distribution(rows),
                            'research_rows':sum(r.get('candidate_count')==count for r in instrumented),
                            'candidate_count_semantics':'research proposals; original legacy comparisons also execute and remain in full latency'}
    return dict(schema='value_learning_actual_artifact_latency_v1',
        evidence_category='descriptive_scientific_simulation_host_profile',source_artifacts=sources,
        task_request_count=len(requests),task_outcomes=dict(Counter(r.get('outcome') for r in requests)),
        sample_capture_to_actual_activation_ms=distribution(r['activation_age_ms'] for r in activated if r.get('activation_age_ms') is not None),
        sample_capture_to_reference_validated_ms=distribution((r['validation_finish_ns']-r['sensor_capture_ns'])/1e6
            for r in activated if r.get('validation_finish_ns') is not None),
        all_outcomes_disposition_age_ms=distribution(r['disposition_age_ms'] for r in requests if r.get('disposition_age_ms') is not None),
        lifecycle_components_ms={name:distribution(r[name] for r in requests if r.get(name) is not None) for name in COMPONENTS},
        research_instrumentation_count=len(instrumented),research_components_ms={name:distribution(r[name] for r in instrumented if r.get(name) is not None) for name in RESEARCH_COMPONENTS},
        high_level_source_sample_interval_s=distribution(intervals),selected_schedule_duration_s=distribution(durations),
        moving_bridge_duration_s=distribution(r['bridge_duration_s'] for r in bridges if r.get('bridge_duration_s') is not None),
        moving_fork_commit_progress_s=distribution(r['fallback_commit_progress_s'] for r in bridges if r.get('fallback_commit_progress_s') is not None),
        candidate_count_distribution=dict(Counter(counts)),
        research_candidate_count_distribution=dict(Counter(r.get('candidate_count') for r in instrumented)),
        candidate_count_scaling=scaling,
        caveats=['sensor capture precedes observation ready, so capture-to-validation is a conservative broader boundary',
                 'activation validation is later than candidate feasibility/scheduling; they must not be conflated',
                 'Scientific Simulation freezes physics during producer compute, host latency is profiling only',
                 'older artifacts have no learned feature/proposal/inference decomposition; absent fields are not zero'],
        runtime_assurance_status='RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifact',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    result=analyze_artifacts(args.artifact);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('task_request_count','sample_capture_to_actual_activation_ms','high_level_source_sample_interval_s','selected_schedule_duration_s','moving_bridge_duration_s','moving_fork_commit_progress_s')},indent=2))


if __name__=='__main__':main()
