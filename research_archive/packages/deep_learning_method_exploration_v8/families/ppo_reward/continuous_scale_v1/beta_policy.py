"""Proposed scalar Beta policy mathematics. Import never initializes or trains.

No optimizer or physical dispatch is implemented in this candidate. The main
agent must first approve numerical tests and B/lambda engineering gates.
"""
from __future__ import annotations
import copy
import math

from axis_mapping import digest, finite, map_lambda, validate_axis

BETA_NAMES = ['a_inertia_combination','b_distal_inertia_combination','d_mass_length_com_combination','g1_proximal_gravity_combination','g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness','rho1_stiffness_rest_combination','rho2_stiffness_rest_combination','bv1_viscous_damping','bv2_viscous_damping']
FEATURE_NAMES = ['estimated_beta_'+n for n in BETA_NAMES]+['estimated_geometry_'+n for n in ['hip_plane_x','hip_plane_z','thigh_length','knee_to_cuff_distance']]+['residual_weight_'+j+'_'+n for j in ['hip','knee'] for n in ['constant','q_hip_normalized','q_knee_normalized','dq_hip_bounded','dq_knee_bounded']]


def _softplus(u):
    return max(u,0.0)+math.log1p(math.exp(-abs(u)))


def _sigmoid(u):
    return 1.0/(1.0+math.exp(-u)) if u>=0 else math.exp(u)/(1.0+math.exp(u))


def _digamma(x):
    """Positive-real recurrence plus DLMF 5.11.2; validation still proposed."""
    if not finite(x) or x<=0:
        raise ValueError("DIGAMMA_POSITIVE_FINITE_REQUIRED")
    correction = 0.0
    while x<10.0:
        correction -= 1.0/x
        x += 1.0
    inv = 1.0/x
    v = inv*inv
    expansion = -v/12.0+v*v/120.0-v**3/252.0+v**4/240.0-v**5/132.0
    return correction+math.log(x)-.5*inv+expansion


def shapes_from_raw(raw_alpha, raw_beta):
    if not finite(raw_alpha) or not finite(raw_beta):
        raise ValueError("NONFINITE_SHAPE_LOGIT")
    alpha,beta = 1.0+_softplus(raw_alpha),1.0+_softplus(raw_beta)
    if not finite(alpha+beta) or alpha<=0 or beta<=0:
        raise ValueError("NUMERICAL_SHAPE_OVERFLOW_NO_ACTION")
    return alpha,beta


def log_density(lambda_value, alpha, beta):
    if not finite(lambda_value) or not 0.0<lambda_value<1.0:
        raise ValueError("BETA_SAMPLE_MUST_BE_INTERIOR_NO_CLIP")
    if not finite(alpha) or not finite(beta) or alpha<=0 or beta<=0 or not finite(alpha+beta):
        raise ValueError("INVALID_BETA_SHAPES")
    value = ((alpha-1.0)*math.log(lambda_value)+(beta-1.0)*math.log1p(-lambda_value)
             +math.lgamma(alpha+beta)-math.lgamma(alpha)-math.lgamma(beta))
    if not math.isfinite(value):
        raise ValueError("NONFINITE_EXACT_BETA_LOG_DENSITY")
    return value


def raw_shape_score(lambda_value, raw_alpha, raw_beta):
    alpha,beta = shapes_from_raw(raw_alpha,raw_beta)
    log_density(lambda_value,alpha,beta)
    common = _digamma(alpha+beta)
    return [(math.log(lambda_value)-_digamma(alpha)+common)*_sigmoid(raw_alpha),
            (math.log1p(-lambda_value)-_digamma(beta)+common)*_sigmoid(raw_beta)]


def initialize(feature_names, normalization, axis, *, axis_sha256, seed, arm_id, gain):
    """Defined for future reviewed initialization; never called on import."""
    validate_axis(axis,axis_sha256)
    if gain not in (1.0,20.0) or not arm_id or list(feature_names)!=FEATURE_NAMES:
        raise ValueError("DECLARED_ARM_GAIN_AND_COMMISSIONED25_REQUIRED")
    if len(normalization["mean"])!=25 or len(normalization["scale"])!=25 or any(not finite(v) or v<=0 for v in normalization["scale"]):
        raise ValueError("FROZEN_TRAIN_ONLY_NORMALIZATION_REQUIRED")
    if any(not finite(v) for v in normalization["mean"]):
        raise ValueError("NONFINITE_NORMALIZATION")
    raw_two = math.log(math.expm1(1.0))  # 1+softplus(raw_two)=2.
    weights = [[raw_two]+[0.0]*25 for _ in range(2)]
    return {"schema":"v8.scalar_beta_linear25.v1","feature_names":list(feature_names),
            "normalization":copy.deepcopy(normalization),"weights":weights,"axis_contract":copy.deepcopy(axis),
            "axis_contract_sha256":axis_sha256,"seed":seed,"arm_id":arm_id,"gain":gain,"version":0,
            "counters":{"forward":0,"score_evaluations":0,"parameter_updates":0},
            "status":"INITIALIZED_IF_APPROVED_NOT_PHYSICALLY_QUALIFIED"}


def policy_sha256(policy):
    # Include actual axis bytes as well as its externally frozen hash.
    fields = ("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version")
    return digest({k:policy[k] for k in fields})


def _forward(policy, feature_names, commissioned25, *, qa_validated, frozen_axis_sha256):
    validate_axis(policy["axis_contract"],frozen_axis_sha256)
    if frozen_axis_sha256!=policy["axis_contract_sha256"] or qa_validated is not True or list(feature_names)!=policy["feature_names"] or policy["feature_names"]!=FEATURE_NAMES:
        raise ValueError("AXIS_OR_CAUSAL_SCHEMA_OR_QA_IDENTITY")
    if len(commissioned25)!=25 or not all(finite(v) for v in commissioned25):
        raise ValueError("INVALID_COMMISSIONED25")
    norm = policy["normalization"]
    x = [1.0]+[(v-m)/s for v,m,s in zip(commissioned25,norm["mean"],norm["scale"])]
    if len(policy["weights"])!=2 or any(len(w)!=26 or not all(finite(v) for v in w) for w in policy["weights"]):
        raise ValueError("INVALID_TWO_SHAPE_LINEAR_WEIGHTS")
    raw = [sum(w*v for w,v in zip(row,x)) for row in policy["weights"]]
    alpha,beta = shapes_from_raw(*raw)
    policy["counters"]["forward"] += 1
    return x,raw,alpha,beta


def sample(policy, feature_names, commissioned25, *, qa_validated, frozen_axis_sha256, rng):
    _,raw,alpha,beta = _forward(policy,feature_names,commissioned25,qa_validated=qa_validated,frozen_axis_sha256=frozen_axis_sha256)
    before = rng.getstate()
    lam = rng.betavariate(alpha,beta)
    if not finite(lam) or not 0.0<lam<1.0:
        # Do not clip or silently resample. Main must preserve consumed RNG and
        # record a numerical no-proposal failure, with zero physical dispatch.
        raise ValueError("NUMERICAL_BETA_ENDPOINT_NO_CLIP_NO_RESAMPLE")
    density = log_density(lam,alpha,beta)
    mapped = map_lambda(policy["axis_contract"],lam,expected_axis_sha256=frozen_axis_sha256)
    return {**mapped,"distribution":"Beta_on_lambda","lambda_sample":lam,"alpha":alpha,"beta":beta,
            "raw_shape_logits":raw,"old_logprob":density,"sampling_measure":"scalar Lebesgue d_lambda",
            "affine_lambda_interval":[0.0,1.0],"log_abs_scalar_affine_jacobian":0.0,
            "ambient_18d_density_defined":False,"post_sampling_clip":False,
            "policy_sha256":policy_sha256(policy),"policy_version":policy["version"],
            "arm_id":policy["arm_id"],"gain":policy["gain"],"rng_before":before,"rng_after":rng.getstate(),
            "deterministic_mean_deployment":False,"original_qualification_granted":False}


def deploy_mean(policy, feature_names, commissioned25, *, qa_validated, frozen_axis_sha256):
    _,raw,alpha,beta = _forward(policy,feature_names,commissioned25,qa_validated=qa_validated,frozen_axis_sha256=frozen_axis_sha256)
    lam = alpha/(alpha+beta)
    mapped = map_lambda(policy["axis_contract"],lam,expected_axis_sha256=frozen_axis_sha256)
    return {**mapped,"alpha":alpha,"beta":beta,"raw_shape_logits":raw,"policy_sha256":policy_sha256(policy),
            "deterministic_mean_deployment":True,"old_logprob":None,"training_sample_eligible":False,
            "mean_of_physical_trajectory_claimed":False,"original_qualification_granted":False}


def score_for_weights(policy, feature_names, commissioned25, lambda_sample, *, qa_validated, frozen_axis_sha256):
    x,raw,alpha,beta = _forward(policy,feature_names,commissioned25,qa_validated=qa_validated,frozen_axis_sha256=frozen_axis_sha256)
    scores = raw_shape_score(lambda_sample,*raw)
    policy["counters"]["score_evaluations"] += 1
    return {"score_gradient":[[s*v for v in x] for s in scores],"logprob":log_density(lambda_sample,alpha,beta),
            "no_parameter_update":True,"sampling_measure":"d_lambda"}


def surrogate_coefficient(*, algorithm, new_logprob, old_logprob, advantage, clip_range=.2):
    """Mathematical scalar multiplying score gradient; does not update weights."""
    if algorithm not in ("REINFORCE","PPO") or not all(finite(v) for v in (new_logprob,old_logprob,advantage)):
        raise ValueError("INVALID_SURROGATE_ARGUMENT")
    if algorithm=="REINFORCE":
        return {"score_coefficient":advantage,"objective":advantage*new_logprob,"parameter_updates":0}
    log_ratio = new_logprob-old_logprob
    if abs(log_ratio)>50:
        raise ValueError("DENSITY_RATIO_EXTREME_STOP_NO_RATIO_CLIP")
    ratio = math.exp(log_ratio)
    if not 0<clip_range<1:
        raise ValueError("INVALID_PPO_CLIP_RANGE")
    clipped = min(1+clip_range,max(1-clip_range,ratio))
    active = (advantage>=0 and ratio<=1+clip_range) or (advantage<0 and ratio>=1-clip_range)
    return {"ratio":ratio,"objective":min(ratio*advantage,clipped*advantage),
            "score_coefficient":advantage*ratio if active else 0.0,"parameter_updates":0}


def single_force_feedback(result, baseline, *, gain):
    if gain not in (1.0,20.0) or baseline.get("complete") is not True or baseline.get("original_qualified") is not True:
        raise ValueError("REGISTERED_GAIN_AND_QUALIFIED_B_REQUIRED")
    if result.get("true_hard_safety_violation") is True:
        raise ValueError("HARD_SAFETY_STOP")
    if result.get("engineering_complete") is not True or result.get("ownership_and_causality_audit_pass") is not True:
        raise ValueError("ENGINEERING_CENSOR_NOT_TASK_REWARD")
    if result.get("true_hard_safety_violation") is not False:
        raise ValueError("HARD_SAFETY_STATUS_UNRESOLVED")
    if result.get("complete") is not True or result.get("original_qualified") is not True:
        if result.get("complete") is not True and result.get("protected_task_failure") is not True:
            raise ValueError("UNRESOLVED_PARTIAL_NOT_REWARD")
        return {"reward":-1.0,"qualified":False,"gain":gain,"JF_partial_not_ranked":True}
    if any(not finite(row.get(k)) for row in (result,baseline) for k in ("JF_N_s","JM_Nm_s")):
        raise ValueError("FULL_SEPARATE_COSTS_REQUIRED")
    jf = result["JF_N_s"]
    anchor = baseline["JF_N_s"]
    return {"reward":min(.9,max(-.9,gain*(anchor-jf)/max(abs(anchor),1.0))),"qualified":True,"gain":gain,
            "JF_N_s":jf,"JM_Nm_s":result["JM_Nm_s"],"delta_JM_vs_B":result["JM_Nm_s"]-baseline["JM_Nm_s"],
            "JM_scalarized":False,"original_gate_unchanged":True}
