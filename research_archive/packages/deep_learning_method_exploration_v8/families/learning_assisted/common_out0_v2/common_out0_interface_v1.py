"""SOURCE_ONLY pure schema and fixed baselines. No I/O, imports of learners, or fit.

All 39 numbers originate in the registered common pre-action OUT0 payload.
Query elapsed time is a requested forecast horizon, not a future observation.
"""
import copy,hashlib,json,math

BETAS=['a_inertia_combination','b_distal_inertia_combination','d_mass_length_com_combination','g1_proximal_gravity_combination','g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness','rho1_stiffness_rest_combination','rho2_stiffness_rest_combination','bv1_viscous_damping','bv2_viscous_damping']
FEATURE_NAMES=['estimated_beta_'+n for n in BETAS]
FEATURE_NAMES+=['estimated_geometry_'+n for n in ['hip_plane_x','hip_plane_z','thigh_length','knee_to_cuff_distance']]
FEATURE_NAMES+=['residual_weight_'+j+'_'+n for j in ['hip','knee'] for n in ['constant','q_hip_normalized','q_knee_normalized','dq_hip_bounded','dq_knee_bounded']]
FEATURE_NAMES+=['estimated_q_hip','estimated_q_knee','estimated_dq_hip','estimated_dq_knee','request_reference_q_hip','request_reference_q_knee','request_reference_dq_hip','request_reference_dq_knee']
FEATURE_NAMES+=['measured_force_world_'+a for a in 'xyz']+['measured_moment_world_'+a for a in 'xyz']

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def input_vector(context39,recipe_sha256,menu,*,query_time_s=None):
    """Return vector only; identity/QA metadata are never model coordinates."""
    names=context39['feature_names'];values=context39['features']
    if names!=FEATURE_NAMES or len(values)!=39:raise ValueError('EXACT_LEGAL39_REQUIRED')
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values):raise ValueError('FINITE39_REQUIRED')
    if any(any(word in n.lower() for word in ('future','truth','case_id','patient_id','group','path','hash','final_jf','final_jm','qualified')) for n in names):raise ValueError('FORBIDDEN_FEATURE_NAME')
    if [m['tag'] for m in menu]!=['B','LATE_H150','EARLY_H150','LATE_PHASE','EARLY_PHASE']:raise ValueError('EXACT_FULL_FIVE_RECIPE_MENU')
    hashes=[m['recipe_sha256'] for m in menu]
    if any(digest(m['action_recipe'])!=m['recipe_sha256'] or m['action_recipe']['action']!=m['action'] for m in menu):raise ValueError('FULL_RECIPE_CONTENT_IDENTITY')
    index=hashes.index(recipe_sha256)
    vector=list(values)+[float(i==index) for i in range(5)]
    if query_time_s is not None:
        if not isinstance(query_time_s,(int,float)) or isinstance(query_time_s,bool) or not math.isfinite(query_time_s) or query_time_s<0:raise ValueError('PUBLIC_QUERY_TIME_ONLY')
        vector.append(float(query_time_s))
    return vector

def initial14(context39):
    if context39['feature_names']!=FEATURE_NAMES or len(context39['features'])!=39:raise ValueError('EXACT_LEGAL39_REQUIRED')
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in context39['features']):raise ValueError('FINITE39_REQUIRED')
    values=dict(zip(context39['feature_names'],context39['features']))
    names=['estimated_q_hip','estimated_q_knee','estimated_dq_hip','estimated_dq_knee',
        'request_reference_q_hip','request_reference_q_knee','request_reference_dq_hip','request_reference_dq_knee']
    names+=['measured_force_world_'+a for a in 'xyz']+['measured_moment_world_'+a for a in 'xyz']
    return [values[n] for n in names]

def fixed_baseline(context39,horizon_s,*,kind):
    """Unfitted persistence/constant-velocity endpoint14 + left-rule JF/JM."""
    if horizon_s<=0 or not math.isfinite(horizon_s):raise ValueError('POSITIVE_HORIZON')
    y=initial14(context39)
    if kind=='KINEMATIC':
        for q,dq in [(0,2),(1,3),(4,6),(5,7)]:y[q]+=horizon_s*y[dq]
    elif kind!='PERSISTENCE':raise ValueError('UNKNOWN_FIXED_BASELINE')
    jf=math.sqrt(sum(v*v for v in y[8:11]))*horizon_s
    jm=math.sqrt(sum(v*v for v in y[11:14]))*horizon_s
    return dict(endpoint14=copy.deepcopy(y),window_JF_N_s=jf,window_JM_Nm_s=jm,
        estimated_only=True,future_reference_or_wrench_input=False,full_task_qualification_predicted=False)
