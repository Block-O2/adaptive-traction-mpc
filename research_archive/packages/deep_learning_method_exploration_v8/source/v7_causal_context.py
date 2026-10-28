"""Pure reads of existing causal objects; no observe/model/scheduler/plant call.

Candidate for main-agent registration/review. capture(b, it) never mutates b/it,
imports scientific runtime, touches a case/plant/native trace, or fills missing
fork data from a tail. Returned missing fields invalidate the 77D model vector.
"""
import hashlib
import json
import math
import sys

SCHEMA = 'ihear.causal_human_context.v1.77d'
FEATURE_NAMES = ('estimated_q_hip', 'estimated_q_knee', 'estimated_dq_hip', 'estimated_dq_knee', 'request_reference_q_hip', 'request_reference_q_knee', 'request_reference_dq_hip', 'request_reference_dq_knee', 'emitted_reference_q_hip', 'emitted_reference_q_knee', 'emitted_reference_dq_hip', 'emitted_reference_dq_knee', 'emitted_reference_ddq_hip', 'emitted_reference_ddq_knee', 'measured_force_world_x', 'measured_force_world_y', 'measured_force_world_z', 'measured_moment_world_x', 'measured_moment_world_y', 'measured_moment_world_z', 'estimated_beta_a_inertia_combination', 'estimated_beta_b_distal_inertia_combination', 'estimated_beta_d_mass_length_com_combination', 'estimated_beta_g1_proximal_gravity_combination', 'estimated_beta_g2_distal_gravity_combination', 'estimated_beta_k1_passive_stiffness', 'estimated_beta_k2_passive_stiffness', 'estimated_beta_rho1_stiffness_rest_combination', 'estimated_beta_rho2_stiffness_rest_combination', 'estimated_beta_bv1_viscous_damping', 'estimated_beta_bv2_viscous_damping', 'residual_weight_hip_constant', 'residual_weight_hip_q_hip_normalized', 'residual_weight_hip_q_knee_normalized', 'residual_weight_hip_dq_hip_bounded', 'residual_weight_hip_dq_knee_bounded', 'residual_weight_knee_constant', 'residual_weight_knee_q_hip_normalized', 'residual_weight_knee_q_knee_normalized', 'residual_weight_knee_dq_hip_bounded', 'residual_weight_knee_dq_knee_bounded', 'estimated_geometry_hip_plane_x', 'estimated_geometry_hip_plane_z', 'estimated_geometry_thigh_length', 'estimated_geometry_knee_to_cuff_distance', 'phase_OUTBOUND', 'phase_HOLD', 'phase_RETURN', 'task_elapsed', 'phase_elapsed', 'task_contract_remaining', 'request_source_age', 'decision_slot', 'previous_executed_delta_q_hip', 'previous_executed_delta_q_knee', 'previous_K3_residual_0', 'previous_K3_residual_1', 'previous_K3_residual_2', 'task_measured_JF', 'task_measured_JM', 'task_estimated_peak_velocity_hip', 'task_estimated_peak_velocity_knee', 'task_estimated_peak_acceleration_hip', 'task_estimated_peak_acceleration_knee', 'task_estimated_peak_jerk_hip', 'task_estimated_peak_jerk_knee', 'task_estimated_q_min_hip', 'task_estimated_q_min_knee', 'task_estimated_q_max_hip', 'task_estimated_q_max_knee', 'session_guard_calls', 'session_guard_active', 'session_guard_unsatisfied', 'session_guard_peak_correction', 'task_context_rejections', 'task_history_samples', 'task_history_age')
BETA_NAMES = ('a_inertia_combination','b_distal_inertia_combination','d_mass_length_com_combination','g1_proximal_gravity_combination','g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness','rho1_stiffness_rest_combination','rho2_stiffness_rest_combination','bv1_viscous_damping','bv2_viscous_damping')


def _flat(value):
    if hasattr(value, 'tolist'):
        value = value.tolist()  # Existing array -> copied Python scalars only.
    if isinstance(value, (list, tuple)):
        return [item for row in value for item in _flat(row)]
    if isinstance(value, dict):
        raise ValueError('hashed or structured metadata is not a numeric array')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('nonfinite causal field')
    return [value]


def capture(b, it):
    values = []
    missing = {}
    quality = {}
    quality_missing = {}

    def vec(label, count, read):
        try:
            x = _flat(read())
            if len(x) != count:
                raise ValueError('expected ' + str(count) + ' scalars')
        except (AttributeError, KeyError, TypeError, ValueError, IndexError) as error:
            x = [None] * count
            missing[label] = type(error).__name__ + ': ' + str(error)
        values.extend(x)

    def qa(name, read):
        try:
            x = _flat(read())
            if len(x) != 1:
                raise ValueError('expected scalar')
            quality[name] = x[0]
        except (AttributeError, KeyError, TypeError, ValueError, IndexError) as error:
            quality[name] = None
            quality_missing[name] = type(error).__name__ + ': ' + str(error)

    now = float(b['physical_now'])
    task_start = float(b['task_start_time'])
    belief = b['belief']
    geometry = belief.geometry
    task = b['task_state']
    phase = task.phase.value
    vec('estimated_q_dq', 4, lambda: b['observation'].state_rad_rad_s)
    vec('request_reference_q_dq', 4, lambda: b['arguments']['current_reference_state'])
    vec('emitted_reference_q', 2, lambda: b['reference'].q_rad)
    vec('emitted_reference_dq', 2, lambda: b['reference'].dq_rad_s)
    vec('emitted_reference_ddq', 2, lambda: b['reference'].ddq_rad_s2)
    vec('measured_force', 3, lambda: b['interface'].measured_force_world_n)
    vec('measured_moment', 3, lambda: b['interface'].measured_moment_world_nm)
    vec('estimated_beta', 11, lambda: belief.beta)
    vec('residual_weights', 10, lambda: belief.state_residual_weights_nm)
    vec('effective_hip', 2, lambda: geometry.hip_plane_m)
    vec('effective_thigh_length', 1, lambda: geometry.thigh_length_m)
    vec('effective_cuff_distance', 1, lambda: math.sqrt(sum(x*x for x in _flat(geometry.knee_to_cuff_in_cuff_m))))
    vec('phase_onehot', 3, lambda: [phase == name for name in ('OUTBOUND', 'HOLD', 'RETURN')])
    vec('task_elapsed', 1, lambda: now-task_start)
    vec('phase_elapsed', 1, lambda: task.phase_elapsed_s)
    vec('task_remaining', 1, lambda: max(0., 30.-(now-task_start)))
    vec('request_source_age', 1, lambda: now-b['request'].source_sample_time_s)
    vec('decision_slot', 1, lambda: it.count[phase])
    vec('previous_executed_delta_q', 2, lambda: b['planner'].previous_executed_delta_q_rad)
    vec('previous_K3_residual', 3, lambda: it.previous)
    vec('task_history_JF', 1, lambda: it.risk_history.jf if it.risk_history.n > 0 else None)
    vec('task_history_JM', 1, lambda: it.risk_history.jm if it.risk_history.n > 0 else None)
    for label, attribute in [('peak_velocity','peak_v'), ('peak_acceleration','peak_a'), ('peak_jerk','peak_j'), ('q_min','qmin'), ('q_max','qmax')]:
        vec('task_history_'+label, 2, lambda attribute=attribute: getattr(it.risk_history, attribute) if it.risk_history.n > 0 else None)
    # Read a module already installed by the worker. Never import/tap/update it.
    def guard():
        module = sys.modules.get('v6_features')
        if module is None or not isinstance(getattr(module, 'GUARD', None), dict):
            raise ValueError('existing v6_features.GUARD not available')
        return module.GUARD
    for name in ('calls', 'active', 'unsatisfied', 'max_correction'):
        vec('session_guard_'+name, 1, lambda name=name: guard()[name])
    vec('task_context_rejections', 1, lambda: len(it.skips))
    vec('task_history_samples', 1, lambda: it.risk_history.n if it.risk_history.n > 0 else None)
    vec('task_history_age', 1, lambda: now-it.risk_history.last[0] if it.risk_history.n > 0 and it.risk_history.last is not None else None)
    if len(values) != len(FEATURE_NAMES):
        raise RuntimeError('CAUSAL_CAPTURE_SCHEMA_IMPLEMENTATION_MISMATCH')

    for name in ('accepted','sample_count','angular_span_rad','residual_rms_m','condition_number'):
        qa('geometry_fit_'+name, lambda name=name: getattr(b['fit'], name))
    qa('dynamics_sample_count', lambda: len(b['updater'].dynamics.rows))
    qa('accepted_beta_updates', lambda: b['updater'].dynamics.accepted_updates)
    qa('rejected_beta_updates', lambda: b['updater'].dynamics.rejected_updates)
    for name, key in [('last_attempt_samples','sample_count'), ('last_attempt_rank','rank'), ('last_attempt_condition','condition_number'), ('last_attempt_accepted','accepted'), ('last_attempt_trusted_RMS','trusted_candidate_residual_rms_nm'), ('last_attempt_mass_margin','minimum_mass_matrix_eigenvalue'), ('last_attempt_bound_hit','bound_hit'), ('last_attempt_rate_limit_hit','rate_limit_hit')]:
        qa(name, lambda key=key: b['updater'].dynamics.last_attempt_diagnostics[key])
    for name in BETA_NAMES:
        qa('last_attempt_conditional_frozen_'+name, lambda name=name: name in b['updater'].dynamics.last_attempt_diagnostics['frozen_conditional_parameter_names'])
    for name in ('excluded_soft_limit_sample_count','coefficient_projection_count','observed_output_cap_count','sequence'):
        qa(name, lambda name=name: getattr(b['updater'], name))
    qa('observation_age', lambda: now-b['observation'].sample_timestamp_s)
    qa('interface_age', lambda: now-b['interface'].sample_timestamp_s)
    causality_errors = []
    if getattr(it, 'child', None) is not None:
        causality_errors.append('capture_is_not_in_cold_parent')
    if phase != 'OUTBOUND' or it.count.get('OUTBOUND') != 1:
        causality_errors.append('capture_is_not_registered_OUT1_boundary')
    for name in ('observation_age','interface_age'):
        age = quality[name]
        if age is not None and age < -1e-9:
            causality_errors.append(name+'_sample_in_future')
    for name in ('request_source_age','task_history_age'):
        value = values[FEATURE_NAMES.index(name)]
        if value is not None and value < -1e-9:
            causality_errors.append(name+'_sample_in_future')
    if quality['observation_age'] is not None and quality['interface_age'] is not None and abs(quality['observation_age']-quality['interface_age']) > 1e-9:
        causality_errors.append('observation_interface_sample_not_aligned')
    if getattr(belief, 'deployable_truth_consumed', None) is not False:
        causality_errors.append('belief_truth_firewall_not_explicit_false')
    payload = dict(schema=SCHEMA, physical_s=now, task_s=now-task_start, phase=phase,
        feature_names=list(FEATURE_NAMES), features=values, feature_dimension=len(values),
        model_vector_valid=not missing and not causality_errors, missing_model_groups=missing,
        quality=quality, quality_missing=quality_missing, causality_errors=causality_errors,
        history_window='risk_history: completed TASK boundaries only; GUARD: all prior software guard calls, not physical incidents',
        capture_position='parent request boundary BEFORE fork loop/candidate selection/control mutation',
        hidden_or_future_inputs_used=False, model_prediction_or_observe_calls=0)
    payload['causal_payload_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return payload
