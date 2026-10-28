"""Source-only continuous-Beta sampler for the original live-fork v8 worker.

Each approved case: B then four arms x two fresh child attempts, NO update.
Only the original fork parent may write files. Child GeneratorExit is silent.
"""
from pathlib import Path
import copy
import importlib.util
import os
import sys
import time

from beta_sampling_common_v1 import ARM_IDS,bounded_path,canonical,digest,load,sha,verify_launch


def sequence(study,config):
    owner_pid=os.getpid()
    owner_ticks=int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19])
    from acl2_shared import put as root_put
    def assert_owner():
        if os.getpid()!=owner_pid:raise GeneratorExit("FORK_CHILD_NO_GENERATOR_AUTHORITY")
    def put(relative,payload):
        assert_owner();root_put(relative,canonical(payload))
    package=Path(os.environ["ACL2_PACKAGE"]).resolve()
    family=package/"families/ppo_reward/continuous_scale_v1"
    sys.path.insert(0,str(family));sys.path.insert(0,str(package/"families/critic_value/source"))
    from value_api import to_context25
    import beta_policy as beta
    from beta_optimizer_candidate_v2 import BetaArm
    from axis_mapping import validate_axis
    if study.metrics or config.get("fork_phase")!="OUTBOUND" or config.get("fork_slot")!=0:
        raise ValueError("FRESH_SINGLE_OUT0_PARENT_REQUIRED")
    spec=config["onpolicy_sampling"]
    frozen=config["frozen_artifacts"]
    def required(relative,expected=None):
        if relative not in frozen or (expected is not None and frozen[relative]!=expected):
            raise ValueError("BETA_DEPENDENCY_NOT_IN_WORKER_FREEZE:"+relative)
        return bounded_path(package,relative)
    def verify_frozen():
        for relative,expected in frozen.items():
            if sha(bounded_path(package,relative))!=expected:raise ValueError("BETA_FROZEN_INPUT_CHANGED:"+relative)
    for relative in ("families/ppo_reward/continuous_scale_v1/beta_sampling_sequence_candidate_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_sampling_common_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_onpolicy_receipt_adapter_candidate_v1.py",
        "families/ppo_reward/continuous_scale_v1/beta_optimizer_candidate_v2.py",
        "families/ppo_reward/continuous_scale_v1/beta_policy.py",
        "families/ppo_reward/continuous_scale_v1/axis_mapping.py",
        "families/critic_value/source/value_api.py","source/v8_onpolicy_receipt_adapter_v2.py",
        "runtime/code/stream_runtime_evidence.py","source/v8_worker_v1.py","source/acl2_shared.py"):
        required(relative)
    for pathkey,shakey in (("launch_authorization_path","launch_authorization_sha256"),
         ("approved_contract_path","approved_contract_sha256"),("gate1_review_path","gate1_review_sha256"),
         ("axis_path","axis_file_sha256"),("case_route_manifest","case_route_manifest_sha256"),
         ("receipt_adapter_path","receipt_adapter_sha256")):
        required(spec[pathkey],spec[shakey])
    verify_frozen();auth,gate,routes=verify_launch(package,spec,group=config["group"])
    logical=spec["development_context_id"]
    if logical not in routes["development_routes"] or routes["development_routes"][logical]["case_sha256"]!=config["case_sha256"] or sha(required(config["case_path"],config["case_sha256"]))!=config["case_sha256"]:
        raise ValueError("ORIGINAL_TWO_DEV_ROUTE_CASE_IDENTITY")
    axis=load(required(spec["axis_path"],spec["axis_file_sha256"]));validate_axis(axis,spec["axis_object_sha256"])
    for relative,expected in axis["source_files_sha256"].items():required(relative,expected)
    action_set=load(package/"runtime/ACTION_SET.json")
    for name in ("B","H150"):
        if config[name]!=next(x for x in action_set["arms"] if x["id"]==name):raise ValueError("BETA_ORIGINAL_BASE_CANDIDATE_CHANGED")
    if config["H150"]!=axis["h150_candidate"]:raise ValueError("BETA_H150_AXIS_BASE_CANDIDATE_IDENTITY")
    context=to_context25(study.prefork_causal_context)
    context_sha=digest({"names":context["feature_names"],"values":context["features"]})
    dependencies={name:frozen["families/ppo_reward/continuous_scale_v1/"+name] for name in ("axis_mapping.py","beta_policy.py","beta_optimizer_candidate_v2.py")}
    items=spec["arm_inputs"]
    if [item["arm_id"] for item in items]!=ARM_IDS:raise ValueError("REGISTERED_FOUR_BETA_ARM_ORDER")
    restore_kwargs={"frozen_axis_sha256":spec["axis_object_sha256"],"approved_training_contract_sha256":spec["approved_contract_sha256"],
        "gate1_pass_receipt_sha256":spec["gate1_review_sha256"],"case_split_sha256":spec["case_route_manifest_sha256"],"dependency_sha256":dependencies}
    arms={};source_states={}
    for item in items:
        assert_owner()
        snapshot=load(required(item["snapshot_path"],item["snapshot_sha256"]))
        arm=BetaArm.restore(snapshot,**restore_kwargs)
        expected_algorithm="PPO" if item["arm_id"].startswith("BETA_PPO") else "REINFORCE"
        expected_gain=20.0 if item["arm_id"].endswith("SCALED") else 1.0
        if arm.execution_mode!="GENUINE_ON_POLICY" or arm.math_fixture_contract_sha256 is not None or arm.policy["arm_id"]!=item["arm_id"] or arm.algorithm!=expected_algorithm or arm.policy["gain"]!=expected_gain:
            raise ValueError("BETA_ARM_ALGORITHM_GAIN_OR_MODE_IDENTITY")
        if arm.local_stop_unix!=auth["initialized_window"]["local_stop_unix"] or set(arm.expected_context_counts)!=set(routes["development_routes"]) or any(v!=2 for v in arm.expected_context_counts.values()):
            raise ValueError("BETA_SNAPSHOT_CLOCK_AND_TWO_CASE_BATCH_IDENTITY")
        if digest(arm.policy["axis_contract"])!=spec["axis_object_sha256"] or arm.policy["feature_names"]!=context["feature_names"]:
            raise ValueError("BETA_ACTUAL_AXIS_CAUSAL_SCHEMA")
        if any(p.get("physical_receipt") is None for p in arm.pending):
            raise ValueError("ROOT_MUST_RECONCILE_UNJOINED_PRIOR_BETA_ATTEMPT")
        if any(p["context_group_evaluation_only"]==logical for p in arm.pending):
            raise ValueError("CURRENT_CONTEXT_ALREADY_SAMPLED_NO_AUTOMATIC_RERUN")
        arms[item["arm_id"]]=arm
        source_states[item["arm_id"]]={"input_snapshot_sha256":item["snapshot_sha256"],"policy_sha256":beta.policy_sha256(arm.policy),
            "parameter_updates":arm.policy["counters"]["parameter_updates"],"version":arm.policy["version"],"rng_initial_canonical_sha256":digest(arm.rng.getstate())}
    if len({a.batch_id for a in arms.values()})!=1 or len({digest(a.policy["normalization"]) for a in arms.values()})!=1:
        raise ValueError("FOUR_BETA_ARMS_MUST_SHARE_GENERATION_AND_FIXED_NORMALIZATION")
    if next(iter(arms.values())).batch_id==0 and len({digest(a.policy["weights"]) for a in arms.values()})!=1:
        raise ValueError("FIRST_BETA_BATCH_MUST_SHARE_IDENTICAL_INITIAL_WEIGHTS")
    adapter_path=required(spec["receipt_adapter_path"],spec["receipt_adapter_sha256"])
    loader=importlib.util.spec_from_file_location("_v8_continuous_beta_receipt_adapter_candidate",adapter_path)
    adapter=importlib.util.module_from_spec(loader);loader.loader.exec_module(adapter)
    if adapter.ADAPTER_SCHEMA!="v8.reviewed_continuous_beta_receipt_adapter.v1":raise ValueError("WRONG_BETA_ADAPTER_SCHEMA")
    output_relative=spec["output_directory"];output=bounded_path(package,output_relative)
    if not output.is_relative_to(family) or output.exists():raise ValueError("FRESH_BETA_FAMILY_OUTPUT_REQUIRED")
    assert_owner();output.mkdir(parents=True)
    def save(stage):
        assert_owner()
        snapshots={}
        for arm_id,arm in arms.items():
            if beta.policy_sha256(arm.policy)!=source_states[arm_id]["policy_sha256"] or arm.policy["counters"]["parameter_updates"]!=source_states[arm_id]["parameter_updates"] or arm.policy["version"]!=source_states[arm_id]["version"]:
                raise ValueError("BETA_POLICY_UPDATED_WITHIN_SAMPLING_ONLY_JOB")
            snapshot=canonical(arm.snapshot());snapshots[arm_id]=snapshot
            put(output_relative+"/"+arm_id+"_PENDING.json",snapshot)
        put(output_relative+"/PENDING_CHECKPOINTS.json",{"schema":"v8.continuous_beta_pending_bundle.v1","stage":stage,
            "group_evaluation_only":config["group"],"logical_context_evaluation_only":logical,
            "owner_pid":owner_pid,"owner_start_ticks":owner_ticks,"owner_only_writes":True,
            "source_inputs":source_states,"context25":context,"causal_features_sha256":context_sha,"snapshots":snapshots,
            "parameter_updates_in_this_job":0,"root_transaction_after_two_dev_jobs_required":True,
            "created_unix":time.time(),"root_worker_DONE_and_actual_parent_closure_required_separately":True})
    try:
        save("READY_BEFORE_ORIGINAL_B")
        yield {"tag":"B","action":{"family":"B"},"category":"BETA_FRESH_BASELINE_CONTROL_OUTSIDE_POLICY_SUPPORT",
            "prediction":{"training_sample":False,"role":"ORIGINAL_B_SAFE_ANCHOR_NOT_ON_BETA_CURVE",
                "sampling_parent_pid":owner_pid,"sampling_parent_start_ticks":owner_ticks}}
        assert_owner()
        row=study.last_row
        baseline=adapter.build_baseline_receipt(package=package,config=config,context25=context,logical_context_id=logical,row=copy.deepcopy(row))
        put(output_relative+"/B_BASELINE_RECEIPT.json",baseline)
        for arm_id in ARM_IDS:
            arm=arms[arm_id]
            for sample_index in range(2):
                assert_owner();verify_frozen();verify_launch(package,spec,group=config["group"])
                tag="OP_"+arm_id+"_"+str(sample_index+1).zfill(2);attempt_id=config["group"]+"_"+tag
                proposal=arm.propose(attempt_id=attempt_id,context_group_evaluation_only=logical,
                    feature_names=context["feature_names"],commissioned25=context["features"],qa_validated=True,completed_B_receipt=baseline)
                canonical_proposal=canonical(proposal)
                if digest(canonical_proposal)!=digest(proposal):raise ValueError("RNG_JSON_CANONICAL_ROUNDTRIP_CHANGED_PROPOSAL")
                relative=output_relative+"/"+tag+"_PROPOSAL.json";put(relative,canonical_proposal)
                if digest(load(package/relative))!=digest(proposal):raise ValueError("PERSISTED_CANONICAL_BETA_PROPOSAL_CHANGED")
                save("PROPOSED_BEFORE_PHYSICS:"+tag)
                sample=proposal["sample"]
                yield {"tag":tag,"action":copy.deepcopy(sample["proposal_action"]),"category":"GENUINE_CONTINUOUS_BETA_ONPOLICY_ROLLOUT",
                    "prediction":{"arm_id":arm_id,"proposal_identity_sha256":proposal["proposal_identity_sha256"],
                        "proposal_path":relative,"proposal_file_sha256":sha(package/relative),
                        "collection_policy_sha256":sample["policy_sha256"],"old_scalar_logdensity":sample["old_logprob"],
                        "selected_lambda":sample["lambda_sample"],"axis_contract_sha256":sample["axis_contract_sha256"],
                        "selected_physical_action_sha256":sample["physical_action_sha256"],"full_recipe_sha256":sample["full_recipe_sha256"],
                        "rng_before_canonical_sha256":digest(sample["rng_before"]),"rng_after_canonical_sha256":digest(sample["rng_after"]),
                        "sampling_parent_pid":owner_pid,"sampling_parent_start_ticks":owner_ticks,
                        "scalar_measure":"d_lambda_not_ambient18D","identical_recipes_still_require_separate_START_END":True}}
                assert_owner()
                row=study.last_row
                receipt=adapter.build_onpolicy_receipt(package=package,config=config,context25=context,
                    logical_context_id=logical,proposal=copy.deepcopy(proposal),row=copy.deepcopy(row))
                put(output_relative+"/"+tag+"_PHYSICAL_RECEIPT.json",receipt)
                try:
                    arm.accept_physical_receipt(receipt)
                finally:
                    # Same-owner only, even when hard=True has already attached
                    # its original evidence and accept raises the hard stop.
                    if os.getpid()==owner_pid:save("PHYSICAL_RECEIPT_JOIN_ATTEMPTED:"+tag)
                if receipt.get("true_hard_safety_violation") is True:raise ValueError("BETA_HARD_SAFETY_STOP")
                saved=arm.pending[-1]["physical_receipt"]
                if saved.get("driver_receipt_errors") or receipt.get("engineering_complete") is not True or receipt.get("ownership_and_causality_audit_pass") is not True or receipt.get("true_hard_safety_violation") is not False:
                    raise ValueError("BETA_ENGINEERING_PARTIAL_OR_UNRESOLVED_RECEIPT_STOP_ROOT_CANCELS_ALL_ARMS")
        save("ALL_EIGHT_FRESH_CHILD_RECEIPTS_COLLECTED_NO_UPDATE")
        put(output_relative+"/SAMPLING_DONE.json",{"schema":"v8.continuous_beta_sampling_done.v1","status":"PENDING_ONLY_NO_UPDATE",
            "owner_pid":owner_pid,"owner_start_ticks":owner_ticks,"new_policy_children_requested":8,"new_original_B_controls_requested":1,
            "same_recipe_outcomes_not_shared_or_cached":True,"parameter_updates":0,
            "root_worker_DONE_all_START_END_and_parent_closure_required":True,"created_unix":time.time()})
    except GeneratorExit:
        if os.getpid()!=owner_pid:return
        save("OWNER_GENERATOR_CLOSED_PENDING_PRESERVED_ROOT_RECONCILIATION_REQUIRED")
        return
    except BaseException as error:
        if os.getpid()!=owner_pid:return
        save("OWNER_STOPPED_PENDING_PRESERVED_NO_UPDATE")
        put(output_relative+"/SAMPLING_ERROR.json",{"error_type":type(error).__name__,"error":str(error),
            "owner_pid":owner_pid,"owner_start_ticks":owner_ticks,"parameter_updates":0,"created_unix":time.time(),
            "root_must_reconcile_all_started_attempts_and_check_hard_safety_before_censor":True})
        raise
