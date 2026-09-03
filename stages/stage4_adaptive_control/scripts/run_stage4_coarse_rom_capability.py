#!/usr/bin/env python3
"""Frozen, user-authorized engineering capability scan; never tunes a controller."""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict
import hashlib
import json
import csv
import math
from pathlib import Path
import subprocess
import time as clock

import mujoco
import numpy as np

from run_stage4_phase5_high_rom_system_pilot import (
    HIGH_ROM_HUMAN, DEFAULT_MATRIX, _alpha_metrics, _filter_metrics, _smoothness,
    _distribution,
)
from traction_mpc_stage3.coupled import SUSPENDED_SEATED_LIKE_SCENARIO
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF, base_from_attachment_target
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage3.ik import _initial_solution, _solve_candidates, _pose_residual
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff, quintic_progress
from traction_mpc_stage4.reference import TeachingWaypoint
from traction_mpc_stage4.trajectory_excitation import trajectory_case, trajectory_waypoints
from traction_mpc_stage4.confidence_execution import UnifiedReferenceManager
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.measurement import measurement_case_dict
from traction_mpc_stage4.mpc import HumanSpaceMPC, HumanMPCConfig
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.report_validation import load_report_validation_matrix, measurement_case
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant, run_sensor_realism_case
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor
from traction_mpc_stage4.physical_force_contract import (
    evaluate_physical_force_trace, SIMULATION_ENGINEERING_TRANSIENT_V1,
    STRICT_PHYSICAL_FORCE_V1, RUNTIME_OBSERVATION, FINE_REPLAY_CONFIRMED,
    EXACT_REPLAY_UNAVAILABLE, HARD_PHYSICAL_VIOLATION, NUMERICALLY_UNRESOLVED,
)
from traction_mpc_stage4.surface_loads import CylindricalSurfaceConfig, CylindricalSurfaceLoadModel

STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[1]
OUTPUT = STAGE / 'results/engineering_validation/coarse_rom_capability_20260904'
SOURCE = STAGE / ('results/controller_validation/trajectory_generalization/demo_sources/'
    'nominal_reference__moderate_rom_23s__seed44104/trusted_adaptive_mpc/trusted_adaptive_mpc_trace.npz')
CONTROL_FILES = [
    STAGE/'src/traction_mpc_stage4'/name for name in (
        'mpc.py', 'cuff_allocator.py', 'executable_command.py', 'safety_filter.py',
        'confidence_execution.py', 'track_brake.py', 'online_trust.py')
] + [REPO/'stages/stage3_full3d/src/traction_mpc_stage3'/name
     for name in ('coupled.py', 'executable_command.py', 'human.py')]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_sha(*values):
    digest=hashlib.sha256()
    for value in values:
        if isinstance(value,np.ndarray):
            array=np.ascontiguousarray(value)
            digest.update(str(array.dtype).encode()); digest.update(str(array.shape).encode())
            digest.update(array.tobytes())
        else:
            digest.update(json.dumps(clean(value),sort_keys=True,separators=(',',':')).encode())
    return digest.hexdigest()


def geometry_values(geometry):
    return np.concatenate([
        np.asarray(geometry.origin_world_m),np.asarray(geometry.plane_x_world),
        np.asarray(geometry.joint_axis_world),np.asarray(geometry.plane_z_world),
        np.asarray(geometry.hip_plane_m),[float(geometry.thigh_length_m)],
        np.asarray(geometry.knee_to_cuff_in_cuff_m),
    ])


class CompleteModelLockMonitor:
    """Per-cycle assertions for the opt-in nominal commissioning model lock."""
    def __init__(self,allocator):
        self.allocator=allocator; self.expected=None; self.records=[]; self.states=[]
        self.shadow_geometry_hashes=[]

    def __call__(self,estimator,model,estimated_state):
        beta_hash=value_sha(np.asarray(model.beta,dtype=float))
        geometry_hash=value_sha(geometry_values(model.geometry))
        model_hash=value_sha(
            np.asarray(model.beta,dtype=float),geometry_values(model.geometry),
            asdict(model.rom_human),
        )
        allocator_hash=value_sha(
            geometry_values(model.geometry),asdict(self.allocator.config),
            ENGINEERING_ATTACHMENT_FROM_CUFF.translation,
            ENGINEERING_ATTACHMENT_FROM_CUFF.rotation,
        )
        incumbent_source='population_prior_no_control_promotions'
        incumbent_hash=value_sha(incumbent_source)
        current=dict(
            beta=beta_hash,human_geometry=geometry_hash,control_model=model_hash,
            allocator_cuff_geometry=allocator_hash,incumbent_source=incumbent_hash,
        )
        np.testing.assert_array_equal(
            np.asarray(model.beta),estimator.dynamic_identifier.population_prior,
        )
        assert estimator.freeze_control_geometry
        assert not estimator.apply_qualified_model
        assert not estimator.control_promotions
        assert model.geometry is estimator.control_geometry
        assert np.all(np.isfinite(estimated_state))
        if self.expected is None:
            np.testing.assert_array_equal(
                estimator.geometry_identifier.last_valid,
                estimator.geometry_identifier.prior,
            )
            self.expected=current
        assert current==self.expected
        self.records.append(current)
        self.states.append(np.asarray(estimated_state,dtype=float).copy())
        self.shadow_geometry_hashes.append(
            value_sha(geometry_values(estimator.geometry_identifier.geometry))
        )

    def diagnostics(self):
        fields=tuple(self.expected or {})
        unique={name:sorted({item[name] for item in self.records}) for name in fields}
        states=np.asarray(self.states)
        return dict(
            assertion_count=len(self.records),all_cycle_assertions_passed=True,
            expected_fingerprints=self.expected,unique_observed_fingerprints=unique,
            shadow_geometry_unique_fingerprints=sorted(set(self.shadow_geometry_hashes)),
            shadow_geometry_changed=len(set(self.shadow_geometry_hashes))>1,
            live_estimated_q_range_deg=(np.ptp(np.degrees(states[:,:2]),axis=0) if len(states) else np.zeros(2)),
            live_estimated_dq_range_deg_s=(np.ptp(np.degrees(states[:,2:]),axis=0) if len(states) else np.zeros(2)),
        )

    def save_cycles(self,path):
        fields=tuple(self.expected or {})
        np.savez_compressed(
            path,cycle_index=np.arange(len(self.records),dtype=int),
            assertion_pass=np.ones(len(self.records),dtype=bool),
            estimated_state=np.asarray(self.states),
            shadow_geometry_fingerprint=np.asarray(self.shadow_geometry_hashes),
            **{name+'_fingerprint':np.asarray([item[name] for item in self.records]) for name in fields},
        )


def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(clean(value), indent=2, sort_keys=True, allow_nan=False)+'\n')


class NormalizedTrajectory:
    def __init__(self, point):
        self.point = point
        self.name = point['id']
        self.endpoint_deg = tuple(point['endpoint_deg'])
        self.leg = point['outbound_duration_s']
        self.duration = point['phase_duration_s']

    @property
    def waypoints(self):
        return tuple(TeachingWaypoint(t, tuple(q), label) for t,q,label in (
            (0., [5.,10.], 'initial_hold'), (1.,[5.,10.],'outbound'),
            (1.+self.leg,self.endpoint_deg,'target_hold'),
            (2.5+self.leg,self.endpoint_deg,'return'),
            (2.5+2*self.leg,[5.,10.],'final_hold'),
            (self.duration,[5.,10.],'end')))

    def reference(self, phase):
        t=float(np.clip(phase,0.,self.duration)); initial=np.radians([5.,10.])
        delta=np.radians(self.endpoint_deg)-initial
        if t <= 1.: q,dq,ddq=initial,np.zeros(2),np.zeros(2)
        elif t < 1.+self.leg:
            s,ds,dds=quintic_progress((t-1.)/self.leg)
            q,dq,ddq=initial+delta*s,delta*ds/self.leg,delta*dds/self.leg**2
        elif t <= 2.5+self.leg: q,dq,ddq=initial+delta,np.zeros(2),np.zeros(2)
        elif t < 2.5+2*self.leg:
            s,ds,dds=quintic_progress((t-2.5-self.leg)/self.leg)
            q,dq,ddq=initial+delta*(1-s),-delta*ds/self.leg,-delta*dds/self.leg**2
        else: q,dq,ddq=initial,np.zeros(2),np.zeros(2)
        return CuffPoseReference(q,dq,ddq,_world_from_cuff(q))


def build_spec():
    knots=trajectory_waypoints(trajectory_case('moderate_rom_23s'))
    vmax=np.zeros(2); amax=np.zeros(2)
    for a,b in zip(knots[:-1],knots[1:]):
        delta=np.abs(np.asarray(b.q_deg)-np.asarray(a.q_deg)); dt=b.time_s-a.time_s
        vmax=np.maximum(vmax,1.875*delta/dt)
        amax=np.maximum(amax,(10/math.sqrt(3))*delta/dt**2)
    with np.load(SOURCE,allow_pickle=False) as z:
        ref=z['human_q_ref_deg']; q=z['human_q_deg_god_view']
        goal=np.max(ref,axis=0)
        hold=np.all(np.abs(ref-goal)<1e-8,axis=1)
        endpoint_tolerance=float(np.max(np.abs(q[hold]-ref[hold])))
    points=[]
    for hip,knee in [(h,k) for h in (40,60,80,100,120) for k in (40,60,80,100,120)]+[(75,90),(90,120)]:
        delta=np.abs(np.array([hip,knee])-[5,10])
        leg=float(max(np.max(1.875*delta/vmax),np.max(np.sqrt((10/math.sqrt(3))*delta/amax))))
        duration=3.5+2*leg
        points.append(dict(id=f'hip{hip}_knee{knee}',endpoint_deg=[hip,knee],
            outbound_duration_s=leg,return_duration_s=leg,target_hold_s=1.5,
            initial_hold_s=1.,final_hold_s=1.,phase_duration_s=duration,
            maximum_simulation_duration_s=math.ceil(2*duration/.005)*.005))
    return dict(schema='coarse_rom_capability_v1',evidence_category='user_authorized_engineering_not_formal_not_clinical',
        checkpoint=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        controller='fixed_population_prior_pre_gamma_rigid',scenario='suspended_high_rom',
        scenario_implementation=SUSPENDED_SEATED_LIKE_SCENARIO,measurement_seed=44104,
        mpc_config=asdict(HumanMPCConfig()),alpha_trust=1.,alpha_force_behavior='unchanged',
        adapter_translation_m=ENGINEERING_ATTACHMENT_FROM_CUFF.translation,
        human_rom_deg=[0.,125.],physical_policy=SIMULATION_ENGINEERING_TRANSIENT_V1,
        strict_policy=STRICT_PHYSICAL_FORCE_V1,command_limit_n=200.,
        contract_sha256=sha(STAGE/'configs/simulation_engineering_transient_v1.json'),
        trajectory=dict(equation='q=q0+(qgoal-q0)*(10u^3-15u^4+6u^5); return reversed',
            start_deg=[5.,10.],velocity_limit_deg_s=vmax,acceleration_limit_deg_s2=amax,
            source='moderate_rom_23s analytic maxima across all quintic segments',
            source_suite_sha256=sha(STAGE/'configs/stage4_trajectory_excitation_suite.json'),
            shortest_leg_formula='max_i(1.875*abs(delta_i)/v_i, sqrt((10/sqrt(3))*abs(delta_i)/a_i))',
            timeout_formula='ceil((phase_duration/minimum_existing_alpha_0.5)/0.005)*0.005'),
        endpoint_rule=dict(tolerance_deg=endpoint_tolerance,source=str(SOURCE.relative_to(REPO)),
            source_sha256=sha(SOURCE),derivation='maximum absolute joint error during nominal moderate reference target hold',
            test='minimum max-absolute endpoint error in target hold and final return error <= retained tolerance'),
        tracking_quality_band=None,tracking_quality_note='continuous metrics only; no nominal/degraded band',
        precheck=dict(path_samples_per_outbound=101,ik_residual_limit=1e-8,
            note='deterministic continuous IK branch check; sampled feasibility, not proof over all configurations'),
        replay=dict(timestep_s=.00025,prehistory_s=.100,maximum_local_duration_s=.250,
            command_semantics='exact saved integration state and recorded issued torque schedule, not a new controller rollout',
            unavailable_or_open_result=NUMERICALLY_UNRESOLVED),
        commissioning='hip40_knee40 must be engineering-complete before remaining 26',
        controller_hashes={str(p.relative_to(REPO)):sha(p) for p in CONTROL_FILES},points=points)


class ForceMonitor:
    """Causal bounded-window supervision using the frozen shared pure evaluator."""
    def __init__(self):
        self.samples=deque(); self.stop=False; self.cost=[]
    def update(self,t,f):
        begin=clock.perf_counter(); self.samples.append((float(t),np.asarray(f).copy()))
        while len(self.samples)>2 and self.samples[1][0]<t-.101: self.samples.popleft()
        forces=np.array([x[1] for x in self.samples])
        if np.any(np.linalg.norm(forces,axis=1)>200):
            r=evaluate_physical_force_trace([x[0] for x in self.samples],forces,
                policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,numerical_confirmation=RUNTIME_OBSERVATION)
            self.stop=self.stop or r.runtime_stop_required
        self.cost.append(1000*(clock.perf_counter()-begin)); return self.stop


class CapturePlant(SensorBoundaryStage4Plant):
    def __init__(self,human):
        super().__init__(human,attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO)
        self.history=deque(maxlen=102); self.episodes=[]; self.active=None; self.commands=[]
    def apply_executable_command(self,preview):
        super().apply_executable_command(preview)
        self.commands.append(dict(time_s=float(self.data.time),ctrl=self.data.ctrl.copy(),
            force=self.last_force.copy(),moment=self.last_moment.copy(),torque=self.last_joint_torque.copy()))
    def step(self):
        state=np.empty(mujoco.mj_stateSize(self.model,mujoco.mjtState.mjSTATE_INTEGRATION))
        mujoco.mj_getState(self.model,self.data,state,mujoco.mjtState.mjSTATE_INTEGRATION)
        self.history.append((float(self.data.time),state,self.neutral_robot_q.copy()))
        obs=super().step(); norm=float(np.linalg.norm(obs.cuff_force_vector_n))
        if norm>=198 and self.active is None:
            t,s,n=self.history[0]
            self.active=dict(start_time_s=t,state=s.copy(),neutral=n.copy(),trigger_time_s=obs.time_s,
                end_time_s=obs.time_s,closed=False)
            self.episodes.append(self.active)
        if self.active is not None:
            self.active['end_time_s']=float(obs.time_s)
            if norm<198:
                self.active['closed']=True; self.active=None
        return obs


def prechecks(spec):
    plant=CapturePlant(HIGH_ROM_HUMAN); robot=plant._ik_robot
    target=base_from_attachment_target(_world_from_cuff(np.radians([5,10])),attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF)
    initial=_initial_solution(robot,target); results={}
    for point in spec['points']:
        previous=initial.copy(); residuals=[]; contacts=[]; failure=None
        for u in np.linspace(0,1,spec['precheck']['path_samples_per_outbound']):
            q=np.radians(np.array([5,10])+u*(np.array(point['endpoint_deg'])-[5,10]))
            target=base_from_attachment_target(_world_from_cuff(q),attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF)
            candidates=_solve_candidates(robot,target,[previous],periodic_reference=previous)
            error,solution=min(candidates,key=lambda x:x[0]); residuals.append(error)
            if error>=1e-8: failure='continuous_ik_branch_not_verified'; break
            previous=solution; robot.set_configuration(solution)
            contacts.extend(robot.contact_pairs())
            if contacts: failure='robot_self_contact'; break
            if np.any(q<0) or np.any(q>np.radians(125)): failure='human_rom'; break
        results[point['id']]=dict(qualified=failure is None,reason=failure,
            sampled_ik_max_residual=max(residuals),contacts=contacts,samples_checked=len(residuals))
        print('precheck',point['id'],results[point['id']]['qualified'],flush=True)
    return results


def replay_episode(episode,commands,dt):
    plant=CapturePlant(HIGH_ROM_HUMAN); plant.model.opt.timestep=dt
    mujoco.mj_setState(plant.model,plant.data,episode['state'],mujoco.mjtState.mjSTATE_INTEGRATION)
    plant.neutral_robot_q=episode['neutral'].copy()
    mujoco.mj_forward(plant.model,plant.data)
    times=[]; forces=[]; moments=[]; ci=0
    steps=int(round((episode['end_time_s']-episode['start_time_s'])/dt))
    for _ in range(steps):
        while ci+1<len(commands) and commands[ci+1]['time_s']<=plant.data.time+1e-10: ci+=1
        cmd=commands[ci]
        if cmd['time_s']<=plant.data.time+1e-10:
            plant.data.ctrl[:]=cmd['ctrl']; plant.last_force=cmd['force'].copy()
            plant.last_moment=cmd['moment'].copy(); plant.last_joint_torque=cmd['torque'].copy()
        obs=SensorBoundaryStage4Plant.step(plant)
        times.append(obs.time_s)
        forces.append(obs.attachment_rotation_matrix.T@obs.cuff_force_vector_n)
        moments.append(obs.attachment_rotation_matrix.T@obs.cuff_moment_vector_nm)
    return np.array(times),np.array(forces),np.array(moments)


def force_reports(trace,plant,run_dir):
    t=trace['time_s']; f=trace['cuff_force_local_n_god_view']; m=trace['cuff_moment_local_nm_god_view']
    strict=evaluate_physical_force_trace(t,f,policy_id=STRICT_PHYSICAL_FORCE_V1,numerical_confirmation=RUNTIME_OBSERVATION)
    merged_t=t.copy(); merged_f=f.copy(); merged_m=m.copy(); confirmation=[]; unresolved=False
    for i,ep in enumerate(plant.episodes):
        np.savez_compressed(run_dir/f'event_{i:03d}_snapshot.npz',state=ep['state'],neutral=ep['neutral'],
            command_time_s=np.array([c['time_s'] for c in plant.commands]),
            ctrl=np.array([c['ctrl'] for c in plant.commands]),
            force=np.array([c['force'] for c in plant.commands]),moment=np.array([c['moment'] for c in plant.commands]),
            torque=np.array([c['torque'] for c in plant.commands]))
        meta={k:v for k,v in ep.items() if k not in {'state','neutral'}}
        if ep['end_time_s']-ep['start_time_s']>.250:
            meta.update(exact=False,reason='episode_exceeds_frozen_local_window'); unresolved=True
        else:
            ct,cf,_=replay_episode(ep,plant.commands,.001)
            indices=np.searchsorted(t,ct-1e-10); indices=np.minimum(indices,len(t)-1)
            residual=float(np.max(np.abs(cf-f[indices]))) if len(cf) else float('inf')
            ft,ff,fm=replay_episode(ep,plant.commands,.00025)
            exact=residual<=1e-8
            opened=bool(len(ff) and np.linalg.norm(ff[-1])>200)
            meta.update(exact=exact,coarse_vector_reproduction_max_error_n=residual,fine_event_open=opened)
            np.savez_compressed(run_dir/f'event_{i:03d}_fine.npz',time_s=ft,force_local_n=ff,moment_local_nm=fm)
            unresolved=unresolved or not exact or opened
            # Union replacement makes overlapping locally confirmed windows explicit.
            keep=(merged_t<=ep['start_time_s']+1e-10)|(merged_t>ep['end_time_s']+1e-10)
            merged_t=np.concatenate([merged_t[keep],ft]); merged_f=np.vstack([merged_f[keep],ff]); merged_m=np.vstack([merged_m[keep],fm])
            order=np.argsort(merged_t); merged_t=merged_t[order]; merged_f=merged_f[order]; merged_m=merged_m[order]
        write_json(run_dir/f'event_{i:03d}_manifest.json',meta); confirmation.append(meta)
    surface_model=CylindricalSurfaceLoadModel(CylindricalSurfaceConfig(.080))
    surface=np.linalg.norm(np.column_stack([merged_f,merged_m])@surface_model.minimum_norm_operator.T,axis=1)
    engineering=evaluate_physical_force_trace(merged_t,merged_f,
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=EXACT_REPLAY_UNAVAILABLE if unresolved else FINE_REPLAY_CONFIRMED,
        moment_vectors_nm=merged_m,surface_proxy_n=surface)
    # Near-limit initial conditions without a replay snapshot are not silently qualified.
    if engineering.peak_force_n>=198 and not plant.episodes:
        engineering=evaluate_physical_force_trace(merged_t,merged_f,
            policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,numerical_confirmation=EXACT_REPLAY_UNAVAILABLE)
    return strict.as_dict(),engineering.as_dict(),confirmation


def run_point(
    point,spec,output,*,run_name=None,freeze_control_geometry=False,
    spec_filename='scan_spec.json',
):
    run_dir=output/(run_name or point['id']); run_dir.mkdir()
    trajectory=NormalizedTrajectory(point); matrix=load_report_validation_matrix(DEFAULT_MATRIX)
    case=measurement_case(matrix,measurement_seed=44104); allocator=default_engineering_cuff_allocator()
    manager=UnifiedReferenceManager(trajectory.reference,confidence_aware=False)
    supervisor=TrackBrakeSupervisor(); monitor=ForceMonitor(); plants=[]
    model_lock=CompleteModelLockMonitor(allocator) if freeze_control_geometry else None
    def factory(human):
        plant=CapturePlant(human); plants.append(plant); return plant
    def estimator(measurement,q_prior):
        return OnlineSingleChallengerTrustEstimator(measurement,q_prior,measurement_case=case,
            apply_qualified_model=False,rom_human=HIGH_ROM_HUMAN,
            freeze_control_geometry=freeze_control_geometry)
    begin=clock.perf_counter()
    summary,trace=run_sensor_realism_case(case,duration_s=point['maximum_simulation_duration_s'],
        estimator_architecture='integral_minimal',result_case_name=point['id'],
        true_human_override=HIGH_ROM_HUMAN,true_metadata_override={'case':'nominal_high_rom'},
        reference_fn=trajectory.reference,trajectory_label=point['id'],trajectory_waypoints=trajectory.waypoints,
        plant_factory=factory,reference_execution=manager,reference_completion_phase_s=trajectory.duration,
        capture_system_pilot_diagnostics=True,track_brake_supervisor=supervisor,
        mpc_factory=lambda:HumanSpaceMPC(cuff_allocator=allocator),cuff_allocator=allocator,
        estimator_factory=estimator,physical_force_supervisor=monitor,terminate_on_structural_events=True,
        control_model_cycle_assertion=model_lock)
    beta=trace['dynamic_base_estimate']
    np.testing.assert_allclose(beta,np.broadcast_to(nominal_base_parameters(HUMAN),beta.shape),rtol=0,atol=1e-12)
    np.testing.assert_allclose(trace['reference_alpha_trust'],1.,rtol=0,atol=0)
    if model_lock is not None:
        lock_diagnostics=model_lock.diagnostics()
        assert lock_diagnostics['all_cycle_assertions_passed']
        assert all(len(values)==1 for values in lock_diagnostics['unique_observed_fingerprints'].values())
        assert np.all(np.asarray(lock_diagnostics['live_estimated_q_range_deg'])>0.)
        model_lock.save_cycles(run_dir/'model_lock_cycles.npz')
        write_json(run_dir/'model_lock.json',lock_diagnostics)
    write_json(run_dir/'raw_summary.json',summary)
    np.savez_compressed(run_dir/'trace.npz',**trace)
    strict,force,replays=force_reports(trace,plants[0],run_dir)
    t=trace['time_s']; q=trace['human_q_deg_god_view']; phase=trace['reference_phase_time_s']
    hold=(phase>=1.+trajectory.leg)&(phase<=2.5+trajectory.leg)
    endpoint_error=float(np.min(np.max(np.abs(q[hold]-point['endpoint_deg']),axis=1))) if np.any(hold) else None
    return_error=float(np.max(np.abs(q[-1]-[5,10])))
    command=np.linalg.norm(trace['executed_command_force_total_n'],axis=1)
    events=summary['events']; brake=summary['track_brake_supervisor']
    endpoint_rule=spec.get('endpoint_rule')
    if endpoint_rule is None:
        base_path=REPO/spec['additive_to_base_scan_spec']
        assert sha(base_path)==spec['base_scan_spec_sha256']
        endpoint_rule=json.loads(base_path.read_text())['endpoint_rule']
    unsafe=bool(events['rom_event_samples'] or events['mujoco_warning_counts'] or events['unintended_contact_pairs']
        or summary['robot']['joint_position_limit_samples'] or (len(command) and np.max(command)>200+1e-9)
        or force['classification']==HARD_PHYSICAL_VIOLATION)
    complete=bool(summary['mechanically_completed_requested_duration'] and endpoint_error is not None
        and endpoint_error<=endpoint_rule['tolerance_deg'] and return_error<=endpoint_rule['tolerance_deg']
        and supervisor.mode=='TRACK' and not unsafe
        and force['classification'] in {'STRICT_PASS','TRANSIENT_ENGINEERING_QUALIFIED'})
    status=('UNSAFE_TERMINATION' if unsafe else 'NUMERICALLY_UNRESOLVED' if force['classification']==NUMERICALLY_UNRESOLVED
        else 'COMPLETE' if complete else 'SAFE_INCOMPLETE')
    lambdas=trace['safety_filter_lambda']; filter_times=trace['safety_filter_time_s']
    metrics=dict(id=point['id'],endpoint_deg=point['endpoint_deg'],execution_status='EXECUTED',task_status=status,
        force_status=force['classification'],strict_force_status=strict['classification'],
        engineering_complete=complete,strict_complete=complete and strict['classification']=='STRICT_PASS',
        termination_reason=summary['termination_reason'],endpoint_error_deg=endpoint_error,return_error_deg=return_error,
        duration_s=float(t[-1]),phase_duration_s=trajectory.duration,
        tracking_rmse_deg=summary['tracking']['combined_rmse_deg'],tracking_max_error_deg=float(np.max(summary['tracking']['max_abs_error_deg'])),
        reference_manager=_alpha_metrics(trace),safety_filter=_filter_metrics(trace,brake),
        lambda_abs=_distribution(np.abs(lambdas)),lambda_slew=_distribution(np.abs(np.diff(lambdas)/np.diff(filter_times))),
        no_safe_action_count=events['mpc_solver_failures'],brake_entry_count=brake['transition_count'],
        brake_duration_s=.005*brake['brake_cycle_count'],brake_final_mode=supervisor.mode,
        command_force_n=_distribution(command),physical_force_n=_distribution(np.linalg.norm(trace['cuff_force_local_n_god_view'],axis=1)),
        physical_moment_nm=_distribution(np.linalg.norm(trace['cuff_moment_local_nm_god_view'],axis=1)),
        force_contract=force,strict_contract=strict,replay_confirmation=replays,motion=_smoothness(trace),
        runtime=summary['computational_cost'],force_supervision_latency_ms=_distribution(np.array(monitor.cost)),
        total_host_elapsed_s=clock.perf_counter()-begin,population_prior_verified=True,alpha_trust_one_verified=True,
        complete_model_lock=(lock_diagnostics if model_lock is not None else None))
    write_json(run_dir/'manifest.json',dict(spec_sha256=sha(output/spec_filename),point=point,
        command='python stages/stage4_adaptive_control/scripts/run_stage4_coarse_rom_capability.py --run',
        measurement_case=measurement_case_dict(case),
        controller_hashes=spec.get('controller_hashes',spec.get('wiring_source_hashes')),
        metrics=metrics))
    return clean(metrics)


def render_outputs(spec,rows,output,*,only_maps=False):
    if not only_maps:
        write_json(output/'coarse_rom_capability.json',dict(spec_sha256=sha(output/'scan_spec.json'),runs=rows,
            engineering_only_not_clinical=True,commissioning_passed=rows[0].get('engineering_complete',False)))
    fields=['id','hip_deg','knee_deg','execution_status','task_status','force_status','strict_force_status',
        'engineering_complete','strict_complete','termination_reason','duration_s','endpoint_error_deg',
        'tracking_rmse_deg','tracking_max_error_deg','physical_force_peak_n','brake_duration_s']
    if not only_maps:
        with (output/'coarse_rom_capability.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n'); writer.writeheader()
            for row in rows:
                flat={k:row.get(k) for k in fields}; flat.update(hip_deg=row['endpoint_deg'][0],knee_deg=row['endpoint_deg'][1],
                    physical_force_peak_n=row.get('physical_force_n',{}).get('peak')); writer.writerow(flat)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    categories=['NOT_RUN','STRUCTURALLY_INVALID','NUMERICALLY_UNRESOLVED','UNSAFE_TERMINATION','SAFE_INCOMPLETE','COMPLETE']
    colors=['#dedede','#706d8d','#dfb347','#c64843','#6996b5','#419575']
    for name in ('task_force_capability','physical_force_peak','tracking_rmse','filter_brake_burden','strict_capability','engineering_transient_capability'):
        fig,ax=plt.subplots(figsize=(8,7)); numeric=name in {'physical_force_peak','tracking_rmse','filter_brake_burden'}
        values=[]
        for row in rows:
            if numeric:
                value=(row.get('physical_force_n',{}).get('peak') if name=='physical_force_peak' else row.get('tracking_rmse_deg') if name=='tracking_rmse' else row.get('brake_duration_s'))
            else:
                status=row.get('task_status') or 'NOT_RUN'
                if name=='strict_capability' and status=='COMPLETE' and not row.get('strict_complete'): status='SAFE_INCOMPLETE'
                value=categories.index(status)
            values.append(value)
        valid=[v for v in values if v is not None]
        for row,value in zip(rows,values):
            x,y=row['endpoint_deg']; label=row.get('task_status') or 'NOT_RUN'
            if numeric:
                kwargs=dict(c=[value] if value is not None else ['#dedede'],cmap='viridis',vmin=min(valid,default=0),vmax=max(valid,default=1)+1e-12) if value is not None else dict(c='#dedede')
                text='NOT RUN' if value is None else f'{value:.2f}'
            else:
                kwargs=dict(c=[colors[int(value)]]); text=label.replace('NUMERICALLY_UNRESOLVED','UNRESOLVED').replace('SAFE_INCOMPLETE','INCOMPLETE')
                if name=='task_force_capability': text+='\n'+str(row.get('force_status') or '—').replace('TRANSIENT_ENGINEERING_QUALIFIED','TRANSIENT').replace('NUMERICALLY_UNRESOLVED','UNRESOLVED').replace('HARD_PHYSICAL_VIOLATION','HARD')
            ax.scatter(x,y,s=1750 if x%20==0 and y%20==0 else 700,marker='s' if x%20==0 and y%20==0 else 'D',edgecolors='black',**kwargs)
            ax.text(x,y,text,ha='center',va='center',fontsize=5.5,
                color='white' if numeric and value is not None else 'black')
        units={'physical_force_peak':' (N)','tracking_rmse':' (deg)','filter_brake_burden':' (BRAKE seconds; filter count = 0 in commissioning)'}
        ax.set(xlabel='Hip endpoint (deg)',ylabel='Knee endpoint (deg)',title=name.replace('_',' ')+units.get(name,'')+'\nCommissioning diagnostic only; model-freeze gap; no interpolation',xlim=(30,130),ylim=(30,130))
        ax.set_xticks([40,60,80,100,120]); ax.set_yticks([40,60,80,100,120]); fig.tight_layout()
        fig.savefig(output/(name+'.png'),dpi=170); plt.close(fig)
    if only_maps: return
    complete=[r['endpoint_deg'] for r in rows if r.get('engineering_complete')]
    executed=[r for r in rows if r.get('execution_status')=='EXECUTED']
    lines=['# Coarse ROM capability engineering audit','',f"Scan spec SHA: `{sha(output/'scan_spec.json')}`",'',
        f'Executed {len(executed)} / 27. Verified sampled endpoints: {complete}. No unsampled region is implied.',
        'Tracking is reported continuously; no nominal/degraded-quality band was invented.','']
    if not rows[0].get('engineering_complete'):
        lines+=['Commissioning did not complete cleanly. Remaining grid was not executed, as required.',
            'No ROM-region, hip-versus-knee limitation, or envelope-expansion conclusion is supported.',
            'No 3–6 speed-boundary trajectories are recommended from a failed commissioning gate; diagnose setup first.','']
    lines+=['| Hip/knee | Task | Force | End error deg | RMSE deg | Physical peak N |', '|---|---|---|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['endpoint_deg']} | {r.get('task_status') or 'NOT_RUN'} | {r.get('force_status') or '—'} | {r.get('endpoint_error_deg')} | {r.get('tracking_rmse_deg')} | {r.get('physical_force_n',{}).get('peak')} |")
    (output/'research_report.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--freeze',action='store_true'); parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.freeze:
        OUTPUT.mkdir(parents=True,exist_ok=False); spec=build_spec(); write_json(OUTPUT/'scan_spec.json',spec)
        (OUTPUT/'scan_spec.sha256').write_text(sha(OUTPUT/'scan_spec.json')+'  scan_spec.json\n')
        print('frozen',sha(OUTPUT/'scan_spec.json'),flush=True); return
    if not args.run: parser.error('choose --freeze or --run')
    spec=json.loads((OUTPUT/'scan_spec.json').read_text())
    assert sha(OUTPUT/'scan_spec.json')==(OUTPUT/'scan_spec.sha256').read_text().split()[0]
    for name,expected in spec['controller_hashes'].items(): assert sha(REPO/name)==expected,name
    if (OUTPUT/'prechecks.json').exists(): raise FileExistsError('refusing to overwrite scan')
    checks=prechecks(spec); write_json(OUTPUT/'prechecks.json',checks); rows=[]; commissioning=True
    for point in spec['points']:
        if not commissioning:
            row=dict(id=point['id'],endpoint_deg=point['endpoint_deg'],execution_status='NOT_RUN_COMMISSIONING_GATE',task_status=None,force_status=None)
        elif not checks[point['id']]['qualified']:
            row=dict(id=point['id'],endpoint_deg=point['endpoint_deg'],execution_status='PRECHECK_ONLY',task_status='STRUCTURALLY_INVALID',force_status=None,engineering_complete=False)
        else:
            print('RUN',point['id'],flush=True); row=run_point(point,spec,OUTPUT)
            print('RESULT',point['id'],row['task_status'],row['force_status'],flush=True)
        rows.append(row)
        write_json(OUTPUT/'progress.json',rows)
        if point['id']=='hip40_knee40': commissioning=row.get('engineering_complete',False)
    render_outputs(spec,rows,OUTPUT)


if __name__=='__main__': main()
