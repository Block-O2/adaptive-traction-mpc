"""Gate scope guards: plausible algorithm work is not wall/hardware qualification."""
import unittest
from latency_gate_builder import build_gate


def fixtures():
    cpu={'models':{'ridge_full':[{}],'mlp_full':[{}]},'model_file_sha256':{'ridge_full':'ridge','mlp_full':'mlp'}}
    row=lambda count,maximum:dict(legacy_candidate_limit=1,requested_research_candidate_count=count,
        observed_research_candidate_count=[count]*3,failed_count=0,admitted_completed_count=3,
        algorithm_through_original_epoch_reference_validation_ms={'count':3,'maximum':maximum})
    replays=[dict(captured_phase='OUTBOUND',captured_path_index=0,captured_continuation_committed=False,
                  captured_reference_stationary=True,model_file_sha256='ridge',rows=[row(4,70)]),
             dict(captured_phase='OUTBOUND',captured_path_index=1,captured_continuation_committed=True,
                  captured_reference_stationary=False,
                  model_file_sha256='ridge',rows=[row(1,20)])]
    normal={'status':'VALID','active_model_file_immutable_during_rep':True,'model_sha256_at_start':'ridge',
            'pattern':{'mode':'VALUE_PATTERN','legacy_candidate_limit':1,'proposal_descriptors':[{}]*4}}
    profile={'source_complete':True,'snapshot_capture_extra_io_source_count':0,'clean_role_timings_ms':{
        'first_pattern_selection':{'capture_to_activation_ms':{'count':1,'maximum':80}},
        'moving_continuation':{'capture_to_activation_ms':{'count':5,'maximum':50}}}}
    return cpu,{'ranking_gate':'PASS'},replays,profile,normal


class GateScopeTest(unittest.TestCase):
    def test_pure_algorithm_plausibility_does_not_claim_wall_qualification(self):
        cpu,offline,replays,profile,normal=fixtures()
        result=build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)
        self.assertTrue(result['ready_for_small_scientific_pilot'])
        self.assertFalse(result['observed_full_host_spans_within_architecture_opportunity'])
        self.assertFalse(result['hardware_realtime_qualified'])

    def test_exact_ceiling_is_not_inside_strict_source_age(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[0]['rows'][0]['algorithm_through_original_epoch_reference_validation_ms']['maximum']=100
        self.assertFalse(build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)['ready_for_small_scientific_pilot'])

    def test_capture_io_cannot_replace_clean_model_run(self):
        cpu,offline,replays,profile,normal=fixtures()
        normal['pattern']['capture_snapshot_dir']='captured'
        self.assertFalse(build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)['clean_normal_model_rollout_validated'])

    def test_mixed_model_timing_cannot_gate_one_configuration(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[1]['model_file_sha256']='mlp'
        self.assertFalse(build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)['immutable_model_hashes_match'])

    def test_missing_evidence_remains_pending(self):
        cpu,offline,replays,profile,normal=fixtures()
        self.assertEqual(build_gate(cpu,offline,[])['status'],'PENDING_ACTUAL_COMPUTATION_EVIDENCE')

    def test_first_role_does_not_accept_later_one_candidate_as_four(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[0]['rows'][0]['observed_research_candidate_count']=[1,1,1]
        self.assertEqual(build_gate(cpu,offline,replays)['status'],'PENDING_ACTUAL_COMPUTATION_EVIDENCE')

    def test_moving_first_reference_cannot_receive_stationary_100ms_budget(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[0]['captured_reference_stationary']=False
        self.assertEqual(build_gate(cpu,offline,replays)['status'],'PENDING_ACTUAL_COMPUTATION_EVIDENCE')

    def test_normal_run_must_match_exact_profiled_proposal_descriptors(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[0]['rows'][0]['proposed_descriptor_content_sha256']='different_bank'
        self.assertFalse(build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)['clean_normal_model_rollout_validated'])

    def test_stationary_committed_proxy_never_claims_direct_moving_measurement(self):
        cpu,offline,replays,profile,normal=fixtures()
        replays[1]['captured_reference_stationary']=True
        replays[1]['captured_reference_velocity_rad_s']=[0.,0.]
        gate=build_gate(cpu,offline,replays,normal_profile=profile,normal_run=normal)
        self.assertFalse(gate['moving_handoff_algorithm_directly_measured'])
        self.assertFalse(gate['ready_for_small_scientific_pilot'])
        self.assertEqual(gate['status'],'PENDING_ACTUAL_COMPUTATION_EVIDENCE')


if __name__=='__main__':unittest.main()
