#!/usr/bin/env python3
"""Frozen three-run qualification; every invocation admits at most one trajectory."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import types

REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
for stage in ('stage3_full3d','stage4_adaptive_control'):
    sys.path.insert(0,str(REPO/'stages'/stage/'src'))
import mujoco
import numpy as np
from traction_mpc_stage3.spring_damper_interface import (
    InterfaceParameters, SpringDamperCoupledUR10eHumanV2, SoftInterfacePhysicalObservation)
from traction_mpc_stage3.interface_measurement_contract import RobotInterfaceSensorTruth
from traction_mpc_stage3.frames import ENGINEERING_ATTACHMENT_FROM_CUFF
from traction_mpc_stage3.coupled import SUSPENDED_SEATED_LIKE_SCENARIO
from traction_mpc_stage4 import sensor_realism as original
from traction_mpc_stage4.measurement import CausalMeasurementLayer
from traction_mpc_stage4.physical_force_contract import (
    evaluate_physical_force_trace, SIMULATION_ENGINEERING_TRANSIENT_V1,
    STRICT_PHYSICAL_FORCE_V1, RUNTIME_OBSERVATION, EXACT_REPLAY_UNAVAILABLE)
import run_stage4_coarse_rom_capability as base
from run_stage4_phase3a_rigid_gate import compare_arrays as deterministic_arrays

SPEC_NAME='PHASE3A_1MS_QUALIFICATION_SPEC_APPROVED'
EXPECTED_SHA={'.json':'4450bade85e12859cf25174fc7663bec639d26118f2539c8d033bdac4021d89b',
              '.md':'a7a0cb502f6ab3e0a4199fa1478130e42f898f33233f3bbc8ddaf97ef8c2c387'}
OUTPUT=STAGE/'results/engineering_validation/phase3a_soft_1ms_qualification_20260904_v1'
NEW_FILES=[Path(__file__), STAGE/'tests/test_phase3a_soft_qualification.py',
 REPO/'stages/stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py',
 REPO/'stages/stage3_full3d/src/traction_mpc_stage3/interface_measurement_contract.py',
 STAGE/'scripts/run_stage4_coarse_rom_capability.py',
 STAGE/'scripts/run_stage4_phase3a_rigid_gate.py']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(base.clean(x),indent=2,sort_keys=True,allow_nan=False)+'\n')
def load_npz(p):
    with np.load(p,allow_pickle=False) as z: return {k:z[k] for k in z.files}
def cumtrap(y,t): return np.r_[0.,np.cumsum(.5*(y[1:]+y[:-1])*np.diff(t))]
def norm(y):
    y=np.asarray(y)
    return np.abs(y) if y.ndim==1 else np.linalg.norm(y,axis=1)
def rms(y,t):
    return float(np.sqrt(np.trapezoid(norm(y)**2,t)/(t[-1]-t[0]))) if len(t)>1 else float(norm(y)[0])


def approved_spec():
    for suffix,h in EXPECTED_SHA.items():
        assert sha(STAGE/'docs'/(SPEC_NAME+suffix))==h, 'approved_spec_hash'
    s=json.loads((STAGE/'docs'/(SPEC_NAME+'.json')).read_text())
    assert s['status']=='APPROVED_FROZEN_FOR_ORDERED_EXECUTION'
    assert [r['physics_dt_s'] for r in s['runs']]==[.001,.001,.00025]
    for p,h in s['original_source_config_model_sha256'].items():
        assert sha(REPO/p)==h,p
    return s


def parameters(s):
    return InterfaceParameters(**{k:v for k,v in s['candidate'].items()
                                  if k not in ('loaded_rest_capture','per_trajectory_rest_reset')})


@dataclass(frozen=True)
class PortObservation(SoftInterfacePhysicalObservation):
    robot_sensor: RobotInterfaceSensorTruth | None = None


class RobotPortMeasurementLayer(CausalMeasurementLayer):
    """Only restrict/re-reference ideal input; all sampling/noise/filter laws inherited."""
    def _capture(self,truth):
        if not isinstance(truth,PortObservation) or not isinstance(truth.robot_sensor,RobotInterfaceSensorTruth):
            raise TypeError('soft controller boundary requires a restricted robot-port sample')
        assert truth.robot_sensor.cuff_wrench_reference_point=='adapter_cuff_site'
        super()._capture(truth.robot_sensor)


class LoggedSupervisor(base.TrackBrakeSupervisor):
    def __init__(self):
        super().__init__(); self.records=[]

    def command(self,**kwargs):
        decision=super().command(**kwargs)
        self.records.append(dict(time_s=float(kwargs["measurement"].arrival_time_s),
            mode=self.mode,mpc_status=kwargs.get("mpc_status") or "NO_NEW_MPC",
            trigger=self.trigger or "NONE",terminal_status=self.termination_reason or "NONE"))
        return decision


class QualificationStop(RuntimeError):
    pass


class CompliantPlant(SpringDamperCoupledUR10eHumanV2,original.SensorBoundaryStage4Plant):
    def __init__(self,human,params,dt,tolerance):
        self.records=[]; self.commands=[]; self.fatal=None; self.tolerance=tolerance
        super().__init__(params,human,physics_dt_s=dt,
                         attachment_from_cuff=ENGINEERING_ATTACHMENT_FROM_CUFF,
                         engineering_scenario=SUSPENDED_SEATED_LIKE_SCENARIO)

    def observe(self):
        physical=super().observe()
        interface=self._evaluate_current_interface()
        r=self._attachment_state(self.attachment_site_id)
        h=self._attachment_state(self.sleeve_site_id)
        ws=-interface.robot_wrench_world
        sensor=RobotInterfaceSensorTruth(physical.time_s,physical.robot_q_rad.copy(),
            physical.robot_dq_rad_s.copy(),r.position_world_m.copy(),r.rotation_world.copy(),
            r.velocity_world_m_s.copy(),r.angular_velocity_world_rad_s.copy(),ws[:3].copy(),ws[3:].copy())
        fr=interface.robot_wrench_world; fh=interface.human_wrench_world
        pr=float(fr@np.r_[r.velocity_world_m_s,r.angular_velocity_world_rad_s])
        ph=float(fh@np.r_[h.velocity_world_m_s,h.angular_velocity_world_rad_s])
        moment_h_at_r=fh[3:]+np.cross(h.position_world_m-r.position_world_m,fh[:3])
        rec=dict(time_s=physical.time_s,q_true_rad=physical.human_q_rad.copy(),
            dq_true_rad_s=physical.human_dq_rad_s.copy(),robot_q_rad=physical.robot_q_rad.copy(),
            robot_dq_rad_s=physical.robot_dq_rad_s.copy(),
            position_R=r.position_world_m.copy(),position_H=h.position_world_m.copy(),
            rotation_R=r.rotation_world.copy(),rotation_H=h.rotation_world.copy(),
            velocity_R=r.velocity_world_m_s.copy(),velocity_H=h.velocity_world_m_s.copy(),
            omega_R=r.angular_velocity_world_rad_s.copy(),omega_H=h.angular_velocity_world_rad_s.copy(),
            wrench_R=fr.copy(),wrench_H=fh.copy(),force_R_world=ws[:3].copy(),moment_R_world=ws[3:].copy(),
            moment_H_world=fh[3:].copy(),deformation_H=interface.displacement_human_m.copy(),
            rotation_vector_H=interface.rotation_error_human_rad.copy(),
            relative_velocity_H=interface.velocity_human_m_s.copy(),
            relative_angular_velocity_H=interface.angular_velocity_human_rad_s.copy(),
            stored_energy=interface.spring_energy_j,damping_power=interface.damping_dissipation_w,
            power_R=pr,power_H=ph,spring_energy_rate=interface.spring_energy_rate_w,
            force_balance_residual=float(np.linalg.norm(fr[:3]+fh[:3])),
            moment_balance_residual=float(np.linalg.norm(fr[3:]+moment_h_at_r)),
            force_balance_scale=float(np.linalg.norm(fr[:3])+np.linalg.norm(fh[:3])),
            moment_balance_scale=float(np.linalg.norm(fr[3:])+np.linalg.norm(moment_h_at_r)),
            power_identity_residual=pr+ph+interface.spring_energy_rate_w+interface.damping_dissipation_w,
            power_identity_scale=max(1.,abs(pr)+abs(ph)+abs(interface.spring_energy_rate_w)+abs(interface.damping_dissipation_w)),
            control_torque_nm=self.data.ctrl.copy(),warnings=sum(self.warning_counts().values()))
        if not self.records or rec['time_s']>self.records[-1]['time_s']:
            self.records.append(rec)
        tol=self.tolerance
        reason=None
        if not all(np.all(np.isfinite(v)) for v in rec.values()): reason='nonfinite_state_or_diagnostic'
        elif rec['warnings']: reason='mujoco_warning'
        elif (rec['force_balance_residual']>tol['action_reaction_force_absolute_n']+tol['action_reaction_relative']*rec['force_balance_scale']
              or rec['moment_balance_residual']>tol['action_reaction_moment_absolute_nm']+tol['action_reaction_relative']*rec['moment_balance_scale']
              or abs(rec['power_identity_residual'])>tol['instantaneous_power_identity_relative']*rec['power_identity_scale']):
            reason='mechanics_consistency'
        if reason:
            self.fatal=dict(reason=reason,time_s=physical.time_s)
            raise QualificationStop(reason)
        return PortObservation(**vars(physical),robot_sensor=sensor)

    def apply_executable_command(self,preview):
        super().apply_executable_command(preview)
        self.commands.append(dict(time_s=float(self.data.time),force=preview.force_total_n.copy(),
            moment=preview.moment_total_nm.copy(),torque=preview.joint_torque_command_nm.copy(),
            ctrl=self.data.ctrl.copy()))

    def trace(self):
        if not self.records: return {}
        p={k:np.asarray([r[k] for r in self.records]) for k in self.records[0]}
        t=p['time_s']
        p['work_R']=cumtrap(p['power_R'],t); p['work_H']=cumtrap(p['power_H'],t)
        p['net_work']=cumtrap(p['power_R']+p['power_H'],t)
        p['cumulative_damping_loss']=cumtrap(p['damping_power'],t)
        p['energy_residual']=p['stored_energy']-p['stored_energy'][0]+p['net_work']+p['cumulative_damping_loss']
        return p


def local_verdicts(p,tol):
    finite=bool(p and all(np.all(np.isfinite(v)) for v in p.values()))
    if not finite:
        return dict(MECHANICS_CONSISTENCY='FAIL',DISCRETE_ENERGY='NOT_EVALUATED',reason='nonfinite_or_missing_trace')
    mechanics=bool(not np.any(p['warnings'])
      and np.all(p['force_balance_residual']<=tol['action_reaction_force_absolute_n']+tol['action_reaction_relative']*p['force_balance_scale'])
      and np.all(p['moment_balance_residual']<=tol['action_reaction_moment_absolute_nm']+tol['action_reaction_relative']*p['moment_balance_scale'])
      and np.all(np.abs(p['power_identity_residual'])<=tol['instantaneous_power_identity_relative']*p['power_identity_scale']))
    scale=float(max(np.max(p['stored_energy']),p['cumulative_damping_loss'][-1],np.max(np.abs(p['net_work']))))
    residual=float(np.max(np.abs(p['energy_residual'])))
    positive=float(max(0.,np.max(p['energy_residual'])))
    energy=bool((residual<=tol['energy_max_abs_residual_ratio']*scale
                and positive<=tol['energy_max_positive_residual_ratio']*scale) if scale else
                residual<=tol['energy_zero_scale_absolute_residual_j'])
    energy=energy and bool(np.min(p['stored_energy'])>=-tol['spring_energy_roundoff_j']
                          and np.min(p['damping_power'])>=-tol['negative_damping_roundoff_w'])
    return dict(MECHANICS_CONSISTENCY='PASS' if mechanics else 'FAIL',
                DISCRETE_ENERGY='PASS' if energy else 'FAIL',
                finite=True,warning_count=int(np.max(p['warnings'])),
                max_force_balance_residual_n=float(np.max(p['force_balance_residual'])),
                max_moment_balance_residual_nm=float(np.max(p['moment_balance_residual'])),
                max_power_identity_residual_w=float(np.max(np.abs(p['power_identity_residual']))),
                energy_scale_j=scale,max_abs_energy_residual_j=residual,max_positive_energy_residual_j=positive,
                normalized_max_abs_energy_residual=residual/scale if scale else None,
                normalized_max_positive_energy_residual=positive/scale if scale else None,
                minimum_damping_power_w=float(np.min(p['damping_power'])))


def waveform_gate(tc,yc,tf,yf,a,tol):
    yc=np.asarray(yc); yf=np.asarray(yf)
    scalar=yc.ndim==1
    cc=yc[:,None] if scalar else yc; ff=yf[:,None] if scalar else yf
    mask=(tf>=tc[0])&(tf<=tc[-1]); t=tf[mask]; f=ff[mask]
    if len(t)<2: return dict(passed=False,reason='insufficient_overlap')
    c=np.column_stack([np.interp(t,tc,cc[:,j]) for j in range(cc.shape[1])])
    e=c-f; einf=float(np.max(norm(e))); bmax=float(np.max(norm(f))); e2=rms(e,t); b2=rms(f,t)
    limits=dict(linf=max(a,tol['waveform_linf_relative']*bmax),l2=max(a,tol['waveform_l2_relative']*b2))
    scalars={}
    for name,x,y in [('peak',float(np.max(norm(yc))),float(np.max(norm(yf)))),
                     ('rms',rms(yc,tc),rms(yf,tf))]:
        d=abs(x-y); lim=max(a,tol['scalar_peak_rms_final_relative']*abs(y))
        scalars[name]=dict(coarse=x,fine=y,difference=d,limit=lim,passed=d<=lim)
    final_difference=float(np.linalg.norm(yc[-1]-yf[-1])); final_ref=float(np.linalg.norm(yf[-1]))
    lim=max(a,tol['scalar_peak_rms_final_relative']*final_ref)
    scalars['final']=dict(difference=final_difference,limit=lim,passed=final_difference<=lim)
    return dict(passed=einf<=limits['linf'] and e2<=limits['l2'] and all(x['passed'] for x in scalars.values()),
                linf_absolute=einf,linf_relative=einf/bmax if bmax else None,
                l2_absolute=e2,l2_relative=e2/b2 if b2 else None,limits=limits,scalars=scalars,
                common_interval_s=[float(t[0]),float(t[-1])],native_end_times_s=[float(tc[-1]),float(tf[-1])])


def force_peak_gate(coarse,fine,tolerance_n):
    difference=abs(float(np.max(norm(coarse)))-float(np.max(norm(fine))))
    return dict(passed=difference<=tolerance_n,absolute_difference_n=difference,limit_n=tolerance_n)


def status_transitions(t,values):
    values=np.asarray(values); indices=np.r_[0,1+np.flatnonzero(values[1:]!=values[:-1])]
    return values[indices].tolist(),np.asarray(t)[indices]


def cross_timestep(s,coarse_dir,fine_dir):
    c=load_npz(coarse_dir/'mechanics.npz'); f=load_npz(fine_dir/'mechanics.npz')
    ct=load_npz(coarse_dir/'trace.npz'); ft=load_npz(fine_dir/'trace.npz')
    cr=json.loads((coarse_dir/'result.json').read_text()); fr=json.loads((fine_dir/'result.json').read_text())
    tol=s['tolerances']; gates={}
    for key,conf in tol['absolute_signal_tolerances'].items():
        if key=='executable_command_force_world':
            tc,yc=ct['executed_command_time_s'],ct['executed_command_force_total_n']
            tf,yf=ft['executed_command_time_s'],ft['executed_command_force_total_n']
        else: tc,yc,tf,yf=c['time_s'],c[key],f['time_s'],f[key]
        gates[key]=waveform_gate(tc,yc,tf,yf,conf['value'],tol)
    gates['independent_force_peak']=force_peak_gate(c['force_R_world'],f['force_R_world'],tol['transmitted_physical_force_peak_absolute_difference_n'])
    for key,ta,tb,a,b,limit in [
      ('q_true',c['time_s'],f['time_s'],np.degrees(c['q_true_rad']),np.degrees(f['q_true_rad']),tol['q_true_and_proxy_max_difference_deg']),
      ('dq_true',c['time_s'],f['time_s'],np.degrees(c['dq_true_rad_s']),np.degrees(f['dq_true_rad_s']),tol['dq_true_and_proxy_max_difference_deg_s']),
      ('q_proxy',ct['control_time_s'],ft['control_time_s'],np.degrees(ct['control_estimated_state'][:,:2]),np.degrees(ft['control_estimated_state'][:,:2]),tol['q_true_and_proxy_max_difference_deg']),
      ('dq_proxy',ct['control_time_s'],ft['control_time_s'],np.degrees(ct['control_estimated_state'][:,2:]),np.degrees(ft['control_estimated_state'][:,2:]),tol['dq_true_and_proxy_max_difference_deg_s'])]:
        mask=(tb>=ta[0])&(tb<=ta[-1]); interp=np.column_stack([np.interp(tb[mask],ta,a[:,j]) for j in range(a.shape[1])])
        delta=np.max(np.abs(interp-b[mask]),axis=0)
        gates[key]=dict(passed=bool(np.all(delta<=limit)),max_difference_per_joint=delta,limit=limit)
    interp=np.interp(ft['time_s'],ct['time_s'],ct['reference_phase_time_s'])
    phase_delta=float(np.max(np.abs(interp-ft['reference_phase_time_s'])))
    gates['phase']=dict(passed=phase_delta<=tol['reference_phase_max_difference_s'],max_difference_s=phase_delta)
    for name in ('endpoint_error_deg','return_error_deg','tracking_rmse_per_joint_deg'):
        if cr['task_metrics'][name] is None or fr['task_metrics'][name] is None:
            gates[name]=dict(passed=False,reason='missing_metric'); continue
        delta=np.abs(np.asarray(cr['task_metrics'][name])-np.asarray(fr['task_metrics'][name]))
        gates[name]=dict(passed=bool(np.all(delta<=tol['tracking_rmse_endpoint_return_metric_absolute_difference_deg'])),difference=delta)
    labels=['termination_reason','TASK_RESULT','FORCE_CONTRACT']
    gates['labels']=dict(passed=all(cr[k]==fr[k] for k in labels),coarse={k:cr[k] for k in labels},fine={k:fr[k] for k in labels})
    for key in ('safety_filter_status',):
        ac,tc=status_transitions(ct['safety_filter_time_s'],ct[key]); af,tf=status_transitions(ft['safety_filter_time_s'],ft[key])
        delta=float(np.max(np.abs(tc-tf))) if ac==af else None
        gates[key]=dict(passed=ac==af and delta<=tol['brake_filter_event_time_difference_s'],coarse=ac,fine=af,max_time_difference_s=delta)
    cm=load_npz(coarse_dir/'modes.npz'); fm=load_npz(fine_dir/'modes.npz')
    ac,tc=status_transitions(cm['time_s'],cm['mode']); af,tf=status_transitions(fm['time_s'],fm['mode'])
    delta=float(np.max(np.abs(tc-tf))) if ac==af else None
    gates['brake']=dict(passed=ac==af and delta<=tol['brake_filter_event_time_difference_s'],coarse=ac,fine=af,max_time_difference_s=delta)
    events_c=cr['force_report']['events']; events_f=fr['force_report']['events']; event_ok=len(events_c)==len(events_f)
    if event_ok:
        event_ok=all(abs(a[k]-b[k])<=tol['physical_event_time_difference_s'] for a,b in zip(events_c,events_f) for k in ('start_time_s','end_time_s'))
    gates['physical_event_times']=dict(passed=event_ok)
    delta=abs(float(c['time_s'][-1]-f['time_s'][-1]))
    gates['coverage']=dict(passed=cr['coverage_complete'] and fr['coverage_complete'] and delta<=tol['physical_event_time_difference_s'],end_time_difference_s=delta)
    return dict(verdict='PASS' if all(g['passed'] for g in gates.values()) else 'FAIL',gates=gates,
      attribution='Cross-timestep closed-loop sensitivity; no automatic attribution to interface mechanics. See independent mechanics/energy verdicts.')


def run_one(s,index,root):
    run=s['runs'][index]; out=root/run['id']; out.mkdir(exist_ok=False)
    write(out/'started.json',dict(run=run,command_argv=[sys.executable,*sys.argv],spec_sha256=EXPECTED_SHA,
        evidence_category='user_authorized_engineering_numerical_qualification_not_formal'))
    plants=[]; point=s['frozen_trajectory']; trajectory=base.NormalizedTrajectory(point)
    matrix=base.load_report_validation_matrix(base.DEFAULT_MATRIX)
    case=base.measurement_case(matrix,measurement_seed=s['measurement_seed'])
    allocator=base.default_engineering_cuff_allocator()
    manager=base.UnifiedReferenceManager(trajectory.reference,confidence_aware=False)
    supervisor=LoggedSupervisor(); force_monitor=base.ForceMonitor()
    lock=base.CompleteModelLockMonitor(allocator)
    def factory(human):
        p=CompliantPlant(human,parameters(s),run['physics_dt_s'],s['tolerances']); plants.append(p)
        return p
    def estimator(measurement,q_prior):
        return base.OnlineSingleChallengerTrustEstimator(measurement,q_prior,measurement_case=case,
           apply_qualified_model=False,rom_human=base.HIGH_ROM_HUMAN,freeze_control_geometry=True)
    # Original bytecode/control law; only explicit sensor adapter and number of
    # physics integrations per unchanged low-level tick differ in local bindings.
    env=dict(original.run_sensor_realism_case.__globals__)
    env.update(CausalMeasurementLayer=RobotPortMeasurementLayer,CONTROL_SUBSTEPS=run['low_level_substeps'])
    fn=types.FunctionType(original.run_sensor_realism_case.__code__,env,
        original.run_sensor_realism_case.__name__,original.run_sensor_realism_case.__defaults__,original.run_sensor_realism_case.__closure__)
    fn.__kwdefaults__=original.run_sensor_realism_case.__kwdefaults__
    summary=None; trace=None; exception=None
    try:
        summary,trace=fn(case,duration_s=point['maximum_simulation_duration_s'],
            estimator_architecture='integral_minimal',result_case_name=point['id'],
            true_human_override=base.HIGH_ROM_HUMAN,true_metadata_override={'case':'nominal_high_rom'},
            reference_fn=trajectory.reference,trajectory_label=point['id'],trajectory_waypoints=trajectory.waypoints,
            plant_factory=factory,reference_execution=manager,reference_completion_phase_s=trajectory.duration,
            capture_system_pilot_diagnostics=True,track_brake_supervisor=supervisor,
            mpc_factory=lambda:base.HumanSpaceMPC(cuff_allocator=allocator),cuff_allocator=allocator,
            estimator_factory=estimator,physical_force_supervisor=force_monitor,
            terminate_on_structural_events=True,control_model_cycle_assertion=lock)
    except Exception:
        exception=traceback.format_exc(); (out/'exception.txt').write_text(exception)
    if not plants: raise RuntimeError('plant was not created; preserved started marker blocks retry')
    p=plants[0]; physical=p.trace(); np.savez_compressed(out/'mechanics.npz',**physical)
    if supervisor.records:
        np.savez_compressed(out/'modes.npz',**{k:np.asarray([r[k] for r in supervisor.records]) for k in supervisor.records[0]})
    if p.commands: np.savez_compressed(out/'commands.npz',**{k:np.asarray([r[k] for r in p.commands]) for k in p.commands[0]})
    write(out/'model_lock.json',lock.diagnostics()); lock.save_cycles(out/'model_lock_cycles.npz')
    if summary is not None:
        write(out/'raw_summary.json',summary)
        write(out/'raw_report_semantics.json',dict(
            physical_trace_cuff_moment='Human-site moment expressed in robot cuff axes; use mechanics.npz for separately referenced R and H moments',
            inherited_moment_measurement_error='Not used: inherited diagnostic subtracts H-referenced physical moment from R-referenced measurement. Controller receives R-referenced wrench only.',
            inherited_force_moment_rate='Original raw summary assumes 1 ms; corrected actual-timestamp rates are in physical_rate_diagnostics_actual_dt.json.'))
    if trace is not None: np.savez_compressed(out/'trace.npz',**trace)
    local=local_verdicts(physical,s['tolerances'])
    finite=local.get('finite',False); force=None; strict=None
    if finite:
        t=physical['time_s']; forces=physical['force_R_world']
        force=evaluate_physical_force_trace(t,forces,policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
            numerical_confirmation=RUNTIME_OBSERVATION,moment_vectors_nm=physical['moment_R_world']).as_dict()
        strict=evaluate_physical_force_trace(t,forces,policy_id=STRICT_PHYSICAL_FORCE_V1,
            numerical_confirmation=RUNTIME_OBSERVATION).as_dict()
        if force['numerical_confirmation_required']:
            force=evaluate_physical_force_trace(t,forces,policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
                numerical_confirmation=EXACT_REPLAY_UNAVAILABLE,moment_vectors_nm=physical['moment_R_world']).as_dict()
    coverage=bool(summary is not None and summary['termination_reason']=='reference_completed'
                  and trace['reference_phase_time_s'][-1]>=trajectory.duration-1e-12)
    endpoint=None; ret=None; task='NOT_EVALUATED'; task_metrics={}; brake=supervisor.summary()
    if summary is not None:
        phase=trace['reference_phase_time_s']; q=trace['human_q_deg_god_view']
        mask=(phase>=1+trajectory.leg)&(phase<=2.5+trajectory.leg)
        endpoint=float(np.min(np.max(np.abs(q[mask]-point['endpoint_deg']),axis=1))) if np.any(mask) else None
        ret=float(np.max(np.abs(q[-1]-s['initial_human_q_deg'])))
        brake=summary['track_brake_supervisor']; events=summary['events']
        unsafe=bool(events['rom_event_samples'] or events['mujoco_warning_counts'] or events['unintended_contact_pairs']
          or summary['robot']['joint_position_limit_samples'] or np.max(norm(trace['executed_command_force_total_n']),initial=0)>200+1e-9
          or (force and force['classification']=='HARD_PHYSICAL_VIOLATION'))
        task=('UNSAFE_TERMINATION' if unsafe else 'NUMERICALLY_UNRESOLVED' if force and force['classification']=='NUMERICALLY_UNRESOLVED'
              else 'COMPLETE' if coverage and endpoint is not None and endpoint<=s['frozen_endpoint_rule']['tolerance_deg']
              and ret<=s['frozen_endpoint_rule']['tolerance_deg'] and brake['active_mode']=='TRACK' else 'SAFE_INCOMPLETE')
        task_metrics=dict(endpoint_error_deg=endpoint,return_error_deg=ret,
            tracking_rmse_per_joint_deg=summary['tracking']['rmse_deg'],tracking_rmse_deg=summary['tracking']['combined_rmse_deg'],
            max_tracking_error_deg=summary['tracking']['max_abs_error_deg'],final_reference_phase_s=float(phase[-1]),
            completion_tolerance_deg=s['frozen_endpoint_rule']['tolerance_deg'],
            no_safe_action_count=events['mpc_solver_failures'],filter_status_counts=brake.get('safety_filter_status_counts'))
        # Original raw report is preserved; derivative correction is diagnostics-only.
        rates={}
        for name,key in [('force','force_R_world'),('moment_R','moment_R_world'),('moment_H','moment_H_world')]:
            rate=np.diff(physical[key],axis=0)/np.diff(physical['time_s'])[:,None]
            rates[name]=dict(peak=float(np.max(norm(rate),initial=0)),rms=float(np.sqrt(np.mean(norm(rate)**2))) if len(rate) else 0.)
        write(out/'physical_rate_diagnostics_actual_dt.json',rates)
    reasons=[]
    if exception: reasons.append('FAIL_NUMERICAL_STATE' if p.fatal and p.fatal['reason'] in ('nonfinite_state_or_diagnostic','mujoco_warning') else 'FAIL_IMPLEMENTATION_EXCEPTION')
    if local['MECHANICS_CONSISTENCY']!='PASS': reasons.append('FAIL_MECHANICS_CONSISTENCY')
    if local['DISCRETE_ENERGY']!='PASS': reasons.append('FAIL_DISCRETE_ENERGY')
    if not coverage: reasons.append('FAIL_EVIDENCE_INCOMPLETE')
    if force is None or force['classification']=='NUMERICALLY_UNRESOLVED': reasons.append('FAIL_FORCE_EVIDENCE_INCOMPLETE')
    deterministic=None
    if index==1 and not reasons:
        old=root/s['runs'][0]['id']; arrays={}
        for name in ('trace.npz','mechanics.npz','commands.npz','model_lock_cycles.npz','modes.npz'):
            arrays[name]=deterministic_arrays(load_npz(old/name),load_npz(out/name))
        old_result=json.loads((old/'result.json').read_text())
        passed=all(c['passed'] for group in arrays.values() for c in group.values())
        passed=passed and old_result['TASK_RESULT']==task and old_result['FORCE_CONTRACT']==force['classification']
        deterministic=dict(passed=passed,rtol=0.,atol=1e-12,arrays=arrays)
        if not passed: reasons.append('FAIL_DETERMINISM')
        write(out/'determinism.json',deterministic)
    result=dict(run_id=run['id'],physics_dt_s=run['physics_dt_s'],
        MECHANICS_CONSISTENCY=local['MECHANICS_CONSISTENCY'],DISCRETE_ENERGY=local['DISCRETE_ENERGY'],
        CLOSED_LOOP_TIMESTEP_AGREEMENT='NOT_EVALUATED',TASK_RESULT=task,
        FORCE_CONTRACT=force['classification'] if force else 'NOT_EVALUATED',
        local_checks=local,coverage_complete=coverage,task_metrics=task_metrics,brake=brake,
        force_report=force,strict_force_report=strict,termination_reason=summary['termination_reason'] if summary else p.fatal or 'exception',
        admit_next=not reasons,overall='PENDING' if not reasons else 'FAIL',causes=reasons,
        deterministic_repeat_passed=deterministic['passed'] if deterministic else None,
        simulated_duration_s=float(physical['time_s'][-1]) if physical else None,
        diagnostics=dict(force_peak_n=float(np.max(norm(physical['force_R_world']))) if finite else None,
          moment_R_peak_nm=float(np.max(norm(physical['moment_R_world']))) if finite else None,
          moment_H_peak_nm=float(np.max(norm(physical['moment_H_world']))) if finite else None,
          deformation_peak_m=float(np.max(norm(physical['deformation_H']))) if finite else None,
          rotation_peak_rad=float(np.max(norm(physical['rotation_vector_H']))) if finite else None,
          stored_energy_peak_j=float(np.max(physical['stored_energy'])) if finite else None,
          damping_energy_final_j=float(physical['cumulative_damping_loss'][-1]) if finite else None),
        source_or_config_changed=False)
    write(out/'result.json',result)
    if index==2 and not reasons:
        comparison=cross_timestep(s,root/s['runs'][0]['id'],out)
        write(root/'timestep_comparison.json',comparison)
        result['CLOSED_LOOP_TIMESTEP_AGREEMENT']=comparison['verdict']
        if comparison['verdict']!='PASS': result['causes'].append('FAIL_CLOSED_LOOP_TIMESTEP_AGREEMENT')
        result['overall']='PASS' if not result['causes'] else 'FAIL'; result['admit_next']=False
        write(out/'result.json',result)
    write(root/'campaign_status.json',dict(last_run=run['id'],overall=result['overall'],causes=result['causes'],
        runs_executed=index+1,runs_not_executed=[r['id'] for r in s['runs'][index+1:]],
        rigid_vs_soft_ab_authorized_next=result['overall']=='PASS',stop=bool(result['causes']) or index==2,
        spec_sha256=EXPECTED_SHA))
    print(json.dumps({k:result[k] for k in ('run_id','overall','causes','MECHANICS_CONSISTENCY','DISCRETE_ENERGY','TASK_RESULT','FORCE_CONTRACT')}),flush=True)
    return not result['causes']


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--freeze-implementation',action='store_true'); ap.add_argument('--run-next',action='store_true')
    a=ap.parse_args(); s=approved_spec()
    if a.freeze_implementation:
        OUTPUT.mkdir(parents=True,exist_ok=False)
        for suffix in ('.md','.json','.sha256'): shutil.copyfile(STAGE/'docs'/(SPEC_NAME+suffix),OUTPUT/(SPEC_NAME+suffix))
        write(OUTPUT/'implementation_registration.json',dict(
          command_argv=[sys.executable,*sys.argv],source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          hashes={str(p.relative_to(REPO)):sha(p) for p in NEW_FILES},
          environment=dict(python=sys.version,numpy=np.__version__,mujoco=mujoco.__version__,platform=platform.platform()),
          original_source_config_model_sha256=s['original_source_config_model_sha256'],
          source_modifications='Two added donor modules (constructor API adaptation only), new boundary/runner/tests. All 61 original frozen files unchanged.',
          allowed_runtime_bindings=dict(CausalMeasurementLayer='RobotPortMeasurementLayer',CONTROL_SUBSTEPS=[5,5,20]),
          rigid_gate_reused='phase3a_rigid_gate_20260904_v1; no rigid rerun',spec_sha256=EXPECTED_SHA))
        print('IMPLEMENTATION_FROZEN',flush=True); return
    if not a.run_next: ap.error('choose --freeze-implementation or --run-next')
    impl=json.loads((OUTPUT/'implementation_registration.json').read_text())
    for p,h in impl['hashes'].items(): assert sha(REPO/p)==h,p
    for suffix,h in EXPECTED_SHA.items(): assert sha(OUTPUT/(SPEC_NAME+suffix))==h
    index=0
    while index<len(s['runs']) and (OUTPUT/s['runs'][index]['id']).exists():
        result=json.loads((OUTPUT/s['runs'][index]['id']/'result.json').read_text())
        if not result['admit_next']: raise RuntimeError('campaign stopped; no further trajectory authorized')
        index+=1
    if index>=3: raise RuntimeError('no fourth run')
    print('START',s['runs'][index]['id'],flush=True)
    success=run_one(s,index,OUTPUT)
    approved_spec()
    for p,h in impl['hashes'].items(): assert sha(REPO/p)==h,p
    raise SystemExit(0 if success else 2)


if __name__=='__main__': main()
