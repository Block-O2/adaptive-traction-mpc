"""Future real Beta backend. Source-only delivery; no calls on import.

Only initialize/compute lazily import the actor. prepare uses original artifact
adapters and JSON joins, and never restores an actor. No physics is dispatched.
"""
from pathlib import Path
import copy
import importlib.util
import time
from beta_durable_transaction_candidate_v2 import ARMS, digest, load, sha, verified, within
from beta_transaction_evidence_candidate_v2 import hard_gate, verify_pending_input

CONTROL_SOURCES = ["beta_durable_transaction_candidate_v2.py", "beta_transaction_backend_candidate_v2.py",
                   "beta_transaction_evidence_candidate_v2.py"]
FAMILY = "families/ppo_reward/continuous_scale_v1/"


def _keys(document, keys):
    for key in keys:
        document = document[key]
    return document


class RealBetaBackend:
    mode = "GENUINE_BETA_REAL_BACKEND_REQUIRES_MAIN_APPROVAL"

    def __init__(self, package):
        self.package = Path(package).resolve()
        self.work = {"beta_policy_initialize": 0, "logical_policy_copies": 0,
                     "BetaArm_constructors": 0, "new_physics": 0, "adapter_baseline_calls": 0,
                     "adapter_policy_receipt_calls": 0, "actor_restore_in_prepare": 0}

    def work_accounting(self):
        return copy.deepcopy(self.work)

    def validate_plan(self, plan, *, require_live_window):
        if plan.get("schema") != "v8.beta_durable_run_plan.v1":
            raise ValueError("EXPLICIT_FUTURE_BETA_DURABLE_PLAN_REQUIRED")
        from beta_sampling_common_v1 import verify_launch
        spec = plan["launch_spec"]
        auth, gate, routes = verify_launch(self.package, spec, require_live_window=require_live_window)
        for relative in [FAMILY + name for name in CONTROL_SOURCES]:
            if auth["source_files_sha256"].get(relative) != sha(within(self.package, relative)):
                raise ValueError("MAIN_AUTHORIZATION_MUST_FREEZE_NEW_TRANSACTION_SOURCES")
        verified(self.package, plan["normalization_source"])
        if (plan.get("expected_context_counts") != {k: 2 for k in routes["development_routes"]} or
                plan.get("local_stop_unix") != auth["initialized_window"]["local_stop_unix"]):
            raise ValueError("ORIGINAL_REGISTERED_TWO_CONTEXT_BATCH_AND_CLOCK")
        if plan.get("beta_initial_shapes") != [2.0, 2.0] or plan.get("same_initial_weights_and_sampling_seed") is not True:
            raise ValueError("PREAPPROVED_SYMMETRIC_BETA_INITIALIZATION_REQUIRED")
        init_keys = ["normalization_source", "normalization_keys", "feature_names_keys", "initialization_seed",
                     "sampling_seed", "optimizer", "expected_context_counts", "local_stop_unix",
                     "beta_initial_shapes", "same_initial_weights_and_sampling_seed"]
        if auth.get("durable_initialization_parameters_sha256") != digest({key: plan[key] for key in init_keys}):
            raise ValueError("MAIN_APPROVAL_MUST_BIND_INITIALIZATION_SEEDS_NORMALIZATION_AND_OPTIMIZER")
        if set(plan["optimizer"]) != {"learning_rate", "max_gradient_norm", "ppo_clip_range"}:
            raise ValueError("EXACT_REGISTERED_OPTIMIZER_ARGUMENTS")
        paths = [(spec[k], spec[s]) for k, s in (
            ("launch_authorization_path", "launch_authorization_sha256"),
            ("approved_contract_path", "approved_contract_sha256"), ("gate1_review_path", "gate1_review_sha256"),
            ("axis_path", "axis_file_sha256"), ("case_route_manifest", "case_route_manifest_sha256"))]
        paths += list(auth["source_files_sha256"].items())
        paths += [("ACTIVATION.json", auth["activation_sha256"]),
                  (plan["normalization_source"]["path"], plan["normalization_source"]["sha256"])]
        return [{"path": path, "sha256": expected} for path, expected in sorted(set(paths))]

    def _launch(self, plan, *, live):
        from beta_sampling_common_v1 import verify_launch
        return verify_launch(self.package, plan["launch_spec"], require_live_window=live)

    def _adapter(self, plan):
        spec = plan["launch_spec"]
        path = within(self.package, spec["receipt_adapter_path"])
        if sha(path) != spec["receipt_adapter_sha256"]:
            raise ValueError("FROZEN_BETA_ADAPTER_CHANGED")
        module_spec = importlib.util.spec_from_file_location("_beta_transaction_reviewed_adapter", path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        if module.ADAPTER_SCHEMA != "v8.reviewed_continuous_beta_receipt_adapter.v1":
            raise ValueError("EXPLICIT_BETA_ADAPTER_SCHEMA")
        return module

    def prepare(self, plan, inputs, current, operation):
        cancelling = operation == "cancel"
        review = verified(self.package, inputs["root_closure_review"])
        pending = verified(self.package, inputs["final_pending_bundle"])
        hard_gate(review, pending["snapshots"], cancelling=cancelling)
        # Source and approval closure is checked before importing an adapter;
        # the live-clock decision follows the original hard-safety review.
        self.validate_plan(plan, require_live_window=False)
        adapter = self._adapter(plan)

        def baseline(config, context, row):
            self.work["adapter_baseline_calls"] += 1
            return adapter.build_baseline_receipt(package=self.package, config=config, context25=context,
                logical_context_id=config["onpolicy_sampling"]["development_context_id"], row=copy.deepcopy(row))

        def receipt(config, context, proposal, row):
            self.work["adapter_policy_receipt_calls"] += 1
            return adapter.build_onpolicy_receipt(package=self.package, config=config, context25=context,
                logical_context_id=config["onpolicy_sampling"]["development_context_id"],
                proposal=copy.deepcopy(proposal), row=copy.deepcopy(row))

        proof = verify_pending_input(self.package, inputs, current, cancelling=cancelling,
                                      rebuild_receipt=receipt, rebuild_baseline=baseline)
        auth, gate, routes = self._launch(plan, live=not cancelling)
        if not cancelling and auth.get("approved_for_real_updates") is not True:
            raise ValueError("SEPARATE_MAIN_APPROVAL_FOR_ACTUAL_BETA_UPDATES_REQUIRED")
        return proof

    def _dependencies(self, plan):
        auth, gate, routes = self._launch(plan, live=False)
        return {name: auth["source_files_sha256"][FAMILY + name] for name in
                ("axis_mapping.py", "beta_policy.py", "beta_optimizer_candidate_v2.py")}

    def initialize(self, plan):
        self.validate_plan(plan, require_live_window=True)
        auth, gate, routes = self._launch(plan, live=True)
        if auth.get("approved_for_real_initialization") is not True:
            raise ValueError("EXPLICIT_MAIN_APPROVAL_FOR_REAL_BETA_INITIALIZATION_REQUIRED")
        # These are the first actor imports/calls, after the durable intent.
        import beta_policy
        from beta_optimizer_candidate_v2 import BetaArm
        spec = plan["launch_spec"]
        norm_source = verified(self.package, plan["normalization_source"])
        norm = _keys(norm_source, plan["normalization_keys"])
        feature_names = _keys(norm_source, plan["feature_names_keys"])
        axis = verified(self.package, {"path": spec["axis_path"], "sha256": spec["axis_file_sha256"]})
        self.work["beta_policy_initialize"] += 1
        base = beta_policy.initialize(feature_names, norm, axis, axis_sha256=spec["axis_object_sha256"],
                                      seed=plan["initialization_seed"], arm_id=ARMS[0], gain=1.0)
        snapshots = {}
        self.work["initialization_partial_snapshots"] = snapshots
        for index, arm_id in enumerate(ARMS):
            self._launch(plan, live=True)
            policy = base if index == 0 else copy.deepcopy(base)
            if index:
                self.work["logical_policy_copies"] += 1
            policy["arm_id"] = arm_id
            policy["gain"] = 20.0 if arm_id.endswith("SCALED") else 1.0
            self.work["BetaArm_constructors"] += 1
            arm = BetaArm(policy, algorithm="PPO" if arm_id.startswith("BETA_PPO") else "REINFORCE",
                seed=plan["sampling_seed"], frozen_axis_sha256=spec["axis_object_sha256"],
                approved_training_contract_sha256=spec["approved_contract_sha256"],
                gate1_pass_receipt_sha256=spec["gate1_review_sha256"], case_split_sha256=spec["case_route_manifest_sha256"],
                dependency_sha256=self._dependencies(plan), expected_context_counts=plan["expected_context_counts"],
                local_stop_unix=plan["local_stop_unix"], **plan["optimizer"])
            snapshots[arm_id] = arm.snapshot()
        if len({digest(s["policy"]["weights"]) for s in snapshots.values()}) != 1:
            raise ValueError("INITIAL_FOUR_ARM_WEIGHT_IDENTITY")
        self.work.pop("initialization_partial_snapshots", None)
        return {"status": "READY_ALL_FOUR_INITIALIZED", "snapshots": snapshots,
                "accounting": self.work_accounting(), "parameter_updates": 0,
                "registered_initialized_window": auth["initialized_window"], "new_clock_created": False}

    def compute(self, plan, prepared, operation):
        inputs = verified(self.package, prepared["input"])
        review = verified(self.package, inputs["root_closure_review"])
        pending = verified(self.package, inputs["final_pending_bundle"])
        hard_gate(review, pending["snapshots"], cancelling=operation == "cancel")
        from beta_group_transaction_candidate_v1 import prepare_group_transaction
        draft = prepare_group_transaction(package=self.package, launch_spec=plan["launch_spec"],
            snapshots_by_arm=pending["snapshots"], root_closure_review=review,
            root_group_transaction_id=review["group_transaction_id"], dependency_sha256=self._dependencies(plan))
        self.work["private_draft_original_accounting_and_failed_work"] = draft
        statuses = {"DRAFT_ALL_FOUR_ENDPOINTS_ALIGNED_READY_FOR_ROOT_ATOMIC_PUBLICATION": "READY_ALL_FOUR_UPDATED",
                    "DRAFT_CANCEL_ALL_ARMS_NO_LEARNING": "READY_ALL_FOUR_CANCELLED"}
        status = statuses.get(draft["status"], "FAILED_PRIVATE_DRAFT_NO_PUBLICATION")
        return {"status": status, "snapshots": draft.get("draft_snapshots", {}), "original_draft": draft,
                "accounting": {"draft_restored_logical_arms": draft.get("restored_logical_arm_objects", 0),
                    "draft_private_copies": draft.get("copied_logical_arm_objects", 0),
                    "new_parameter_steps": draft.get("new_parameter_steps", 0),
                    "new_training_forward": draft.get("new_training_forward", 0),
                    "new_manual_score_evaluations": draft.get("new_manual_score_evaluations", 0),
                    "all_failed_private_work_preserved_in_original_draft": True}}
