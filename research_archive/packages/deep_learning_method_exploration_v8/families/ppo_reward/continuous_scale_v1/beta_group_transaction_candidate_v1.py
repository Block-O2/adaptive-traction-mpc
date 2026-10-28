"""Source-only four-arm draft transaction; ROOT alone publishes atomically.

No IO mutation, physical dispatch or update runs on import. Future invocation
needs a separate real-update authorization and root's completed closure review.
"""
import copy

from beta_sampling_common_v1 import ARM_IDS,canonical,digest,load_verified,sha,bounded_path,verify_launch


def prepare_group_transaction(*,package,launch_spec,snapshots_by_arm,root_closure_review,
                              root_group_transaction_id,dependency_sha256):
    from beta_optimizer_candidate_v2 import BetaArm
    if root_closure_review.get("true_hard_safety_violation") is True:
        raise ValueError("HARD_SAFETY_STOP_BEFORE_CLOCK_CENSOR_OR_UPDATE")
    cancelling=root_closure_review.get("status")=="ENGINEERING_CENSOR_CANCEL_ALL_ARMS"
    auth,gate,routes=verify_launch(package,launch_spec,require_live_window=not cancelling)
    if (not cancelling and auth.get("approved_for_real_updates") is not True) or not root_group_transaction_id:
        raise ValueError("SEPARATE_MAIN_REAL_UPDATE_APPROVAL_AND_TRANSACTION_ID_REQUIRED")
    if set(snapshots_by_arm)!=set(ARM_IDS):raise ValueError("EXACT_FOUR_BETA_INPUT_STATES_REQUIRED_JSON_KEY_ORDER_IGNORED")
    review=root_closure_review
    if review.get("schema")!="v8.beta_four_arm_root_closure_review.v1" or review.get("group_transaction_id")!=root_group_transaction_id or review.get("all_started_children_joined") is not True or review.get("all_parent_prefixes_unchanged") is not True or review.get("all_started_attempts_hard_safety_reviewed") is not True:
        raise ValueError("ROOT_ORIGINAL_PHYSICAL_CLOSURE_REVIEW_REQUIRED")
    # Root review includes raw/unattached failure evidence. Never let an absent
    # receipt turn a reviewed physical hard violation into engineering censor.
    if review.get("true_hard_safety_violation") is True:
        raise ValueError("HARD_SAFETY_STOP_BEFORE_ANY_GROUP_CENSOR_OR_UPDATE")
    if review.get("true_hard_safety_violation") is not False:
        raise ValueError("UNRESOLVED_GLOBAL_HARD_SAFETY_STATUS")
    if not review.get("original_evidence_files_sha256"):
        raise ValueError("ROOT_REAL_CLOSURE_ARTIFACTS_REQUIRED")
    for relative,expected in review["original_evidence_files_sha256"].items():
        if sha(bounded_path(package,relative))!=expected:raise ValueError("ROOT_CLOSURE_EVIDENCE_CHANGED")
    if review.get("pending_snapshot_object_sha256")!={name:digest(snapshots_by_arm[name]) for name in ARM_IDS}:
        raise ValueError("ROOT_REVIEW_NOT_OF_EXACT_FOUR_CANONICAL_PENDING_STATES")
    restore=dict(frozen_axis_sha256=launch_spec["axis_object_sha256"],
        approved_training_contract_sha256=launch_spec["approved_contract_sha256"],
        gate1_pass_receipt_sha256=launch_spec["gate1_review_sha256"],
        case_split_sha256=launch_spec["case_route_manifest_sha256"],dependency_sha256=dependency_sha256)
    arms={name:BetaArm.restore(canonical(snapshots_by_arm[name]),**restore) for name in ARM_IDS}
    if len({a.batch_id for a in arms.values()})!=1:raise ValueError("FOUR_ARM_GENERATIONS_NOT_ALIGNED")
    for name,arm in arms.items():
        if arm.execution_mode!="GENUINE_ON_POLICY" or arm.policy["arm_id"]!=name:
            raise ValueError("REAL_BETA_ARM_IDENTITY_REQUIRED")
        if arm.local_stop_unix!=auth["initialized_window"]["local_stop_unix"] or set(arm.expected_context_counts)!=set(routes["development_routes"]):
            raise ValueError("GROUP_CLOCK_OR_CASE_ROUTE_MISMATCH")
        for p in arm.pending:
            receipt=p.get("physical_receipt")
            if isinstance(receipt,dict) and receipt.get("true_hard_safety_violation") is True:
                raise ValueError("HARD_SAFETY_STOP_BEFORE_ANY_GROUP_CENSOR_OR_UPDATE")
    original_states={name:digest(snapshots_by_arm[name]) for name in ARM_IDS}
    common={"schema":"v8.beta_four_arm_transaction_draft.v1","group_transaction_id":root_group_transaction_id,
            "source_snapshot_object_sha256":original_states,"root_closure_review_sha256":digest(review),
            "publication_authorized_by_this_function":False,"root_atomic_generation_publication_required":True,
            "new_physics":0,"input_snapshots_mutated":False,"restored_logical_arm_objects":4}
    copies={name:copy.deepcopy(arm) for name,arm in arms.items()}
    if review.get("status")=="ENGINEERING_CENSOR_CANCEL_ALL_ARMS":
        cancellations={name:arm.cancel_pending_batch(root_group_transaction_id=root_group_transaction_id,
            reason=review.get("engineering_censor_reason") or "ROOT_REVIEWED_ENGINEERING_PARTIAL_OR_UNBOUND_RECEIPT") for name,arm in copies.items()}
        return {**common,"status":"DRAFT_CANCEL_ALL_ARMS_NO_LEARNING","draft_snapshots":{name:canonical(a.snapshot()) for name,a in copies.items()},
                "cancellations":cancellations,"parameter_updates":0,"RNG_and_physical_cost_not_rewound":True,
                "copied_logical_arm_objects":4}
    if review.get("status")!="READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS":
        raise ValueError("NO_UPDATE_WITH_UNCLOSED_OR_INCOMPLETE_GROUP")
    # All metadata preflights precede every actor forward / update.
    preflight={name:arm.preflight_batch_metadata() for name,arm in arms.items()}
    if not all(p["admissible"] for p in preflight.values()):
        return {**common,"status":"ROOT_MUST_REVIEW_AND_CANCEL_WHOLE_GROUP_NO_UPDATE",
                "preflight":preflight,"parameter_updates":0,"original_pending_states_preserved":True}
    results={}
    try:
        for name in ARM_IDS:
            results[name]=copies[name].finish_batch(root_group_transaction_id=root_group_transaction_id)
    except BaseException as error:
        # Includes work already paid on earlier copies and the failing arm's
        # private SGD trace. None of those copies is published as a live model.
        return {**common,"status":"FAILED_PRIVATE_GROUP_UPDATE_DO_NOT_PUBLISH_ANY_ARM",
                "error_type":type(error).__name__,"error":str(error),"completed_private_results":results,
                "all_private_snapshots_for_consumed_work_accounting":{name:canonical(a.snapshot()) for name,a in copies.items()},
                "live_generation_parameter_updates":0,"failed_private_work_must_be_counted":True,
                "copied_logical_arm_objects":4}
    if {name:digest(snapshots_by_arm[name]) for name in ARM_IDS}!=original_states:
        raise ValueError("INPUT_SNAPSHOTS_MUTATED_DURING_PRIVATE_TRANSACTION")
    return {**common,"status":"DRAFT_ALL_FOUR_ENDPOINTS_ALIGNED_READY_FOR_ROOT_ATOMIC_PUBLICATION",
            "results":results,"draft_snapshots":{name:canonical(a.snapshot()) for name,a in copies.items()},
            "copied_logical_arm_objects":4,"new_parameter_steps":sum(r["new_parameter_steps"] for r in results.values()),
            "new_training_forward":sum(r["new_training_forward"] for r in results.values()),
            "new_manual_score_evaluations":sum(r["new_manual_score_evaluations"] for r in results.values()),
            "RNG_and_physical_receipts_preserved":True}
