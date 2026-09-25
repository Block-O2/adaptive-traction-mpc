"""Serial, budgeted local MuJoCo recovery runs; never starts model workers.

The optional detailed trace is evaluation-only and invalidates timing claims.
Every admitted run is charged before execution, including exceptions/stops.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

import mujoco
import numpy as np
import scipy

import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime_module
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1
from run_rigid_table_reference_development_v1 import run_one, ASSEMBLY

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parents[1]
DOC = STAGE / 'docs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1'
OUT = STAGE / 'results/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1'


def dump(path, obj):
    path=Path(path);temp=path.with_name(path.name+'.pending')
    with temp.open('w') as f:
        f.write(json.dumps(runtime_module._jsonable(obj),indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def source_manifest(*, persist=True):
    original = json.loads((OUT / 'startup_snapshot/MANIFEST.json').read_text())
    paths = set(original['files'])
    paths.add(str(Path(__file__).relative_to(ROOT)))
    paths.add(str((STAGE/'scripts/generate_autonomous_qualification_v1.py').relative_to(ROOT)))
    paths.add('stages/stage3_full3d/models/ur10e_torque.xml')
    paths.update(str(p.relative_to(ROOT)) for p in
                 (STAGE / 'vendor/rokae_ros2_xmatecr12/meshes').glob('*.stl'))
    paths.update(str(p.relative_to(ROOT)) for root in [STAGE/'src', STAGE/'configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1']
                 for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    blobs = OUT / 'source_blobs'
    if persist:
        blobs.mkdir(exist_ok=True)
    hashes = {}
    for p in sorted(paths):
        if not (ROOT / p).is_file():
            continue
        content = (ROOT / p).read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        if persist and not (blobs / sha).exists():
            (blobs / sha).write_bytes(content)
        hashes[p] = sha
    return hashes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', required=True)
    p.add_argument('--case-keys', nargs='+')
    p.add_argument('--development-case-file', type=Path,
                   help='One retained exposed case, development only; never qualification evidence')
    p.add_argument('--qualification-bundle', type=Path)
    p.add_argument('--resume-qualification', action='store_true')
    p.add_argument('--diagnostic', action='store_true')
    p.add_argument('--profile', action='store_true')
    p.add_argument('--diagnostic-delay-s', type=float)
    p.add_argument('--delay-trigger-task-s', type=float, default=3.020)
    p.add_argument('--controller-config', type=Path)
    args = p.parse_args()
    if args.diagnostic_delay_s is not None and not (0 < args.diagnostic_delay_s <= .100 and 0 <= args.delay_trigger_task_s < 30):
        raise ValueError("diagnostic delay must be finite positive <=100ms, trigger inside original task")
    timing_diagnostic = args.diagnostic or args.profile or args.diagnostic_delay_s is not None
    options = {} if args.controller_config is None else json.loads(args.controller_config.read_text())
    bundle = seal = None
    qualification_contract = None
    checkpoint = None
    if args.qualification_bundle is not None:
        from generate_autonomous_qualification_v1 import verify_bundle,atomic,CONTRACT,reserve_execution
        if timing_diagnostic or args.case_keys or args.development_case_file is not None:
            raise ValueError("qualification requires the complete fixed bundle and no timing diagnostics")
        bundle,seal=verify_bundle(args.qualification_bundle)
        if args.controller_config is not None and options != seal['controller_options']:
            raise ValueError("qualification controller options differ from frozen seal")
        options=seal['controller_options'];qualification_contract=CONTRACT
        args.case_keys=[r['case_key'] for r in bundle['rows']]
        checkpoint={'contract':CONTRACT,'batch':bundle['batch'],'rows':{k:{'status':'NOT_EXECUTED'} for k in args.case_keys}}
    elif not args.case_keys:
        raise ValueError("development case keys are required")
    if args.development_case_file is not None:
        if len(args.case_keys) != 1:
            raise ValueError('one explicit development case key is required')
        exposed_case = json.loads(args.development_case_file.read_text())
        if exposed_case['case_key'] != args.case_keys[0]:
            raise ValueError('development file/key mismatch')
    if args.resume_qualification and bundle is None:
        raise ValueError("resume flag is only for the same reserved qualification execution")
    directory = OUT / args.candidate
    execution_lock=None
    if bundle is not None:
        execution_lock=reserve_execution(args.qualification_bundle,directory,bundle,resume=args.resume_qualification)
    try:
        directory.mkdir(exist_ok=bundle is None or args.resume_qualification)
        if checkpoint is not None:
            if args.resume_qualification:
                saved=directory/"qualification_execution_checkpoint.json"
                if not saved.exists():
                    raise ValueError('Missing original qualification checkpoint; cannot silently reconstruct consumption')
                checkpoint=json.loads(saved.read_text())
                if checkpoint['contract']!=CONTRACT or checkpoint['batch']!=bundle['batch'] or list(checkpoint['rows'])!=args.case_keys:
                    raise ValueError('qualification checkpoint identity/order changed')
            atomic(directory/"qualification_execution_checkpoint.json",checkpoint)
        for key in args.case_keys:
            if checkpoint is not None and checkpoint['rows'][key]['status']!='NOT_EXECUTED':
                previous=checkpoint['rows'][key]
                if previous['status']=='STARTED':
                    saved=directory/(key+'_result.json')
                    if saved.exists():
                        previous=json.loads(saved.read_text())
                    else:
                        previous={**previous,'status':'INTERRUPTED','abort_reason':'Prior charged execution has no final result; prefix retained; no replacement retry'}
                        dump(saved,previous)
                    checkpoint['rows'][key]=previous;atomic(directory/'qualification_execution_checkpoint.json',checkpoint)
                continue
            state = json.loads((DOC / 'STATE.json').read_text())
            if state['status'] != 'CONTINUE':
                raise RuntimeError('campaign is not active: ' + state['status'])
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(state['started_at_utc'])).total_seconds()
            if elapsed >= state['budget']['maximum_active_seconds'] or state['budget']['new_rollouts'] >= state['budget']['maximum_new_rollouts']:
                state['status'] = 'PAUSED_RESOURCE'
                dump(DOC / 'STATE.json', state)
                raise RuntimeError('shared campaign budget exhausted')
            if (DOC / 'STOP').exists():
                state['status'] = 'STOPPED_BY_USER'
                dump(DOC / 'STATE.json', state)
                raise RuntimeError('campaign STOP file exists')
            output = directory / key
            if output.exists():
                raise FileExistsError(output)
            if bundle is not None:
                # Verify immutable source/options/cases/evidence again before each run.
                verify_bundle(args.qualification_bundle)
                slot=next(r for r in bundle['rows'] if r['case_key']==key)
                if not slot['valid']:
                    result={'case_key':key,'status':'PRECHECK_REJECTED','abort_reason':slot.get('v2_validity',{}).get('reason',slot['status']),
                            'evidence_category':'fresh_registered_precheck','batch':bundle['batch'],'started_rollout':False}
                    dump(directory/(key+'_result.json'),result);checkpoint['rows'][key]=result
                    atomic(directory/'qualification_execution_checkpoint.json',checkpoint)
                    print(json.dumps(result),flush=True)
                    continue
                case_path=Path(slot['case_path'])
            else:
                case_path = (args.development_case_file if args.development_case_file is not None
                             else ASSEMBLY / 'cases' / (key + '.json'))
            assert case_path.is_file(), case_path
            state['budget']['new_rollouts'] += 1
            state['budget']['elapsed_wall_seconds_conservative'] = elapsed
            state['status'] = 'CONTINUE'
            state['candidate'] = args.candidate
            state['current_run'] = str(output.relative_to(ROOT))
            dump(DOC / 'STATE.json', state)
            if checkpoint is not None:
                checkpoint['rows'][key]={'case_key':key,'status':'STARTED','started_rollout':True,
                    'campaign_rollout_charge':state['budget']['new_rollouts'],'started_at_utc':datetime.now(timezone.utc).isoformat()}
                atomic(directory/'qualification_execution_checkpoint.json',checkpoint)
            provenance = {'command': sys.argv, 'case_sha256': hashlib.sha256(case_path.read_bytes()).hexdigest(),
                          'source_sha256': source_manifest(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                          'diagnostic': args.diagnostic, 'profile': args.profile,
                          'raw_timing_measurement_eligible': not timing_diagnostic,
                          'timing_eligible': False,
                          'timing_eligibility_note': 'Whole-session wall/physics coupling and independent timing audit remain required; raw ages alone do not qualify.',
                          'environment': {'python': sys.version, 'platform': platform.platform(), 'mujoco': mujoco.__version__,
                                          'numpy': np.__version__, 'scipy': scipy.__version__}}
            provenance['controller_options'] = options
            if bundle is not None:
                provenance.update(qualification_contract=qualification_contract,qualification_batch=bundle['batch'],
                    qualification_bundle_sha256=hashlib.sha256((args.qualification_bundle/'manifest.json').read_bytes()).hexdigest(),
                    candidate_seal_sha256=bundle['candidate_seal_sha256'])
            dump(directory / (key + '_provenance.json'), provenance)
            rows = []
            injected_delays = []
            from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
            original_tick = WallPhysicsSession.next_control_tick
            def delayed_tick(wall):
                phase=wall.phase_records[-1]
                if not injected_delays and phase["phase"] == "TASK" and float(wall.plant.data.time)-phase["start_physics_s"] >= args.delay_trigger_task_s:
                    event={"scope":"development timing-neighbor stress, excluded from qualification timing", "physics_s":float(wall.plant.data.time),
                           "task_elapsed_s":float(wall.plant.data.time)-phase["start_physics_s"],
                           "requested_host_delay_s":args.diagnostic_delay_s,"host_start_ns":time.monotonic_ns()}
                    injected_delays.append(event)
                    time.sleep(args.diagnostic_delay_s)
                    event["host_finish_ns"]=time.monotonic_ns()
                return original_tick(wall)
            if args.diagnostic_delay_s is not None:
                WallPhysicsSession.next_control_tick=delayed_tick
            deadline_monotonic = time.monotonic() + state['budget']['maximum_active_seconds'] - elapsed
            def stop_check():
                if time.monotonic() >= deadline_monotonic:
                    raise RuntimeError('CAMPAIGN_RESOURCE_DEADLINE')
                if (DOC / 'STOP').exists():
                    raise RuntimeError('CAMPAIGN_STOPPED_BY_USER')
            runtime_capture = {'stop_check': stop_check}
            original = runtime_module._execute_interval
            def observed(rt, **kw):
                interface, measurement, candidate = kw['interface'], kw['measurement'], kw['candidate']
                plant = rt['plant']
                truth = plant.observe()
                envelope = RigidTableReferenceEnvelopeV1(rt['model'].geometry)
                mapped = kw.get('mapped_override')
                if mapped is None:
                    mapped = rt['contract'].prepare(candidate)
                    kw['mapped_override'] = mapped
                target = mapped.execution_target
                row = {'time_s': float(truth.time_s), 'context': candidate.execution_context.value,
                       'q_ref': candidate.q_waypoint_rad, 'dq_ref': candidate.dq_waypoint_rad_s,
                       'state_hat': kw['observation'].as_array(),
                       'state_true_evaluation_only': np.r_[truth.human_q_rad, truth.human_dq_rad_s],
                       'interface_hat': asdict(interface),
                       'interface_true_evaluation_only': asdict(plant._evaluate_current_interface()),
                       'robot_attachment_p': measurement.attachment_position_m,
                       'robot_attachment_rotation': measurement.attachment_rotation_matrix,
                       'robot_attachment_v': measurement.attachment_velocity_m_s,
                       'target_human_p': target.human_cuff_target.world_from_cuff.translation,
                       'target_robot_p': target.robot_cuff_target.world_from_cuff.translation,
                       'target_robot_rotation': target.robot_cuff_target.world_from_cuff.rotation,
                       'reference_margins': envelope.margins(candidate.q_waypoint_rad),
                       'measured_sleeve_gap_m': envelope.measured_sleeve_gap(interface.human_position_world_m, interface.human_rotation_world)}
                # Copy before stepping: some fields refer to mutable plant buffers.
                row = runtime_module._jsonable(row)
                rows.append(row)
                command, execution = original(rt, **kw)
                row['applied_command'] = runtime_module._jsonable(asdict(command))
                row['execution'] = runtime_module._jsonable(execution)
                return command, execution
            if args.diagnostic:
                runtime_module._execute_interval = observed
            start = time.perf_counter()
            execution_error=None
            try:
                if args.profile:
                    import cProfile
                    profiler = cProfile.Profile()
                    profiler.enable()
                result = run_one(case_path, output, autonomous_recovery_options=options,
                                 runtime_capture=runtime_capture, qualification_contract=qualification_contract)
            except BaseException as error:
                execution_error=error
                result={'case_key':key,'status':'EXECUTION_EXCEPTION','abort_reason':repr(error),'started_rollout':True}
            finally:
                runtime_module._execute_interval = original
                WallPhysicsSession.next_control_tick = original_tick
                if injected_delays:
                    dump(directory / (key + "_delay_injection.json"), injected_delays)
                try:
                    runtime_module.persist_runtime_artifacts(output, runtime_capture)
                except BaseException as error:
                    execution_error=execution_error or error
                    result={'case_key':key,'status':'PERSISTENCE_EXCEPTION','abort_reason':repr(error),'started_rollout':True}
                if args.profile:
                    profiler.disable()
                    profiler.dump_stats(str(directory / (key + '.prof')))
                if rows:
                    dump(directory / (key + '_diagnostic.json'), rows)
            result['wall_seconds'] = time.perf_counter() - start
            result['output'] = str(output.relative_to(ROOT))
            result['candidate'] = args.candidate
            result['evidence_category'] = ('formal_fresh_autonomous_recovery_v1' if bundle is not None else
                                          'development_diagnostic' if timing_diagnostic else 'development')
            dump(directory / (key + '_result.json'), result)
            if checkpoint is not None:
                checkpoint['rows'][key]=result
                atomic(directory/'qualification_execution_checkpoint.json',checkpoint)
            with (DOC / 'EXPERIMENT_LOG.jsonl').open('a') as f:
                f.write(json.dumps(result) + '\n')
            print(json.dumps(result), flush=True)
            if execution_error is not None:
                raise execution_error
    finally:
        if execution_lock is not None:
            execution_lock.close()


if __name__ == '__main__':
    main()
