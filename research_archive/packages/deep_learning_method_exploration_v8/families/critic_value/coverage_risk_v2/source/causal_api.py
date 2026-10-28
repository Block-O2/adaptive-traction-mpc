"""A2 独立因果转换；仅纯 Python 数值转换，无模型、I/O 或仿真。"""
import hashlib
import json
import math

BETA = ['a_inertia_combination', 'b_distal_inertia_combination', 'd_mass_length_com_combination', 'g1_proximal_gravity_combination', 'g2_distal_gravity_combination', 'k1_passive_stiffness', 'k2_passive_stiffness', 'rho1_stiffness_rest_combination', 'rho2_stiffness_rest_combination', 'bv1_viscous_damping', 'bv2_viscous_damping']
FEATURE_NAMES = ['estimated_beta_' + n for n in BETA] + ['estimated_geometry_' + n for n in ['hip_plane_x', 'hip_plane_z', 'thigh_length', 'knee_to_cuff_distance']] + ['residual_weight_' + j + '_' + n for j in ['hip', 'knee'] for n in ['constant', 'q_hip_normalized', 'q_knee_normalized', 'dq_hip_bounded', 'dq_knee_bounded']]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def to_context25(payload):
    if not isinstance(payload, dict) or any(n in payload for n in ['labels_evaluation_only', 'original_qualified', 'JF', 'JM', 'case_key', 'case_path']):
        raise ValueError('ONLY_CAUSAL_CONTEXT_NOT_DATASET_ROW')
    if payload.get('schema') == 'ihear.causal_human_context.v1.77d':
        body = {k: v for k, v in payload.items() if k != 'causal_payload_sha256'}
        assert digest(body) == payload['causal_payload_sha256']
        assert payload['hidden_or_future_inputs_used'] is False
        assert payload['model_prediction_or_observe_calls'] == 0 and payload['model_vector_valid'] is False
        assert payload['phase'] == 'OUTBOUND' and abs(payload['task_s']) < 1e-9
        assert payload['capture_position'] == 'parent request boundary BEFORE fork loop/candidate selection/control mutation'
        assert len(payload['feature_names']) == len(payload['features']) == len(set(payload['feature_names'])) == 77
        values = dict(zip(payload['feature_names'], payload['features']))
        assert values['decision_slot'] == 0 and payload['quality_missing'] == {}
        checks = {'payload_checksum': True, 'out0_before_selection': True, 'read_only': True, 'legacy_remains_invalid': True}
    else:
        assert payload.get('schema') == 'v8.recipe_context.commissioning25.v1'
        assert payload['legacy77d_valid'] is False and payload['feature_names'] == FEATURE_NAMES
        assert payload.get('checks') and all(payload['checks'].values())
        values = dict(zip(payload['feature_names'], payload['features']))
        checks = dict(payload['checks'])
    vector = [values[n] for n in FEATURE_NAMES]
    assert all(finite(v) for v in vector) and all(finite(v) for v in payload['quality'].values())
    return {'schema': 'v8.recipe_context.commissioning25.v1', 'feature_names': FEATURE_NAMES[:], 'features': vector,
            'quality': dict(payload['quality']), 'legacy77d_valid': False, 'checks': checks,
            'subset_numeric_identity_sha256': digest({'feature_names': FEATURE_NAMES, 'features': vector, 'quality': payload['quality']}),
            'fit_absolute_timestamp': None}
