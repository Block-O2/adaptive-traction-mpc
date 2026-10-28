"""Source-only OUT0 BC/rule deployment candidate; no fit or import side effects."""
import copy
import hashlib
import math
from pathlib import Path
import sys

BETA_NAMES = ['a_inertia_combination','b_distal_inertia_combination','d_mass_length_com_combination','g1_proximal_gravity_combination','g2_distal_gravity_combination','k1_passive_stiffness','k2_passive_stiffness','rho1_stiffness_rest_combination','rho2_stiffness_rest_combination','bv1_viscous_damping','bv2_viscous_damping']
FEATURE_NAMES = ['estimated_beta_'+name for name in BETA_NAMES]+['estimated_geometry_'+name for name in ['hip_plane_x','hip_plane_z','thigh_length','knee_to_cuff_distance']]+['residual_weight_'+joint+'_'+name for joint in ['hip','knee'] for name in ['constant','q_hip_normalized','q_knee_normalized','dq_hip_bounded','dq_knee_bounded']]


def digest(value):
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def select_out0(bundle, feature_names, commissioned25, *, qa_validated, expected_bundle_sha256, frozen_recipe_sha256):
    """Pure fixed deployment. Current costs, case IDs and labels have no input."""
    if digest(bundle) != expected_bundle_sha256 or bundle.get("schema") != "v8.context_aggregation_policy_bundle.v1":
        raise ValueError("FROZEN_ACTUAL_BUNDLE_IDENTITY")
    if qa_validated is not True or list(feature_names) != FEATURE_NAMES or bundle["feature_names"] != FEATURE_NAMES or len(commissioned25) != 25 or not all(finite(v) for v in commissioned25):
        raise ValueError("CAUSAL_25D_SCHEMA_OR_QA")
    menu = bundle["menu"]
    contracts = menu["action_contracts"]
    actual = [digest(contract) for contract in contracts]
    if len(contracts) != 5 or actual != list(frozen_recipe_sha256) or actual != menu["full_recipe_sha256"]:
        raise ValueError("ACTUAL_FIVE_RECIPE_CONTRACTS_MUST_MATCH_EXTERNAL_FREEZE")
    if menu["action_names"] != ["B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]:
        raise ValueError("FIXED_FIVE_MENU_ORDER")
    model = bundle["model"]
    kind = model["kind"]
    probabilities = None
    if kind == "BC_LINEAR":
        family = Path(__file__).resolve().parents[2] / "ppo_reward"
        path = family / "categorical_policy.py"
        if hashlib.sha256(path.read_bytes()).hexdigest() != bundle["source_dependency_sha256"]["categorical_policy.py"]:
            raise ValueError("FROZEN_CATEGORICAL_DEPENDENCY_CHANGED")
        sys.path.insert(0, str(family))
        import categorical_policy as categorical
        if Path(categorical.__file__).resolve() != path:
            raise ValueError("WRONG_CATEGORICAL_MODULE_RESOLUTION")
        policy = copy.deepcopy(model["policy"])
        if policy["action_contracts"] != contracts or policy["action_sha256"] != actual or policy["feature_names"] != list(feature_names):
            raise ValueError("ACTUAL_POLICY_ACTION_OR_FEATURE_IDENTITY")
        prediction = categorical.select_out0(policy, feature_names, commissioned25, qa_validated=True)
        index = prediction["action_index"]
        probabilities = prediction["probabilities"]
    elif kind in ("CONSTANT", "STUMP", "TREE_DEPTH2"):
        node = model["tree"]
        depth = 0
        while "action_index" not in node:
            if depth >= (1 if kind == "STUMP" else 2) or kind == "CONSTANT":
                raise ValueError("REGISTERED_RULE_DEPTH_EXCEEDED")
            feature = node["feature_index"]
            if not isinstance(feature, int) or isinstance(feature, bool) or not 0 <= feature < 25 or not finite(node["threshold"]):
                raise ValueError("INVALID_FROZEN_RULE_NODE")
            node = node["left"] if commissioned25[feature] <= node["threshold"] else node["right"]
            depth += 1
        index = node["action_index"]
    elif kind == "NEAREST":
        normalization = model["normalization"]
        if len(normalization["mean"]) != 25 or len(normalization["scale"]) != 25 or not all(finite(v) for v in normalization["mean"]) or not all(finite(v) and v > 0 for v in normalization["scale"]):
            raise ValueError("INVALID_FIXED_NEAREST_NORMALIZATION")
        z = [(v-m)/s for v,m,s in zip(commissioned25,normalization["mean"],normalization["scale"])]
        distances = []
        for row in model["training_points"]:
            if len(row["standardized_features"]) != 25 or not all(finite(v) for v in row["standardized_features"]):
                raise ValueError("INVALID_FIXED_NEAREST_POINT")
            distances.append(sum((a-b)**2 for a,b in zip(z,row["standardized_features"])))
        if not distances:
            raise ValueError("EMPTY_NEAREST_TRAINING_SUPPORT")
        nearest = min(range(len(distances)), key=lambda i: (distances[i], i))
        index = model["training_points"][nearest]["teacher_action_index"]
    else:
        raise ValueError("UNREGISTERED_SOURCE_CANDIDATE_KIND")
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 5:
        raise ValueError("INVALID_FINAL_ACTION_INDEX")
    recipe = contracts[index]
    return {"schema": "v8.context_aggregation_out0_choice.v1", "method_name": bundle["method_name"],
            "action_index": index, "action_name": menu["action_names"][index],
            "proposal_action": copy.deepcopy(recipe["action"]), "full_recipe_sha256": digest(recipe),
            "resolved_base_candidate": copy.deepcopy(recipe["resolved_base_candidate"]),
            "probabilities": probabilities, "original_qualification_granted": False,
            "current_or_future_outcomes_used": False, "input_bundle_mutated": False}
