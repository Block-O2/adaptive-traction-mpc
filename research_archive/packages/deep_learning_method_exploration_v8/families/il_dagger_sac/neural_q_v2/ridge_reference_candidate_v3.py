"""UNRUN same-target ridge references. No NumPy/fit/forward on import."""
import copy
import hashlib
from pathlib import Path
from terminal_head_candidate_v3 import _approval, _np, _finite, digest


def _authorized(approval):
    _approval(approval)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != approval.get("ridge_source_sha256"):
        raise ValueError("EXACT_RIDGE_SOURCE_APPROVAL_REQUIRED")


def fit(*, feature_names, values, actions, raw_targets, target, input_normalization,
        output_normalization, training_manifest, approval):
    _authorized(approval)
    if target not in ("RETURN", "JF_CENTERED", "JM_CENTERED"):
        raise ValueError("RIDGE_REGRESSION_ONLY_RISK_USES_MATCHED_LINEAR_LOGISTIC")
    if training_manifest.get("data_sha256") != approval.get("data_sha256") or training_manifest.get("full_recipe_sha256") != approval.get("full_recipe_sha256"):
        raise ValueError("SAME_FROZEN64_MENU_AND_TRAINING_MANIFEST")
    np = _np(); x = np.asarray(values, dtype=np.float64); a = np.asarray(actions); y = np.asarray(raw_targets, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(feature_names) or a.shape != (len(x),) or y.shape != (len(x),) or a.dtype.kind not in "iu" or not ((a >= 0) & (a < 5)).all():
        raise ValueError("OBSERVED_COMPLETE_ROW_SHAPES")
    if digest(list(feature_names)) != training_manifest["feature_names_sha256"] or digest(list(feature_names)) != approval["feature_names_sha256"]:
        raise ValueError("SAME_CAUSAL_FEATURE_WHITELIST")
    _finite(x); _finite(y)
    z = (x - input_normalization["mean"]) / input_normalization["scale"]
    z = np.column_stack([z, np.ones(len(z))])
    standardized = (y - output_normalization["mean"]) / output_normalization["scale"]
    penalty = np.eye(z.shape[1]) * .001; penalty[-1, -1] = 0.
    coefficients, diagnostics = [], []
    for action in range(5):
        _authorized(approval)
        keep = a == action
        if not keep.any():
            coefficients.append(None); diagnostics.append({"action_index": action, "status": "NO_TRAIN_LABEL_HEAD_NOT_IMPUTED"})
            continue
        # Overall-N denominator matches .5 empirical observed-row MSE +
        # .5*.001*||W||^2 used by LINEAR/TANH, with unpenalized bias.
        matrix = z[keep].T @ z[keep] / len(z) + penalty
        rhs = z[keep].T @ standardized[keep] / len(z)
        weights = np.linalg.solve(matrix, rhs); _finite(weights)
        coefficients.append(weights.tolist())
        diagnostics.append({"action_index": action, "observed_training_rows": int(keep.sum()),
                            "normal_equation_residual_L2": float(np.linalg.norm(matrix @ weights-rhs))})
    return {"schema": "v8.neuralq_v2.closed_form_ridge.v1", "target": target, "feature_names": list(feature_names),
            "input_normalization": copy.deepcopy(input_normalization), "output_normalization": copy.deepcopy(output_normalization),
            "coefficients": coefficients, "training_manifest": copy.deepcopy(training_manifest),
            "approval_scope": approval["scope"], "ridge_source_sha256": approval["ridge_source_sha256"],
            "diagnostics": diagnostics, "fit_API_calls": 1, "linear_solve_calls": sum(c is not None for c in coefficients),
            "random_initialization_or_seed_search": False, "forward_API_calls": 0}


def predict(model, feature_names, values, *, qa_validated, approval):
    _authorized(approval)
    if qa_validated is not True or list(feature_names) != model["feature_names"] or model["approval_scope"] != approval["scope"]:
        raise ValueError("SAME_CAUSAL_INPUT_AND_APPROVAL_SCOPE")
    np = _np(); x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(feature_names):
        raise ValueError("INPUT_SHAPE")
    _finite(x)
    z = (x-model["input_normalization"]["mean"]) / model["input_normalization"]["scale"]
    z = np.column_stack([z, np.ones(len(z))])
    result = [[None]*5 for _ in range(len(z))]
    for action, weights in enumerate(model["coefficients"]):
        if weights is not None:
            values = z @ np.asarray(weights) * model["output_normalization"]["scale"] + model["output_normalization"]["mean"]
            _finite(values)
            for index, value in enumerate(values): result[index][action] = float(value)
    model["forward_API_calls"] += 1
    return {"values": result, "missing_train_action_not_filled": True, "qualification_granted": False}
