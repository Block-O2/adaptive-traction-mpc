"""A5 仅stdlib的已曝光数据整理；0模型导入/forward/fit/physics。"""
from pathlib import Path
import copy
import hashlib
import json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def main():
    root = Path(__file__).resolve().parents[1]
    package = root.parents[2]
    paths = {
        'A3_data': 'families/critic_value/coverage_state_v3/data/STATE_JOINED_DATASET_V1.json',
        'A3_bundle': 'families/critic_value/coverage_state_v3/fit_run_v1/A3_FROZEN_BUNDLE_V1.json',
        'A3_LOCO': 'families/critic_value/coverage_state_v3/fit_run_v1/DEVELOPMENT_LOCO_V1.json',
        'A4_LOCO': 'families/critic_value/coverage_margin_v4/fit_run_v1/DEVELOPMENT_LOCO_V1.json',
        'case_identity': 'families/history_conditioned/SAC_REPLAY_V3_CASE_IDENTITY_AUDIT.json',
        'gate_config': 'experiments/V8COMPENG03.json',
        'gate_closed': 'owned/V8COMPENG03_SUPERVISOR_END.json',
        'gate_context': 'history/V8COMPENG03_PREFORK_CAUSAL_CONTEXT.json',
        'gate_proof': 'predictions/V8COMPENG03_FROZEN_CONTEXT_DECISIONS.json',
        'gate_plant': 'audit/V8COMPENG03_ACTUAL_PLANT_BINDING_EVALUATION_ONLY.json',
        'EARLY_PHASE': 'attempts/V8COMPENG03_EARLY_PHASE_RESULT.json',
        'LATE_PHASE': 'attempts/V8COMPENG03_LATE_PHASE_RESULT.json',
    }
    files = {name: {'path': rel, 'sha256': sha(package / rel)} for name, rel in paths.items()}
    assert files['A3_data']['sha256'] == '54b017803ae55575e1284dda2156d7534eaa9a2ebb6796d512709b439a2e863a'
    assert files['A3_bundle']['sha256'] == '7b1be56afdcc29c628a1a96f742caedbb65965d80f96d2799d11fc975a3b356f'
    loaded = {name: json.loads((package / rel).read_text()) for name, rel in paths.items()}
    closed = loaded['gate_closed']
    assert closed['state'] == 'STOP' and closed['worker_exit_code'] == 0 and closed['survivors'] == []
    old = loaded['A3_data']; menu = old['menu']; assert len(old['rows']) == 48 and len(menu) == 5
    identity = {r['group_evaluation_only']: r for r in loaded['case_identity']['identity_evidence_evaluation_only']}
    group_to_case = {g['group']: identity[g['group']]['case_sha256'] for g in old['groups']}
    assert len(group_to_case) == len(set(group_to_case.values())) == 10
    heavy = next(r for r in old['rows'] if r['id'] == 'EARLYH01_B')
    assert group_to_case['EARLYH01'] == loaded['gate_config']['case_sha256'] == loaded['gate_plant']['case_sha256']
    raw = loaded['gate_context']; assert raw == heavy['context']['raw_payload'], 'KNOWN_HEAVY_CAUSAL_PAYLOAD_MUST_BE_EXACT'
    proof = loaded['gate_proof']['A_source_proof_audit']
    assert proof['all_predictions_before_any_B_result'] is True
    assert proof['proof_audit']['prefork_payload_file_sha256'] == files['gate_context']['sha256']
    assert proof['proof_audit']['prefork_payload_checksum'] == raw['causal_payload_sha256']
    assert proof['proof_audit']['actual_in_memory_callback_code_checked'] is True
    assert proof['actual_source_proof'] in old['input_source_profiles']
    for role, entry in proof['proof_audit']['roles'].items():
        assert sha(package / entry['path']) == entry['actual_file_sha256'] == entry['job_manifest_file_sha256'] == entry['expected_profile_sha256'] == proof['actual_source_proof'][role]
    rows = []
    for row in old['rows']:
        label = row['labels_evaluation_only']; assert label['complete'] is True
        rows.append({'id_evaluation_only': row['id'], 'case_sha256_split_evaluation_only': group_to_case[row['group']],
            'old_parent_split_evaluation_only': row['split_parent_group_evaluation_only'],
            'group_evaluation_only': row['group'], 'context': copy.deepcopy(row['context']),
            'recipe_sha256': row['action_recipe_sha256'], 'origin_evaluation_only': 'OLD48_FULL_TASK',
            'operational_qualified_target_only': bool(label['original_qualified']),
            'complete_target_metadata_only': True,
            'provenance_evaluation_only': {'old_row_id': row['id'], 'old_data': files['A3_data']}})
    config_actions = {a['tag']: a['action'] for a in loaded['gate_config']['actions']}
    for tag in ['EARLY_PHASE', 'LATE_PHASE']:
        result = loaded[tag]; item = next(m for m in menu if m['tag'] == tag)
        assert result['complete'] is False and result['qualified'] is False
        assert result['action'] == item['action'] == config_actions[tag]
        assert result['prediction']['recipe_sha256'] == item['recipe_sha256'] == digest(item['action_recipe'])
        assert result['prediction']['all_A_B_D_decisions_frozen_before_B'] is True
        protected = result['protected_task_failure']
        assert protected['abort_reason'] == 'NO_FEASIBLE_WAYPOINT:AssertionError:KNEE_REFERENCE_MUST_BE_CONSTANT'
        assert len(protected['hard_safety_conditions']) == 11 and all(v is True for v in protected['hard_safety_conditions'].values())
        assert result['actual_new_native_steps'] > 0
        assert not any(r['case_sha256_split_evaluation_only'] == group_to_case['EARLYH01'] and r['recipe_sha256'] == item['recipe_sha256'] for r in rows)
        rows.append({'id_evaluation_only': result['id'], 'case_sha256_split_evaluation_only': group_to_case['EARLYH01'],
            'old_parent_split_evaluation_only': heavy['split_parent_group_evaluation_only'],
            'group_evaluation_only': 'V8COMPENG03',
            'context': {'raw_payload': copy.deepcopy(raw), 'source_proof': copy.deepcopy(proof['actual_source_proof'])},
            'recipe_sha256': item['recipe_sha256'], 'origin_evaluation_only': 'EXPOSED_ENGINEERING_PARTIAL_OPERATIONAL_FAILURE',
            'operational_qualified_target_only': False, 'complete_target_metadata_only': False,
            'provenance_evaluation_only': {'result': files[tag], 'config': files['gate_config'], 'closed': files['gate_closed'],
                'capture': files['gate_context'], 'actual_source_proof_archive': files['gate_proof'],
                'native_steps_already_paid': result['actual_new_native_steps'], 'abort_reason': protected['abort_reason'],
                'hard_conditions_all_true': True, 'full_JF_JM_and_45_margins': 'MISSING_NOT_IMPUTED'}})
    assert len(rows) == len({(r['case_sha256_split_evaluation_only'], r['recipe_sha256']) for r in rows}) == 50
    rows.sort(key=lambda r: r['id_evaluation_only'])
    data = {'schema': 'v8.a5.operational_qualification_support_dataset.v1', 'risk_rows': rows, 'menu': menu,
        'input_source_profiles': old['input_source_profiles'], 'input_source_profile_paths': old['input_source_profile_paths'],
        'source_files': files, 'group_to_case_sha256_split_only': group_to_case,
        'cost_targets_and_weights': 'UNCHANGED_A3_OLD48_ONLY_EXTERNAL_FROZEN_SOURCE',
        'partial_cost_or_motion_margin_imputation': False, 'input_representation': 'WRENCH39_ONLY_RAW77_STILL_INVALID',
        'distinct_case_folds': 10, 'all_cases_exposed_development_not_test': True,
        'new_model_init_forward_fit_physics': 0}
    save(root / 'data/OPERATIONAL_RISK50_DATASET_V1.json', data)
    audit = {'status': 'PASS_METADATA_DATA_PREPARATION_ONLY_NOT_FIT', 'dataset_sha256': sha(root / 'data/OPERATIONAL_RISK50_DATASET_V1.json'),
        'source_files': files, 'old_rows': 48, 'new_operational_partial_rows': 2, 'risk_total_rows': 50,
        'distinct_case_and_case_action_cells': [10, 50], 'cost_rows_unchanged': 48,
        'new_complete_cost_or_45_margin_labels': 0, 'causal_payload_exact_old_heavy': True,
        'partial_rows_reuse_real_gate_seven_role_proof': True,
        'heavy_LOCO_old_and_new_train_ids_exact_same': True,
        'heavy_LOCO_improvement_from_own_new_labels_possible': False,
        'extra_physics_paid_here': 0, 'model_import_or_calls': 0, 'fit': 0,
        'unselected_nested_calibration_branch': 'NOT_RUN', 'sealed_or_Beta_reads': 0}
    save(root / 'analysis/DATA_AVAILABILITY_AND_IDENTITY_V1.json', audit)
    print(json.dumps({'dataset_sha256': audit['dataset_sha256'], 'risk_rows': 50, 'case_folds': 10, 'cost_rows': 48}))


if __name__ == '__main__':
    main()
