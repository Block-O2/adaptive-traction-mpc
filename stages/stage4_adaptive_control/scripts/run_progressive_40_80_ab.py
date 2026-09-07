#!/usr/bin/env python3
"""Exactly two fresh-process 40/80 exploratory A/B runs. Never tunes or replays."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import types
import numpy as np
from scipy.spatial.transform import Rotation

REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
sys.path.insert(0,str(STAGE/'scripts'))
import run_stage4_phase3a_soft_qualification as old
from traction_mpc_stage3.progressive_interface import ProgressiveParameters,ProgressiveCoupledUR10eHumanV2
base=old.base
ROOT=STAGE/'results/engineering_validation/progressive_40_80_ab_20260907_v1'
SPEC=STAGE/'docs/PROGRESSIVE_40_80_AB_SPEC.json'
DOC=SPEC.with_suffix('.md')
BENCH=STAGE/'docs/PROGRESSIVE_INTERFACE_BENCH_SPEC.json'
SCRIPTS=[Path(__file__),STAGE/'tests/test_progressive_40_80_ab.py']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):old.write(Path(p),x)
def norm(x):return old.norm(x)
def arrays(rows):return {k:np.asarray([r[k] for r in rows]) for k in rows[0]} if rows else {}


def contract():
    s=read(SPEC);b=read(BENCH)
    assert sha(BENCH)==s['bench_spec_sha256']
    assert s['candidate']==b['candidates'][0] and s['candidate']['id']=='P1'
    assert s['physics_dt_s']==.00025 and s['control_substeps']==20 and s['low_level_period_s']==.005
    assert [(r['point']['endpoint_deg'],r['arm']) for r in s['runs']]==[([40,80],'rigid'),([40,80],'P1')]
    for p,h in s['frozen_hashes'].items():assert sha(REPO/p)==h,p
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==s['head']
    assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True).strip()
    return s


def pathological(rec,s):
    if not all(np.isfinite(v).all() for v in rec.values()):return 'nonfinite_state_or_diagnostic'
    if rec['warnings']:return 'mujoco_warning'
    if np.linalg.norm(rec['deformation_H'])>s['stop']['emergency_translation_m']:return 'gross_translation_departure'
    if np.linalg.norm(rec['rotation_vector_H'])>s['stop']['emergency_rotation_rad']:return 'gross_rotation_departure'
    if rec['damping_power'] < -s['stop']['negative_damping_roundoff_w']:return 'negative_damping'
    if rec['stored_energy'] < -s['stop']['spring_energy_roundoff_j']:return 'negative_spring_energy'
    return None


def growth_reason(windows,s):
    g=s['growth_policy']
    if len(windows)<g['window_count']:return None
    w=windows[-g['window_count']:]
    residual=np.array([a['residual_final_j'] for a in w]);d=np.diff(residual)
    if np.all(d>g['energy_min_increment_j']) and residual[-1]>0 and residual[-1]-residual[0]>max(g['energy_total_growth_absolute_j'],g['energy_total_growth_fraction']*w[-1]['energy_scale_j']):
        return 'persistent_positive_energy_residual_growth'
    def grows(key,floor):
        v=np.array([a[key] for a in w])
        return bool(v[-1]>floor and np.all(v[1:]>=g['amplitude_step_factor']*np.maximum(v[:-1],1e-12)) and v[-1]>=g['amplitude_total_factor']*max(v[0],1e-12))
    if grows('force_peak_n',g['force_peak_floor_n']) and grows('acceleration_peak_m_s2',g['acceleration_floor_m_s2']):return 'growing_force_and_acceleration_amplitude'
    for key,floor in [('force_oscillation_n',g['force_oscillation_floor_n']),('translation_oscillation_m',g['translation_oscillation_floor_m']),('rotation_oscillation_rad',g['rotation_oscillation_floor_rad'])]:
        if grows(key,floor):return 'growing_'+key
    return None


class GrowthWatch:
    def __init__(self,s):self.spec=s;self.windows=[];self.rows=[];self.next_end=s['growth_policy']['window_s'];self.previous=None
    def update(self,r):
        dt=r['time_s']-self.previous['time_s'] if self.previous else 0.
        acc=max(np.linalg.norm(r[k]-self.previous[k])/dt for k in ['velocity_R','velocity_H']) if dt else 0.
        sample=dict(time_s=r['time_s'],residual=r['energy_residual'],energy_scale=r['energy_scale'],force=r['force_R_world'],translation=r['deformation_H'],rotation=r['rotation_vector_H'],acceleration=acc)
        self.rows.append(sample);self.previous=r
        if r['time_s']<self.next_end-1e-10:return None
        rows=self.rows;f=np.asarray([a['force'] for a in rows]);v=np.asarray([a['translation'] for a in rows]);rot=np.asarray([a['rotation'] for a in rows])
        w=dict(start_s=self.next_end-self.spec['growth_policy']['window_s'],end_s=r['time_s'],samples=len(rows),residual_final_j=r['energy_residual'],residual_growth_j=r['energy_residual']-rows[0]['residual'],residual_slope_w=(r['energy_residual']-rows[0]['residual'])/max(r['time_s']-rows[0]['time_s'],1e-12),energy_scale_j=r['energy_scale'],force_peak_n=float(max(norm(f))),acceleration_peak_m_s2=max(a['acceleration'] for a in rows),force_oscillation_n=float(max(norm(f-np.mean(f,axis=0)))),translation_oscillation_m=float(max(norm(v-np.mean(v,axis=0)))),rotation_oscillation_rad=float(max(norm(rot-np.mean(rot,axis=0)))))
        self.windows.append(w);self.rows=[];self.next_end+=self.spec['growth_policy']['window_s']
        reason=growth_reason(self.windows,self.spec);w['stop_reason']=reason;return reason


class DiagnosticMixin:
    def setup(self,s,manager):
        self.spec=s;self.manager=manager;self.samples=[];self.diagnostic_stop=None;self.capture_enabled=False
        self.work=0.;self.loss=0.;self.max_u=0.;self.max_work=0.;self.growth=GrowthWatch(s)
    def observe(self):
        obs=super().observe()
        if not self.capture_enabled:return obs
        if self.samples and obs.time_s<=self.samples[-1]['time_s']:return obs
        if self.is_progressive:
            r=dict(self.records[-1])
        else:
            rp=obs.attachment_position_m.copy();rr=obs.attachment_rotation_matrix.copy()
            hp=self.data.site_xpos[self.sleeve_site_id].copy();hr=self.data.site_xmat[self.sleeve_site_id].reshape(3,3).copy()
            oh,vh=self._site_velocity(self.sleeve_site_id)
            r=dict(time_s=obs.time_s,q_true_rad=obs.human_q_rad.copy(),dq_true_rad_s=obs.human_dq_rad_s.copy(),
                robot_q_rad=obs.robot_q_rad.copy(),robot_dq_rad_s=obs.robot_dq_rad_s.copy(),
                position_R=rp,position_H=hp,velocity_R=obs.attachment_velocity_m_s.copy(),velocity_H=vh,
                omega_R=obs.attachment_angular_velocity_rad_s.copy(),omega_H=oh,
                force_R_world=obs.cuff_force_vector_n.copy(),moment_R_world=obs.cuff_moment_vector_nm.copy(),moment_H_world=obs.cuff_moment_vector_nm.copy(),
                deformation_H=hr.T@(rp-hp),rotation_vector_H=Rotation.from_matrix(hr.T@rr).as_rotvec(),
                stored_energy=0.,damping_power=0.,power_R=0.,power_H=0.,warnings=sum(self.warning_counts().values()),
                control_torque_nm=self.data.ctrl.copy())
        r['reference_phase_s']=self.manager.phase_time_s(obs.time_s)
        r['manager_reference_q_rad']=self.manager.reference(obs.time_s).q_rad.copy()
        if self.samples:
            a=self.samples[-1];dt=r['time_s']-a['time_s']
            self.work+=.5*dt*(r['power_R']+r['power_H']+a['power_R']+a['power_H'])
            self.loss+=.5*dt*(r['damping_power']+a['damping_power'])
        self.max_u=max(self.max_u,r['stored_energy']);self.max_work=max(self.max_work,abs(self.work))
        r['net_work']=self.work;r['cumulative_damping_loss']=self.loss
        r['energy_residual']=r['stored_energy']-(self.samples[0]['stored_energy'] if self.samples else r['stored_energy'])+self.work+self.loss
        r['energy_scale']=max(self.max_u,self.loss,self.max_work)
        if not self.samples:
            self.initial_state=dict(qpos=self.data.qpos.copy(),qvel=self.data.qvel.copy(),ctrl=self.data.ctrl.copy(),time_s=np.array([self.data.time]))
        r['absolute_energy_residual']=abs(r['energy_residual'])
        r['normalized_energy_residual']=r['energy_residual']/max(r['energy_scale'],1e-12)
        r['energy_residual_slope_w']=(r['energy_residual']-self.samples[-1]['energy_residual'])/(r['time_s']-self.samples[-1]['time_s']) if self.samples else 0.
        self.samples.append(r)
        reason=pathological(r,self.spec)
        if reason is None:reason=self.growth.update(r)
        if reason:self.diagnostic_stop=self.diagnostic_stop or dict(reason=reason,time_s=float(obs.time_s))
        if reason=='nonfinite_state_or_diagnostic':raise old.QualificationStop(reason)
        return obs


class RigidPlant(DiagnosticMixin,base.SensorBoundaryStage4Plant):
    is_progressive=False
    def __init__(self,human,s,manager):
        self.setup(s,manager);self.commands=[]
        super().__init__(human,attachment_from_cuff=old.ENGINEERING_ATTACHMENT_FROM_CUFF,engineering_scenario=old.SUSPENDED_SEATED_LIKE_SCENARIO)
        self.model.opt.timestep=s['physics_dt_s'];self.capture_enabled=True
    def apply_executable_command(self,preview):
        super().apply_executable_command(preview)
        self.commands.append(dict(time_s=float(self.data.time),force=preview.force_total_n.copy(),moment=preview.moment_total_nm.copy(),torque=preview.joint_torque_command_nm.copy(),ctrl=self.data.ctrl.copy()))


class ProgressivePlant(DiagnosticMixin,old.CompliantPlant):
    is_progressive=True
    _evaluate_current_interface=ProgressiveCoupledUR10eHumanV2._evaluate_current_interface
    def __init__(self,human,s,manager):
        self.setup(s,manager)
        super().__init__(human,ProgressiveParameters(**s['candidate']['parameters']),s['physics_dt_s'],s['mechanics_tolerances'])
        self.capture_enabled=True


class DetailedSupervisor(old.LoggedSupervisor):
    def command(self,**kwargs):
        decision=super().command(**kwargs)
        row=self.records[-1]
        row.update(decision_status=decision.status,feasible_candidate_count=decision.feasible_candidate_count,
            selected_braking_rate_per_s=np.nan if decision.selected_braking_rate_per_s is None else decision.selected_braking_rate_per_s,
            reference_speed_norm_rad_s=np.nan if decision.reference_speed_norm_rad_s is None else decision.reference_speed_norm_rad_s,
            terminate_reason=decision.terminate_reason or 'NONE',
            safety_filter_status=(decision.safety_filter or {}).get('status','NONE'))
        return decision


class StopMonitor(base.ForceMonitor):
    """Original force monitor plus external experiment stop, no control recovery."""
    def __init__(self,plants):super().__init__();self.plants=plants
    def update(self,t,f):
        physical=super().update(t,f)
        return physical or bool(self.plants and self.plants[0].diagnostic_stop)


def make_runtime(progressive):
    env=dict(old.original.run_sensor_realism_case.__globals__)
    env['CONTROL_SUBSTEPS']=20
    if progressive:env['CausalMeasurementLayer']=old.RobotPortMeasurementLayer
    fn=types.FunctionType(old.original.run_sensor_realism_case.__code__,env,old.original.run_sensor_realism_case.__name__,old.original.run_sensor_realism_case.__defaults__,old.original.run_sensor_realism_case.__closure__)
    fn.__kwdefaults__=old.original.run_sensor_realism_case.__kwdefaults__
    return fn


def vector_metrics(x,t):
    if not len(x):return dict(rms=None,peak=None)
    return dict(rms=old.rms(x,t),peak=float(np.max(norm(x))))
def derivative(x,t):return np.diff(x,axis=0)/np.diff(t).reshape((-1,)+(1,)*(x.ndim-1))

def summarize(s,run,out,p,summary,trace,supervisor,elapsed,exception):
    x=arrays(p.samples);cmd=arrays(p.commands)
    np.savez_compressed(out/'mechanics.npz',**x);np.savez_compressed(out/'commands.npz',**cmd)
    np.savez_compressed(out/'modes.npz',**arrays(supervisor.records))
    if summary is not None:write(out/'raw_summary.json',summary)
    if trace is not None:np.savez_compressed(out/'trace.npz',**trace)
    if exception:(out/'exception.txt').write_text(exception)
    t=x['time_s'];finite=all(np.isfinite(v).all() for v in x.values());pt=run['point'];trajectory=base.NormalizedTrajectory(pt)
    phase=trace['reference_phase_time_s'] if trace is not None else x['reference_phase_s']
    q=trace['human_q_deg_god_view'] if trace is not None else np.degrees(x['q_true_rad'])
    ref=trace['human_q_ref_deg'] if trace is not None else np.degrees(x['manager_reference_q_rad'])
    hold=(phase>=1+trajectory.leg)&(phase<=2.5+trajectory.leg)
    endpoint=float(np.min(np.max(np.abs(q[hold]-pt['endpoint_deg']),axis=1))) if np.any(hold) else None
    return_error=float(np.max(np.abs(q[-1]-[5,10])))
    reason=(p.diagnostic_stop or {}).get('reason') or (getattr(p,'fatal',None) or {}).get('reason') or (summary['termination_reason'] if summary else 'implementation_exception')
    force=None;strict=None
    if finite:
        force=old.evaluate_physical_force_trace(t,x['force_R_world'],policy_id=old.SIMULATION_ENGINEERING_TRANSIENT_V1,numerical_confirmation=old.RUNTIME_OBSERVATION,moment_vectors_nm=x['moment_R_world']).as_dict()
        if force['numerical_confirmation_required']:
            force=old.evaluate_physical_force_trace(t,x['force_R_world'],policy_id=old.SIMULATION_ENGINEERING_TRANSIENT_V1,numerical_confirmation=old.EXACT_REPLAY_UNAVAILABLE,moment_vectors_nm=x['moment_R_world']).as_dict()
        strict=old.evaluate_physical_force_trace(t,x['force_R_world'],policy_id=old.STRICT_PHYSICAL_FORCE_V1,numerical_confirmation=old.RUNTIME_OBSERVATION).as_dict()
    brake=summary['track_brake_supervisor'] if summary else supervisor.summary()
    events=summary['events'] if summary else {}
    rom=bool(np.any(x['q_true_rad']<np.asarray(base.HIGH_ROM_HUMAN.q_min_rad)-1e-9) or np.any(x['q_true_rad']>np.asarray(base.HIGH_ROM_HUMAN.q_max_rad)+1e-9))
    status='INCOMPLETE'
    coverage=reason=='reference_completed' and phase[-1]>=trajectory.duration-1e-12
    unsafe=rom or bool(np.max(x['warnings'])) or bool(events.get('unintended_contact_pairs')) or bool(summary and summary['robot']['joint_position_limit_samples']) or bool(force and force['classification']=='HARD_PHYSICAL_VIOLATION') or bool(cmd and np.max(norm(cmd['force']))>200+1e-9)
    if unsafe:status='UNSAFE_TERMINATION'
    elif p.diagnostic_stop or exception:status='DIAGNOSTIC_STOP'
    elif force and force['classification']=='NUMERICALLY_UNRESOLVED':status='NUMERICALLY_UNRESOLVED'
    elif coverage and endpoint is not None and max(endpoint,return_error)<=s['endpoint_rule']['tolerance_deg'] and supervisor.mode=='TRACK':status='COMPLETE'
    else:status='SAFE_INCOMPLETE'
    stop=[]
    if p.diagnostic_stop:stop.append(p.diagnostic_stop['reason'])
    if exception:stop.append((getattr(p,'fatal',None) or {}).get('reason','implementation_exception'))
    if not finite or np.max(x['warnings']):stop.append('warning_or_nonfinite')
    if rom or reason=='rom_robot_limit_or_structural_event':stop.append('rom_or_structural_event')
    safety_end=reason not in ('reference_completed','completed')
    if safety_end and not stop:stop.append('structural_or_safety_termination:'+reason)
    bounded=bool(max(norm(x['deformation_H']))<=s['stop']['translation_m'] and max(norm(x['rotation_vector_H']))<=s['stop']['rotation_rad'])
    # Formal precision classification is preserved but is never a hard stop in this 40/80 diagnostic pair.
    write(out/'growth_windows.json',p.growth.windows)
    motion={}
    for key,label in [('dq_true_rad_s','human_joint'),('velocity_R','robot_cuff'),('velocity_H','human_cuff')]:
        acc=derivative(x[key],t);at=.5*(t[1:]+t[:-1]);jerk=derivative(acc,at)
        motion[label]=dict(acceleration=vector_metrics(acc,at),jerk=vector_metrics(jerk,.5*(at[1:]+at[:-1])))
    rates={}
    for key,label in [('force_R_world','physical_force_n_s'),('moment_R_world','physical_moment_nm_s')]:rates[label]=vector_metrics(derivative(x[key],t),.5*(t[1:]+t[:-1]))
    energy=None
    if run['arm']=='P1':
        scale=max(x['energy_scale']);energy=dict(stored_peak_j=float(max(x['stored_energy'])),damping_loss_j=float(x['cumulative_damping_loss'][-1]),minimum_damping_power_w=float(min(x['damping_power'])),net_port_work_j=float(x['net_work'][-1]),max_abs_residual_j=float(max(abs(x['energy_residual']))),max_positive_residual_j=float(max(0,max(x['energy_residual']))),final_scale_j=float(scale),max_abs_residual_ratio=float(max(abs(x['energy_residual']))/scale) if scale else 0,max_positive_residual_ratio=float(max(0,max(x['energy_residual']))/scale) if scale else 0,max_power_identity_w=float(max(abs(x['power_identity_residual']))),numerical_qualification='NOT_ESTABLISHED; exploratory override does not erase prior failed bench')
    r=dict(id=run['id'],arm=run['arm'],endpoint_deg=pt['endpoint_deg'],task=status,termination_reason=reason,raw_termination_reason=summary['termination_reason'] if summary else None,reference_completed=coverage,simulated_duration_s=float(t[-1]),reference_phase_s=float(phase[-1]),planned_reference_duration_s=trajectory.duration,tracking_rmse_deg=float(np.sqrt(np.mean((q-ref)**2))),endpoint_error_deg=endpoint,return_error_deg=return_error,return_reached=bool(phase[-1]>=2.5+2*trajectory.leg),command_force_n=vector_metrics(cmd['force'],cmd['time_s']) if cmd else None,physical_force_n=vector_metrics(x['force_R_world'],t),physical_moment_R_nm=vector_metrics(x['moment_R_world'],t),physical_moment_H_nm=vector_metrics(x['moment_H_world'],t),rates=rates,deformation_peak_mm=float(1000*max(norm(x['deformation_H']))),rotation_peak_deg=float(np.degrees(max(norm(x['rotation_vector_H'])))),human_rom_event=rom,human_min_deg=np.min(np.degrees(x['q_true_rad']),axis=0),human_max_deg=np.max(np.degrees(x['q_true_rad']),axis=0),brake=brake,no_safe_action_count=events.get('mpc_solver_failures'),motion=motion,energy=energy,force_contract=force,strict_force_contract=strict,warning_count=int(max(x['warnings'])),runtime=dict(total_run_wall_s=elapsed,wall_per_simulated_second=elapsed/max(float(t[-1]),1e-12),controller_cost=summary['computational_cost'] if summary else None),prefix_only=not coverage,stop_reasons=list(dict.fromkeys(stop)),admit_next=not stop,evidence_category='exploratory_diagnostic_only',source_config_changed=False)
    r['bounded_for_next_pair']=bounded
    r['energy_growth_windows']=len(p.growth.windows)
    r['energy_policy']='relaxed_diagnostic_only_no_instantaneous_relative_stop'
    if (run['arm']=='rigid' and not exception and finite and not p.diagnostic_stop and not np.max(x['warnings']) and not rom
        and reason in ('reference_completed','completed','no_safe_action','BRAKE_INFEASIBLE','brake_infeasible')):
        r['admit_next']=True
    write(out/'result.json',r);return r


def run_one(s,i):
    run=s['runs'][i];out=ROOT/run['id'];out.mkdir(exist_ok=False)
    write(out/'started.json',dict(command=[sys.executable,*sys.argv],pid=os.getpid(),run=run,spec_sha=sha(SPEC)))
    pt=run['point'];trajectory=base.NormalizedTrajectory(pt);plants=[]
    matrix=base.load_report_validation_matrix(base.DEFAULT_MATRIX);case=base.measurement_case(matrix,measurement_seed=s['measurement_seed']);allocator=base.default_engineering_cuff_allocator()
    manager=base.UnifiedReferenceManager(trajectory.reference,confidence_aware=False);supervisor=DetailedSupervisor();monitor=StopMonitor(plants);lock=base.CompleteModelLockMonitor(allocator)
    def factory(human):
        p=(RigidPlant if run['arm']=='rigid' else ProgressivePlant)(human,s,manager);plants.append(p);return p
    def estimator(measurement,q_prior):return base.OnlineSingleChallengerTrustEstimator(measurement,q_prior,measurement_case=case,apply_qualified_model=False,rom_human=base.HIGH_ROM_HUMAN,freeze_control_geometry=True)
    summary=trace=None;exception=None;begin=time.perf_counter()
    try:
        summary,trace=make_runtime(run['arm']=='P1')(case,duration_s=pt['maximum_simulation_duration_s'],estimator_architecture='integral_minimal',result_case_name=run['id'],true_human_override=base.HIGH_ROM_HUMAN,true_metadata_override={'case':'nominal_high_rom'},reference_fn=trajectory.reference,trajectory_label=pt['id'],trajectory_waypoints=trajectory.waypoints,plant_factory=factory,reference_execution=manager,reference_completion_phase_s=trajectory.duration,capture_system_pilot_diagnostics=True,track_brake_supervisor=supervisor,mpc_factory=lambda:base.HumanSpaceMPC(cuff_allocator=allocator),cuff_allocator=allocator,estimator_factory=estimator,physical_force_supervisor=monitor,terminate_on_structural_events=True,control_model_cycle_assertion=lock)
    except Exception:exception=traceback.format_exc()
    elapsed=time.perf_counter()-begin
    if not plants:raise RuntimeError(exception or 'plant_not_created')
    p=plants[0];np.savez_compressed(out/'initial_state.npz',**p.initial_state)
    write(out/'run_config.json',dict(measurement_case=asdict(case),mpc_config=asdict(base.HumanMPCConfig()),human=asdict(base.HIGH_ROM_HUMAN),allocator=asdict(allocator.config),point=pt,physics_dt_s=s['physics_dt_s'],control_substeps=s['control_substeps'],candidate=s['candidate'] if run['arm']=='P1' else None))
    write(out/'model_lock.json',lock.diagnostics());lock.save_cycles(out/'model_lock_cycles.npz')
    old.mujoco.mj_saveLastXML(str(out/'model.xml'),p.model)
    r=summarize(s,run,out,p,summary,trace,supervisor,elapsed,exception)
    write(ROOT/'campaign_status.json',dict(last_run=run['id'],runs_executed=i+1,stop_reasons=r['stop_reasons'],stop=bool(r['stop_reasons']) or i==1,remaining_not_run=[x['id'] for x in s['runs'][i+1:]]))
    print(json.dumps({k:r[k] for k in ['id','task','termination_reason','simulated_duration_s','deformation_peak_mm','rotation_peak_deg','stop_reasons']},indent=2),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--run-next',action='store_true');a=ap.parse_args();s=contract()
    if a.freeze:
        ROOT.mkdir(parents=True,exist_ok=False);shutil.copyfile(SPEC,ROOT/SPEC.name);shutil.copyfile(DOC,ROOT/DOC.name)
        write(ROOT/'registration.json',dict(spec_sha=sha(SPEC),md_sha=sha(DOC),implementation_hashes={str(p.relative_to(REPO)):sha(p) for p in SCRIPTS},head=s['head'],command=[sys.executable,*sys.argv],numpy=np.__version__,mujoco=old.mujoco.__version__,pid=os.getpid()))
        print('FROZEN',sha(SPEC));return
    assert a.run_next
    reg=read(ROOT/'registration.json');assert sha(SPEC)==sha(ROOT/SPEC.name)==reg['spec_sha'];assert sha(DOC)==sha(ROOT/DOC.name)==reg['md_sha']
    for p,h in reg['implementation_hashes'].items():assert sha(REPO/p)==h,p
    i=0
    while i<len(s['runs']) and (ROOT/s['runs'][i]['id']).exists():
        r=read(ROOT/s['runs'][i]['id']/'result.json');assert r['admit_next'],'campaign_stop_no_further_run';i+=1
    assert i<2,'no_extra_run'
    print('START',s['runs'][i]['id'],flush=True);run_one(s,i);contract()
    for p,h in reg['implementation_hashes'].items():assert sha(REPO/p)==h,p
if __name__=='__main__':main()
