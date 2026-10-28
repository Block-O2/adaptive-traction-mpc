"""OUT0用途限定子集复制；不调用observer/model/plant，不升级原77D。"""
import hashlib
import json
import math

BETA = ['a_inertia_combination','b_distal_inertia_combination','d_mass_length_com_combination','g1_proximal_gravity_combination','g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness','rho1_stiffness_rest_combination','rho2_stiffness_rest_combination','bv1_viscous_damping','bv2_viscous_damping']
COMMISSION25 = ['estimated_beta_'+n for n in BETA] + ['estimated_geometry_'+n for n in ['hip_plane_x','hip_plane_z','thigh_length','knee_to_cuff_distance']] + ['residual_weight_'+j+'_'+n for j in ['hip','knee'] for n in ['constant','q_hip_normalized','q_knee_normalized','dq_hip_bounded','dq_knee_bounded']]
KINEMATIC8 = ['estimated_q_hip','estimated_q_knee','estimated_dq_hip','estimated_dq_knee','request_reference_q_hip','request_reference_q_knee','request_reference_dq_hip','request_reference_dq_knee']
WRENCH6 = ['measured_force_world_'+n for n in ['x','y','z']] + ['measured_moment_world_'+n for n in ['x','y','z']]
GUARD4 = ['session_guard_calls','session_guard_active','session_guard_unsatisfied','session_guard_peak_correction']
SUBSETS = {'KIN33':COMMISSION25+KINEMATIC8,'WRENCH39':COMMISSION25+KINEMATIC8+WRENCH6,'SOFTWARE_GUARD43':COMMISSION25+KINEMATIC8+WRENCH6+GUARD4}


def to_subset(raw, subset='WRENCH39'):
    assert isinstance(raw,dict) and 'labels_evaluation_only' not in raw
    assert raw['schema']=='ihear.causal_human_context.v1.77d' and raw['model_vector_valid'] is False
    body={k:v for k,v in raw.items() if k!='causal_payload_sha256'}
    checksum=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    assert checksum==raw['causal_payload_sha256']
    assert raw['hidden_or_future_inputs_used'] is False and raw['model_prediction_or_observe_calls']==0
    assert raw['phase']=='OUTBOUND' and raw['task_s']==0.
    assert raw['capture_position']=='parent request boundary BEFORE fork loop/candidate selection/control mutation'
    assert raw['causality_errors']==['capture_is_not_registered_OUT1_boundary']
    assert len(raw['feature_names'])==len(raw['features'])==len(set(raw['feature_names']))==77
    values=dict(zip(raw['feature_names'],raw['features']))
    assert values['decision_slot']==0 and values['request_source_age']==0.
    assert raw['quality_missing']=={} and raw['quality']['observation_age']==raw['quality']['interface_age']==0.
    assert all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in raw['quality'].values())
    names=SUBSETS[subset];vector=[values[n] for n in names]
    assert all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in vector)
    if subset=='SOFTWARE_GUARD43':
        assert values['session_guard_calls']>=values['session_guard_active']>=0 and values['session_guard_unsatisfied']>=0 and values['session_guard_peak_correction']>=0
    return {'schema':'v8.out0.scoped_state_input.v1','subset':subset,'feature_names':names[:],'features':vector,
        'quality':dict(raw['quality']),'legacy77_valid':False,'scope':'registered cold-parent OUT0 only',
        'software_guard_is_physical_risk':False,'includes_TASK_integrals':False,'includes_emitted_reference':False,
        'checks':{'original_checksum':True,'all_selected_finite':True,'aligned_current_sample':True,'before_selection':True},
        'source_payload_checksum_evaluation_only':checksum}
