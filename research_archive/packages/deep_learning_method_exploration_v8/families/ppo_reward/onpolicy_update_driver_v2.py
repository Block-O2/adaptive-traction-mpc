"""Receipt-bound primitives only. Main agent owns all dispatch and files.

Import has no model, training, environment, physics or process side effects.
Do not invoke proposal/update functions until B-ONPOLICY-V1 is approved and the
main runner has frozen case/action/source/evaluation identities.
"""
from __future__ import annotations

import copy
import math
import random
import time
import hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime

import categorical_policy as _categorical_dependency
from categorical_policy import initialize, choose, update, probabilities, policy_sha256, digest, ON_POLICY

HARD_DEADLINE_UNIX = datetime.fromisoformat("2026-10-27T15:25:40+00:00").timestamp()


def _before_new_learning():
    if time.time() >= HARD_DEADLINE_UNIX:
        raise ValueError("ORIGINAL_GLOBAL_HARD_DEADLINE_REACHED")


def validate_recipe_menu(policy, frozen_menu_sha256, *, expected_size=5):
    """Validate contract bytes, declared hashes and the independently frozen menu.

    V1 policy_sha256 intentionally remains frozen. This explicit V2 check closes
    the metadata-only recipe gap without changing V1 inference semantics.
    """
    menu = list(frozen_menu_sha256)
    contracts = policy.get("action_contracts")
    declared = policy.get("action_sha256")
    if len(menu) != expected_size or len(set(menu)) != expected_size:
        raise ValueError("FROZEN_ORDERED_MENU_SIZE_OR_DUPLICATE")
    if not isinstance(contracts,list) or len(contracts) != expected_size or declared != menu:
        raise ValueError("POLICY_DECLARED_MENU_IDENTITY")
    actual = [digest(contract) for contract in contracts]
    if actual != declared or actual != menu:
        raise ValueError("ACTUAL_ACTION_CONTRACT_NOT_FROZEN_RECIPE")
    if len(policy.get("weights",[])) != expected_size:
        raise ValueError("POLICY_WEIGHT_MENU_SHAPE")
    return actual


def validate_dependency(expected_sha256):
    loaded_path = Path(_categorical_dependency.__file__).resolve()
    actual = hashlib.sha256(loaded_path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError("FROZEN_CATEGORICAL_DEPENDENCY_CHANGED")
    return {"module_file":str(loaded_path),"source_sha256":actual}


def lift_three_to_five(parent, five_action_contracts, *, new_seed):
    """Predeclared common initialization, not a trained five-action policy.

    First three recipe identities must exactly match B/LATE_H150/EARLY_H150.
    New phase logit rows equal the two H150 weight rows' mean. The old three
    logits remain exact but their probabilities change through the denominator.
    """
    _before_new_learning()
    if len(parent["weights"]) != 3 or len(five_action_contracts) != 5:
        raise ValueError("THREE_TO_FIVE_ONLY")
    if [digest(x) for x in five_action_contracts[:3]] != parent["action_sha256"]:
        raise ValueError("PARENT_ACTION_RECIPE_IDENTITY_MISMATCH")
    validate_recipe_menu(parent, [digest(x) for x in five_action_contracts[:3]], expected_size=3)
    lifted = initialize(five_action_contracts, parent["feature_names"], seed=new_seed,
                        normalization=parent["normalization"])
    lifted["representation"] = parent.get("representation", "linear_commissioned25")
    lifted["weights"][:3] = copy.deepcopy(parent["weights"])
    mean = [(a+b)/2 for a,b in zip(parent["weights"][1], parent["weights"][2])]
    lifted["weights"][3] = mean.copy()
    lifted["weights"][4] = mean.copy()
    lifted["initialization"] = {"schema": "v8.three_to_five_logit_lift.v1", "source_policy_sha256": policy_sha256(parent),
                                  "first_three_logits_unchanged": True, "three_action_probabilities_unchanged": False,
                                  "new_phase_logits": "MEAN_OF_TWO_H150_ROWS", "new_case_results_used": False}
    validate_recipe_menu(lifted, [digest(x) for x in five_action_contracts])
    return lifted


class OnPolicyArm:
    """One arm, one current policy, no cross-arm outcome reuse.

    The serialized snapshot includes full RNG and pending proposals. The main
    runner must atomically checkpoint it with its own model/source manifests.
    """
    def __init__(self, policy, *, arm_id, algorithm, gain, seed,
                 approved_contract_sha256, expected_context_counts, local_stop_unix,
                 frozen_menu_sha256, categorical_dependency_sha256):
        if algorithm not in ("REINFORCE", "PPO") or gain not in (1.0, 20.0):
            raise ValueError("UNAPPROVED_ALGORITHM_OR_GAIN")
        if not approved_contract_sha256 or not expected_context_counts or any(v != 2 for v in expected_context_counts.values()):
            raise ValueError("EXPLICIT_TWO_PER_CONTEXT_BATCH_CONTRACT_REQUIRED")
        if len(expected_context_counts) != 2:
            raise ValueError("EXACTLY_TWO_DEVELOPMENT_CONTEXTS_REQUIRED")
        validate_recipe_menu(policy, frozen_menu_sha256)
        self.categorical_dependency = validate_dependency(categorical_dependency_sha256)
        self.frozen_menu_sha256 = list(frozen_menu_sha256)
        self.policy = copy.deepcopy(policy)
        if not isinstance(local_stop_unix,(int,float)) or not math.isfinite(local_stop_unix) or local_stop_unix > HARD_DEADLINE_UNIX:
            raise ValueError("LOCAL_STOP_MUST_RESPECT_ORIGINAL_GLOBAL_DEADLINE")
        self.local_stop_unix = local_stop_unix
        self.arm_id = arm_id
        self.algorithm = algorithm
        self.gain = gain
        self.rng = random.Random(seed)
        self.contract_sha256 = approved_contract_sha256
        self.expected_context_counts = dict(expected_context_counts)
        self.batch_policy_sha256 = policy_sha256(self.policy)
        self.pending = []
        self.seen_attempt_ids = set()
        self.finished_batches = []
        self.batch_id = 0

    def _validate_frozen_identity(self):
        validate_recipe_menu(self.policy, self.frozen_menu_sha256)
        validate_dependency(self.categorical_dependency["source_sha256"])

    def propose(self, *, attempt_id, context_group_evaluation_only,
                feature_names, commissioned_values, qa_validated,
                complete_qualified_baseline_receipt):
        _before_new_learning()
        self._validate_frozen_identity()
        if time.time() >= self.local_stop_unix:
            raise ValueError("LOCAL_EXPERIMENT_DISPATCH_CLOSED")
        if qa_validated is not True or list(feature_names) != self.policy["feature_names"]:
            raise ValueError("CAUSAL_CONTEXT_SCHEMA_OR_QA")
        if policy_sha256(self.policy) != self.batch_policy_sha256:
            raise ValueError("POLICY_CHANGED_WITH_PENDING_BATCH")
        group = context_group_evaluation_only
        if group not in self.expected_context_counts:
            raise ValueError("UNREGISTERED_TRAINING_CONTEXT")
        if Counter(r["context_group_evaluation_only"] for r in self.pending)[group] >= self.expected_context_counts[group]:
            raise ValueError("BATCH_CONTEXT_COUNT_EXCEEDED")
        if attempt_id in self.seen_attempt_ids:
            raise ValueError("DUPLICATE_ATTEMPT_ID")
        base = complete_qualified_baseline_receipt
        if base.get("complete") is not True or base.get("original_qualified") is not True or not base.get("result_source_sha256"):
            raise ValueError("NEW_CONTEXT_B_BASELINE_NOT_COMPLETE_AND_QUALIFIED")
        context_digest = digest({"names": feature_names, "values": commissioned_values})
        if base.get("context_group_evaluation_only") != group or base.get("causal_features_sha256") != context_digest:
            raise ValueError("BASELINE_CONTEXT_IDENTITY_MISMATCH")
        if any(not isinstance(base.get(k), (int,float)) or not math.isfinite(base[k]) for k in ("JF_N_s", "JM_Nm_s")):
            raise ValueError("BASELINE_FULL_COST_MISSING")
        before = self.rng.getstate()
        sample = choose(self.policy, commissioned_values, deterministic=False, rng=self.rng,
                        behavior_sha256=self.batch_policy_sha256)
        if digest(sample["action"]) != sample["action_sha256"] or sample["action_sha256"] != self.frozen_menu_sha256[sample["action_index"]]:
            raise ValueError("SAMPLED_CONTRACT_NOT_ACTUAL_FROZEN_RECIPE")
        proposal = {"schema": "v8.genuine_onpolicy_proposal.v1", "arm_id": self.arm_id,
                    "batch_id": self.batch_id, "attempt_id": attempt_id,
                    "context_group_evaluation_only": group,
                    "features": list(commissioned_values), "feature_names": list(feature_names),
                    "causal_features_sha256": context_digest,
                    "collection_policy_sha256": self.batch_policy_sha256,
                    "collection_policy_version": self.policy["version"],
                    "action_index": sample["action_index"], "old_logprob": sample["logprob"],
                    "proposal_recipe": sample["action"], "proposal_recipe_sha256": sample["action_sha256"],
                    "rng_before": before, "rng_after": self.rng.getstate(),
                    "baseline_evaluation_only": copy.deepcopy(base), "data_semantics": ON_POLICY,
                    "approved_contract_sha256": self.contract_sha256, "physical_result": None}
        proposal["proposal_identity_sha256"] = digest(proposal)
        self.pending.append(proposal)
        self.seen_attempt_ids.add(attempt_id)
        return copy.deepcopy(proposal)

    def accept_physical_receipt(self, receipt):
        """Attach a genuine new physical result, never a historical/cache label.

        Missing/engineering data is stored then invalidates the entire batch.
        Protected task failure is valid target feedback; infrastructure failure
        is censored and is not rewritten as task failure.
        """
        matches = [r for r in self.pending if r["attempt_id"] == receipt.get("attempt_id")]
        if len(matches) != 1 or matches[0]["physical_result"] is not None:
            raise ValueError("UNMATCHED_OR_DUPLICATE_RECEIPT")
        proposal = matches[0]
        if receipt.get("arm_id") != self.arm_id or receipt.get("proposal_identity_sha256") != proposal["proposal_identity_sha256"]:
            raise ValueError("ARM_OR_PROPOSAL_RECEIPT_IDENTITY")
        if receipt.get("selected_full_recipe_sha256") != proposal["proposal_recipe_sha256"]:
            raise ValueError("SELECTED_RECIPE_RECEIPT_IDENTITY")
        if receipt.get("context_group_evaluation_only") != proposal["context_group_evaluation_only"] or receipt.get("causal_features_sha256") != proposal["causal_features_sha256"]:
            raise ValueError("PHYSICAL_RECEIPT_CONTEXT_IDENTITY")
        if receipt.get("genuine_new_physical_attempt") is not True or receipt.get("historical_or_cached_outcome") is not False:
            raise ValueError("NOT_GENUINE_NEW_ON_POLICY_PHYSICS")
        required_hashes = ("attempt_start_sha256", "attempt_end_sha256", "result_source_sha256", "native_ownership_sha256", "applied_reference_receipt_stream_sha256")
        saved = copy.deepcopy(receipt)
        errors = ["MISSING_PHYSICAL_IDENTITY:" + k for k in required_hashes if not receipt.get(k)]
        if not isinstance(receipt.get("actual_new_native_steps"), int) or receipt["actual_new_native_steps"] <= 0:
            errors.append("NO_ACTUAL_NEW_NATIVE_STEPS")
        saved["driver_receipt_errors"] = errors
        proposal["physical_result"] = saved

    def preflight_batch_metadata(self):
        """No model forward/update. Root checks all four arms before committing.

        Any confirmed hard violation wins over every engineering censor reason.
        Root then updates copies transactionally and commits all four or none.
        """
        self._validate_frozen_identity()
        for proposal in self.pending:
            receipt = proposal.get("physical_result")
            if isinstance(receipt,dict) and receipt.get("true_hard_safety_violation") is True:
                raise ValueError("HARD_SAFETY_STOP_MAIN_AGENT_REVIEW")
        if Counter(r["context_group_evaluation_only"] for r in self.pending) != Counter(self.expected_context_counts):
            raise ValueError("INCOMPLETE_CONTEXT_BALANCED_BATCH")
        if any(r["physical_result"] is None for r in self.pending):
            raise ValueError("OUTSTANDING_PHYSICAL_RESULT")
        cancelled = []
        for proposal in self.pending:
            original = copy.deepcopy(proposal)
            stored_identity = original.pop("proposal_identity_sha256")
            original["physical_result"] = None
            if digest(original) != stored_identity:
                raise ValueError("PENDING_PROPOSAL_CHANGED_AFTER_SAMPLING")
            index = proposal["action_index"]
            if digest(proposal["proposal_recipe"]) != proposal["proposal_recipe_sha256"] or proposal["proposal_recipe_sha256"] != self.frozen_menu_sha256[index]:
                raise ValueError("PENDING_RECIPE_NOT_FROZEN_MENU")
            if proposal["collection_policy_sha256"] != self.batch_policy_sha256 or policy_sha256(self.policy) != self.batch_policy_sha256:
                raise ValueError("PENDING_POLICY_DENSITY_IDENTITY")
            receipt = proposal["physical_result"]
            if receipt.get("driver_receipt_errors") or receipt.get("engineering_complete") is not True or receipt.get("ownership_and_causality_audit_pass") is not True:
                cancelled.append(proposal["attempt_id"])
                continue
            if receipt.get("true_hard_safety_violation") is not False:
                cancelled.append(proposal["attempt_id"])
                continue
            if not isinstance(receipt.get("complete"),bool) or not isinstance(receipt.get("original_qualified"),bool):
                cancelled.append(proposal["attempt_id"])
                continue
            if receipt["complete"] is not True and receipt.get("protected_task_failure") is not True:
                cancelled.append(proposal["attempt_id"])
                continue
            if receipt["complete"] and receipt["original_qualified"] and any(not isinstance(receipt.get(k),(int,float)) or not math.isfinite(receipt[k]) for k in ("JF_N_s","JM_Nm_s")):
                cancelled.append(proposal["attempt_id"])
        return {"admissible":not cancelled,"cancelled_receipts":cancelled,"policy_sha256":self.batch_policy_sha256,
                "pending_attempt_ids":[r["attempt_id"] for r in self.pending],"frozen_menu_sha256":self.frozen_menu_sha256,
                "hard_safety_precedes_engineering_censoring":True,"model_forward":0,"parameter_updates":0}

    def finish_batch(self):
        _before_new_learning()
        self._validate_frozen_identity()
        preflight = self.preflight_batch_metadata()
        records = []
        cancelled = preflight["cancelled_receipts"]
        for proposal in self.pending if not cancelled else []:
            actual_logprob = math.log(max(probabilities(self.policy, proposal["features"])[proposal["action_index"]], 1e-300))
            if abs(actual_logprob - proposal["old_logprob"]) > 1e-12:
                raise ValueError("SAVED_LOGPROB_NOT_COLLECTION_POLICY_DENSITY")
            receipt = proposal["physical_result"]
            if receipt["complete"] and receipt["original_qualified"]:
                jf = receipt.get("JF_N_s")
                jm = receipt.get("JM_Nm_s")
                if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in (jf,jm)):
                    cancelled.append(proposal["attempt_id"])
                    continue
                base = proposal["baseline_evaluation_only"]
                reward = max(-0.9, min(0.9, self.gain*(base["JF_N_s"]-jf)/max(abs(base["JF_N_s"]),1.0)))
            else:
                reward = -1.0
            records.append({"features": proposal["features"], "action_index": proposal["action_index"],
                            "old_logprob": proposal["old_logprob"], "reward": reward,
                            "collection_policy_sha256": proposal["collection_policy_sha256"],
                            "physical_attempt_id": proposal["attempt_id"]})
        if time.time() >= self.local_stop_unix:
            result = {"status": "CANCELLED_LOCAL_DEADLINE_NO_UPDATE", "parameter_updates": 0, "all_physical_costs_preserved": True}
        elif cancelled:
            result = {"status": "CANCELLED_ENGINEERING_CENSORING_NO_UPDATE", "cancelled_receipts": cancelled,
                      "parameter_updates": 0, "all_physical_costs_preserved": True}
        else:
            baseline = sum(r["reward"] for r in records)/len(records)
            result = update(self.policy, records, algorithm=self.algorithm, data_semantics=ON_POLICY,
                            learning_rate=0.15, epochs=3 if self.algorithm == "PPO" else 1,
                            clip_range=0.2, advantage_baseline=baseline, max_gradient_norm=1.0)
            result["status"] = "COMPLETED_GENUINE_ON_POLICY_UPDATE"
            result["reward_baseline"] = baseline
        batch = {"batch_id": self.batch_id, "result": result, "proposals_and_physical_receipts": copy.deepcopy(self.pending)}
        self.finished_batches.append(batch)
        self.pending = []
        self.batch_id += 1
        self.batch_policy_sha256 = policy_sha256(self.policy)
        return copy.deepcopy(batch)

    def cancel_pending_batch(self, *, group_transaction_id, reason):
        """Main-agent group censoring: archive costs/RNG without any update.

        Works with partial context counts. Never rewinds sampling RNG or seen
        attempt IDs, and never turns a confirmed hard violation into censoring.
        """
        self._validate_frozen_identity()
        if not group_transaction_id or not reason:
            raise ValueError("EXPLICIT_GROUP_CANCELLATION_ID_AND_REASON_REQUIRED")
        if any(isinstance(r.get("physical_result"),dict) and r["physical_result"].get("true_hard_safety_violation") is True for r in self.pending):
            raise ValueError("HARD_SAFETY_STOP_MAIN_AGENT_REVIEW")
        batch = {"batch_id":self.batch_id,"result":{"status":"CANCELLED_WHOLE_GROUP_NO_UPDATE",
                 "group_transaction_id":group_transaction_id,"reason":reason,"parameter_updates":0,
                 "sampling_rng_not_rewound":True,"all_physical_costs_preserved":True},
                 "proposals_and_physical_receipts":copy.deepcopy(self.pending)}
        self.finished_batches.append(batch)
        self.pending = []
        self.batch_id += 1
        self.batch_policy_sha256 = policy_sha256(self.policy)
        return copy.deepcopy(batch)

    def snapshot(self):
        self._validate_frozen_identity()
        return {"schema": "v8.genuine_onpolicy_arm_checkpoint.v2", "policy": copy.deepcopy(self.policy),
                "frozen_menu_sha256":list(self.frozen_menu_sha256),"categorical_dependency":dict(self.categorical_dependency),
                "arm_id": self.arm_id, "algorithm": self.algorithm, "gain": self.gain,
                "rng": self.rng.getstate(), "contract_sha256": self.contract_sha256,
                "local_stop_unix": self.local_stop_unix, "global_deadline_unix": HARD_DEADLINE_UNIX,
                "expected_context_counts": self.expected_context_counts,
                "batch_policy_sha256": self.batch_policy_sha256,
                "pending": copy.deepcopy(self.pending), "seen_attempt_ids": sorted(self.seen_attempt_ids),
                "finished_batches": copy.deepcopy(self.finished_batches), "batch_id": self.batch_id,
                "owner": "MAIN_AGENT_ONLY", "automatic_physics_dispatch": False}

    @classmethod
    def restore(cls, snapshot, *, approved_contract_sha256, frozen_menu_sha256, categorical_dependency_sha256):
        if snapshot.get("schema") != "v8.genuine_onpolicy_arm_checkpoint.v2" or snapshot.get("contract_sha256") != approved_contract_sha256:
            raise ValueError("UNAPPROVED_RESTORE_CONTRACT")
        validate_recipe_menu(snapshot["policy"], frozen_menu_sha256)
        if snapshot.get("frozen_menu_sha256") != list(frozen_menu_sha256) or snapshot.get("categorical_dependency",{}).get("source_sha256") != categorical_dependency_sha256:
            raise ValueError("RESTORE_FROZEN_MENU_OR_DEPENDENCY_IDENTITY")
        if policy_sha256(snapshot["policy"]) != snapshot["batch_policy_sha256"]:
            raise ValueError("RESTORE_POLICY_PENDING_IDENTITY")
        def tuples(x):
            return tuple(tuples(v) for v in x) if isinstance(x, list) else x
        arm = cls(snapshot["policy"], arm_id=snapshot["arm_id"], algorithm=snapshot["algorithm"], gain=snapshot["gain"],
                  seed=0, approved_contract_sha256=approved_contract_sha256,
                  expected_context_counts=snapshot["expected_context_counts"], local_stop_unix=snapshot["local_stop_unix"],
                  frozen_menu_sha256=frozen_menu_sha256,categorical_dependency_sha256=categorical_dependency_sha256)
        arm.rng.setstate(tuples(snapshot["rng"]))
        arm.batch_policy_sha256 = snapshot["batch_policy_sha256"]
        arm.pending = copy.deepcopy(snapshot["pending"])
        arm.seen_attempt_ids = set(snapshot["seen_attempt_ids"])
        arm.finished_batches = copy.deepcopy(snapshot["finished_batches"])
        arm.batch_id = snapshot["batch_id"]
        if any(r["collection_policy_sha256"] != arm.batch_policy_sha256 for r in arm.pending):
            raise ValueError("RESTORE_MIXED_PENDING_POLICY")
        arm._validate_frozen_identity()
        return arm
