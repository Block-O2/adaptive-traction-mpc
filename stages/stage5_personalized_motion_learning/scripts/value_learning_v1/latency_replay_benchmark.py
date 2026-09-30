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
from time import perf_counter_ns,monotonic_ns
import numpy as np
from latency_tools import distribution
import gzip
from evidence_io import read_json,file_sha


def configure_replay(planner,*,count,legacy_limit=None,mode=None):
    """A pure proposal-count ablation; never bypass the inherited screens."""
    if count<1:raise ValueError('research candidate count must be positive')
    if legacy_limit is not None and legacy_limit<1:raise ValueError('legacy limit must be positive or default')
    spec=planner.research_spec
    selected_mode=mode or spec.get('mode','VALUE_RANK')
    if selected_mode not in ('VALUE_RANK','VALUE_PATTERN'):
        selected_mode='VALUE_RANK'
    spec['mode']=selected_mode
    if legacy_limit is None:spec.pop('legacy_candidate_limit',None)
    else:spec['legacy_candidate_limit']=legacy_limit
    if selected_mode=='VALUE_PATTERN':
        descriptors=spec.get('proposal_descriptors',[])
        if not descriptors:raise ValueError('VALUE_PATTERN replay requires actual captured proposal descriptors')
        if count>len(descriptors):
            raise ValueError('requested pattern count exceeds captured actual descriptor set')
        spec['proposal_descriptors']=descriptors[:count]
    else:
        spec['candidate_offsets']=[0.] if count==1 else np.linspace(-.04,.06,count).tolist()
    return selected_mode


def benchmark_snapshot(payload, *, counts=(1,3,6), legacy_limits=(None,1,3),
                       repeats=30,warmup=2,model=None,mode=None):
    from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import (
        validate_activation,clearance_geometry_signature)
    from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
    if repeats<1 or warmup<0:raise ValueError('invalid benchmark repetition count')
    frozen_planner,frozen_arguments=pickle.loads(payload)
    frozen_spec=frozen_planner.planner.research_spec
    rows=[]
    for legacy_limit,count in ((limit,count) for limit in legacy_limits for count in counts):
        samples=[];errors=[];components={};feasible=[];legacy_counts=[]
        observed_counts=[];observed_modes=[];cold=None
        for repetition in range(repeats+warmup):
            start=perf_counter_ns()
            adaptive,arguments=pickle.loads(payload)
            restored=perf_counter_ns()
            planner=adaptive.planner
            if not hasattr(planner,'research_spec'):
                raise TypeError('expected actual ResearchPlanner snapshot')
            if model is not None:planner.research_model=model
            try:
                selected_mode=configure_replay(planner,count=count,legacy_limit=legacy_limit,mode=mode)
                observed_modes.append(selected_mode)
                workload_start=perf_counter_ns()
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
                validation_finish_ns=monotonic_ns()
                if not validation['feasible']:raise ValueError('ORIGINAL_EPOCH_ACTIVATION_REJECTED')
                latency=decision.executed.execution_screen.get('research_latency',{})
                if repetition==0:cold=(finish-workload_start)/1e6
                if repetition>=warmup:
                    exact={}
                    for name,event in (('adapter_start_to_original_epoch_validated_ms','adapter_start_ns'),
                                       ('first_feature_start_to_original_epoch_validated_ms','first_feature_start_ns'),
                                       ('reference_selected_to_original_epoch_validated_ms','reference_selected_ns')):
                        if latency.get(event) is not None:
                            delta=(validation_finish_ns-latency[event])/1e6
                            if delta<0:raise ValueError('incompatible absolute monotonic timestamps')
                            exact[name]=delta
                    samples.append((finish-workload_start)/1e6)
                    feasible.append(latency.get('feasible_count',0))
                    legacy_counts.append(len(decision.evaluations)-latency.get('candidate_count',0))
                    observed_counts.append(latency.get('candidate_count',0))
                    for name,value in latency.items():
                        if name.endswith('_ms'):components.setdefault(name,[]).append(value)
                    for name,value in {'snapshot_unpickle_ms':(restored-start)/1e6,
                                       'adapter_return_to_escape_prepared_ms':(prepared-selected)/1e6,
                                       'original_epoch_activation_validation_ms':(finish-prepared)/1e6}.items():
                        components.setdefault(name,[]).append(value)
                    for name,delta in exact.items():components.setdefault(name,[]).append(delta)
            except Exception as error:
                if repetition>=warmup:errors.append(dict(repetition=repetition-warmup,error=f'{type(error).__name__}:{error}',elapsed_ms=(perf_counter_ns()-restored)/1e6))
        rows.append(dict(candidate_count=count,requested_research_candidate_count=count,
                         legacy_candidate_limit=legacy_limit,legacy_limit_label='default' if legacy_limit is None else str(legacy_limit),
                         observed_research_modes=sorted(set(observed_modes)),
                         observed_research_candidate_count=observed_counts,
                         first_call_original_epoch_validated_ms=cold,
                         measured_repeats=repeats,warmup=warmup,
                         admitted_completed_count=len(samples),failed_count=len(errors),failures=errors,
                         algorithm_through_original_epoch_reference_validation_ms=distribution(samples),
                         components_ms={k:distribution(v) for k,v in components.items()},
                         admitted_research_candidate_count=feasible,legacy_comparator_candidate_count=legacy_counts))
    return dict(schema='real_deployable_snapshot_candidate_scaling_v1',
                evidence_category='offline_same_epoch_algorithm_microbenchmark',
                snapshot_sha256=hashlib.sha256(payload).hexdigest(),rows=rows,
                captured_phase=getattr(frozen_arguments['phase'],'value',str(frozen_arguments['phase'])),
                captured_path_index=getattr(frozen_planner.planner,'research_phase_index',None),
                captured_research_mode=frozen_spec.get('mode'),
                captured_continuation_committed=bool(frozen_spec.get('committed_descriptor')),
                captured_reference_velocity_rad_s=np.asarray(frozen_arguments['current_reference_state'])[2:].tolist(),
                captured_reference_stationary=bool(not np.any(np.abs(np.asarray(frozen_arguments['current_reference_state'])[2:])>1e-12)),
                legacy_limits=list(legacy_limits),research_counts=list(counts),
                full_live_decision_latency_measured=False,
                excluded=['capture/observation construction','worker transport and main scheduling',
                          'snapshot unpickle and benchmark proposal configuration',
                          'fresh-state future-handoff revalidation','low-level command construction/write'],
                caveat='snapshot replay repeats the SAME real observed state; pattern scaling only changes first uncommitted OUTBOUND descriptor proposals; committed/terminal decisions may retain one actual candidate; no trajectory or robustness claim',
                runtime_assurance_status='RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS')


def main():
    root=Path(__file__).resolve().parents[4]
    for relative in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src',
                     'stages/stage3_full3d/src','stages/stage5_personalized_motion_learning/scripts/high_rom_v1'):
        sys.path.insert(0,str(root/relative))
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--repeats',type=int,default=30)
    parser.add_argument('--model',type=Path,help='actual trained model; otherwise replay frozen snapshot model')
    parser.add_argument('--counts',default='1,3,6')
    parser.add_argument('--legacy-limits',default='default,1,3')
    parser.add_argument('--mode',choices=('VALUE_RANK','VALUE_PATTERN'),help='otherwise preserve captured value mode')
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    logical_snapshot=Path(str(args.snapshot)[:-3]) if args.snapshot.suffix=='.gz' else args.snapshot
    archive_snapshot=Path(str(logical_snapshot)+'.gz')
    physical_snapshot=logical_snapshot if logical_snapshot.exists() else archive_snapshot
    if physical_snapshot.suffix=='.gz':
        with gzip.open(physical_snapshot,'rb') as stream:payload=stream.read()
    else:payload=physical_snapshot.read_bytes()
    metadata_path=logical_snapshot.with_suffix('.json')
    metadata=read_json(metadata_path)
    if hashlib.sha256(payload).hexdigest()!=metadata['sha256']:raise ValueError('snapshot hash mismatch')
    model=None
    if args.model:
        from value_models import load_model
        model=load_model(args.model)
    limits=tuple(None if x=='default' else int(x) for x in args.legacy_limits.split(','))
    result=benchmark_snapshot(payload,counts=tuple(map(int,args.counts.split(','))),legacy_limits=limits,
                              repeats=args.repeats,model=model,mode=args.mode)
    result['model_file_sha256']=hashlib.sha256(args.model.read_bytes()).hexdigest() if args.model else None
    result['model_source']='explicit actual trained model' if args.model else 'original frozen snapshot model, possibly zero/no learner'
    result['snapshot_source_metadata']=metadata
    result['snapshot_physical_path']=str(physical_snapshot)
    result['snapshot_gzip_sha256']=file_sha(archive_snapshot) if archive_snapshot.exists() else None
    result['snapshot_metadata_original_content_sha256']=file_sha(metadata_path)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps([{k:row[k] for k in ('candidate_count','legacy_limit_label','admitted_completed_count','failed_count','algorithm_through_original_epoch_reference_validation_ms')} for row in result['rows']],indent=2))


if __name__=='__main__':main()
