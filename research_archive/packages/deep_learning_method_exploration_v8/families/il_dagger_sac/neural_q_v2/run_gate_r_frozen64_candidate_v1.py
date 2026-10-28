"""UNRUN bounded GateR candidate, fixed 25D frozen64 supervised diagnosis.

Requires a passed, separately approved math fixture and a NEW explicit main
offline-fit approval. No physics or deployment API. No best/early stop search.
The 120s bound can stop this fixed design incomplete; it never changes epochs.
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
DATA = "families/il_dagger_sac/discrete_sac_v1/data/offpolicy_first_completed_v5/SAC_OFFPOLICY_DATASET_V5.json"
DATA_SHA = "b8a2b12479f25112a8cdfc720a6ad0f56f24467cd4c143425c675f814812c39d"
AVAILABILITY = "families/il_dagger_sac/neural_q_v2/AVAILABILITY_SOURCE_ONLY_V2.json"
FAMILY = "families/il_dagger_sac/neural_q_v2/"
SEEDS = [20261027101, 20261027102, 20261027103]
ARCHITECTURES = ["LINEAR", "TANH16"]
TARGETS = ["RETURN", "RISK", "JF_FIXED", "JM_FIXED", "JF_CENTERED", "JM_CENTERED"]
ENDPOINTS = [0, 25, 200]
EXACT_MAXIMUM = {"head_initializations": 468, "Adam_group_updates": 93600,
    "gradient_API": 93600, "training_forward_API": 93600, "observed_gradient_rows": 5529600,
    "evaluation_predict_API": 2700, "evaluation_rows": 89856, "normalizer_fits": 13,
    "target_scale_fits": 26, "ridge_fits": 39, "ridge_solves": 195,
    "ridge_predict_API": 75, "ridge_evaluation_rows": 2496}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4*2**20), b""):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())


def process():
    use = resource.getrusage(resource.RUSAGE_SELF)
    return {"unix": time.time(), "monotonic": time.monotonic(), "cpu_self_s": use.ru_utime+use.ru_stime,
        "maxrss_KiB": use.ru_maxrss, "pid": os.getpid(), "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),
        "executable": sys.executable, "resolved_binary": str(Path(sys.executable).resolve()),
        "binary_sha256": sha(Path(sys.executable).resolve())}


def bounded(package, relative):
    path = (package / relative).resolve()
    if not path.is_relative_to(package):
        raise ValueError("DATA_OR_SOURCE_PATH_ESCAPES_PACKAGE")
    return path


def verify_sources(package, files):
    for relative, expected in files.items():
        if sha(bounded(package, relative)) != expected:
            raise ValueError("APPROVED_FROZEN_SOURCE_OR_DATA_CHANGED:"+relative)


def observed_metrics(rows, indices, values, target):
    """Observed action only; row, unique cell and case averages kept separate."""
    errors = []
    for position, index in enumerate(indices):
        row = rows[index]; estimate = values[position][row["action_index"]]
        if estimate is None:
            continue
        truth = row["canonical_terminal_return"] if target == "RETURN" else row["failure"] if target == "RISK" else row["JF_N_s"] if target.startswith("JF") else row["JM_Nm_s"]
        error = float(estimate)-truth
        errors.append((row["split_case_sha256_evaluation_only"], row["full_recipe_sha256"], abs(error), error*error))
    groups = {}
    case_groups = {}
    for case, action, absolute, squared in errors:
        groups.setdefault((case,action), []).append((absolute,squared))
        case_groups.setdefault(case, []).append((absolute,squared))
    def mean(items, column):
        return sum(item[column] for item in items)/len(items) if items else None
    return {"observed_rows_scored":len(errors), "missing_observed_train_action_prediction":len(indices)-len(errors),
        "row_MAE":mean([(e[2],e[3]) for e in errors],0), "row_MSE_or_risk_Brier":mean([(e[2],e[3]) for e in errors],1),
        "unique_cell_MAE":sum(mean(items,0) for items in groups.values())/len(groups) if groups else None,
        "case_mean_MAE":sum(mean(items,0) for items in case_groups.values())/len(case_groups) if case_groups else None,
        "case_count":len(case_groups), "unique_cell_count":len(groups), "target":target,
        "missing_actions_imputed":False}


def fit_train_input_normalization(rows, train_indices, *, approval):
    """Same function exercised by GateM synthetic train/held leakage fixture."""
    from terminal_head_candidate_v1 import _approval
    _approval(approval)
    import numpy as np
    unique = {}
    for index in train_indices:
        case = rows[index]["split_case_sha256_evaluation_only"]
        if case in unique and rows[index]["features"] != rows[unique[case]]["features"]:
            raise ValueError("ONE_OUT0_CONTEXT_PER_CASE_NO_OUTPUT_FEATURE_REPLACEMENT")
        unique[case] = index
    raw = np.asarray([rows[index]["features"] for index in unique.values()],dtype=float)
    if raw.ndim != 2 or raw.shape[1] != 25 or not np.isfinite(raw).all():
        raise ValueError("FINITE_REGISTERED_25D_UNIQUE_TRAIN_CONTEXTS")
    mean = raw.mean(axis=0); std = raw.std(axis=0); scale = np.where(std < 1e-6,1.,std)
    return {"mean":mean.tolist(),"scale":scale.tolist(),"fit_scope":"TRAIN_UNIQUE_CONTEXTS_ONLY",
        "train_case_sha256":sorted(unique),"std_below_1e_6_mask":(std < 1e-6).tolist()}


def validate_data(package, approval):
    """JSON only. No normalizer/learner called here; no new result opened."""
    if approval["data_sha256"] != DATA_SHA or sha(package/DATA) != DATA_SHA:
        raise ValueError("EXACT_SAC64_ONLY_NOT_G3_OR_OTHER_NEW_ROWS")
    data = json.loads((package/DATA).read_text())
    availability = json.loads((package/AVAILABILITY).read_text())
    if sha(package/AVAILABILITY) != approval["availability_sha256"]:
        raise ValueError("FROZEN_AVAILABILITY_CASE_PARTITION_REQUIRED")
    rows = data["cohorts"]["AGGREGATE64"]
    names = data["feature_names"]
    menu = data["action_contracts"]; menu_sha = data["full_recipe_sha256"]
    if (len(rows) != 64 or len(names) != 25 or digest(names) != approval["feature_names_sha256"] or
            [digest(a) for a in menu] != menu_sha or menu_sha != approval["full_recipe_sha256"]):
        raise ValueError("SAME_64_OBSERVED_ROWS_25D_AND_ACTUAL_FIVE_RECIPE_MENU")
    seen = set()
    parent_case = {}
    for index, row in enumerate(rows):
        action = row["action_index"]
        case = row["split_case_sha256_evaluation_only"]
        parent = row["parent_fingerprint_evaluation_only"]
        if parent in parent_case and parent_case[parent] != case:
            raise ValueError("SAME_PARENT_MAY_NOT_CROSS_CASE_FOLDS")
        parent_case[parent] = case
        if (row.get("complete") is not True or row.get("qa_validated") is not True or
                row["original_evidence"].get("complete") is not True or
                row["original_evidence"].get("ownership_PASS") is not True or
                row["original_evidence"].get("hard_safety") is not False or
                row["feature_names"] != names or not 0 <= action < 5 or
                row["full_recipe_sha256"] != menu_sha[action] or digest(row["full_recipe"]) != menu_sha[action] or
                row["features"] != availability["cases"][case]["features25"]):
            raise ValueError("OBSERVED_COMPLETE_ORIGINAL_CAUSAL_ROW_REQUIRED:"+str(index))
        if row["attempt_id"] in seen:
            raise ValueError("DUPLICATE_PHYSICAL_ROW_IDENTITY_NOT_REPEAT_SAMPLE")
        seen.add(row["attempt_id"])
        qualified = row["original_qualified"]
        reward = max(-.9, min(.9, (row["baseline"]["JF_N_s"]-row["JF_N_s"])/row["baseline"]["JF_N_s"])) if qualified else -1.
        if (abs(reward-row["canonical_terminal_return"]) > 1e-12 or row["failure"] != int(not qualified) or
                not all(math.isfinite(float(value)) for value in row["features"]+[row["JF_N_s"],row["JM_Nm_s"]])):
            raise ValueError("ORIGINAL_GAIN1_FLOOR_AND_INDEPENDENT_PHYSICAL_LABELS")
    cases = {row["split_case_sha256_evaluation_only"] for row in rows}
    if len(cases) != 12 or len(parent_case) != 12:
        raise ValueError("TWELVE_ACTUAL_CASE_PARENT_GROUPS_REQUIRED")
    folds = copy.deepcopy(availability["case_folds"])
    for fold in folds:
        train = fold["train_indices"]; held = fold["held_indices"]
        if set(train) & set(held) or set(train+held) != set(range(64)):
            raise ValueError("CASE_FOLD_ROWS_NOT_EXACT_PARTITION")
        if ({rows[i]["split_case_sha256_evaluation_only"] for i in train} &
                {rows[i]["split_case_sha256_evaluation_only"] for i in held}):
            raise ValueError("HELD_CASE_LEAKED_INTO_TRAIN")
    if len(folds) != 12:
        raise ValueError("TWELVE_EXPOSED_DEVELOPMENT_LOCO_FOLDS")
    folds.append({"fold": "ALL_DEVELOPMENT", "held_case_sha256": None,
        "train_indices": list(range(64)), "held_indices": []})
    return data, rows, availability, folds


def run(package, approval, out, accounting, working):
    import numpy as np
    import terminal_head_candidate_v1 as head
    import ridge_reference_candidate_v1 as ridge
    if np.__version__ != approval["expected_numpy_version"]:
        raise ValueError("APPROVED_NUMPY_ENVIRONMENT_REQUIRED")
    data, rows, availability, folds = validate_data(package, approval)
    names = data["feature_names"]; menu = data["action_contracts"]; menu_sha = data["full_recipe_sha256"]
    write_new(out/"ENVIRONMENT_BEFORE_FIRST_MODEL_API.json", {"process": process(),
        "numpy_module": np.__file__, "numpy_version": np.__version__, "numpy_module_sha256": sha(np.__file__),
        "source_manifest_sha256": approval["source_manifest_sha256"]})
    def increment(key, amount=1):
        accounting[key] = accounting.get(key, 0)+amount
    def tracked(function, key):
        def call(*args, **kwargs):
            increment(key+"_entry")
            try:
                result = function(*args, **kwargs)
            except BaseException as error:
                increment(key+"_failed")
                if hasattr(error, "neural_q_private_consumed_work"):
                    working["paid_failed_private_step"] = error.neural_q_private_consumed_work
                raise
            increment(key+"_completed")
            return result
        return call
    for key in ("initialize", "step", "_forward", "loss_and_gradient", "predict", "snapshot"):
        setattr(head, key, tracked(getattr(head,key), "head."+key))
    for key in ("fit", "predict"):
        setattr(ridge, key, tracked(getattr(ridge,key), "ridge."+key))
    all_x = np.asarray([row["features"] for row in rows], dtype=float)
    all_a = np.asarray([row["action_index"] for row in rows], dtype=int)
    labels = {"RETURN": np.asarray([row["canonical_terminal_return"] for row in rows]),
        "RISK": np.asarray([row["failure"] for row in rows]),
        "JF_FIXED": np.asarray([row["JF_N_s"] for row in rows]),
        "JM_FIXED": np.asarray([row["JM_Nm_s"] for row in rows]),
        "JF_CENTERED": np.asarray([row["JF_N_s"] for row in rows]),
        "JM_CENTERED": np.asarray([row["JM_Nm_s"] for row in rows])}
    for fold in folds:
        scope = fold["fold"]; train = fold["train_indices"]; held = fold["held_indices"]
        working.update(scope=scope, train_indices=train, held_indices=held)
        normalization = fit_train_input_normalization(rows,train,approval=approval)
        unique = {rows[index]["split_case_sha256_evaluation_only"] for index in train}
        increment("normalizer_fits")
        target_norm = {"RETURN": {"mean": 0., "scale": 1.}, "RISK": {"mean": 0., "scale": 1.},
            "JF_FIXED": {"mean": 0., "scale": 1500.}, "JM_FIXED": {"mean": 0., "scale": 100.}}
        for target in ("JF_CENTERED", "JM_CENTERED"):
            target_norm[target] = {"mean": float(labels[target][train].mean()), "scale": max(1., float(labels[target][train].std()))}
            increment("target_scale_fits")
        manifest = {"data_sha256": DATA_SHA, "full_recipe_sha256": menu_sha,
            "feature_names_sha256": digest(names), "all_rows_complete_original_evidence": True,
            "train_indices": train, "train_case_sha256": sorted(unique),
            "train_row_identity_sha256": digest([{"index": i, "attempt_id": rows[i]["attempt_id"],
                "case": rows[i]["split_case_sha256_evaluation_only"], "recipe": rows[i]["full_recipe_sha256"]} for i in train]),
            "held_rows_or_labels_in_training_manifest": False}
        write_new(out/"scopes"/scope/"TRAINING_NORMALIZATION_AND_IDENTITY.json", {"normalization": normalization,
            "targets": target_norm, "manifest": manifest, "held_indices_evaluation_only": held})
        predictions = {endpoint: {} for endpoint in ENDPOINTS}
        for seed in SEEDS:
            for architecture in ARCHITECTURES:
                for target in TARGETS:
                    key = str(seed)+"/"+architecture+"/"+target
                    working.update(model_key=key, endpoint=None)
                    model = head.initialize(architecture=architecture, target=target, feature_names=names,
                        input_normalization=normalization, output_normalization=target_norm[target], seed=seed,
                        action_contracts=menu, full_recipe_sha256=menu_sha, training_manifest=manifest, approval=approval)
                    working["current_model"] = model
                    increment("normal_output_scalars", model["counters"]["normal_output_scalars"])
                    training_trace = []
                    for step_index in range(201):
                        if step_index > 0:
                            trace = head.step(model, names, all_x[train], all_a[train], labels[target][train], qa_validated=True, approval=approval)
                            training_trace.append(trace)
                            increment("parameter_updates")
                            increment("training_observed_gradient_rows", len(train))
                            increment("gradient_clip_activations", int(trace["gradient_scale"] < 1.))
                        if step_index not in ENDPOINTS:
                            continue
                        working["endpoint"] = step_index
                        records = {}
                        for role, indices in (("TRAIN_EXPOSED_DEVELOPMENT", train), ("HELD_CASE_EXPOSED_DEVELOPMENT", held)):
                            if not indices:
                                continue
                            prediction = head.predict(model, names, all_x[indices], qa_validated=True, approval=approval)
                            increment("evaluation_rows", len(indices))
                            records[role] = {"indices": indices, "values": prediction["values"],
                                "observed_only_metrics":observed_metrics(rows,indices,prediction["values"],target)}
                        predictions[step_index][key] = records
                        path = out/"scopes"/scope/str(seed)/architecture/target/("ENDPOINT_"+str(step_index).zfill(4)+".json")
                        write_new(path, {"checkpoint": head.snapshot(model), "evaluation_only": records,
                            "endpoint_selection": "FIXED_PARENT_EARLY_FINAL_NOT_BEST", "policy_selected_using_JF_JM": False})
                    write_new(out/"scopes"/scope/str(seed)/architecture/target/"UPDATE_TRACE.json", training_trace)
                    working.pop("current_model", None)
        ridge_predictions = {}
        for target in ("RETURN", "JF_CENTERED", "JM_CENTERED"):
            model = ridge.fit(feature_names=names, values=all_x[train], actions=all_a[train], raw_targets=labels[target][train],
                target=target, input_normalization=normalization, output_normalization=target_norm[target], training_manifest=manifest, approval=approval)
            increment("ridge_actual_solves", model["linear_solve_calls"])
            record = {}
            for role, indices in (("TRAIN_EXPOSED_DEVELOPMENT", train), ("HELD_CASE_EXPOSED_DEVELOPMENT", held)):
                if indices:
                    values = ridge.predict(model, names, all_x[indices], qa_validated=True, approval=approval)["values"]
                    record[role] = {"indices": indices, "values": values,
                        "observed_only_metrics":observed_metrics(rows,indices,values,target)}
                    increment("ridge_evaluation_rows", len(indices))
            ridge_predictions[target] = record
            write_new(out/"scopes"/scope/"RIDGE"/(target+".json"), {"checkpoint": model, "evaluation_only": record,
                "same_objective": "overallN halfMSE + .5*.001*W_squared; bias unpenalized"})
        # Select from saved prediction arrays only: zero additional head calls.
        choices = []
        for endpoint in ENDPOINTS:
            for seed in SEEDS:
                for architecture in ARCHITECTURES:
                    return_record = predictions[endpoint][str(seed)+"/"+architecture+"/RETURN"]
                    risk_record = predictions[endpoint][str(seed)+"/"+architecture+"/RISK"]
                    for role, record in return_record.items():
                        already = set()
                        for position, index in enumerate(record["indices"]):
                            case = rows[index]["split_case_sha256_evaluation_only"]
                            if case in already:
                                continue
                            already.add(case)
                            for selector in ("RETURN_GREEDY", "RETURN_RISK_LE_0P1_ELSE_B"):
                                choice = head.choose_from_return_and_risk(record["values"][position], risk_record[role]["values"][position], selector=selector)
                                observed = [i for i, row in enumerate(rows) if row["split_case_sha256_evaluation_only"] == case and row["action_index"] == choice["action_index"]]
                                choices.append({"endpoint": endpoint, "seed": seed, "architecture": architecture, "role": role,
                                    "case_sha256_evaluation_only": case, "old_BC_context_preexposed": availability["cases"][case]["old_BC_training_context_preexposed"],
                                    "selector": selector, "choice": choice, "observed_policy_table_indices": observed,
                                    "selection_status": "OBSERVED_ACTUAL_ROWS" if observed else "UNKNOWN_MISSING_ACTION_LABEL",
                                    "observed_outcomes": [{"index": i, "qualified": rows[i]["original_qualified"],
                                        "return": rows[i]["canonical_terminal_return"], "JF_N_s": rows[i]["JF_N_s"], "JM_Nm_s": rows[i]["JM_Nm_s"]} for i in observed],
                                    "external_original_B_baseline_not_imputed_as_policy_row": rows[index]["baseline"]})
        write_new(out/"scopes"/scope/"FIXED_SELECTORS_DEVELOPMENT_ONLY.json", choices)
        ridge_choices = []
        for seed in SEEDS:
            paired_risk = predictions[200][str(seed)+"/LINEAR/RISK"]
            for role, record in ridge_predictions["RETURN"].items():
                already = set()
                for position, index in enumerate(record["indices"]):
                    case = rows[index]["split_case_sha256_evaluation_only"]
                    if case in already:
                        continue
                    already.add(case)
                    predicted_return = record["values"][position]
                    if any(value is None for value in predicted_return):
                        ridge_choices.append({"seed":seed,"role":role,"case":case,"status":"MISSING_TRAIN_ACTION_HEAD_NO_IMPUTED_SELECTOR"})
                        continue
                    for selector in ("RETURN_GREEDY","RETURN_RISK_LE_0P1_ELSE_B"):
                        choice = head.choose_from_return_and_risk(predicted_return,paired_risk[role]["values"][position],selector=selector)
                        known = [i for i,row in enumerate(rows) if row["split_case_sha256_evaluation_only"]==case and row["action_index"]==choice["action_index"]]
                        ridge_choices.append({"seed":seed,"role":role,"case":case,"selector":selector,"choice":choice,
                            "risk_source":"SAME_SCOPE_SEED_LINEAR_FINAL200_BINARY_RISK", "observed_policy_table_indices":known,
                            "status":"OBSERVED_ACTUAL_ROWS" if known else "UNKNOWN_MISSING_ACTION_LABEL", "independent_ridge_refit_per_seed":False})
        write_new(out/"scopes"/scope/"RIDGE_FIXED_SELECTORS_DEVELOPMENT_ONLY.json",ridge_choices)
        write_new(out/"scopes"/scope/"SCOPE_CLOSED.json", {"scope": scope, "END": process(), "accounting": accounting,
            "best_seed_or_endpoint_selection": False, "development_not_independent_validation": True})
        working["completed_scopes"] = working.get("completed_scopes", [])+[scope]
    expected = {"head.initialize_completed": 468, "head.step_completed": 93600, "head.loss_and_gradient_completed": 93600,
        "head._forward_completed": 96300, "head.predict_completed": 2700, "head.snapshot_completed": 1404,
        "parameter_updates": 93600, "training_observed_gradient_rows": 5529600,
        "evaluation_rows": 89856, "normalizer_fits": 13, "target_scale_fits": 26,
        "ridge.fit_completed": 39, "ridge_actual_solves": 195, "ridge.predict_completed": 75, "ridge_evaluation_rows": 2496}
    for key, value in expected.items():
        if accounting.get(key) != value:
            raise ValueError("EXACT_COMPLETE_DESIGN_ACCOUNTING_MISMATCH:"+key)
    return {"status": "COMPLETE_FROZEN64_DEVELOPMENT_DIAGNOSTIC_NO_CONTROL_GAIN_CLAIM", "accounting": accounting,
        "expected_complete_accounting": expected, "best_seed_or_endpoint_selection": False,
        "real_new_physics": 0, "new_live_deployment_authorization": False,
        "training_approval_expiry_must_not_be_extended_for_live_inference": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True); parser.add_argument("--approval", required=True)
    parser.add_argument("--approval-sha", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args(); package = Path(args.package).resolve(); start = process()
    approval_path = bounded(package,args.approval)
    if sha(approval_path) != args.approval_sha:
        raise ValueError("EXACT_NEW_MAIN_OFFLINE_APPROVAL_REQUIRED")
    approval = json.loads(approval_path.read_text())
    if (approval.get("schema") != "v8.neuralq_v2.explicit_call_authorization.v1" or approval.get("approved") is not True or
            approval.get("scope") != "OFFLINE_FROZEN64_ONLY" or approval.get("runner_source_sha256") != sha(__file__) or
            approval.get("expected_binary_sha256") != start["binary_sha256"] or
            approval.get("maximum_wall_s") != 120 or approval.get("maximum_CPU_s") != 120 or
            approval.get("maximum_AS_bytes") != 1024**3 or approval.get("exact_design_maximum") != EXACT_MAXIMUM or
            not approval.get("approved_unix", float("inf")) <= start["unix"] < approval["local_stop_unix"] <= min(start["unix"]+120.,GLOBAL_STOP)):
        raise ValueError("EXACT_SOURCE_FIXED_DESIGN_BOUNDED_NEW_GATER_APPROVAL_REQUIRED")
    verify_sources(package, approval["source_files_sha256"])
    required_sources = {DATA,AVAILABILITY,FAMILY+"terminal_head_candidate_v1.py",FAMILY+"ridge_reference_candidate_v1.py",
        FAMILY+"run_gate_r_frozen64_candidate_v1.py","ACTIVATION.json",approval["source_manifest_path"],approval["contract_path"]}
    if (not required_sources <= set(approval["source_files_sha256"]) or
            sha(bounded(package,approval["source_manifest_path"])) != approval["source_manifest_sha256"] or
            sha(bounded(package,approval["contract_path"])) != approval["contract_sha256"]):
        raise ValueError("ACTUAL_COMPLETE_GATER_SOURCE_CONTRACT_AND_MANIFEST_CLOSURE_REQUIRED")
    gate = approval["passed_GateM_result"]
    if sha(bounded(package,gate["path"])) != gate["sha256"]:
        raise ValueError("ACTUAL_PASSED_MATH_ARTIFACT_CHANGED")
    math_result = json.loads(bounded(package,gate["path"]).read_text())
    if math_result.get("status") != "PASS_SYNTHETIC_MATH_ONLY_NOT_REAL_FIT_AUTHORIZATION":
        raise ValueError("MATH_PASS_REQUIRED_BEFORE_NEW_OFFLINE_MAIN_APPROVAL")
    out = Path(args.output).resolve()
    if not out.is_relative_to(package/"families/il_dagger_sac/neural_q_v2"):
        raise ValueError("PRIVATE_NEW_NEURALQ_OUTPUT_ONLY")
    out.mkdir(exist_ok=False)
    write_new(out/"START.json", {"START": start, "approval_sha256": args.approval_sha,
        "local_stop_unix": approval["local_stop_unix"], "fixed_design_maximum": EXACT_MAXIMUM,
        "source_manifest_sha256": approval["source_manifest_sha256"], "no_automatic_retry_or_partial_as_final": True})
    resource.setrlimit(resource.RLIMIT_CPU,(120,121)); resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    def timeout(signum, frame):
        raise TimeoutError("ORIGINAL_APPROVED_GATER_LOCAL_CPU_OR_WALL_STOP")
    signal.signal(signal.SIGALRM,timeout); signal.signal(signal.SIGXCPU,timeout)
    signal.setitimer(signal.ITIMER_REAL,max(.001,approval["local_stop_unix"]-time.time()))
    os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    accounting = {}; working = {}
    try:
        result = run(package,approval,out,accounting,working)
        write_new(out/"COMPLETE.json",{**result,"START":start,"END":process()})
    except BaseException as error:
        # Cancel alarm only after the paid work has stopped, to preserve evidence.
        signal.setitimer(signal.ITIMER_REAL,0.)
        live = working.pop("current_model",None)
        if live is not None:
            import terminal_head_candidate_v1 as head
            write_new(out/"LAST_UNCOMMITTED_OR_CURRENT_LIVE_HEAD.json",head.snapshot(live))
        write_new(out/"FAILED_OR_BUDGET_INCOMPLETE.json",{"status":"INCOMPLETE_NO_BEST_AVAILABLE_MODEL_CLAIM",
            "error_type":type(error).__name__,"error":str(error),"START":start,"END":process(),
            "paid_accounting":accounting,"working_state":working,"automatic_retry_authorized":False,
            "original_design_steps_or_targets_changed":False,"new_physics":0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0.)


if __name__ == "__main__":
    main()
