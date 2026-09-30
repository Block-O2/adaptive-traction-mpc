"""Candidate scaling on real immutable deployable worker snapshots.

This is an offline same-epoch algorithm benchmark, not full live decision or
hardware qualification. Actual capture→activation is aggregated separately.
The existing hard screen, escape preparation and activation validator execute;
future-handoff fresh-state revalidation/queue transport/command write do not.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import sys
from time import perf_counter_ns
import numpy as np
from latency_tools import distribution


def benchmark_snapshot(payload, *, counts=(1,3,6,9,12), repeats=30,warmup=2,model=None):
    from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import (
        validate_activation,clearance_geometry_signature)
    from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
    rows=[]
    for count in counts:
        samples=[];errors=[];components={};feasible=[];legacy_counts=[]
        for repetition in range(repeats+warmup):
            start=perf_counter_ns()
            adaptive,arguments=pickle.loads(payload)
            restored=perf_counter_ns()
            planner=adaptive.planner
            if not hasattr(planner,'research_spec'):
                raise TypeError('expected actual ResearchPlanner snapshot')
            planner.research_spec['mode']='VALUE_RANK'
            if model is not None:planner.research_model=model
            planner.research_spec['candidate_offsets']=np.linspace(-.04,.06,count).tolist()
            try:
                decision=adaptive.decide(**arguments)
                selected=perf_counter_ns()
                if getattr(planner,'safe_fallback_enabled',False):
                    decision=prepare_decision(decision,planner,arguments['belief'])
                prepared=perf_counter_ns()
                validation=validate_activation(belief=arguments['belief'],request_sequence=arguments['belief'].sequence,
                    schedule=decision.executed.schedule,clearance=planner.scheduler.clearance_evaluator,
                    phase=arguments['phase'],request_phase=arguments['phase'],
                    remaining_s=arguments['phase_remaining_s'],reference_state=arguments['current_reference_state'],
                    certificate_geometry_at_request=clearance_geometry_signature(planner.scheduler.clearance_evaluator))
                finish=perf_counter_ns()
                if not validation['feasible']:raise ValueError('ORIGINAL_EPOCH_ACTIVATION_REJECTED')
                latency=decision.executed.execution_screen.get('research_latency',{})
                if repetition>=warmup:
                    samples.append((finish-restored)/1e6)
                    feasible.append(latency.get('feasible_count',0))
                    legacy_counts.append(len(decision.evaluations)-latency.get('candidate_count',0))
                    for name,value in latency.items():
                        if name.endswith('_ms'):components.setdefault(name,[]).append(value)
                    for name,value in {'snapshot_unpickle_ms':(restored-start)/1e6,
                                       'selected_to_escape_prepared_ms':(prepared-selected)/1e6,
                                       'original_epoch_activation_validation_ms':(finish-prepared)/1e6}.items():
                        components.setdefault(name,[]).append(value)
            except Exception as error:
                if repetition>=warmup:errors.append(dict(repetition=repetition-warmup,error=f'{type(error).__name__}:{error}',elapsed_ms=(perf_counter_ns()-restored)/1e6))
        rows.append(dict(candidate_count=count,measured_repeats=repeats,warmup=warmup,
                         admitted_completed_count=len(samples),failed_count=len(errors),failures=errors,
                         algorithm_through_original_epoch_reference_validation_ms=distribution(samples),
                         components_ms={k:distribution(v) for k,v in components.items()},
                         admitted_research_candidate_count=feasible,legacy_comparator_candidate_count=legacy_counts))
    return dict(schema='real_deployable_snapshot_candidate_scaling_v1',
                evidence_category='offline_same_epoch_algorithm_microbenchmark',
                snapshot_sha256=hashlib.sha256(payload).hexdigest(),rows=rows,
                full_live_decision_latency_measured=False,
                excluded=['capture/observation construction','worker transport and main scheduling',
                          'fresh-state future-handoff revalidation','low-level command construction/write'],
                caveat='snapshot replay repeats the SAME real observed state; no trajectory or robustness claim',
                runtime_assurance_status='RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS')


def main():
    root=Path(__file__).resolve().parents[4]
    for relative in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src',
                     'stages/stage3_full3d/src','stages/stage5_personalized_motion_learning/scripts/high_rom_v1'):
        sys.path.insert(0,str(root/relative))
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--repeats',type=int,default=30)
    parser.add_argument('--model',type=Path,help='actual trained model; otherwise replay frozen snapshot model')
    parser.add_argument('--counts',default='1,3,6,9,12');args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    payload=args.snapshot.read_bytes()
    metadata=json.loads(args.snapshot.with_suffix('.json').read_text())
    if hashlib.sha256(payload).hexdigest()!=metadata['sha256']:raise ValueError('snapshot hash mismatch')
    model=None
    if args.model:
        from value_models import load_model
        model=load_model(args.model)
    result=benchmark_snapshot(payload,counts=tuple(map(int,args.counts.split(','))),repeats=args.repeats,model=model)
    result['model_file_sha256']=hashlib.sha256(args.model.read_bytes()).hexdigest() if args.model else None
    result['model_source']='explicit actual trained model' if args.model else 'original frozen snapshot model, possibly zero/no learner'
    result['snapshot_source_metadata']=metadata
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps([{k:row[k] for k in ('candidate_count','admitted_completed_count','failed_count','algorithm_through_original_epoch_reference_validation_ms')} for row in result['rows']],indent=2))


if __name__=='__main__':main()
