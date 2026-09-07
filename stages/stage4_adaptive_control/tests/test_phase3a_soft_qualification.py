"""Preflight algebra and gate tests; no trajectory integration or controller rollout."""
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_stage4_phase3a_soft_qualification as q
from traction_mpc_stage3.spring_damper_interface import AttachmentState,evaluate_interface
from scipy.spatial.transform import Rotation

@pytest.fixture(scope='module')
def spec(): return q.approved_spec()


def test_three_run_contract_and_unchanged_sources(spec):
    assert len(spec['runs'])==3
    assert spec['tolerances']['transmitted_physical_force_peak_absolute_difference_n']==2
    assert spec['frozen_trajectory']['endpoint_deg']==[40,40]
    for r in spec['runs']:
        assert r['physics_dt_s']*r['low_level_substeps']==spec['low_level_period_s']


@pytest.mark.parametrize('dt',[.001,.00025])
def test_model_reset_and_robot_boundary(spec,dt):
    p=q.CompliantPlant(q.base.HIGH_ROM_HUMAN,q.parameters(spec),dt,spec['tolerances'])
    rigid=q.base.CapturePlant(q.base.HIGH_ROM_HUMAN)
    o=p.reset(np.radians([5.,10.])); r=rigid.reset(np.radians([5.,10.]))
    np.testing.assert_array_equal(p.data.qpos,rigid.data.qpos)
    np.testing.assert_array_equal(p.data.qvel,rigid.data.qvel)
    assert not p.data.eq_active[p.weld_id] and rigid.data.eq_active[rigid.weld_id]
    assert np.linalg.norm(o.robot_sensor.cuff_force_vector_n)<1e-8
    for name in dir(rigid.model.opt):
        if name.startswith('_') or name=='timestep': continue
        a=getattr(rigid.model.opt,name); b=getattr(p.model.opt,name)
        if isinstance(a,(int,float,np.ndarray)):
            np.testing.assert_array_equal(a,b,err_msg=name)
    assert p.model.opt.timestep==dt
    assert not hasattr(o.robot_sensor,'human_q_rad')
    assert not hasattr(o.robot_sensor,'deformation_H')
    assert q.local_verdicts(p.trace(),spec['tolerances'])['MECHANICS_CONSISTENCY']=='PASS'
    matrix=q.base.load_report_validation_matrix(q.base.DEFAULT_MATRIX)
    case=q.base.measurement_case(matrix,measurement_seed=44104)
    capture=q.CausalMeasurementLayer._capture
    seen=[]
    def audit(self,truth):
        assert isinstance(truth,q.RobotInterfaceSensorTruth)
        seen.append(truth)
        return capture(self,truth)
    with patch.object(q.CausalMeasurementLayer,'_capture',audit):
        layer=q.RobotPortMeasurementLayer(case,o)
    assert len(seen)==1
    expected=q.CausalMeasurementLayer(case,o.robot_sensor)
    np.testing.assert_array_equal(layer.current.cuff_moment_vector_nm,expected.current.cuff_moment_vector_nm)
    with pytest.raises(TypeError): q.RobotPortMeasurementLayer(case,r)


def test_constitutive_transport_and_power(spec):
    r=AttachmentState(np.array([.01,.02,.03]),Rotation.from_rotvec([.05,.02,.01]).as_matrix(),np.array([.1,.2,-.1]),np.array([.2,-.1,.1]))
    h=AttachmentState(np.zeros(3),np.eye(3),np.array([.02,-.03,.01]),np.array([-.1,.02,.2]))
    i=evaluate_interface(q.parameters(spec),r,h)
    np.testing.assert_allclose(i.human_wrench_world[:3]+i.robot_wrench_world[:3],0,atol=1e-12)
    moment=i.human_wrench_world[3:]+np.cross(h.position_world_m-r.position_world_m,i.human_wrench_world[:3])+i.robot_wrench_world[3:]
    np.testing.assert_allclose(moment,0,atol=1e-12)
    assert abs(i.mechanical_power_w+i.spring_energy_rate_w+i.damping_dissipation_w)<1e-12
    assert i.damping_dissipation_w>=0


def synthetic(spec,residual=0.):
    p=q.CompliantPlant(q.base.HIGH_ROM_HUMAN,q.parameters(spec),.001,spec['tolerances'])
    p.reset(np.radians([5.,10.]))
    t=p.trace(); t['stored_energy'][:]=1.;t['energy_residual'][:]=residual
    return t


def test_energy_gate_limits(spec):
    t=synthetic(spec,-.009)
    assert q.local_verdicts(t,spec['tolerances'])['DISCRETE_ENERGY']=='PASS'
    t['energy_residual'][:]=-.011
    assert q.local_verdicts(t,spec['tolerances'])['DISCRETE_ENERGY']=='FAIL'
    t['energy_residual'][:]=.006
    assert q.local_verdicts(t,spec['tolerances'])['DISCRETE_ENERGY']=='FAIL'
    t['energy_residual'][:]=0.;t['damping_power'][:]=-1e-5
    assert q.local_verdicts(t,spec['tolerances'])['DISCRETE_ENERGY']=='FAIL'


def test_mechanics_not_closed_loop_label(spec):
    t=synthetic(spec)
    t['moment_balance_residual'][:]=.01
    assert q.local_verdicts(t,spec['tolerances'])['MECHANICS_CONSISTENCY']=='FAIL'
    t['moment_balance_residual'][:]=0.;t['warnings'][:]=1
    assert q.local_verdicts(t,spec['tolerances'])['MECHANICS_CONSISTENCY']=='FAIL'
    t['warnings'][:]=0;t['stored_energy'][:]=np.nan
    assert q.local_verdicts(t,spec['tolerances'])['MECHANICS_CONSISTENCY']=='FAIL'


def test_waveform_and_independent_peak_gates(spec):
    t=np.linspace(0,1,1001); y=np.ones((len(t),3)); y[:,1:]=0; y*=100
    assert q.waveform_gate(t,y,t,y,.1,spec['tolerances'])['passed']
    assert not q.waveform_gate(t,1.03*y,t,y,.1,spec['tolerances'])['passed'] # L2>2%
    assert not q.force_peak_gate(1.03*y,y,2.)['passed']
    assert q.force_peak_gate(1.02*y,y,2.)['passed']
    zero=np.zeros(len(t)); z=q.waveform_gate(t,zero,t,zero,1e-5,spec['tolerances'])
    assert z['passed'] and z['linf_relative'] is None
    assert not q.waveform_gate(t[:1],zero[:1],t[:1],zero[:1],1e-5,spec['tolerances'])['passed']


def test_determinism_and_discrete_events():
    a={'q':np.array([1.]),'mode':np.array(['TRACK'])}
    assert all(x['passed'] for x in q.deterministic_arrays(a,a).values())
    assert not q.deterministic_arrays(a,{**a,'q':np.array([1.+2e-12])})['q']['passed']
    assert not q.deterministic_arrays(a,{'q':a['q']})['mode']['passed']
    assert not q.deterministic_arrays(a,{**a,'mode':np.array(['BRAKE'])})['mode']['passed']
    labels,t=q.status_transitions([0.,.005,.01],['TRACK','TRACK','BRAKE'])
    assert labels==['TRACK','BRAKE'];np.testing.assert_array_equal(t,[0.,.01])
