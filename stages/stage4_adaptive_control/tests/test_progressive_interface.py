"""Static/algebraic preflight only; these tests integrate no ringdown/trajectory."""
from pathlib import Path
import sys
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_progressive_interface_bench as b

@pytest.fixture(scope='module')
def spec():return b.spec()


def test_registered_budget_and_retirement(spec):
    assert len(spec['candidates'])==2
    assert spec['old_candidate_status'].startswith('RETIRED')
    assert len(spec['candidates'])*len(spec['bench']['cases'])*len(spec['bench']['timesteps_s'])*spec['bench']['repeats_per_case']==36
    assert spec['gate_40_40']['max_runs']==1


@pytest.mark.parametrize('cid',[0,1])
def test_static_targets_positive_tangent_isotropy(spec,cid):
    rows,curves,qualified=b.static_bench(spec)
    c=spec['candidates'][cid];assert qualified[c['id']]['passed']
    p=b.ProgressiveParameters(**c['parameters'])
    for x in (np.zeros(3),np.array([.001,.002,-.001])):
        T=b.tangent_stiffness(x,p.k1_n_m,p.k3_n_m3)
        assert np.min(np.linalg.eigvalsh(T))>0
        np.testing.assert_allclose(T,T.T,atol=1e-12)
    q=Rotation.from_rotvec([.2,-.3,.1]).as_matrix();x=np.array([.001,.0003,-.0005])
    np.testing.assert_allclose(b.radial_load(q@x,p.k1_n_m,p.k3_n_m3),q@b.radial_load(x,p.k1_n_m,p.k3_n_m3),rtol=1e-12)


def test_energy_gradient_action_reaction_and_frame_objectivity(spec):
    p=b.ProgressiveParameters(**spec['candidates'][0]['parameters'])
    h=b.AttachmentState(np.array([.1,.2,.3]),Rotation.from_rotvec([.1,.2,.05]).as_matrix(),np.array([.001,.002,.001]),np.array([.02,.01,-.03]))
    r=b.AttachmentState(h.position_world_m+np.array([.001,.0005,-.0003]),Rotation.from_rotvec([.003,.005,-.002]).as_matrix()@h.rotation_world,np.array([.003,-.002,.004]),np.array([-.03,.05,.01]))
    v=b.evaluate_progressive(p,r,h)
    np.testing.assert_allclose(v.human_wrench_world[:3]+v.robot_wrench_world[:3],0,atol=1e-12)
    residual=v.human_wrench_world[3:]+v.robot_wrench_world[3:]+np.cross(h.position_world_m-r.position_world_m,v.human_wrench_world[:3])
    np.testing.assert_allclose(residual,0,atol=1e-12)
    assert abs(v.mechanical_power_w+v.spring_energy_rate_w+v.damping_dissipation_w)<1e-10
    def moved(a,eps):return b.AttachmentState(a.position_world_m+eps*a.velocity_world_m_s,Rotation.from_rotvec(eps*a.angular_velocity_world_rad_s).as_matrix()@a.rotation_world,a.velocity_world_m_s,a.angular_velocity_world_rad_s)
    eps=1e-6
    dU=(b.evaluate_progressive(p,moved(r,eps),moved(h,eps)).spring_energy_j-b.evaluate_progressive(p,moved(r,-eps),moved(h,-eps)).spring_energy_j)/(2*eps)
    assert np.isclose(dU,v.spring_energy_rate_w,rtol=1e-6,atol=1e-8)
    assert v.damping_dissipation_w>=0


@pytest.mark.parametrize('dt',[.001,.0005,.00025])
def test_fixture_mass_inertia_and_no_controller(spec,dt):
    m,d,xml=b.fixture(spec,dt)
    assert m.nv==6 and m.nu==0
    assert m.opt.timestep==dt and m.opt.integrator==3 and m.opt.solver==2
    assert m.opt.iterations==100 and m.opt.tolerance==1e-8
    assert m.body('plate').mass[0]==spec['bench_inertia']['bench_mass_kg']
    np.testing.assert_allclose(m.body('plate').inertia,[spec['bench_inertia']['bench_inertia_kg_m2']]*3)
    np.testing.assert_array_equal(m.opt.gravity,0)
    assert d.time==0


def test_numerical_error_and_coverage_gates(spec):
    t=np.linspace(0,.2,201)
    p={k:np.ones((len(t),3))*100 if k in ('force','moment','x','theta') else np.ones(len(t)) for k in ('force','moment','x','theta','U','Ed')}
    p['time_s']=t
    assert b.compare(spec,p,p)['passed']
    other={k:a.copy() for k,a in p.items()};other['force']*=1.03
    assert not b.compare(spec,other,p)['passed']
    early={k:a[:20] for k,a in p.items()}
    assert not b.compare(spec,early,p)['passed']
    zero={k:np.zeros_like(a) for k,a in p.items()};zero['time_s']=t
    result=b.compare(spec,zero,zero)
    assert result['passed'] and result['metrics']['force']['linf_relative'] is None


def test_invalid_parameters_rejected(spec):
    p=dict(spec['candidates'][0]['parameters']);p['k3_n_m3']=-1
    with pytest.raises(ValueError):b.ProgressiveParameters(**p)
