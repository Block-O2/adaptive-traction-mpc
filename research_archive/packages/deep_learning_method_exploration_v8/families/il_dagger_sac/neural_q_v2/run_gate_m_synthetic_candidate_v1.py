"""UNRUN GateM candidate. Requires separate exact-source main math approval.

All data are deterministic synthetic arrays. Finite differences call the real
head _forward plus LOSS ONLY arithmetic, never loss_and_gradient. No physics,
real dataset, receipt, training outcome, or sealed source is opened.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import os
import resource
import signal
import sys
import time

GLOBAL_STOP = 1793114740.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())


def process():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"unix": time.time(), "monotonic": time.monotonic(), "cpu_self_s": usage.ru_utime + usage.ru_stime,
        "maxrss_KiB": usage.ru_maxrss, "pid": os.getpid(),
        "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
        "executable": sys.executable, "resolved_binary": str(Path(sys.executable).resolve()),
        "binary_sha256": sha(Path(sys.executable).resolve())}


def fixture_identity():
    names = ["SYNTHETIC_ONLY_feature_" + str(i).zfill(2) for i in range(25)]
    actions = [{"family": "SYNTHETIC_ONLY_NEVER_PHYSICAL", "index": i} for i in range(5)]
    return names, actions, [digest(item) for item in actions]


def run(approval, out, accounting):
    import numpy as np
    import terminal_head_candidate_v1 as head
    import ridge_reference_candidate_v1 as ridge
    from run_gate_r_frozen64_candidate_v1 import fit_train_input_normalization
    from unittest.mock import patch
    if np.__version__ != approval["expected_numpy_version"]:
        raise ValueError("APPROVED_NUMPY_ENVIRONMENT_REQUIRED")
    names, menu, menu_sha = fixture_identity()
    if (approval.get("scope") != "SYNTHETIC_MATH_ONLY" or approval.get("feature_names_sha256") != digest(names) or
            approval.get("full_recipe_sha256") != menu_sha or
            approval.get("data_sha256") != "SYNTHETIC_ONLY_NEURALQ_GATEM_V1"):
        raise ValueError("EXACT_SYNTHETIC_FIXTURE_IDENTITIES_REQUIRED")
    manifest = {"data_sha256": approval["data_sha256"], "full_recipe_sha256": menu_sha,
        "feature_names_sha256": digest(names), "all_rows_synthetic_fixture": True,
        "all_rows_complete_original_evidence": False}
    write_new(out / "ENVIRONMENT_BEFORE_FIRST_MODEL_API.json", {"numpy_version": np.__version__,
        "numpy_module": np.__file__, "numpy_module_sha256": sha(np.__file__), "process": process(),
        "data_are_synthetic_not_original_receipts": True})
    originals = {key: getattr(head, key) for key in ("initialize", "_forward", "loss_and_gradient", "step", "restore", "predict", "snapshot")}
    ridge_original = {key: getattr(ridge, key) for key in ("fit", "predict")}
    def counted(function, key):
        def call(*args, **kwargs):
            counts = accounting.setdefault(key, {"entry": 0, "completed": 0, "failed": 0})
            counts["entry"] += 1
            try:
                value = function(*args, **kwargs)
            except BaseException:
                counts["failed"] += 1
                raise
            counts["completed"] += 1
            return value
        return call
    for key, function in originals.items():
        setattr(head, key, counted(function, "head." + key))
    for key, function in ridge_original.items():
        setattr(ridge, key, counted(function, "ridge." + key))
    base_x = .2 * np.sin(np.arange(12 * 25, dtype=float).reshape(12, 25) / 17.)
    x = base_x
    action = np.arange(12, dtype=int) % 4  # action4 intentionally unobserved.
    returns = np.linspace(-.8, .4, 12)
    risks = np.arange(12) % 2
    norm = {"mean": np.zeros(25).tolist(), "scale": np.ones(25).tolist()}
    output_norm = {"mean": 0., "scale": 1.}
    checks = []

    def loss_only(model, targets, *, perturbation):
        # This is the actual head forward, without any backprop/gradient call.
        _, _, values = head._forward(model, names, x, approval)
        picked = values[np.arange(len(action)), action]
        if model["target"] == "RISK":
            loss = float(np.mean(np.logaddexp(0., picked) - targets * picked))
        else:
            target = (targets - model["output_normalization"]["mean"]) / model["output_normalization"]["scale"]
            loss = .5 * float(np.mean((picked-target)**2))
        loss += .5 * model["optimizer"]["weight_decay"] * sum(float((value**2).sum()) for key, value in model["params"].items() if key.startswith("W"))
        accounting["loss_only_perturbation_forwards" if perturbation else "loss_only_other_forwards"] = accounting.get("loss_only_perturbation_forwards" if perturbation else "loss_only_other_forwards", 0) + 1
        return loss

    def reference_grad(model, targets):
        # Independent fixture arithmetic, counted separately from head API.
        accounting["independent_reference_backprop_evaluations"] = accounting.get("independent_reference_backprop_evaluations", 0) + 1
        z = (x - model["input_normalization"]["mean"]) / model["input_normalization"]["scale"]
        p = model["params"]
        h = np.tanh(z @ p["W1"] + p["b1"]) if model["architecture"] == "TANH16" else None
        values = h @ p["W2"] + p["b2"] if h is not None else z @ p["W"] + p["b"]
        picked = values[np.arange(len(action)), action]
        delta = np.zeros_like(values)
        if model["target"] == "RISK":
            delta[np.arange(len(action)), action] = (1./(1.+np.exp(-picked))-targets)/len(action)
        else:
            delta[np.arange(len(action)), action] = (picked-targets)/len(action)
        if h is None:
            gradients = {"W": z.T @ delta, "b": delta.sum(axis=0)}
        else:
            back = (delta @ p["W2"].T) * (1.-h*h)
            gradients = {"W1": z.T @ back, "b1": back.sum(axis=0), "W2": h.T @ delta, "b2": delta.sum(axis=0)}
        for key in gradients:
            if key.startswith("W"):
                gradients[key] += .001*p[key]
        return gradients

    def reference_update(model, gradients):
        # Scalar equations, no actor optimizer or training API.
        accounting["independent_reference_Adam_arithmetic_groups"] = accounting.get("independent_reference_Adam_arithmetic_groups", 0) + 1
        t = model["counters"]["parameter_updates"] + 1
        norm_g = math.sqrt(sum(float((value*value).sum()) for value in gradients.values()))
        scaling = min(1., 1./max(norm_g, 1e-300))
        for key in model["params"]:
            for index in np.ndindex(model["params"][key].shape):
                g = float(gradients[key][index])*scaling
                m = .9*float(model["adam_m"][key][index])+.1*g
                v = .999*float(model["adam_v"][key][index])+.001*g*g
                model["adam_m"][key][index] = m; model["adam_v"][key][index] = v
                model["params"][key][index] -= .01*(m/(1.-.9**t))/(math.sqrt(v/(1.-.999**t))+1e-8)
        model["counters"]["parameter_updates"] = t

    def arrays_equal(a, b, exact=False):
        for section in ("params", "adam_m", "adam_v"):
            for key in a[section]:
                if exact:
                    assert np.array_equal(a[section][key], b[section][key]), (section, key)
                else:
                    assert np.allclose(a[section][key], b[section][key], atol=2e-12, rtol=2e-12), (section, key)

    models = []
    for model_index, (architecture, target) in enumerate((
            ("LINEAR", "RETURN"), ("LINEAR", "RISK"), ("TANH16", "RETURN"), ("TANH16", "RISK"))):
        # LINEAR/RISK large synthetic features exercise the actual norm1 clip.
        x = base_x * (100. if (architecture, target) == ("LINEAR", "RISK") else 1.)
        model = head.initialize(architecture=architecture, target=target, feature_names=names, input_normalization=norm,
            output_normalization=output_norm, seed=20261027100+model_index, action_contracts=menu,
            full_recipe_sha256=menu_sha, training_manifest=manifest, approval=approval)
        accounting["normal_output_scalars"] = accounting.get("normal_output_scalars",0)+model["counters"]["normal_output_scalars"]
        targets = returns if target == "RETURN" else risks
        _, gradient = head.loss_and_gradient(model, names, x, action, targets, qa_validated=True, approval=approval)
        maximum_error = 0.
        for key, array in model["params"].items():
            for index in np.ndindex(array.shape):
                original = float(array[index]); epsilon = 1e-5
                try:
                    array[index] = original + epsilon; plus = loss_only(model, targets, perturbation=True)
                    array[index] = original - epsilon; minus = loss_only(model, targets, perturbation=True)
                finally:
                    array[index] = original
                maximum_error = max(maximum_error, abs((plus-minus)/(2*epsilon)-float(gradient[key][index])))
        assert maximum_error < 2e-7, (architecture, target, maximum_error)
        w_last = "W" if architecture == "LINEAR" else "W2"
        b_last = "b" if architecture == "LINEAR" else "b2"
        assert np.allclose(gradient[w_last][:, 4], .001*model["params"][w_last][:, 4], atol=1e-15)
        assert gradient[b_last][4] == 0.  # no bias regularization or fabricated action4 data.
        reference = copy.deepcopy(model)
        reference_update(reference, gradient)
        first = head.step(model, names, x, action, targets, qa_validated=True, approval=approval)
        arrays_equal(reference, model)
        restored = head.restore(head.snapshot(model), approval=approval)
        second_grad = reference_grad(reference, targets)
        reference_update(reference, second_grad)
        second = head.step(model, names, x, action, targets, qa_validated=True, approval=approval)
        arrays_equal(reference, model)
        if model_index < 3:
            head.step(restored, names, x, action, targets, qa_validated=True, approval=approval)
            arrays_equal(model, restored, exact=True)
        else:
            before = head.snapshot(model)
            original_approval = head._approval
            approval_calls = [0]
            def expire_after_private_arrays(value):
                approval_calls[0] += 1
                if approval_calls[0] == 3:
                    original_approval({**value, "local_stop_unix": time.time()-1.})
                original_approval(value)
            try:
                with patch.object(head, "_approval", expire_after_private_arrays):
                    head.step(model, names, x, action, targets, qa_validated=True, approval=approval)
            except ValueError as error:
                assert "CLOCK_STOP" in str(error)
                assert head.snapshot(model) == before
                paid = error.neural_q_private_consumed_work
                assert paid["trial_counters"]["parameter_updates"] == 3
                assert paid["trial_counters"]["gradient_API"] == paid["live_counters_before"]["gradient_API"]+1
                assert set(paid["private_parameter_arrays_updated"]) == set(model["params"])
                accounting["clock_failed_private_work"] = paid
            else:
                raise AssertionError("CLOCK_FAILURE_DID_NOT_REJECT")
        checks.append({"architecture": architecture, "target": target, "maximum_full_parameter_FD_error": maximum_error,
            "first_and_second_independent_Adam_verified": True, "replay_second_step_bitwise_equal": model_index < 3,
            "first_update_diagnostics": first, "second_update_diagnostics": second})
        models.append(model)
    assert any(item["first_update_diagnostics"]["gradient_scale"] < 1. for item in checks)
    assert accounting["loss_only_perturbation_forwards"] == 2524
    assert accounting["head.loss_and_gradient"]["completed"] == 16
    assert accounting["head.step"] == {"entry": 12, "completed": 11, "failed": 1}
    assert accounting["head.restore"]["completed"] == 4

    def rejects(label, function):
        try:
            function()
        except (ValueError, TypeError) as error:
            checks.append({"rejection": label, "type": type(error).__name__, "reason": str(error)})
        else:
            raise AssertionError("INVALID_FIXTURE_ACCEPTED:"+label)
    base = models[0]
    rejects("QA", lambda: head.predict(base, names, x, qa_validated=False, approval=approval))
    rejects("feature_order", lambda: head.predict(base, list(reversed(names)), x, qa_validated=True, approval=approval))
    rejects("NaN_input", lambda: head.predict(base, names, x*float("nan"), qa_validated=True, approval=approval))
    rejects("source_SHA", lambda: head.predict(base, names, x, qa_validated=True, approval={**approval, "head_source_sha256": "0"*64}))
    rejects("expired_clock", lambda: head.predict(base, names, x, qa_validated=True, approval={**approval, "local_stop_unix": time.time()-1.}))
    rejects("synthetic_cannot_claim_real", lambda: head.predict(base, names, x, qa_validated=True, approval={**approval, "scope": "OFFLINE_FROZEN64_ONLY"}))
    bad_recipe = copy.deepcopy(base); bad_recipe["action_contracts"][0]["index"] = 999
    rejects("actual_recipe_body", lambda: head.predict(bad_recipe, names, x, qa_validated=True, approval=approval))
    rejects("invalid_action", lambda: head.loss_and_gradient(base, names, x, action+9, returns, qa_validated=True, approval=approval))
    rejects("missing_label", lambda: head.loss_and_gradient(base, names, x, action, returns*float("nan"), qa_validated=True, approval=approval))
    # Large logits/tanh saturation are finite forward tests, not more gradients.
    for risk_model in (models[1], models[3]):
        extreme = copy.deepcopy(risk_model)
        final_bias = "b" if extreme["architecture"] == "LINEAR" else "b2"
        extreme["params"][final_bias][:] = np.asarray([-1000., 1000., -1000., 1000., 0.])
        answer = head.predict(extreme, names, x*1e6, qa_validated=True, approval=approval)
        assert np.isfinite(answer["values"]).all()
        loss = loss_only(extreme, risks, perturbation=False)
        assert math.isfinite(loss)
    tiny = copy.deepcopy(base)
    tiny["input_normalization"]["scale"] = [1e-12]*25
    normal_prediction = head.predict(base, names, x, qa_validated=True, approval=approval)["values"]
    tiny_prediction = head.predict(tiny, names, x*1e-12, qa_validated=True, approval=approval)["values"]
    assert np.allclose(normal_prediction, tiny_prediction, atol=1e-12, rtol=1e-12)
    affine = copy.deepcopy(base); affine["target"] = "JF_CENTERED"
    affine["output_normalization"] = {"mean": 1800., "scale": 1500.}
    affine_prediction = head.predict(affine, names, x, qa_validated=True, approval=approval)["values"]
    assert np.allclose(np.asarray(normal_prediction)*1500.+1800., affine_prediction, atol=2e-12)
    accounting["fixture_explicit_logical_model_deepcopies"] = 9
    accounting["head_internal_private_step_deepcopies"] = 12

    # Same normalized objective and W-only penalty, raw affine equivalent.
    fitted = []
    for target, y, output in (("RETURN", returns, output_norm),
            ("JF_CENTERED", 1800.+1500.*returns, {"mean": 1800., "scale": 1500.})):
        fitted.append(ridge.fit(feature_names=names, values=x, actions=action, raw_targets=y, target=target,
            input_normalization=norm, output_normalization=output, training_manifest=manifest, approval=approval))
    for values in (x, x*1.7+.03):
        a = ridge.predict(fitted[0], names, values, qa_validated=True, approval=approval)["values"]
        b = ridge.predict(fitted[1], names, values, qa_validated=True, approval=approval)["values"]
        for row_a, row_b in zip(a, b):
            assert row_a[4] is None and row_b[4] is None
            assert np.allclose(np.asarray(row_a[:4])*1500.+1800., row_b[:4], atol=2e-8)
    assert all(row["normal_equation_residual_L2"] < 1e-9 for fit in fitted for row in fit["diagnostics"] if "normal_equation_residual_L2" in row)
    accounting["ridge_actual_linear_solve_calls"] = sum(fit["linear_solve_calls"] for fit in fitted)
    assert accounting["ridge_actual_linear_solve_calls"] == 8
    assert head.choose_from_return_and_risk([0., .1, .2, -.3, -.1], [.2]*5, selector="RETURN_RISK_LE_0P1_ELSE_B")["action_index"] == 0
    assert head.choose_from_return_and_risk([0., .1, .2, -.3, -.1], [.9]*5, selector="RETURN_GREEDY")["action_index"] == 2
    grouped = [{"split_case_sha256_evaluation_only":case,"features":[0.,1e-9*value]+[float(value)]*23,
        "evaluation_only_label":99999.} for case,value in (("A",1),("A",1),("B",2),("B",2),("HELD",999))]
    normalization_a = fit_train_input_normalization(grouped,[0,1,2,3],approval=approval)
    grouped[-1]["features"] = [-1e12]*25
    grouped[-1]["evaluation_only_label"] = -1e90
    normalization_b = fit_train_input_normalization(grouped,[0,1,2,3],approval=approval)
    assert normalization_a == normalization_b
    assert normalization_a["train_case_sha256"] == ["A","B"]
    assert normalization_a["scale"][:2] == [1.,1.]
    accounting["synthetic_train_only_normalizer_fit_API"] = 2
    return {"status": "PASS_SYNTHETIC_MATH_ONLY_NOT_REAL_FIT_AUTHORIZATION", "checks": checks,
        "accounting": accounting, "head_completed_forward_upper_bound": 2600,
        "real_dataset_or_physical_receipts_read": 0, "real_model_fit": 0, "new_physics": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", required=True); parser.add_argument("--approval-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    start = process(); out = Path(args.output).resolve()
    if sha(args.approval) != args.approval_sha:
        raise ValueError("EXACT_MAIN_APPROVAL_DOCUMENT_REQUIRED")
    approval = json.loads(Path(args.approval).read_text())
    if (approval.get("schema") != "v8.neuralq_v2.explicit_call_authorization.v1" or approval.get("approved") is not True or
            approval.get("runner_source_sha256") != sha(__file__) or approval.get("scope") != "SYNTHETIC_MATH_ONLY" or
            approval.get("expected_binary_sha256") != start["binary_sha256"] or
            approval.get("maximum_wall_s") != 30 or approval.get("maximum_CPU_s") != 30 or
            not approval.get("approved_unix", float("inf")) <= start["unix"] < approval["local_stop_unix"] <= min(start["unix"]+30., GLOBAL_STOP)):
        raise ValueError("SEPARATE_THIRTY_SECOND_MATH_SOURCE_AND_CLOCK_APPROVAL_REQUIRED")
    if not out.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError("PRIVATE_NEW_NEURALQ_MATH_OUTPUT_ONLY")
    if (sha(approval["contract_path"]) != approval["contract_sha256"] or
            sha(approval["source_manifest_path"]) != approval["source_manifest_sha256"]):
        raise ValueError("ACTUAL_MATH_CONTRACT_AND_MANIFEST_FILES_MUST_BE_BOUND")
    required_files = {str(Path(__file__).resolve()), str(Path(__file__).with_name("terminal_head_candidate_v1.py").resolve()),
        str(Path(__file__).with_name("ridge_reference_candidate_v1.py").resolve()),
        str(Path(__file__).with_name("run_gate_r_frozen64_candidate_v1.py").resolve()),
        str(Path(approval["contract_path"]).resolve()), str(Path(approval["source_manifest_path"]).resolve())}
    if not required_files <= {str(Path(path).resolve()) for path in approval["source_files_sha256"]}:
        raise ValueError("COMPLETE_MATH_SOURCE_CONTRACT_MANIFEST_CLOSURE_REQUIRED")
    for path, expected in approval["source_files_sha256"].items():
        if sha(path) != expected:
            raise ValueError("APPROVED_MATH_SOURCE_CHANGED:"+path)
    out.mkdir(exist_ok=False)
    write_new(out / "START.json", {"process": start, "approval_sha256": args.approval_sha,
        "runner_sha256": sha(__file__), "local_stop_unix": approval["local_stop_unix"], "real_model_calls": 0})
    accounting = {}
    def timeout(signum, frame):
        raise TimeoutError("APPROVED_GATEM_LOCAL_CPU_OR_WALL_STOP")
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    signal.signal(signal.SIGALRM, timeout); signal.signal(signal.SIGXCPU, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, approval["local_stop_unix"]-time.time()))
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    try:
        result = run(approval, out, accounting)
        assert accounting["head._forward"]["completed"] <= 2600
        write_new(out / "RESULT.json", {**result, "START": start, "END": process()})
    except BaseException as error:
        write_new(out / "FAILED.json", {"error_type": type(error).__name__, "error": str(error), "START": start,
            "END": process(), "paid_calls_retained": accounting, "automatic_retry_authorized": False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)


if __name__ == "__main__":
    main()
