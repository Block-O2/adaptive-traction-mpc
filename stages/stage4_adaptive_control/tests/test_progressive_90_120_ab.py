from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_progressive_90_120_ab as a

@pytest.fixture(scope='module')
def spec():return a.contract()

def test_budget_and_original_runtime(spec):
    assert len(spec['runs'])==2
    assert [r['point']['endpoint_deg'] for r in spec['runs']]==[[90,120],[90,120]]
    assert spec['candidate']['id']=='P1'
    for progressive in (False,True):
        f=a.make_runtime(progressive)
        assert f.__code__ is a.old.original.run_sensor_realism_case.__code__
        assert f.__globals__['CONTROL_SUBSTEPS']*.00025==.005
        changed={k for k,v in f.__globals__.items() if v is not a.old.original.run_sensor_realism_case.__globals__.get(k)}
        assert changed==({'CONTROL_SUBSTEPS','CausalMeasurementLayer'} if progressive else {'CONTROL_SUBSTEPS'})

def test_identical_initial_state_and_model_options(spec):
    trajectory=a.base.NormalizedTrajectory(spec['runs'][0]['point'])
    m=a.base.UnifiedReferenceManager(trajectory.reference,confidence_aware=False)
    rigid=a.RigidPlant(a.base.HIGH_ROM_HUMAN,spec,m);soft=a.ProgressivePlant(a.base.HIGH_ROM_HUMAN,spec,m)
    ro=rigid.reset(np.radians([5.,10.]));so=soft.reset(np.radians([5.,10.]))
    assert rigid.data.time==soft.data.time==0
    np.testing.assert_array_equal(rigid.data.qpos,soft.data.qpos)
    np.testing.assert_array_equal(rigid.data.qvel,soft.data.qvel)
    for name in ['body_mass','body_inertia','body_pos','jnt_range','actuator_gainprm','actuator_biasprm']:
        np.testing.assert_array_equal(getattr(rigid.model,name),getattr(soft.model,name))
    for name in dir(rigid.model.opt):
        if not name.startswith('_') and isinstance(getattr(rigid.model.opt,name),(int,float,np.ndarray)):
            np.testing.assert_array_equal(getattr(rigid.model.opt,name),getattr(soft.model.opt,name))
    assert rigid.data.eq_active[rigid.weld_id] and not soft.data.eq_active[soft.weld_id]
    assert rigid.model.opt.timestep==soft.model.opt.timestep==.00025
    assert not hasattr(so.robot_sensor,'human_q_rad')
    assert soft.diagnostic_stop is None and rigid.diagnostic_stop is None
    # No time integration in this preflight.

@pytest.mark.parametrize('key,value,expected',[
 ('warnings',1,'mujoco_warning'),('deformation_H',np.array([.01001,0,0]),'gross_translation_departure'),
 ('rotation_vector_H',np.array([.18,0,0]),'gross_rotation_departure'),('damping_power',-1e-5,'negative_damping'),
 ('energy_residual',.006,None),('energy_residual',-.2,None),('stored_energy',np.nan,'nonfinite_state_or_diagnostic')])
def test_stop_rules(spec,key,value,expected):
    r=dict(warnings=0,deformation_H=np.zeros(3),rotation_vector_H=np.zeros(3),damping_power=0.,stored_energy=1.,energy_residual=0.,energy_scale=1.)
    r[key]=value
    assert a.pathological(r,spec)==expected

def test_actual_timestep_derivative():
    t=np.arange(5)*.00025;v=np.c_[t*3,t*-2]
    np.testing.assert_allclose(a.derivative(v,t),np.tile([3,-2],(4,1)))


def synthetic_windows(residuals,amplitudes=None):
    amplitudes=amplitudes or [1]*4
    return [dict(residual_final_j=r,energy_scale_j=1.,force_peak_n=f,acceleration_peak_m_s2=f,force_oscillation_n=f,translation_oscillation_m=f/1e6,rotation_oscillation_rad=f/1e6) for r,f in zip(residuals,amplitudes)]

def test_startup_and_persistent_energy(spec):
    assert a.growth_reason(synthetic_windows([0,1e-7,2e-7,3e-7]),spec) is None
    assert a.growth_reason(synthetic_windows([0,.04,.08,.12]),spec)=='persistent_positive_energy_residual_growth'
    assert a.growth_reason(synthetic_windows([0,.04,.08,.12])[:3],spec) is None
    assert a.growth_reason(synthetic_windows([0,.04,.02,.12]),spec) is None
    assert a.growth_reason(synthetic_windows([0,-.04,-.08,-.12]),spec) is None

def test_growing_amplitude_and_steady_signal(spec):
    assert a.growth_reason(synthetic_windows([0]*4,[20,40,80,160]),spec)=='growing_force_and_acceleration_amplitude'
    assert a.growth_reason(synthetic_windows([0]*4,[160]*4),spec) is None
    assert a.growth_reason(synthetic_windows([0]*4,[20,30,20,160]),spec) is None


def test_precision_rule_is_classification_only(spec):
    assert spec['endpoint_rule']['tolerance_deg']==0.06896926724078867
    assert all('precision' not in reason.lower() for reason in spec['growth_policy'])
    assert spec['max_runs']==2

def test_detailed_supervisor_fields():
    assert issubclass(a.DetailedSupervisor,a.old.LoggedSupervisor)
