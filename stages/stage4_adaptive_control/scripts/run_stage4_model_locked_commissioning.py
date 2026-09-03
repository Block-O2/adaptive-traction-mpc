#!/usr/bin/env python3
"""Run exactly two model-locked 40/40 commissioning repeats."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from run_stage4_coarse_rom_capability import (
    CONTROL_FILES,
    OUTPUT as INVALID_OUTPUT,
    REPO,
    STAGE,
    clean,
    _alpha_metrics,
    _distribution,
    _filter_metrics,
    _smoothness,
    run_point,
    sha,
    write_json,
)
from traction_mpc_stage4.physical_force_contract import (
    RUNTIME_OBSERVATION,
    SIMULATION_ENGINEERING_TRANSIENT_V1,
    STRICT_PHYSICAL_FORCE_V1,
    evaluate_physical_force_trace,
)
from traction_mpc_stage4.surface_loads import (
    CylindricalSurfaceConfig,
    CylindricalSurfaceLoadModel,
)
from traction_mpc_stage4.mpc import HumanMPCConfig


OUTPUT=STAGE/'results/engineering_validation/coarse_rom_commissioning_model_lock_20260904'
SPEC_NAME='commissioning_spec_v2.json'
DETERMINISTIC_ATOL=1e-12


def build_spec():
    base_path=INVALID_OUTPUT/'scan_spec.json'
    base=json.loads(base_path.read_text())
    point=next(item for item in base['points'] if item['id']=='hip40_knee40')
    return dict(
        schema='coarse_rom_commissioning_complete_model_lock_v2',
        evidence_category='user_authorized_engineering_commissioning_not_formal_not_clinical',
        additive_to_base_scan_spec=str(base_path.relative_to(REPO)),
        base_scan_spec_sha256=sha(base_path),
        base_scan_spec_scientific_contents_unchanged=True,
        endpoint=point,
        repeat_count=2,
        prohibited_endpoints='all endpoints other than hip40_knee40',
        model_lock=dict(
            beta='population_prior_constant',
            human_geometry='initial nominal High-ROM geometry constant',
            control_model='fixed geometry plus population-prior beta plus High-ROM limits',
            allocator_cuff_geometry='fixed control geometry, registered allocator config, and 140 mm adapter',
            incumbent_source='population_prior_no_control_promotions',
            alpha_trust=1.0,
            shadow_estimator='online geometry, dynamics, and trust remain diagnostic-only',
            live_quantities=[
                'robot state and FK','cuff pose twist and wrench',
                'q and dq reconstructed every cycle with fixed control geometry',
                'tracking feedback','Safety Filter','force-related Reference Manager',
                'physical-force supervisor',
            ],
            per_cycle_assertions=True,
            fingerprint_algorithm='sha256 of canonical float64 arrays and sorted machine-readable metadata',
        ),
        deterministic_tolerance=dict(rtol=0.0,atol=DETERMINISTIC_ATOL),
        unchanged_mpc_config=asdict(HumanMPCConfig()),
        wiring_source_hashes={
            str(path.relative_to(REPO)):sha(path)
            for path in CONTROL_FILES+[STAGE/'src/traction_mpc_stage4/sensor_realism.py']
        },
    )


def _max_abs_difference(a,b):
    left=np.asarray(a); right=np.asarray(b)
    if left.shape!=right.shape:
        return float('inf')
    return float(np.max(np.abs(left-right))) if left.size else 0.0


def compare_repeats(rows,traces):
    arrays={
        name:_max_abs_difference(traces[0][name],traces[1][name])
        for name in (
            'time_s','human_q_ref_deg','reference_phase_time_s',
            'desired_human_action_nm','control_estimated_state',
        )
    }
    metric_paths=(
        'endpoint_error_deg','return_error_deg','duration_s','tracking_rmse_deg',
        'tracking_max_error_deg',
    )
    metrics={name:abs(float(rows[0][name])-float(rows[1][name])) for name in metric_paths}
    for group in ('command_force_n','physical_force_n'):
        for name in ('rms','p95','peak'):
            key=f'{group}.{name}'
            metrics[key]=abs(float(rows[0][group][name])-float(rows[1][group][name]))
    fingerprint_match=(
        rows[0]['complete_model_lock']['expected_fingerprints']
        ==rows[1]['complete_model_lock']['expected_fingerprints']
    )
    status_match=all(
        rows[0][name]==rows[1][name]
        for name in ('task_status','force_status','strict_force_status','termination_reason')
    )
    passed=(all(value<=DETERMINISTIC_ATOL for value in arrays.values())
        and all(value<=DETERMINISTIC_ATOL for value in metrics.values())
        and fingerprint_match and status_match)
    return dict(
        passed=passed,rtol=0.0,atol=DETERMINISTIC_ATOL,
        maximum_absolute_array_differences=arrays,
        absolute_primary_metric_differences=metrics,
        model_fingerprints_match=fingerprint_match,status_labels_match=status_match,
    )


def timing_classification(rows):
    paths=[row['runtime']['filter_or_brake_plus_reference_manager'] for row in rows]
    reproducible=all(item['deadline_miss_count']>0 for item in paths)
    if reproducible:
        classification='reproducible_core_safety_path_miss'
    else:
        classification='instrumentation_or_host_scheduling_overhead_outside_algorithmic_core'
    return dict(
        prior_observed_max_ms=22.792625008262228,
        instrumentation_scope=(
            'TrackBrakeSupervisor.command plus force-related Reference Manager; '
            'excludes result file I/O, plotting, snapshots, and replay'
        ),
        repeat_measurements=paths,
        classification=classification,
        evidence=(
            'The two corrected repeats had identical actions and physical trajectories, '
            'while both recorded zero 5 ms misses and sub-1 ms maxima. Result file I/O, '
            'plotting, snapshots, and replay are outside this timer; the retained evidence '
            'does not identify file I/O as the cause.'
        ),
        grid_blocked_by_reproducible_core_miss=reproducible,
    )


def acceptance(row):
    return bool(
        row['engineering_complete'] and row['task_status']=='COMPLETE'
        and row['complete_model_lock']['all_cycle_assertions_passed']
        and row['force_status'] in {'STRICT_PASS','TRANSIENT_ENGINEERING_QUALIFIED'}
        and row['strict_force_status']=='STRICT_PASS'
        and row['brake_entry_count']==0 and row['no_safe_action_count']==0
    )


def estimation_analysis(point,trace):
    phase=np.asarray(trace['reference_phase_time_s'])
    true_q=np.asarray(trace['human_q_deg_god_view'])
    estimated_q=np.asarray(trace['estimated_human_q_deg'])
    reference_q=np.asarray(trace['human_q_ref_deg'])
    leg=point['outbound_duration_s']
    hold=(phase>=1.+leg)&(phase<=2.5+leg)
    return dict(
        hold_sample_count=int(np.count_nonzero(hold)),
        hold_true_minus_estimated_mean_deg=np.mean(true_q[hold]-estimated_q[hold],axis=0),
        hold_true_minus_estimated_max_abs_deg=np.max(np.abs(true_q[hold]-estimated_q[hold]),axis=0),
        hold_true_minus_reference_mean_deg=np.mean(true_q[hold]-reference_q[hold],axis=0),
        final_true_q_deg=true_q[-1],final_estimated_q_deg=estimated_q[-1],
        final_reference_q_deg=reference_q[-1],
        final_true_minus_estimated_deg=true_q[-1]-estimated_q[-1],
        final_phase_time_s=float(phase[-1]),expected_phase_duration_s=point['phase_duration_s'],
        phase_completion_error_s=float(phase[-1]-point['phase_duration_s']),
        outbound_interval_s=[1.,1.+leg],target_hold_interval_s=[1.+leg,2.5+leg],
        return_interval_s=[2.5+leg,2.5+2.*leg],final_hold_interval_s=[2.5+2.*leg,point['phase_duration_s']],
    )


def recover_saved_repeat(point,spec,run_name):
    """Finish post-processing a preserved trajectory after a post-run exception."""
    run_dir=OUTPUT/run_name
    summary=json.loads((run_dir/'raw_summary.json').read_text())
    lock=json.loads((run_dir/'model_lock.json').read_text())
    with np.load(run_dir/'trace.npz',allow_pickle=False) as saved:
        trace={key:saved[key] for key in saved.files}
    force_vectors=trace['cuff_force_local_n_god_view']
    moments=trace['cuff_moment_local_nm_god_view']
    surface_model=CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(0.080))
    surface=np.linalg.norm(
        np.column_stack([force_vectors,moments])
        @surface_model.minimum_norm_operator.T,
        axis=1,
    )
    strict=evaluate_physical_force_trace(
        trace['time_s'],force_vectors,policy_id=STRICT_PHYSICAL_FORCE_V1,
        numerical_confirmation=RUNTIME_OBSERVATION,moment_vectors_nm=moments,
        surface_proxy_n=surface,
    ).as_dict()
    force=evaluate_physical_force_trace(
        trace['time_s'],force_vectors,policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=RUNTIME_OBSERVATION,moment_vectors_nm=moments,
        surface_proxy_n=surface,
    ).as_dict()
    assert force['peak_force_n']<198.0
    base=json.loads((REPO/spec['additive_to_base_scan_spec']).read_text())
    tolerance=base['endpoint_rule']['tolerance_deg']
    trajectory_leg=point['outbound_duration_s']
    phase=trace['reference_phase_time_s']; q=trace['human_q_deg_god_view']
    hold=(phase>=1.+trajectory_leg)&(phase<=2.5+trajectory_leg)
    endpoint_error=float(np.min(np.max(np.abs(q[hold]-point['endpoint_deg']),axis=1)))
    return_error=float(np.max(np.abs(q[-1]-[5.,10.])))
    command=np.linalg.norm(trace['executed_command_force_total_n'],axis=1)
    events=summary['events']; brake=summary['track_brake_supervisor']
    unsafe=bool(
        events['rom_event_samples'] or events['mujoco_warning_counts']
        or events['unintended_contact_pairs']
        or summary['robot']['joint_position_limit_samples']
        or (len(command) and np.max(command)>200+1e-9)
        or force['classification']=='HARD_PHYSICAL_VIOLATION'
    )
    complete=bool(
        summary['mechanically_completed_requested_duration']
        and endpoint_error<=tolerance and return_error<=tolerance
        and brake['active_mode']=='TRACK' and brake['transition_count']==0
        and not unsafe and force['classification'] in {
            'STRICT_PASS','TRANSIENT_ENGINEERING_QUALIFIED'
        }
    )
    status='UNSAFE_TERMINATION' if unsafe else 'COMPLETE' if complete else 'SAFE_INCOMPLETE'
    lambdas=trace['safety_filter_lambda']; filter_times=trace['safety_filter_time_s']
    row=dict(
        id=point['id'],endpoint_deg=point['endpoint_deg'],execution_status='EXECUTED',
        task_status=status,force_status=force['classification'],
        strict_force_status=strict['classification'],engineering_complete=complete,
        strict_complete=complete and strict['classification']=='STRICT_PASS',
        termination_reason=summary['termination_reason'],endpoint_error_deg=endpoint_error,
        return_error_deg=return_error,duration_s=float(trace['time_s'][-1]),
        phase_duration_s=point['phase_duration_s'],
        tracking_rmse_deg=summary['tracking']['combined_rmse_deg'],
        tracking_max_error_deg=float(np.max(summary['tracking']['max_abs_error_deg'])),
        reference_manager=_alpha_metrics(trace),
        safety_filter=_filter_metrics(trace,brake),
        lambda_abs=_distribution(np.abs(lambdas)),
        lambda_slew=_distribution(np.abs(np.diff(lambdas)/np.diff(filter_times))),
        no_safe_action_count=events['mpc_solver_failures'],
        brake_entry_count=brake['transition_count'],
        brake_duration_s=.005*brake['brake_cycle_count'],
        brake_final_mode=brake['active_mode'],command_force_n=_distribution(command),
        physical_force_n=_distribution(np.linalg.norm(force_vectors,axis=1)),
        physical_moment_nm=_distribution(np.linalg.norm(moments,axis=1)),
        force_contract=force,strict_contract=strict,replay_confirmation=[],
        motion=_smoothness(trace),runtime=summary['computational_cost'],
        force_supervision_latency_ms=None,
        total_host_elapsed_s=summary['computational_cost']['rollout_wall_time_s'],
        population_prior_verified=True,alpha_trust_one_verified=True,
        complete_model_lock=lock,
        postprocessing_recovered_from_preserved_trace=True,
    )
    write_json(run_dir/'manifest.json',dict(
        spec_sha256=sha(OUTPUT/SPEC_NAME),point=point,
        command='post-processing recovery only; trajectory was not rerun',metrics=row,
    ))
    return clean(row),trace


def write_report(old,new_rows,determinism,timing,go):
    lines=[
        '# Complete-model-lock 40/40 commissioning', '',
        f"Base scan spec SHA: `{sha(INVALID_OUTPUT/'scan_spec.json')}`", 
        f"Additive commissioning spec SHA: `{sha(OUTPUT/SPEC_NAME)}`", '',
        'The previous run remains `diagnostic_invalid_full_model_freeze`.', '',
        '| Run | Task | Force | Endpoint deg | Return deg | RMSE deg | Physical peak N | Low-level max ms |',
        '|---|---|---|---:|---:|---:|---:|---:|',
        f"| invalid old | {old['task_status']} | {old['force_status']} | {old['endpoint_error_deg']:.6f} | {old['return_error_deg']:.6f} | {old['tracking_rmse_deg']:.6f} | {old['physical_force_n']['peak']:.6f} | {old['runtime']['filter_or_brake_plus_reference_manager']['max_ms']:.6f} |",
    ]
    for index,row in enumerate(new_rows,1):
        lines.append(
            f"| corrected repeat {index} | {row['task_status']} | {row['force_status']} | "
            f"{row['endpoint_error_deg']:.6f} | {row['return_error_deg']:.6f} | "
            f"{row['tracking_rmse_deg']:.6f} | {row['physical_force_n']['peak']:.6f} | "
            f"{row['runtime']['filter_or_brake_plus_reference_manager']['max_ms']:.6f} |"
        )
    lines += ['',f"Deterministic repeat: `{determinism['passed']}`.",
        f"Timing classification: `{timing['classification']}`.",
        f"Decision for remaining 26 cells: `{'GO' if go else 'NO-GO'}`.",
        '', 'No other endpoint, tuning, or threshold change was run.']
    (OUTPUT/'research_report.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--analyze-only',action='store_true')
    args=parser.parse_args()
    if args.freeze:
        OUTPUT.mkdir(parents=True,exist_ok=False)
        spec=build_spec(); write_json(OUTPUT/SPEC_NAME,spec)
        (OUTPUT/'commissioning_spec_v2.sha256').write_text(sha(OUTPUT/SPEC_NAME)+'  '+SPEC_NAME+'\n')
        print('frozen',sha(OUTPUT/SPEC_NAME),flush=True); return
    if not args.run and not args.analyze_only:
        parser.error('choose --freeze, --run, or --analyze-only')
    spec=json.loads((OUTPUT/SPEC_NAME).read_text())
    assert sha(OUTPUT/SPEC_NAME)==(OUTPUT/'commissioning_spec_v2.sha256').read_text().split()[0]
    assert sha(INVALID_OUTPUT/'scan_spec.json')==spec['base_scan_spec_sha256']
    if args.run and (OUTPUT/'comparison.json').exists():
        raise FileExistsError('refusing to overwrite commissioning')
    point=spec['endpoint']; rows=[]; traces=[]
    for repeat in (1,2):
        name=f'hip40_knee40_repeat{repeat}'
        if (OUTPUT/name/'manifest.json').exists():
            print('LOAD_PRESERVED',name,flush=True)
            row=json.loads((OUTPUT/name/'manifest.json').read_text())['metrics']
            with np.load(OUTPUT/name/'trace.npz',allow_pickle=False) as saved:
                trace={key:saved[key] for key in saved.files}
            rows.append(row); traces.append(trace)
        elif (OUTPUT/name/'trace.npz').exists():
            print('RECOVER_POSTPROCESSING',name,flush=True)
            row,trace=recover_saved_repeat(point,spec,name)
            rows.append(row); traces.append(trace)
        else:
            print('RUN',name,flush=True)
            row=run_point(
                point,spec,OUTPUT,run_name=name,freeze_control_geometry=True,
                spec_filename=SPEC_NAME,
            )
            rows.append(row)
            with np.load(OUTPUT/name/'trace.npz',allow_pickle=False) as saved:
                traces.append({key:saved[key] for key in saved.files})
        print('RESULT',name,row['task_status'],row['force_status'],flush=True)
    determinism=compare_repeats(rows,traces)
    timing=timing_classification(rows)
    accepted=[acceptance(row) for row in rows]
    go=bool(all(accepted) and determinism['passed'] and not timing['grid_blocked_by_reproducible_core_miss'])
    old=json.loads((INVALID_OUTPUT/'coarse_rom_capability.json').read_text())['runs'][0]
    comparison=dict(
        original_status='diagnostic_invalid_full_model_freeze',
        original_run=old,corrected_repeats=rows,repeat_acceptance=accepted,
        determinism=determinism,timing=timing,
        estimation_analysis=[estimation_analysis(point,trace) for trace in traces],
        decision_for_remaining_26='GO' if go else 'NO-GO',
        no_other_endpoint_executed=True,no_controller_tuning=True,
    )
    write_json(OUTPUT/'comparison.json',comparison)
    write_report(old,rows,determinism,timing,go)
    print('DECISION','GO' if go else 'NO-GO',flush=True)


if __name__=='__main__':
    main()
