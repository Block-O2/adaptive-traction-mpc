import inspect
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_stage4_coarse_rom_capability import (
    NormalizedTrajectory, ForceMonitor, OUTPUT, sha, build_spec,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case
from traction_mpc_stage4.online_trust import OnlineSingleChallengerTrustEstimator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, sensor_realism_cases
from traction_mpc_stage4.sensor_realism import SensorBoundaryStage4Plant
from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.physical_force_contract import (
    evaluate_physical_force_trace, SIMULATION_ENGINEERING_TRANSIENT_V1, RUNTIME_OBSERVATION,
)


def test_frozen_spec_is_reproducible_and_has_27_unique_points():
    spec=json.loads((OUTPUT/'scan_spec.json').read_text())
    assert sha(OUTPUT/'scan_spec.json')==(OUTPUT/'scan_spec.sha256').read_text().split()[0]
    assert len(spec['points'])==len({p['id'] for p in spec['points']})==27
    assert spec['points'][0]['endpoint_deg']==[40,40]
    assert np.allclose(build_spec()['trajectory']['velocity_limit_deg_s'],spec['trajectory']['velocity_limit_deg_s'])


def test_shortest_common_bound_trajectory_limits_and_endpoints():
    spec=json.loads((OUTPUT/'scan_spec.json').read_text())
    vmax=np.asarray(spec['trajectory']['velocity_limit_deg_s'])
    amax=np.asarray(spec['trajectory']['acceleration_limit_deg_s2'])
    durations=[]
    for p in spec['points']:
        trajectory=NormalizedTrajectory(p); durations.append(trajectory.duration)
        delta=np.abs(np.asarray(p['endpoint_deg'])-[5,10]); leg=trajectory.leg
        assert np.all(1.875*delta/leg<=vmax+1e-12)
        assert np.all(10/np.sqrt(3)*delta/leg**2<=amax+1e-12)
        assert np.any(np.isclose(1.875*delta/leg,vmax)) or np.any(np.isclose(10/np.sqrt(3)*delta/leg**2,amax))
        np.testing.assert_allclose(np.degrees(trajectory.reference(1+leg).q_rad),p['endpoint_deg'])
        np.testing.assert_allclose(np.degrees(trajectory.reference(trajectory.duration).q_rad),[5,10])
    assert len(set(durations))>1


def test_default_runner_remains_strict_and_structural_opt_in_only():
    parameters=inspect.signature(run_sensor_realism_case).parameters
    assert parameters['physical_force_supervisor'].default is None
    assert parameters['terminate_on_structural_events'].default is False
    assert parameters['control_model_cycle_assertion'].default is None


def _online_estimator(*, frozen, perturb_shadow=False):
    case=sensor_realism_cases()[0]
    plant=SensorBoundaryStage4Plant(HUMAN)
    truth=plant.reset(np.radians([5.,10.]))
    measurement=CausalMeasurementLayer(case,truth).current
    estimator=OnlineSingleChallengerTrustEstimator(
        measurement,np.radians([5.,10.]),measurement_case=case,
        apply_qualified_model=False,freeze_control_geometry=frozen,
    )
    if perturb_shadow:
        geometry=estimator.geometry_identifier.geometry
        estimator.geometry_identifier.geometry=replace(
            geometry,thigh_length_m=geometry.thigh_length_m+0.02,
        )
    return estimator


def test_frozen_mode_keeps_nominal_control_geometry_while_shadow_changes():
    estimator=_online_estimator(frozen=True)
    frozen=estimator.model.geometry
    estimator.geometry_identifier.geometry=replace(
        estimator.geometry_identifier.geometry,
        thigh_length_m=estimator.geometry_identifier.geometry.thigh_length_m+0.02,
    )
    assert estimator.geometry.thigh_length_m != frozen.thigh_length_m
    assert estimator.model.geometry is frozen
    np.testing.assert_array_equal(
        estimator.model.beta,estimator.dynamic_identifier.population_prior,
    )


def test_shadow_geometry_change_does_not_change_frozen_mpc_action():
    case=sensor_realism_cases()[0]
    traces=[]
    for perturb in (False,True):
        def factory(measurement,q_prior,perturb=perturb):
            estimator=OnlineSingleChallengerTrustEstimator(
                measurement,q_prior,measurement_case=case,
                apply_qualified_model=False,freeze_control_geometry=True,
            )
            if perturb:
                geometry=estimator.geometry_identifier.geometry
                estimator.geometry_identifier.geometry=replace(
                    geometry,thigh_length_m=geometry.thigh_length_m+0.02,
                )
            return estimator
        _,trace=run_sensor_realism_case(
            case,duration_s=.10,estimator_architecture='integral_minimal',
            estimator_factory=factory,true_human_override=HUMAN,
            true_metadata_override={'case':'nominal_test'},
        )
        traces.append(trace)
    np.testing.assert_array_equal(
        traces[0]['desired_human_action_nm'],
        traces[1]['desired_human_action_nm'],
    )


def test_nonfrozen_mode_still_routes_shadow_geometry_to_control():
    estimator=_online_estimator(frozen=False)
    changed=replace(
        estimator.geometry_identifier.geometry,
        thigh_length_m=estimator.geometry_identifier.geometry.thigh_length_m+0.02,
    )
    estimator.geometry_identifier.geometry=changed
    assert estimator.model.geometry is changed


def test_frozen_geometry_reconstructs_live_q_and_dq_measurements():
    geometry=_online_estimator(frozen=True).model.geometry
    q0=np.radians([5.,10.]); q1=np.radians([7.,14.])
    dq0=np.zeros(2); dq1=np.radians([1.5,-2.])
    states=[]
    for q,dq in ((q0,dq0),(q1,dq1)):
        pose=geometry.cuff_pose(q)
        velocity,angular=geometry.cuff_velocity(q,dq)
        states.append(geometry.estimate_state(
            pose.translation,pose.rotation,velocity,angular,
        ))
    np.testing.assert_allclose(states[0],np.r_[q0,dq0],rtol=0,atol=1e-12)
    np.testing.assert_allclose(states[1],np.r_[q1,dq1],rtol=0,atol=1e-12)
    assert not np.array_equal(states[0],states[1])


def test_monitor_stops_immediately_on_hard_and_tolerates_short_transient():
    t=np.arange(0,.040,.001); f=np.full(len(t),180.)
    f[15:17]=210.
    monitor=ForceMonitor()
    for timestamp,force in zip(t,f): assert not monitor.update(timestamp,np.array([force,0.,0.]))
    report=evaluate_physical_force_trace(t,f,policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,numerical_confirmation=RUNTIME_OBSERVATION)
    assert report.classification=='TRANSIENT_ENGINEERING_QUALIFIED'
    assert monitor.update(.041,np.array([221.,0.,0.]))
