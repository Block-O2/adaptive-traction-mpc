"""Source-only original-file Beta joins; no actor imports or RNG draws."""
import copy
import hashlib
from collections import Counter
from beta_durable_transaction_candidate_v1 import ARMS, digest, load, sha, verified, within


def hard_gate(review, snapshots, *, cancelling):
    """A true anywhere wins before censor/clock; unknown needs explicit review."""
    receipts = [p.get("physical_receipt") for s in snapshots.values() for p in s.get("pending", [])]
    if review.get("true_hard_safety_violation") is True or any(
            isinstance(r, dict) and r.get("true_hard_safety_violation") is True for r in receipts):
        raise ValueError("GLOBAL_HARD_SAFETY_STOP_BEFORE_CENSOR_OR_CLOCK")
    if (review.get("true_hard_safety_violation") is not False or
            review.get("all_started_attempts_hard_safety_reviewed") is not True):
        raise ValueError("UNKNOWN_GLOBAL_HARD_SAFETY_NO_UPDATE_OR_CANCELLATION")
    for arm, snapshot in snapshots.items():
        for proposal in snapshot.get("pending", []):
            receipt = proposal.get("physical_receipt")
            if not isinstance(receipt, dict) or receipt.get("true_hard_safety_violation") is not False:
                resolution = review.get("resolved_unknown_hard_attempts", {}).get(proposal["attempt_id"])
                if (not cancelling or not isinstance(resolution, dict) or
                        resolution.get("true_hard_safety_violation") is not False or
                        not resolution.get("original_evidence_files_sha256")):
                    raise ValueError("UNKNOWN_RECEIPT_HARD_STATUS_REQUIRES_ORIGINAL_MAIN_RECONCILIATION")


def _events(package, groups):
    import json
    found = {}
    for raw in (package / "runtime/ATTEMPTS.jsonl").read_bytes().splitlines():
        event = json.loads(raw)
        if event.get("event") not in ("START", "END") or not any(
                event.get("id", "").startswith(g + "_") for g in groups):
            continue
        key = (event["id"], event["event"])
        if key in found:
            raise ValueError("DUPLICATE_ORIGINAL_ATTEMPT_EVENT")
        found[key] = {"record": event, "raw_line_without_newline_sha256": hashlib.sha256(raw).hexdigest(),
                      "canonical_record_sha256": digest(event)}
    return found


def _rng_chain(start, proposals, numerical, end):
    edges = [(p["sample"]["rng_before"], p["sample"]["rng_after"]) for p in proposals]
    edges += [(p["rng_before"], p["rng_after"]) for p in numerical]
    state = start
    while edges:
        matches = [i for i, (before, after) in enumerate(edges) if digest(before) == digest(state)]
        if len(matches) != 1:
            raise ValueError("RNG_CHAIN_MISSING_DUPLICATED_OR_AMBIGUOUS_RESERVATION")
        before, state = edges.pop(matches[0])
    if digest(state) != digest(end):
        raise ValueError("RNG_RESERVATION_CHAIN_ENDPOINT_CHANGED")


def verify_pending_input(package, inputs, current, *, cancelling, rebuild_receipt, rebuild_baseline):
    """Return deterministic proof of the exact closed-job chain, without actors.

    Complete updates require exactly two closed jobs, each cold parent+B+8
    children. Cancellation can use one/two closed partial jobs; it never fills
    missing proposals/receipts and requires explicit safe reconciliation.
    """
    if inputs.get("schema") != "v8.beta_root_bound_pending_input.v1":
        raise ValueError("EXPLICIT_BETA_BOUND_INPUT_SCHEMA")
    review = verified(package, inputs["root_closure_review"])
    final = verified(package, inputs["final_pending_bundle"])
    snapshots = final["snapshots"]
    if set(snapshots) != set(ARMS):
        raise ValueError("FOUR_EXACT_BETA_PENDING_STATES")
    hard_gate(review, snapshots, cancelling=cancelling)
    if (review.get("schema") != "v8.beta_four_arm_root_closure_review.v1" or
            review.get("all_started_children_joined") is not True or
            review.get("all_parent_prefixes_unchanged") is not True):
        raise ValueError("ORIGINAL_ROOT_PHYSICAL_CLOSURE_REQUIRED")
    expected_status = "ENGINEERING_CENSOR_CANCEL_ALL_ARMS" if cancelling else "READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS"
    if review.get("status") != expected_status:
        raise ValueError("ROOT_REVIEW_STATUS_NOT_THIS_OPERATION")
    if review.get("pending_snapshot_object_sha256") != {a: digest(snapshots[a]) for a in ARMS}:
        raise ValueError("ROOT_REVIEW_NOT_OF_EXACT_PENDING_OBJECTS")
    evidence = dict(review.get("original_evidence_files_sha256", {}))
    if not evidence:
        raise ValueError("ROOT_ORIGINAL_CLOSURE_FILES_REQUIRED")
    for resolution in review.get("resolved_unknown_hard_attempts", {}).values():
        evidence.update(resolution.get("original_evidence_files_sha256", {}))
    for path, expected in evidence.items():
        if sha(within(package, path)) != expected:
            raise ValueError("ROOT_HARD_OR_CLOSURE_EVIDENCE_CHANGED")
    job_refs = inputs.get("job_configs", [])
    if len(job_refs) not in ((1, 2) if cancelling else (2,)):
        raise ValueError("ONE_OR_TWO_PARTIAL_CANCEL_JOBS_OR_EXACT_TWO_FULL_JOBS")
    configs = [verified(package, ref) for ref in job_refs]
    groups = [c["group"] for c in configs]
    if len(set(groups)) != len(groups) or groups != inputs["root_expected_sampling_groups"]:
        raise ValueError("EXACT_ORDERED_DISTINCT_SAMPLING_GROUPS")
    events = _events(package, groups)
    bundles, closed = [], {}
    for config, ref in zip(configs, job_refs):
        group = config["group"]
        if within(package, ref["path"]) != package / "experiments" / (group + ".json"):
            raise ValueError("CONFIG_NOT_ORIGINAL_EXPERIMENT_FILE")
        spec = config["onpolicy_sampling"]
        if spec.get("schema") != "v8.continuous_beta_sampling_job.v1":
            raise ValueError("CATEGORICAL_CONFIG_NOT_A_BETA_JOB")
        for path, expected in config["frozen_artifacts"].items():
            if sha(within(package, path)) != expected:
                raise ValueError("JOB_FROZEN_ARTIFACT_CHANGED:" + path)
        output = within(package, spec["output_directory"])
        bundle_path = output / "PENDING_CHECKPOINTS.json"
        bundle = load(bundle_path)
        if (bundle.get("schema") != "v8.continuous_beta_pending_bundle.v1" or
                bundle.get("parameter_updates_in_this_job") != 0 or
                bundle.get("group_evaluation_only") != group or
                bundle.get("logical_context_evaluation_only") != spec["development_context_id"]):
            raise ValueError("ORIGINAL_PENDING_BUNDLE_IDENTITY")
        if not cancelling and bundle.get("stage") != "ALL_EIGHT_FRESH_CHILD_RECEIPTS_COLLECTED_NO_UPDATE":
            raise ValueError("CLOSED_PENDING_NOT_FULL_EIGHT_SAMPLES")
        if not cancelling:
            sampling_done = load(output / "SAMPLING_DONE.json")
            if sampling_done.get("status") != "PENDING_ONLY_NO_UPDATE" or sampling_done.get("parameter_updates") != 0:
                raise ValueError("SAMPLER_DID_NOT_CLOSE_WITHOUT_UPDATE")
        done_path = package / "jobs" / group / "WORKER_DONE.json"
        done = load(done_path)
        if not cancelling and done.get("status") != "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS":
            raise ValueError("FULL_WORKER_CLOSURE_REQUIRED")
        supervisor_path = package / "owned" / (group + "_SUPERVISOR_END.json")
        supervisor = load(supervisor_path)
        exit_path = package / "owned" / (group + "_EXIT.json")
        if supervisor.get("state") != "STOP" or supervisor.get("survivors") or not exit_path.is_file():
            raise ValueError("PHYSICAL_OWNER_NOT_CLOSED")
        if not cancelling and supervisor.get("worker_exit_code") != 0:
            raise ValueError("FULL_WORKER_EXIT_NOT_ZERO")
        parent_gate = package / "audit" / (group + "_PARENT_RAW_GATE.json")
        if load(parent_gate).get("status") != "PASS":
            raise ValueError("ORIGINAL_PARENT_RAW_GATE_NOT_PASS")
        starts = {i for (i, kind) in events if kind == "START" and i.startswith(group + "_")}
        ends = {i for (i, kind) in events if kind == "END" and i.startswith(group + "_")}
        if starts != ends or (not cancelling and len(starts) != 10):
            raise ValueError("ALL_ACTUAL_START_END_MUST_CLOSE_PARENT_B_AND_EIGHT_CHILDREN")
        for ident in starts:
            end = events[(ident, "END")]["record"]
            if end.get("joined") is not True or (not cancelling and end.get("returncode") != 0):
                raise ValueError("ACTUAL_CHILD_OR_PARENT_NOT_JOINED")
            if events[(ident, "START")]["record"]["config_sha256"] != ref["sha256"]:
                raise ValueError("ACTUAL_START_NOT_THIS_FROZEN_CONFIG")
        if set(bundle["snapshots"]) != set(ARMS):
            raise ValueError("JOB_MISSING_ARM_SNAPSHOT")
        for arm in ARMS:
            direct = output / (arm + "_PENDING.json")
            if digest(load(direct)) != digest(bundle["snapshots"][arm]):
                raise ValueError("DIRECT_PENDING_NOT_EXACT_BUNDLE_STATE")
            evidence[str(direct.relative_to(package))] = sha(direct)
        for path in (bundle_path, done_path, supervisor_path, exit_path, parent_gate):
            evidence[str(path.relative_to(package))] = sha(path)
        bundles.append(bundle)
        closed[group] = {"config_sha256": ref["sha256"], "worker_done_sha256": sha(done_path),
                         "supervisor_end_sha256": sha(supervisor_path), "attempt_ids": sorted(starts)}
    if digest(final) != digest(bundles[-1]) or within(package, inputs["final_pending_bundle"]["path"]) != within(
            package, configs[-1]["onpolicy_sampling"]["output_directory"]) / "PENDING_CHECKPOINTS.json":
        raise ValueError("FINAL_PENDING_NOT_LAST_CLOSED_JOB")
    contexts = [c["onpolicy_sampling"]["development_context_id"] for c in configs]
    if len(set(contexts)) != len(contexts):
        raise ValueError("SAME_CONTEXT_CANNOT_BE_COUNTED_AS_TWO_DEV_CASES")
    previous = {a: verified(package, current["checkpoints"][a]) for a in ARMS}
    for job_index, (config, bundle) in enumerate(zip(configs, bundles)):
        items = config["onpolicy_sampling"]["arm_inputs"]
        if [item["arm_id"] for item in items] != ARMS:
            raise ValueError("EXACT_INPUT_ARM_ORDER")
        for item in items:
            arm = item["arm_id"]
            source = verified(package, {"path": item["snapshot_path"], "sha256": item["snapshot_sha256"]})
            if job_index == 0:
                if item["snapshot_path"] != current["checkpoints"][arm]["path"] or item["snapshot_sha256"] != current["checkpoints"][arm]["sha256"]:
                    raise ValueError("FIRST_JOB_NOT_FROM_CURRENT_GENERATION")
            elif digest(source) != digest(bundles[job_index - 1]["snapshots"][arm]):
                raise ValueError("SECOND_JOB_NOT_EXACT_FIRST_PENDING_RNG_AND_RECEIPT_STATE")
            output_snapshot = bundle["snapshots"][arm]
            prefix = source["pending"]
            if output_snapshot["pending"][:len(prefix)] != prefix:
                raise ValueError("LATER_JOB_CHANGED_EARLIER_EXACT_PROPOSALS_OR_RECEIPTS")
            old_numerical = source["numerical_no_proposal"]
            if output_snapshot["numerical_no_proposal"][:len(old_numerical)] != old_numerical:
                raise ValueError("NUMERICAL_RESERVATION_EVIDENCE_CHANGED")
            _rng_chain(source["rng"], output_snapshot["pending"][len(prefix):],
                       output_snapshot["numerical_no_proposal"][len(old_numerical):], output_snapshot["rng"])
    seen, joins, checked_baselines = set(), [], {}
    for arm in ARMS:
        old, final_state = previous[arm], snapshots[arm]
        if old["pending"]:
            raise ValueError("CURRENT_GENERATION_CONTAINS_PENDING_COLLECTION")
        stable = ["schema", "execution_mode", "math_fixture_contract_sha256", "algorithm", "policy_behavior_sha256",
                  "batch_policy_sha256", "frozen_axis_sha256", "training_contract_sha256", "gate1_pass_receipt_sha256",
                  "case_split_sha256", "dependency_sha256", "expected_context_counts", "local_stop_unix",
                  "original_global_deadline_unix", "optimizer", "finished_batches", "batch_id", "failed_private_updates"]
        if any(final_state.get(k) != old.get(k) for k in stable):
            raise ValueError("SAMPLING_CHANGED_FROZEN_MODEL_OPTIMIZER_OR_GENERATION")
        old_policy = {k: v for k, v in old["policy"].items() if k != "counters"}
        new_policy = {k: v for k, v in final_state["policy"].items() if k != "counters"}
        if old_policy != new_policy:
            raise ValueError("SAMPLING_CHANGED_ACTUAL_POLICY_PARAMETERS")
        if final_state["policy"]["counters"]["parameter_updates"] != old["policy"]["counters"]["parameter_updates"]:
            raise ValueError("SAMPLING_PERFORMED_PARAMETER_UPDATE")
        rng = old["rng"]
        for proposal in final_state["pending"]:
            ident = proposal["attempt_id"]
            if ident in seen:
                raise ValueError("CROSS_ARM_OR_CONTEXT_ACTUAL_ATTEMPT_REUSE")
            seen.add(ident)
            candidates = [c for c in configs if ident.startswith(c["group"] + "_OP_" + arm + "_")]
            if len(candidates) != 1:
                raise ValueError("PROPOSAL_NOT_ROUTED_TO_EXACT_ARM_AND_JOB")
            config = candidates[0]; spec = config["onpolicy_sampling"]
            sample = proposal["sample"]
            if not cancelling and digest(sample["rng_before"]) != digest(rng):
                raise ValueError("CANONICAL_RNG_CHAIN_BROKEN")
            rng = sample["rng_after"]
            if (sample["policy_sha256"] != old["policy_behavior_sha256"] or proposal["batch_id"] != old["batch_id"] or
                    proposal["context_group_evaluation_only"] != spec["development_context_id"]):
                raise ValueError("PROPOSAL_NOT_THIS_COLLECTION_POLICY_CONTEXT_OR_BATCH")
            output = within(package, spec["output_directory"])
            baseline_path = output / "B_BASELINE_RECEIPT.json"
            baseline = load(baseline_path)
            if baseline != proposal["baseline_evaluation_only"]:
                raise ValueError("PROPOSAL_BASELINE_CHANGED")
            if config["group"] not in checked_baselines:
                rebuilt_b = rebuild_baseline(config, bundles[configs.index(config)]["context25"], baseline["original_worker_result"])
                if digest(rebuilt_b) != digest(baseline):
                    raise ValueError("BASELINE_NOT_ORIGINAL_ARTIFACT_REBUILD")
                checked_baselines[config["group"]] = digest(baseline)
            original = copy.deepcopy(proposal); receipt = original["physical_receipt"]; original["physical_receipt"] = None
            tag = ident.removeprefix(config["group"] + "_")
            source = output / (tag + "_PROPOSAL.json")
            if digest(load(source)) != digest(original):
                raise ValueError("PENDING_NOT_EXACT_PRESAMPLED_JSON")
            body = copy.deepcopy(original); identity = body.pop("proposal_identity_sha256")
            if digest(body) != identity:
                raise ValueError("ORIGINAL_CANONICAL_PROPOSAL_IDENTITY_CHANGED")
            for path in (source, baseline_path):
                evidence[str(path.relative_to(package))] = sha(path)
            if receipt is None:
                if not cancelling:
                    raise ValueError("MISSING_GENUINE_RECEIPT")
                joins.append({"attempt_id": ident, "receipt": "MISSING_CENSORED_NOT_IMPUTED"})
                continue
            saved_path = output / (tag + "_PHYSICAL_RECEIPT.json")
            saved = load(saved_path)
            missing = [k for k in ("attempt_start_sha256", "attempt_end_sha256", "result_source_sha256",
                       "native_ownership_sha256", "applied_reference_receipt_stream_sha256") if not saved.get(k)]
            if saved.get("genuine_new_physical_attempt") is not True or saved.get("historical_or_cached_outcome") is not False:
                missing.append("NOT_GENUINE_NEW_PHYSICAL_ATTEMPT")
            if not isinstance(saved.get("actual_new_native_steps"), int) or saved["actual_new_native_steps"] <= 0:
                missing.append("NO_NEW_NATIVE_STEPS")
            if receipt != {**saved, "driver_receipt_errors": missing}:
                raise ValueError("ATTACHED_RECEIPT_NOT_EXACT_SAVED_ADAPTER_RESULT")
            rebuilt = rebuild_receipt(config, bundles[configs.index(config)]["context25"], original, saved["original_worker_result"])
            if digest(rebuilt) != digest(saved):
                raise ValueError("BETA_RECEIPT_NOT_EXACT_ORIGINAL_ARTIFACT_ROUNDTRIP")
            for kind in ("START", "END"):
                if saved["events_original_records_and_hash_scopes"][kind] != events[(ident, kind)]:
                    raise ValueError("ORIGINAL_EVENT_RAW_LINE_OR_CANONICAL_RECORD_CHANGED")
            for path, expected in saved["original_artifact_files_sha256"].items():
                if sha(within(package, path)) != expected:
                    raise ValueError("ORIGINAL_PHYSICAL_ARTIFACT_CHANGED")
                evidence[path] = expected
            evidence[str(saved_path.relative_to(package))] = sha(saved_path)
            joins.append({"attempt_id": ident, "proposal_sha256": sha(source), "physical_receipt_sha256": sha(saved_path),
                          "actual_start_end_verified": True, "scalar_lambda_logdensity_unchanged": sample["old_logprob"]})
        if final_state["numerical_no_proposal"][:len(old["numerical_no_proposal"])] != old["numerical_no_proposal"]:
            raise ValueError("OLD_NUMERICAL_RESERVATIONS_CHANGED")
        new_numerical = final_state["numerical_no_proposal"][len(old["numerical_no_proposal"]):]
        _rng_chain(old["rng"], final_state["pending"], new_numerical, final_state["rng"])
        if not cancelling and Counter(p["context_group_evaluation_only"] for p in final_state["pending"]) != old["expected_context_counts"]:
            raise ValueError("EXACT_TWO_SAMPLES_PER_ORIGINAL_DEV_CONTEXT_REQUIRED")
        expected_seen = set(old["seen_attempt_ids"]) | {p["attempt_id"] for p in final_state["pending"]}
        expected_seen |= {p["attempt_id_reserved_but_not_dispatched"] for p in new_numerical}
        if set(final_state["seen_attempt_ids"]) != expected_seen or (not cancelling and new_numerical):
            raise ValueError("UNACCOUNTED_NUMERICAL_RESERVATION_OR_SEEN_ATTEMPT")
    if not cancelling and len(seen) != 16:
        raise ValueError("COMPLETE_BATCH_REQUIRES_SIXTEEN_NEW_POLICY_ATTEMPTS")
    return {"schema": "v8.beta_exact_original_two_job_chain_proof.v1", "status": expected_status,
            "closed_jobs": closed, "joins": joins, "input_snapshots_sha256": {a: digest(snapshots[a]) for a in ARMS},
            "root_review_object_sha256": digest(review), "original_evidence_files_sha256": evidence,
            "original_event_records_and_hash_scopes": {ident + "|" + kind: event
                for (ident, kind), event in events.items()},
            "group_transaction_id": review["group_transaction_id"], "physical_samples_not_shared": True,
            "actor_initializations_restores_forwards_updates": 0, "cancellation": cancelling}
