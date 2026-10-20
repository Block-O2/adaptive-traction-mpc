"""Meaningful bookkeeping, causal feature, action authority and finite-deadline tests."""
import unittest,sys
import numpy as np
from sac_env import *
from traction_mpc_stage5.task import load_goal_task_spec,GoalTaskState
class Tests(unittest.TestCase):
    def setUp(self):
        self.spec=load_goal_task_spec(S/'configs/high_rom_v1/stage5_goal_task_120_v1.json')
    def test_all_ROM_targets_and_joint_independence(self):
        bounds=np.asarray(self.spec.q_bounds_rad)
        for action in ([-1,-1],[-1,1],[1,-1],[1,1],[.3,-.2],[0,0]):
            target=action_to_target(action,self.spec)
            np.testing.assert_allclose(target_to_action(target,self.spec),action,atol=1e-14)
            self.assertTrue(np.all(target>=bounds[:,0]) and np.all(target<=bounds[:,1]))
        self.assertGreater(action_to_target([1,-1],self.spec)[0],action_to_target([-1,1],self.spec)[0])
    def test_fixed_normalization_no_episode_statistics(self):
        spec=feature_spec();self.assertEqual(len(spec),55)
        self.assertTrue(all(f['scale']>0 and f['clip'] is None and not f['evaluation_statistics_update'] for f in spec))
        np.testing.assert_allclose(normalized(SCALES),np.ones(55))
        np.testing.assert_allclose(normalized(20*SCALES),np.full(55,20.))
        self.assertFalse(any('truth' in f['name'] or 'future' in f['name'] for f in spec))
    def test_left_quadrature_reward_sign_and_terminal_penalty(self):
        env=SACExpertEnv('/tmp/not_started',{},{});env.last_decision_potential=.3
        env.force_integral=20.;env.rejections=2
        reward,parts=env._reward(.4,False,False)
        self.assertAlmostEqual(parts['force'],-.2);self.assertAlmostEqual(parts['rejection'],-.4)
        self.assertAlmostEqual(parts['shaping'],5*(gamma_for(.05)*.4-.3))
        reward,parts=env._reward(0.,False,True);self.assertEqual(parts['failure'],-1000.)
        self.assertEqual(parts['completion'],0.);self.assertLess(reward,-999.)
        env.close()
    def test_discount_horizon_is_physical_time(self):
        for p in (.01,.02,.05):self.assertAlmostEqual(gamma_for(p)**(30/p),np.exp(-30/150),places=12)
    def test_potential_never_rewards_more_than_complete_path(self):
        self.assertEqual(potential(TaskPhase.OUTBOUND,self.spec.start_return_target_rad,self.spec,0.),0.)
        self.assertEqual(potential(TaskPhase.OUTBOUND,self.spec.outbound_goal_target_rad,self.spec,0.),1.)
        self.assertEqual(potential(TaskPhase.HOLD,self.spec.outbound_goal_target_rad,self.spec,.5),2.)
        self.assertEqual(potential(TaskPhase.RETURN,self.spec.start_return_target_rad,self.spec,0.),3.)
        self.assertEqual(potential(TaskPhase.ABORTED,self.spec.start_return_target_rad,self.spec,0.),0.)
if __name__=='__main__':unittest.main()
