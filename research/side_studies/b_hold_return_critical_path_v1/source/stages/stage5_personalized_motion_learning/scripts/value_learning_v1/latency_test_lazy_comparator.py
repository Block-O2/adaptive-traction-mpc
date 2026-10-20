"""Actual-snapshot semantic comparisons; no plant rollout or threshold change."""
import hashlib
import json
from pathlib import Path
import pickle
import sys
from dataclasses import replace
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
for relative in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src',
                 'stages/stage3_full3d/src','stages/stage5_personalized_motion_learning/scripts/high_rom_v1'):
    sys.path.insert(0,str(ROOT/relative))
from research_adapter import ResearchPlanner
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation,clearance_geometry_signature

SNAPS=ROOT/'stages/stage5_personalized_motion_learning/results/value_learning_research_v1/latency_actual_moving_snapshots_v1'


def snapshot(stem,lazy):
    payload=(SNAPS/(stem+'.pickle')).read_bytes()
    metadata=json.loads((SNAPS/(stem+'.json')).read_text())
    if hashlib.sha256(payload).hexdigest()!=metadata['sha256']:raise ValueError('actual snapshot hash mismatch')
    adaptive,args=pickle.loads(payload)
    adaptive.planner.research_spec['lazy_legacy_comparator_on_committed']=lazy
    return adaptive,args


def validate(adaptive,args,decision):
    planner=adaptive.planner
    prepared=prepare_decision(decision,planner,args['belief'])
    result=validate_activation(belief=args['belief'],request_sequence=args['belief'].sequence,
        schedule=prepared.executed.schedule,clearance=planner.scheduler.clearance_evaluator,
        phase=args['phase'],request_phase=args['phase'],remaining_s=args['phase_remaining_s'],
        reference_state=args['current_reference_state'],
        certificate_geometry_at_request=clearance_geometry_signature(planner.scheduler.clearance_evaluator))
    return prepared,result


class LazyComparatorTest(unittest.TestCase):
    def test_actual_moving_same_target_schedule_cost_features_escape_validation(self):
        outputs=[]
        for lazy in (False,True):
            adaptive,args=snapshot('moving_outbound',lazy)
            decision=adaptive.decide(**args);prepared,validated=validate(adaptive,args,decision)
            self.assertTrue(validated['feasible'])
            outputs.append((decision,prepared))
            timing=decision.executed.execution_screen['research_latency']
            self.assertEqual(timing['legacy_candidate_count'],0 if lazy else 1)
            self.assertEqual(timing['legacy_comparator_computed'],not lazy)
        eager,lazy=outputs
        for left,right in zip(eager,lazy):
            np.testing.assert_array_equal(left.executed.target_q_rad,right.executed.target_q_rad)
            np.testing.assert_array_equal(left.executed.schedule.coefficients,right.executed.schedule.coefficients)
            self.assertEqual(left.executed.schedule.duration_s,right.executed.schedule.duration_s)
            self.assertEqual(left.executed.feasible,right.executed.feasible)
            self.assertEqual(left.executed.total_cost,right.executed.total_cost)
            self.assertEqual(left.executed.cost_terms,right.executed.cost_terms)
            self.assertEqual(left.executed.execution_screen['research_context'],right.executed.execution_screen['research_context'])

    def test_initial_uncommitted_remains_eager_with_identical_choice(self):
        outputs=[]
        for lazy in (False,True):
            adaptive,args=snapshot('outbound',lazy)
            decision=adaptive.decide(**args);outputs.append(decision)
            self.assertTrue(decision.executed.execution_screen['research_latency']['legacy_comparator_computed'])
        np.testing.assert_array_equal(outputs[0].executed.schedule.coefficients,outputs[1].executed.schedule.coefficients)
        self.assertEqual(outputs[0].executed.total_cost,outputs[1].executed.total_cost)

    def test_matched_rejection_computes_legacy_then_preserves_research_failure(self):
        original_screen=ResearchPlanner.screen_target
        def rejected(planner,*args,**kwargs):
            return replace(original_screen(planner,*args,**kwargs),feasible=False,rejection_reason='FORCED_HARD_SCREEN_REJECTION')
        for lazy in (False,True):
            adaptive,args=snapshot('moving_outbound',lazy);planner=adaptive.planner
            previous=planner.previous_executed_delta_q_rad.copy()
            with patch.object(ResearchPlanner,'screen_target',rejected):
                with self.assertRaisesRegex(ValueError,'RESEARCH_INFEASIBLE:FORCED_HARD_SCREEN_REJECTION'):
                    adaptive.decide(**args)
            self.assertEqual(len(planner.decisions),1)
            self.assertTrue(planner.decisions[0].executed.feasible)
            self.assertTrue(planner.decisions[0].executed.label.startswith('outbound_dq_'))
            np.testing.assert_array_equal(planner.previous_executed_delta_q_rad,previous)

    def test_rejected_committed_precheck_does_not_silently_execute_baseline(self):
        original_evaluate=ResearchPlanner._evaluate
        def rejected(planner,**kwargs):
            ev=original_evaluate(planner,**kwargs)
            is_committed=getattr(planner,'_research_committed_candidate_action',None) is not None or kwargs['label'].startswith('research_')
            return replace(ev,feasible=False,rejection_reason='FORCED_PRECHECK_REJECTION') if is_committed else ev
        for lazy in (False,True):
            adaptive,args=snapshot('moving_outbound',lazy)
            with patch.object(ResearchPlanner,'_evaluate',rejected):
                with self.assertRaisesRegex(ValueError,'RESEARCH_INFEASIBLE:FORCED_PRECHECK_REJECTION'):
                    adaptive.decide(**args)
            self.assertEqual(len(adaptive.planner.decisions),1)
            self.assertTrue(adaptive.planner.decisions[0].executed.label.startswith('outbound_dq_'))
            self.assertIsNone(getattr(adaptive.planner,'_research_committed_candidate_action',None))


if __name__=='__main__':unittest.main()
