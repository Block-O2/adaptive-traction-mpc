"""UNRUN source: independent terminal supervised heads, not Bellman/SAC.

No NumPy or learner calls on import. Explicit future approval is required even
for synthetic initialization/forward/gradient checks. No environment APIs.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import time

DATA_SHA = "b8a2b12479f25112a8cdfc720a6ad0f56f24467cd4c143425c675f814812c39d"
GLOBAL_STOP = 1793114740.0
TARGETS = ("RETURN", "RISK", "JF_FIXED", "JM_FIXED", "JF_CENTERED", "JM_CENTERED")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _approval(approval):
    if (approval.get("schema") != "v8.neuralq_v2.explicit_call_authorization.v1" or
            approval.get("approved") is not True or approval.get("scope") not in ("SYNTHETIC_MATH_ONLY", "OFFLINE_FROZEN64_ONLY")):
        raise ValueError("SEPARATE_MAIN_APPROVAL_REQUIRED_EVEN_FOR_MATH")
    if approval["scope"] == "OFFLINE_FROZEN64_ONLY" and approval.get("data_sha256") != DATA_SHA:
        raise ValueError("ONLY_FROZEN_SAC64_NO_NEW_ACTIVE_ROWS")
    if approval["scope"] == "SYNTHETIC_MATH_ONLY" and not str(approval.get("data_sha256", "")).startswith("SYNTHETIC_ONLY_"):
        raise ValueError("SYNTHETIC_DATA_MUST_NOT_CLAIM_REAL_RECEIPTS")
    actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if approval.get("head_source_sha256") != actual or len(approval.get("contract_sha256", "")) != 64:
        raise ValueError("FROZEN_SOURCE_AND_APPROVED_CONTRACT_REQUIRED")
    if not time.time() < min(approval["local_stop_unix"], GLOBAL_STOP):
        raise ValueError("ORIGINAL_LOCAL_OR_GLOBAL_CLOCK_STOP")


def _np():
    import numpy as np
    return np


def _finite(array):
    np = _np()
    if not np.isfinite(array).all():
        raise ValueError("NONFINITE_ARRAY_NO_UPDATE")


def _sigmoid(z):
    np = _np()
    e = np.exp(-np.abs(z))
    return np.where(z >= 0, 1. / (1. + e), e / (1. + e))


def initialize(*, architecture, target, feature_names, input_normalization, output_normalization,
               seed, action_contracts, full_recipe_sha256, training_manifest, approval):
    _approval(approval)
    np = _np()
    if architecture not in ("LINEAR", "TANH16") or target not in TARGETS or len(feature_names) not in (25, 39):
        raise ValueError("REGISTERED_ARCH_TARGET_INPUT_ONLY")
    if (len(action_contracts) != 5 or [digest(a) for a in action_contracts] != full_recipe_sha256 or
            full_recipe_sha256 != approval.get("full_recipe_sha256") or
            full_recipe_sha256 != training_manifest.get("full_recipe_sha256")):
        raise ValueError("ACTUAL_COMPLETE_FIVE_RECIPE_IDENTITY")
    if training_manifest["data_sha256"] != approval["data_sha256"]:
        raise ValueError("FROZEN_TRAIN_ROW_MANIFEST_REQUIRED")
    if approval["scope"] == "OFFLINE_FROZEN64_ONLY" and training_manifest.get("all_rows_complete_original_evidence") is not True:
        raise ValueError("REAL_COMPLETE_ORIGINAL_ROWS_REQUIRED")
    if approval["scope"] == "SYNTHETIC_MATH_ONLY" and (training_manifest.get("all_rows_synthetic_fixture") is not True or training_manifest.get("all_rows_complete_original_evidence") is True):
        raise ValueError("SYNTHETIC_MATH_MUST_NOT_CLAIM_ORIGINAL_PHYSICAL_EVIDENCE")
    if digest(list(feature_names)) != training_manifest.get("feature_names_sha256") or digest(list(feature_names)) != approval.get("feature_names_sha256"):
        raise ValueError("MAIN_AND_DATA_FEATURE_WHITELIST_IDENTITY")
    d = len(feature_names)
    mean = np.asarray(input_normalization["mean"], dtype=np.float64)
    scale = np.asarray(input_normalization["scale"], dtype=np.float64)
    if mean.shape != (d,) or scale.shape != (d,) or not (scale > 0).all():
        raise ValueError("TRAIN_ONLY_NORMALIZATION_SHAPE")
    _finite(mean); _finite(scale)
    if target in ("RETURN", "RISK") and output_normalization != {"mean": 0., "scale": 1.}:
        raise ValueError("RETURN_FLOOR_AND_BINARY_RISK_NOT_NORMALIZED_OR_MIXED")
    if target == "JF_FIXED" and output_normalization != {"mean": 0., "scale": 1500.}:
        raise ValueError("PREREGISTERED_FIXED_JF_N_S_SCALE")
    if target == "JM_FIXED" and output_normalization != {"mean": 0., "scale": 100.}:
        raise ValueError("PREREGISTERED_FIXED_JM_NM_S_SCALE")
    if not math.isfinite(output_normalization["mean"]) or not math.isfinite(output_normalization["scale"]) or output_normalization["scale"] <= 0:
        raise ValueError("INVALID_TARGET_SCALE")
    rng = np.random.default_rng(seed)
    if architecture == "LINEAR":
        params = {"W": rng.normal(0., .001, (d, 5)), "b": np.zeros(5)}
        normal_outputs = d * 5
    else:
        params = {"W1": rng.normal(0., math.sqrt(2. / (d + 16)), (d, 16)), "b1": np.zeros(16),
                  "W2": rng.normal(0., math.sqrt(2. / 21), (16, 5)), "b2": np.zeros(5)}
        normal_outputs = d * 16 + 80
    return {"schema": "v8.neuralq_v2.independent_terminal_head.v1", "architecture": architecture, "target": target,
        "feature_names": list(feature_names), "input_normalization": copy.deepcopy(input_normalization),
        "output_normalization": copy.deepcopy(output_normalization), "seed": seed, "params": params,
        "adam_m": {k: np.zeros_like(v) for k, v in params.items()}, "adam_v": {k: np.zeros_like(v) for k, v in params.items()},
        "initialization_rng_state": copy.deepcopy(rng.bit_generator.state), "training_manifest": copy.deepcopy(training_manifest),
        "action_contracts": copy.deepcopy(action_contracts), "full_recipe_sha256": list(full_recipe_sha256),
        "approval_scope": approval["scope"], "head_source_sha256": approval["head_source_sha256"],
        "optimizer": {"kind": "MANUAL_FULL_BATCH_ADAM", "learning_rate": .01, "beta1": .9, "beta2": .999,
                      "epsilon": 1e-8, "weight_decay": .001, "max_gradient_norm": 1., "maximum_steps": 200},
        "counters": {"initializations": 1, "normal_output_scalars": normal_outputs, "forward_API": 0,
                     "forward_rows": 0, "gradient_API": 0, "gradient_observed_rows": 0,
                     "parameter_updates": 0, "gradient_clip_activations": 0, "restore_API": 0}}


def _forward(model, feature_names, values, approval):
    _approval(approval)
    if model["approval_scope"] != approval["scope"] or model["training_manifest"]["data_sha256"] != approval["data_sha256"]:
        raise ValueError("SYNTHETIC_AND_REAL_HEADS_CANNOT_BE_RELABELED")
    if list(feature_names) != model["feature_names"]:
        raise ValueError("CAUSAL_FEATURE_ORDER")
    if ([digest(a) for a in model["action_contracts"]] != model["full_recipe_sha256"] or
            model["full_recipe_sha256"] != approval.get("full_recipe_sha256")):
        raise ValueError("RECIPE_ACTUAL_BODY_CHANGED")
    np = _np(); x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(feature_names):
        raise ValueError("FINITE_N_BY_D_INPUT")
    _finite(x)
    z = (x - model["input_normalization"]["mean"]) / model["input_normalization"]["scale"]
    p = model["params"]
    d = len(feature_names)
    shapes = {"W": (d, 5), "b": (5,)} if model["architecture"] == "LINEAR" else {"W1": (d, 16), "b1": (16,), "W2": (16, 5), "b2": (5,)}
    if set(p) != set(shapes) or any(p[k].shape != shape for k, shape in shapes.items()):
        raise ValueError("FROZEN_PARAMETER_SHAPES")
    if model["architecture"] == "LINEAR":
        h = None; out = z @ p["W"] + p["b"]
    else:
        h = np.tanh(z @ p["W1"] + p["b1"]); out = h @ p["W2"] + p["b2"]
    _finite(out)
    model["counters"]["forward_API"] += 1; model["counters"]["forward_rows"] += len(x)
    return z, h, out


def predict(model, feature_names, values, *, qa_validated, approval):
    if qa_validated is not True:
        raise ValueError("QA_REQUIRED")
    z, h, out = _forward(model, feature_names, values, approval)
    result = _sigmoid(out) if model["target"] == "RISK" else out * model["output_normalization"]["scale"] + model["output_normalization"]["mean"]
    return {"target": model["target"], "values": result.tolist(), "uncalibrated_risk": model["target"] == "RISK",
            "original_qualification_granted": False, "no_new_physics": True}


def loss_and_gradient(model, feature_names, values, actions, raw_targets, *, qa_validated, approval):
    if qa_validated is not True:
        raise ValueError("QA_REQUIRED")
    np = _np(); actions = np.asarray(actions)
    target = np.asarray(raw_targets, dtype=np.float64)
    if actions.ndim != 1 or target.shape != actions.shape or actions.dtype.kind not in "iu" or not ((actions >= 0) & (actions < 5)).all() or not len(actions):
        raise ValueError("OBSERVED_ACTIONS_ONLY_NO_MISSING_LABEL_FILL")
    _finite(target)
    if model["target"] == "RETURN" and not ((target >= -1.) & (target <= .9)).all():
        raise ValueError("ORIGINAL_CANONICAL_RETURN_RANGE")
    if model["target"].startswith(("JF", "JM")) and not (target >= 0).all():
        raise ValueError("COMPLETE_NONNEGATIVE_PHYSICAL_COST")
    z, h, out = _forward(model, feature_names, values, approval)
    if len(out) != len(actions):
        raise ValueError("ROW_TARGET_COUNT")
    picked = out[np.arange(len(out)), actions]
    delta = np.zeros_like(out)
    if model["target"] == "RISK":
        if not ((target == 0) | (target == 1)).all():
            raise ValueError("ORIGINAL_BINARY_FAILURE_ONLY")
        loss = float(np.mean(np.logaddexp(0., picked) - target * picked))
        delta[np.arange(len(out)), actions] = (_sigmoid(picked) - target) / len(out)
    else:
        standardized = (target - model["output_normalization"]["mean"]) / model["output_normalization"]["scale"]
        error = picked - standardized
        loss = .5 * float(np.mean(error**2)); delta[np.arange(len(out)), actions] = error / len(out)
    p = model["params"]
    if model["architecture"] == "LINEAR":
        gradients = {"W": z.T @ delta, "b": delta.sum(axis=0)}
    else:
        dh = (delta @ p["W2"].T) * (1. - h*h)
        gradients = {"W1": z.T @ dh, "b1": dh.sum(axis=0), "W2": h.T @ delta, "b2": delta.sum(axis=0)}
    wd = model["optimizer"]["weight_decay"]
    for key in gradients:
        if key.startswith("W"):
            gradients[key] += wd * p[key]; loss += .5 * wd * float((p[key]**2).sum())
        _finite(gradients[key])
    model["counters"]["gradient_API"] += 1; model["counters"]["gradient_observed_rows"] += len(out)
    return loss, gradients


def step(model, feature_names, values, actions, raw_targets, *, qa_validated, approval):
    _approval(approval)
    if model["counters"]["parameter_updates"] >= model["optimizer"]["maximum_steps"]:
        raise ValueError("FIXED_FINAL_UPDATE_REACHED_NO_AUTOMATIC_EXTENSION")
    # Private copy: even a failed finite check cannot partially update live W/m/v.
    trial = copy.deepcopy(model)
    private_arrays_updated = []
    try:
        loss, gradients = loss_and_gradient(trial, feature_names, values, actions, raw_targets, qa_validated=qa_validated, approval=approval)
        np = _np(); norm = math.sqrt(sum(float((g*g).sum()) for g in gradients.values()))
        scale = min(1., trial["optimizer"]["max_gradient_norm"] / max(norm, 1e-300))
        t = trial["counters"]["parameter_updates"] + 1
        cfg = trial["optimizer"]
        for key, gradient in gradients.items():
            g = gradient * scale
            trial["adam_m"][key] = cfg["beta1"] * trial["adam_m"][key] + (1. - cfg["beta1"]) * g
            trial["adam_v"][key] = cfg["beta2"] * trial["adam_v"][key] + (1. - cfg["beta2"]) * g*g
            trial["params"][key] -= cfg["learning_rate"] * (trial["adam_m"][key] / (1. - cfg["beta1"]**t)) / (np.sqrt(trial["adam_v"][key] / (1. - cfg["beta2"]**t)) + cfg["epsilon"])
            private_arrays_updated.append(key)
            _finite(trial["params"][key])
        trial["counters"]["parameter_updates"] = t
        trial["counters"]["gradient_clip_activations"] += int(scale < 1.)
        _approval(approval)
    except BaseException as error:
        error.neural_q_private_consumed_work = {"trial_counters": copy.deepcopy(trial["counters"]),
            "live_counters_before": copy.deepcopy(model["counters"]), "private_parameter_arrays_updated": private_arrays_updated,
            "live_model_parameters_or_optimizer_committed": False}
        raise
    model.clear(); model.update(trial)
    return {"step": t, "loss": loss, "raw_gradient_norm": norm, "gradient_scale": scale,
            "new_parameter_updates": 1, "new_physics": 0}


def snapshot(model):
    result = copy.deepcopy(model)
    for key in ("params", "adam_m", "adam_v"):
        result[key] = {name: value.tolist() for name, value in result[key].items()}
    # JSON itself validates all floats; no pickle/hidden optimizer/RNG state.
    return json.loads(json.dumps(result, allow_nan=False))


def restore(document, *, approval):
    _approval(approval)
    if document.get("schema") != "v8.neuralq_v2.independent_terminal_head.v1" or document.get("head_source_sha256") != approval["head_source_sha256"] or document.get("approval_scope") != approval["scope"]:
        raise ValueError("FROZEN_SOURCE_SCOPE_CHECKPOINT")
    np = _np(); model = copy.deepcopy(document)
    for key in ("params", "adam_m", "adam_v"):
        model[key] = {name: np.asarray(value, dtype=np.float64) for name, value in model[key].items()}
        for value in model[key].values(): _finite(value)
    model["counters"]["restore_API"] += 1
    return model


def choose_from_return_and_risk(return_prediction, failure_prediction, *, selector):
    # Pure postprocessing; neither physical cost head participates in selection.
    return_prediction = list(return_prediction); failure_prediction = list(failure_prediction)
    if len(return_prediction) != 5 or len(failure_prediction) != 5 or not all(math.isfinite(x) for x in return_prediction + failure_prediction):
        raise ValueError("FINITE_FIVE_RETURN_RISK_VALUES")
    if not all(0. <= x <= 1. for x in failure_prediction):
        raise ValueError("FAILURE_PROBABILITY_RANGE")
    if selector not in ("RETURN_GREEDY", "RETURN_RISK_LE_0P1_ELSE_B"):
        raise ValueError("PREREGISTERED_SELECTOR_ONLY")
    allowed = list(range(5)) if selector == "RETURN_GREEDY" else [i for i, p in enumerate(failure_prediction) if p <= .1]
    index = max(allowed, key=lambda i: (return_prediction[i], -i)) if allowed else 0
    return {"action_index": index, "reason": "ARGMAX_PREREGISTERED_TERMINAL_RETURN" if allowed else "ORIGINAL_B_FALLBACK_NO_ESTIMATED_LOW_RISK_ACTION",
            "risk_is_uncalibrated": True, "qualification_granted": False, "JF_JM_weighted_score_used": False}
