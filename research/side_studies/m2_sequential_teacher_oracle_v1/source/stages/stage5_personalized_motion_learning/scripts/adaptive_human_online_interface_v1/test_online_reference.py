"""Kinematic/ownership unit checks; full safety probes and physics are separate."""
from pathlib import Path
import sys,unittest
import numpy as np
from types import SimpleNamespace
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1/source')
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_reference import realize,OnlineReferenceOwner
from traction_mpc_stage5.task import TaskPhase
SPEC=SimpleNamespace(q_bounds_rad=((0.,2.2),(0.,2.2)),start_return_target_rad=(.1,.2),outbound_goal_target_rad=(2.,2.))
LIMITS=dict(max_velocity=[.5,.4],max_acceleration=[.8,.7],max_jerk=[4.,3.5])
class Tests(unittest.TestCase):
    def test_nonzero_state(self):
        state=(np.array([.4,.5]),np.array([.1,-.05]),np.array([.2,-.1]))
        s=realize(state,[1.,1.1],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS);f=s.sample(0.)
        for x,y in zip(state,(f.q_rad,f.dq_rad_s,f.ddq_rad_s2)):np.testing.assert_allclose(x,y,atol=1e-12,rtol=0)
        end=s.sample(s.duration_s);np.testing.assert_allclose(end.q_rad,[1.,1.1],atol=1e-10);np.testing.assert_allclose(end.dq_rad_s,0.,atol=1e-10);np.testing.assert_allclose(end.ddq_rad_s2,0.,atol=1e-10)
    def test_continuous_bounds(self):
        s=realize(([.4,.5],[.1,-.05],[.2,-.1]),[1.,1.1],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS)
        t=np.linspace(0.,s.duration_s,5001);x=[s.sample(float(ti)) for ti in t];v=np.array([p.dq_rad_s for p in x]);a=np.array([p.ddq_rad_s2 for p in x]);j=np.diff(a,axis=0)/np.diff(t)[:,None]
        self.assertTrue(np.all(np.max(abs(v),axis=0)<=np.array(LIMITS['max_velocity'])+1e-9));self.assertTrue(np.all(np.max(abs(a),axis=0)<=np.array(LIMITS['max_acceleration'])+1e-9));self.assertTrue(np.all(np.max(abs(j),axis=0)<=np.array(LIMITS['max_jerk'])+1e-8))
    def test_ROM_rejection(self):
        with self.assertRaisesRegex(ValueError,'TARGET_OUTSIDE_ROM'):realize(([.4,.5],[0,0],[0,0]),[3.,1.],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS)
    def test_no_backdate(self):
        o=OnlineReferenceOwner(([.4,.5],[0,0],[0,0]),epoch_s=1.)
        with self.assertRaisesRegex(ValueError,'NO_REFERENCE_BACKDATING'):o.sample(.99)
    def test_continuation_origin_guard(self):
        s=realize(([.4,.5],[.1,0],[.2,0]),[1.,1.],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS)
        with self.assertRaisesRegex(ValueError,'INITIAL_CONTINUATION_C2_MISMATCH'):OnlineReferenceOwner(([.5,.5],[0,0],[0,0]),initial_schedule=s)
    def test_independent_axes(self):
        s=realize(([.4,.5],[0,0],[0,0]),[1.4,.6],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS)
        self.assertNotAlmostEqual(*s.trajectory.independent_min_durations)
    def test_repeat_exact_sample(self):
        s=realize(([.4,.5],[.1,0],[.2,0]),[1.,1.],spec=SPEC,phase=TaskPhase.OUTBOUND,**LIMITS);o=OnlineReferenceOwner(([.4,.5],[.1,0],[.2,0]),initial_schedule=s)
        a=o.sample(.02);b=o.sample(.02);np.testing.assert_array_equal(a.ddq_rad_s2,b.ddq_rad_s2)
if __name__=='__main__':unittest.main()
