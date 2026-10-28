"""Final exact physics ledger plus scoped, nonadditive resource evidence index."""
from pathlib import Path
import hashlib
import json
import resource
import time

P = Path(__file__).resolve().parents[1]


def ref(rel):
    raw = (P / rel).read_bytes()
    return dict(path=rel, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def read(rel):
    return json.loads((P / rel).read_text())


def main():
    started, cpu = time.monotonic(), time.process_time()
    sr = 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'
    cr = 'families/history_conditioned/audit/coverage_runs/MAIN_FINAL_CLOSED_V2_ONCE/RESULT.json'
    snapshot, coverage = read(sr), read(cr)
    assert snapshot['status'] == 'CLOSED_EXACT' and not snapshot['open_attempt_ids']
    assert coverage['status'] == 'COMPLETE_SCOPE_APPROPRIATE_METADATA_COVERAGE' and not coverage['gaps']
    assert snapshot['original_start_count'] == snapshot['original_end_count'] == coverage['physical_id_count']
    current_snapshot_sha = ref(sr)['sha256']
    assert coverage['physical_snapshot']['path'] == sr and coverage['physical_snapshot']['sha256'] == current_snapshot_sha
    assert read(str(Path(cr).with_name('END.json')))['result_sha256'] == ref(cr)['sha256']
    verification = read('audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json')
    assert verification['references'][sr] == current_snapshot_sha
    prefixes = [row for row in coverage['rows'] if row['partial_parent_prefix_no_TASK_scorer']]
    assert coverage['counts']['partial_parent_prefix_no_TASK_scorer'] == len(prefixes) == 3
    assert {row['id'] for row in prefixes} == {'V8FROZENENG01_parent', 'V8OP01H_parent', 'V8BETA02L_parent'}
    assert all(row['TASK_scorer_applicable'] is False and row['complete_task'] is None and row['original_qualified'] is None for row in prefixes)
    assert read('audit/HISTORY_PROTECTION_FINAL.json')['status'] == 'PASS'
    assert verification['status'] == 'PASS'
    indices = [
        'families/history_conditioned/audit/FAMILY_RESOURCE_EVIDENCE_INVENTORY_V3.json',
        'families/history_conditioned/audit/FAMILY_RESOURCE_EVIDENCE_INCREMENT_V4.json',
        'audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json',
        'audit/HISTORY_PROTECTION_FINAL.json', 'audit/HISTORY_FINAL_PROCESS_END.json',
        'audit/NEW_CONTEXT_SPAN_EXECUTION_END_V1.json',
        'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/new_context_span_diagnostic_v1/diagnostics/NEWCTX_ONCE_V1/RESULT.json',
        'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/new_context_span_diagnostic_v1/diagnostics/NEWCTX_ONCE_V1/DONE.json',
        'families/history_conditioned/audit/V8CONVAL01_INDEPENDENT_CONTINUOUS_C4_V1/END.json',
        'families/history_conditioned/audit/V8CONVAL02_INDEPENDENT_CONTINUOUS_C4_V1/END.json',
        'families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL03_MAIN_V1/RESULT.json',
        'families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL04_MAIN_V1/RESULT.json',
        'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/outputs/V8FMEAN03_ONCE_V2/REPORT.json',
        'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/outputs/V8FMEAN04_ONCE_V2/REPORT.json',
        'families/critic_value/analysis/postapp01_closed_metadata_review_v1/RESULT.json',
        'families/critic_value/analysis/final_scientific_consistency_review_v1/REVIEW_EVIDENCE_V1.json']
    external = [ref(str(f.relative_to(P))) for f in sorted((P / 'audit').rglob('*RESOURCE*.txt'))]
    supervisors = [ref('owned/' + group + '_SUPERVISOR_END.json') for group in sorted(snapshot['groups'])]
    data = dict(
        schema='v8.final_resource_and_attempt_accounting.v1', status='EXACT_PHYSICAL_INCREMENT_SCOPED_RESOURCE_EVIDENCE_GLOBAL_COST_UNKNOWN',
        created_unix=time.time(), activation=read('ACTIVATION.json')['activation_id'],
        T0_unix=1793071540.0, original_global_stop_unix=1793114740.0,
        global_attempt_episode_gradient_model_quota=None,
        actual_physical=dict(START=snapshot['original_start_count'], END=snapshot['original_end_count'],
                             actual_new_native_steps=snapshot['actual_new_native_steps_closed'],
                             actual_new_simulation_s=snapshot['actual_new_simulation_s_closed'],
                             open_attempts=[], unresolved_increment_counts=[], groups=snapshot['groups'],
                             source=ref(sr), rule=snapshot['accounting_rule'], reused_historical_native_steps_added=0),
        evaluator_coverage=dict(source=ref(cr), counts=coverage['counts'], physical_ids=coverage['physical_id_count'],
                                gaps=[], audit_PASS_does_not_imply_TASK_qualified=True,
                                three_paid_parent_prefixes_no_TASK_evaluator_and_Beta_three_UNKNOWNs_retained=True),
        research_condition_units=dict(original_new_parameter_conditions=2,
                                      six_original_jobs_are_not_six_independent_conditions=True,
                                      postvalidation_and_old_development_diagnostics_add_no_original_independent_conditions=True,
                                      seeds_aliases_heads_folds_and_replays_are_not_independent_patients=True),
        selected_actual_operation_counts=dict(
            A1_fit_calls=48,
            A2=dict(risk_fits=54, two_RHS_ridge_solves=324, prediction_APIs=960),
            A3=dict(risk_fits=33, two_RHS_ridge_solves=198, prediction_APIs=720),
            A4=dict(ridge_solves=33, RHS=1617, prediction_APIs=320, A3_cost_dots=600),
            A5=dict(fits=11, LBFGS_iterations=96, objective_gradient_evaluations=107, prediction_APIs=20),
            categorical_fresh=dict(policy_rollouts=32, complete_qualified=24, complete_motion_failed=8,
                                    parameter_updates=16, score_calls=64, train_forward_calls=96),
            Beta_original=dict(policy_children_started=25, complete_policy_children=24, complete_qualified=0,
                               partial_policy_children=1, committed_update_calls=8, nonzero_updates=0,
                               committed_score_calls=32, committed_train_forward_calls=48,
                               second_batch_updates=0, second_batch_external_pending_draws=9,
                               unresolved_parent_hard_scopes=3, no_second_commit_or_cancel=True),
            feasibility_private_old_behavior=dict(unique_old_draws=4, old_contexts=2, private_steps=12,
                                                  train_forward_calls=72, score_calls=48, fresh_sampling_physics=0),
            frozen_new_context_arithmetic=dict(dot26=111, dot2=48, two_by_two_solves=14,
                                               explicit_two_head_linear_projection_equivalents=12,
                                               new_nonlinear_mean_learner_fit_RNG_physics=0),
            BC_aggregation=dict(SGD_steps=720, normalization_fits=1, simple_rules=6),
            terminal_SAC=dict(replay_rows=64, initializations=48, SGD_steps=1650,
                              exact_critic_new_solves=26, exact_critic_heads=39,
                              semantics='terminal done=True y=r, not multistep SAC'),
            neural_Q=dict(initializations=468, SGD_steps=93600, forward_calls=96300,
                          prediction_calls=2700, snapshots=1404, physical_trials_added_by_offline_fit=0),
            E2_full_TASK=dict(ridge_solves=704, RHS=11264, initializations=66,
                              Adam_updates=13200, training_forward_calls=17600, training_backward_calls=17600,
                              predict_calls=2240, prediction_query_vectors=5853696),
            continuous_BO=dict(known_CONTILC01=dict(solves=42, heads_per_solve=47, decision='ABSTAIN', new_candidates=0),
                               original_heavy_CONVAL01=dict(status='NOT_RUN_FRONT_GATE_PARTIAL', new_candidates=0),
                               original_light_CONVAL02=dict(solves=42, heads_per_solve=47, decision='ABSTAIN', new_candidates=0))),
        operation_count_scope='Selected actually instrumented operations; not a global model/fit total. Full per-variant counts and sources remain in family receipts/indices. Composite bundles, aliases, heads and fit calls use distinct units.',
        resource_evidence=dict(indices=[ref(x) for x in indices], external_time_receipts=external,
                               external_time_receipt_count=len(external), closed_supervisors=supervisors,
                               summation_forbidden='Core, launcher-inclusive, parent/child, repeated snapshots and ru_maxrss overlap; do not sum as global totals.'),
        global_resource_totals=dict(total_CPU_s=None, total_GPU_s=None, global_peak_RSS_bytes=None,
                                    total_tool_and_LLM_compute=None,
                                    status='UNKNOWN_NOT_IMPUTED_ZERO_INCOMPLETE_GLOBAL_TELEMETRY',
                                    measured_receipts_available=True,
                                    initial_or_final_memory_snapshots_are_not_peak_usage=True),
        scope_limits=['Scientific simulation only; host realtime validity, hardware and clinical qualification not established.',
                      'Original partial costs are not complete-task ranks; UNKNOWN safety scopes remain UNKNOWN.',
                      'Menu sharing and offpolicy reuse do not demonstrate net physical or compute efficiency.'],
        collector=dict(wall_s=time.monotonic()-started, CPU_s=time.process_time()-cpu,
                       RSS_raw_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       RSS_scope='collector process high-water mark, not incremental memory or global peak',
                       new_model_scorer_fit_physics_calls=0,
                       source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    with (P / 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json').open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=data['status'], physical=data['actual_physical']['START'],
                          native=data['actual_physical']['actual_new_native_steps'], resource_receipts=len(external))))


if __name__ == '__main__':
    main()
