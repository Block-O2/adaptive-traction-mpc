"""Independent continuous-Beta RF/PPO optimizer/checkpoint candidate.

CODE ONLY: no calls occur on import. No categorical indices, action clipping,
physics launcher or implicit approval. Real use requires Gate1 and main approval.
SGD state is weights + step counter; no Adam/momentum is hidden.
"""
from __future__ import annotations
import copy
import hashlib
import math
from pathlib import Path
import random
import time
from datetime import datetime

import axis_mapping as axis_module
import beta_policy as beta
from axis_mapping import digest, finite, map_lambda, validate_axis

GLOBAL_DEADLINE = datetime.fromisoformat("2026-10-27T15:25:40+00:00").timestamp()


def _before_science(local_stop):
    if time.time()>=min(local_stop,GLOBAL_DEADLINE):
        raise ValueError("ORIGINAL_GLOBAL_OR_LOCAL_SCIENTIFIC_DEADLINE")


def _tuple_tree(value):
    return tuple(_tuple_tree(v) for v in value) if isinstance(value,list) else value


class BetaArm:
    def __init__(self, policy, *, algorithm, seed, frozen_axis_sha256,
                 approved_training_contract_sha256, gate1_pass_receipt_sha256,
                 case_split_sha256, dependency_sha256, expected_context_counts,
                 local_stop_unix, learning_rate=.15, max_gradient_norm=1.0,
                 ppo_clip_range=.2):
        if algorithm not in ("REINFORCE","PPO") or policy.get("gain") not in (1.0,20.0):
            raise ValueError("REGISTERED_BETA_ALGORITHM_AND_GAIN_ONLY")
        if str(policy.get("arm_id","")).startswith("SYNTHETIC") or "SYNTHETIC" in str(policy.get("normalization",{}).get("fit_scope","")).upper():
            raise ValueError("GATE0_SYNTHETIC_FIXTURE_IS_NOT_A_REAL_TRAINING_PARENT")
        if not approved_training_contract_sha256 or not gate1_pass_receipt_sha256 or not case_split_sha256:
            raise ValueError("MAIN_TRAINING_APPROVAL_GATE1_AND_SPLIT_REQUIRED")
        if len(expected_context_counts)!=2 or any(not isinstance(k,str) or not k for k in expected_context_counts) or any(not isinstance(v,int) or isinstance(v,bool) or v!=2 for v in expected_context_counts.values()):
            raise ValueError("REGISTERED_TWO_CONTEXT_TWO_DRAW_BATCH_REQUIRED")
        if not finite(local_stop_unix) or local_stop_unix>GLOBAL_DEADLINE:
            raise ValueError("LOCAL_WINDOW_CANNOT_RESET_GLOBAL_CLOCK")
        if not 0<learning_rate<=1 or not 0<max_gradient_norm<=10 or not 0<ppo_clip_range<1:
            raise ValueError("INVALID_OPTIMIZER_BOUND")
        validate_axis(policy["axis_contract"],frozen_axis_sha256)
        if policy["axis_contract_sha256"]!=frozen_axis_sha256 or policy["feature_names"]!=beta.FEATURE_NAMES:
            raise ValueError("ACTUAL_AXIS_OR_FEATURE_SCHEMA_IDENTITY")
        self.policy = copy.deepcopy(policy)
        self.algorithm = algorithm
        self.axis_sha256 = frozen_axis_sha256
        self.training_contract_sha256 = approved_training_contract_sha256
        self.gate1_pass_receipt_sha256 = gate1_pass_receipt_sha256
        self.case_split_sha256 = case_split_sha256
        self.dependencies = dict(dependency_sha256)
        self.expected_context_counts = dict(expected_context_counts)
        self.local_stop_unix = local_stop_unix
        self.optimizer = {"kind":"MANUAL_SGD_NO_MOMENTUM","learning_rate":learning_rate,
                          "max_gradient_norm":max_gradient_norm,"ppo_clip_range":ppo_clip_range,
                          "epochs_per_batch":3 if algorithm=="PPO" else 1,"completed_parameter_steps":0}
        self.rng = random.Random(seed)
        self.pending = []
        self.seen_attempt_ids = set()
        self.finished_batches = []
        self.numerical_no_proposal = []
        self.failed_private_updates = []
        self.batch_id = 0
        self.batch_policy_sha256 = beta.policy_sha256(self.policy)
        self._validate_identity()

    def _validate_identity(self):
        paths = {"beta_policy.py":Path(beta.__file__).resolve(),"axis_mapping.py":Path(axis_module.__file__).resolve(),
                 "beta_optimizer_candidate_v1.py":Path(__file__).resolve()}
        if set(self.dependencies)!=set(paths):
            raise ValueError("COMPLETE_BETA_OPTIMIZER_DEPENDENCY_BINDING_REQUIRED")
        for key,path in paths.items():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=self.dependencies[key]:
                raise ValueError("DEPENDENCY_SOURCE_CHANGED:"+key)
        validate_axis(self.policy["axis_contract"],self.axis_sha256)
        if self.policy["axis_contract_sha256"]!=self.axis_sha256 or self.policy["feature_names"]!=beta.FEATURE_NAMES:
            raise ValueError("AXIS_ACTUAL_CONTENT_OR_CAUSAL_SCHEMA_CHANGED")
        weights = self.policy.get("weights")
        norm = self.policy.get("normalization",{})
        if not isinstance(weights,list) or len(weights)!=2 or any(not isinstance(row,list) or len(row)!=26 or not all(finite(v) for v in row) for row in weights):
            raise ValueError("BETA_TWO_HEAD_WEIGHT_SHAPE_OR_FINITE")
        if len(norm.get("mean",[]))!=25 or len(norm.get("scale",[]))!=25 or not all(finite(v) for v in norm["mean"]) or not all(finite(v) and v>0 for v in norm["scale"]):
            raise ValueError("BETA_FIXED_NORMALIZATION_SHAPE_OR_FINITE")

    def propose(self, *, attempt_id, context_group_evaluation_only, feature_names,
                commissioned25, qa_validated, completed_B_receipt):
        _before_science(self.local_stop_unix)
        self._validate_identity()
        if beta.policy_sha256(self.policy)!=self.batch_policy_sha256:
            raise ValueError("POLICY_CHANGED_WITH_PENDING_ON_POLICY_BATCH")
        if qa_validated is not True or list(feature_names)!=beta.FEATURE_NAMES or len(commissioned25)!=25 or not all(finite(v) for v in commissioned25):
            raise ValueError("CAUSAL_INPUT_OR_QA_INVALID_BEFORE_SAMPLING")
        group = context_group_evaluation_only
        if group not in self.expected_context_counts or sum(p["context_group_evaluation_only"]==group for p in self.pending)>=self.expected_context_counts[group]:
            raise ValueError("UNREGISTERED_OR_OVERFILLED_CONTEXT")
        if attempt_id in self.seen_attempt_ids:
            raise ValueError("DUPLICATE_PHYSICAL_ATTEMPT")
        context_sha = digest({"names":feature_names,"values":commissioned25})
        base = completed_B_receipt
        if base.get("complete") is not True or base.get("original_qualified") is not True or not base.get("result_source_sha256"):
            raise ValueError("B_FULL_ORIGINAL_QUALIFICATION_REQUIRED")
        if base.get("context_group_evaluation_only")!=group or base.get("causal_features_sha256")!=context_sha:
            raise ValueError("B_BASELINE_CONTEXT_BINDING")
        if any(not finite(base.get(k)) or base[k]<0 for k in ("JF_N_s","JM_Nm_s")):
            raise ValueError("B_FULL_COMPONENT_COSTS_REQUIRED")
        before = self.rng.getstate()
        try:
            sample = beta.sample(self.policy,feature_names,commissioned25,qa_validated=qa_validated,
                                 frozen_axis_sha256=self.axis_sha256,rng=self.rng)
        except BaseException as error:
            self.numerical_no_proposal.append({"attempt_id_reserved_but_not_dispatched":attempt_id,"error_type":type(error).__name__,
                "error":str(error),"rng_before":before,"rng_after":self.rng.getstate(),"new_physics":0,
                "policy_sha256":self.batch_policy_sha256,"sample_not_clipped_or_rewritten":True})
            self.seen_attempt_ids.add(attempt_id)
            raise
        proposal = {"schema":"v8.continuous_beta_physical_proposal.v1","attempt_id":attempt_id,
                    "arm_id":self.policy["arm_id"],"batch_id":self.batch_id,"algorithm":self.algorithm,"gain":self.policy["gain"],
                    "context_group_evaluation_only":group,"feature_names":list(feature_names),"commissioned25":list(commissioned25),
                    "qa_validated":qa_validated,"causal_features_sha256":context_sha,"sample":sample,
                    "baseline_evaluation_only":copy.deepcopy(base),"physical_receipt":None,
                    "data_semantics":"GENUINE_NEW_ON_POLICY_CONTINUOUS_SCALAR_ROLLOUT",
                    "approved_training_contract_sha256":self.training_contract_sha256}
        proposal["proposal_identity_sha256"] = digest(proposal)
        self.pending.append(proposal)
        self.seen_attempt_ids.add(attempt_id)
        return copy.deepcopy(proposal)

    def accept_physical_receipt(self, receipt):
        self._validate_identity()
        matches = [p for p in self.pending if p["attempt_id"]==receipt.get("attempt_id")]
        if len(matches)!=1 or matches[0]["physical_receipt"] is not None:
            raise ValueError("UNMATCHED_OR_DUPLICATE_CONTINUOUS_RECEIPT")
        p = matches[0]
        sample = p["sample"]
        for field,expected in {"arm_id":self.policy["arm_id"],"proposal_identity_sha256":p["proposal_identity_sha256"],
             "context_group_evaluation_only":p["context_group_evaluation_only"],"causal_features_sha256":p["causal_features_sha256"],
             "axis_contract_sha256":self.axis_sha256,"selected_lambda":sample["lambda_sample"],
             "selected_physical_action_sha256":sample["physical_action_sha256"],"selected_full_recipe_sha256":sample["full_recipe_sha256"]}.items():
            if receipt.get(field)!=expected:
                raise ValueError("CONTINUOUS_RECEIPT_BINDING:"+field)
        saved = copy.deepcopy(receipt)
        missing = [name for name in ("attempt_start_sha256","attempt_end_sha256","result_source_sha256",
                    "native_ownership_sha256","applied_reference_receipt_stream_sha256") if not saved.get(name)]
        if saved.get("genuine_new_physical_attempt") is not True or saved.get("historical_or_cached_outcome") is not False:
            missing.append("NOT_GENUINE_NEW_PHYSICAL_ATTEMPT")
        if not isinstance(saved.get("actual_new_native_steps"),int) or saved["actual_new_native_steps"]<=0:
            missing.append("NO_NEW_NATIVE_STEPS")
        saved["driver_receipt_errors"] = missing
        p["physical_receipt"] = saved
        if saved.get("true_hard_safety_violation") is True:
            raise ValueError("HARD_SAFETY_STOP_BEFORE_ANY_ENGINEERING_CENSOR")

    def preflight_batch_metadata(self):
        """Root inspects every arm before copied-object transactional updates."""
        self._validate_identity()
        for p in self.pending:
            r = p.get("physical_receipt")
            if isinstance(r,dict) and r.get("true_hard_safety_violation") is True:
                raise ValueError("HARD_SAFETY_STOP_BEFORE_ANY_ENGINEERING_CENSOR")
        counts = {g:sum(p["context_group_evaluation_only"]==g for p in self.pending) for g in self.expected_context_counts}
        if counts!=self.expected_context_counts or len(self.pending)!=sum(counts.values()):
            raise ValueError("INCOMPLETE_BALANCED_CONTINUOUS_BATCH")
        censored = []
        for p in self.pending:
            original = copy.deepcopy(p)
            expected_identity = original.pop("proposal_identity_sha256")
            original["physical_receipt"] = None
            if digest(original)!=expected_identity:
                raise ValueError("PROPOSAL_CHANGED_AFTER_SAMPLING")
            s = p["sample"]
            if s["policy_sha256"]!=self.batch_policy_sha256 or beta.policy_sha256(self.policy)!=self.batch_policy_sha256:
                raise ValueError("STALE_OR_MIXED_BETA_BEHAVIOR_POLICY")
            if s["axis_contract_sha256"]!=self.axis_sha256 or s.get("post_sampling_clip") is not False or s.get("deterministic_mean_deployment") is not False:
                raise ValueError("NOT_ACTUAL_STOCHASTIC_BETA_LAMBDA")
            mapped = map_lambda(self.policy["axis_contract"],s["lambda_sample"],expected_axis_sha256=self.axis_sha256)
            if mapped["proposal_action"]!=s["proposal_action"] or mapped["full_recipe_sha256"]!=s["full_recipe_sha256"]:
                raise ValueError("ACTUAL_LAMBDA_TO_PHYSICAL_RECIPE_CHANGED")
            if not finite(s["old_logprob"]) or not 0.0<s["lambda_sample"]<1.0:
                raise ValueError("INVALID_OLD_SCALAR_BETA_LOGDENSITY")
            r = p.get("physical_receipt")
            if not isinstance(r,dict) or r.get("driver_receipt_errors") or r.get("engineering_complete") is not True or r.get("ownership_and_causality_audit_pass") is not True or r.get("true_hard_safety_violation") is not False:
                censored.append(p["attempt_id"])
                continue
            if not isinstance(r.get("complete"),bool) or not isinstance(r.get("original_qualified"),bool) or (r["complete"] is not True and r.get("protected_task_failure") is not True):
                censored.append(p["attempt_id"])
                continue
            if r["complete"] and r["original_qualified"] and any(not finite(r.get(k)) or r[k]<0 for k in ("JF_N_s","JM_Nm_s")):
                censored.append(p["attempt_id"])
        return {"admissible":not censored,"engineering_censored_attempts":censored,
                "model_forward":0,"parameter_updates":0,"lambda_mapping_validations":len(self.pending),
                "hard_safety_priority":True,"action_index_used":False}

    def finish_batch(self, *, root_group_transaction_id):
        """Only run on root's copies after ALL arms' metadata preflight passes.

        This method internally uses a private policy and commits only after all
        requested epochs finish. Failed private SGD/model calls are preserved.
        Root still commits all four arm snapshots in one generation or none.
        """
        _before_science(self.local_stop_unix)
        if not root_group_transaction_id:
            raise ValueError("EXPLICIT_ROOT_TRANSACTION_ID_REQUIRED")
        inspection = self.preflight_batch_metadata()
        if not inspection["admissible"]:
            raise ValueError("ROOT_MUST_CANCEL_ALL_ARMS_FOR_ENGINEERING_CENSOR")
        working = copy.deepcopy(self.policy)
        before_counters = dict(working["counters"])
        before_weights = copy.deepcopy(working["weights"])
        trace = []
        feedback = [beta.single_force_feedback(p["physical_receipt"],p["baseline_evaluation_only"],gain=working["gain"]) for p in self.pending]
        rewards = [f["reward"] for f in feedback]
        baseline = sum(rewards)/len(rewards)
        advantages = [r-baseline for r in rewards]
        try:
            # Explicit density validation against the frozen pre-update actor.
            for p in self.pending:
                _,_,a,b = beta._forward(working,p["feature_names"],p["commissioned25"],qa_validated=p["qa_validated"],frozen_axis_sha256=self.axis_sha256)
                s = p["sample"]
                lp = beta.log_density(s["lambda_sample"],a,b)
                if abs(lp-s["old_logprob"])>1e-10 or abs(a-s["alpha"])>1e-12 or abs(b-s["beta"])>1e-12:
                    raise ValueError("OLD_SCALAR_LOGDENSITY_OR_SHAPES_NOT_COLLECTION_POLICY")
            for epoch in range(self.optimizer["epochs_per_batch"]):
                _before_science(self.local_stop_unix)
                gradient = [[0.0]*26 for _ in range(2)]
                rows = []
                objective = 0.0
                for p,advantage in zip(self.pending,advantages):
                    s = p["sample"]
                    score = beta.score_for_weights(working,p["feature_names"],p["commissioned25"],s["lambda_sample"],
                               qa_validated=p["qa_validated"],frozen_axis_sha256=self.axis_sha256)
                    coeff = beta.surrogate_coefficient(algorithm=self.algorithm,new_logprob=score["logprob"],old_logprob=s["old_logprob"],
                               advantage=advantage,clip_range=self.optimizer["ppo_clip_range"])
                    objective += coeff["objective"]/len(self.pending)
                    for head in range(2):
                        for j in range(26):
                            gradient[head][j] += coeff["score_coefficient"]*score["score_gradient"][head][j]/len(self.pending)
                    ratio = math.exp(score["logprob"]-s["old_logprob"])
                    rows.append({"attempt_id":p["attempt_id"],"lambda_unchanged":s["lambda_sample"],"old_logprob":s["old_logprob"],
                       "new_logprob":score["logprob"],"ratio":ratio,"advantage":advantage,"score_coefficient":coeff["score_coefficient"],
                       "outside_ratio_clip_range":abs(ratio-1.0)>self.optimizer["ppo_clip_range"],
                       "objective_clip_inactive":self.algorithm=="PPO" and ((advantage>=0 and ratio>1+self.optimizer["ppo_clip_range"]) or (advantage<0 and ratio<1-self.optimizer["ppo_clip_range"]))})
                norm = math.sqrt(sum(v*v for row in gradient for v in row))
                if not math.isfinite(norm) or not all(finite(v) for row in gradient for v in row):
                    raise ValueError("NONFINITE_BETA_SCORE_GRADIENT")
                scale = min(1.0,self.optimizer["max_gradient_norm"]/max(norm,1e-300))
                old_weights = copy.deepcopy(working["weights"])
                for head in range(2):
                    for j in range(26):
                        working["weights"][head][j] += self.optimizer["learning_rate"]*scale*gradient[head][j]
                if not all(finite(v) for row in working["weights"] for v in row):
                    raise ValueError("NONFINITE_PRIVATE_BETA_PARAMETER_STEP")
                working["counters"]["parameter_updates"] += 1
                delta = math.sqrt(sum((a-b)**2 for r,s in zip(working["weights"],old_weights) for a,b in zip(r,s)))
                trace.append({"epoch":epoch,"objective_before_update":objective,"raw_gradient_norm":norm,"gradient_clip_scale":scale,
                              "raw_gradient":gradient,"applied_gradient":[[scale*v for v in row] for row in gradient],
                              "weights_before_sha256":digest(old_weights),"weights_after_sha256":digest(working["weights"]),
                              "parameter_delta_norm":delta,"rows":rows,"action_sample_rewritten":False,"adam_steps":0})
            _before_science(self.local_stop_unix)
            working["version"] += 1
        except BaseException as error:
            self.failed_private_updates.append({"group_transaction_id":root_group_transaction_id,"error_type":type(error).__name__,"error":str(error),
                "private_trace":trace,"private_policy_after_failure":working,"live_policy_weights_committed":False,
                "consumed_training_forward":working["counters"]["forward"]-before_counters["forward"],
                "consumed_private_parameter_steps":working["counters"]["parameter_updates"]-before_counters["parameter_updates"],
                "pending_and_physical_costs_preserved":True})
            raise
        result = {"schema":"v8.continuous_beta_update.v1","batch_id":self.batch_id,"root_group_transaction_id":root_group_transaction_id,
            "algorithm":self.algorithm,"gain":working["gain"],"source_policy_sha256":self.batch_policy_sha256,"result_policy_sha256":beta.policy_sha256(working),
            "rewards":rewards,"feedback_components":feedback,"advantage_baseline":baseline,"advantages":advantages,"epochs":trace,
            "reward_range":[min(rewards),max(rewards)],"all_rewards_equal_in_this_batch":min(rewards)==max(rewards),
            "advantage_L2_norm":math.sqrt(sum(v*v for v in advantages)),"weights_changed":working["weights"]!=before_weights,
            "old_scalar_density_validations":len(self.pending),
            "new_training_forward":working["counters"]["forward"]-before_counters["forward"],
            "new_manual_score_evaluations":working["counters"]["score_evaluations"]-before_counters["score_evaluations"],
            "new_parameter_steps":working["counters"]["parameter_updates"]-before_counters["parameter_updates"],"adam_steps":0,
            "total_parameter_delta_norm":math.sqrt(sum((a-b)**2 for r,s in zip(working["weights"],before_weights) for a,b in zip(r,s))),
            "action_index_used":False,"logdensity_measure":"scalar d_lambda","full_physical_receipts":copy.deepcopy(self.pending),
            "root_group_commit_still_required":True}
        self.policy = working
        self.optimizer["completed_parameter_steps"] += self.optimizer["epochs_per_batch"]
        self.finished_batches.append(result)
        self.pending = []
        self.batch_id += 1
        self.batch_policy_sha256 = beta.policy_sha256(self.policy)
        return copy.deepcopy(result)

    def cancel_pending_batch(self, *, root_group_transaction_id, reason):
        self._validate_identity()
        if any(isinstance(p.get("physical_receipt"),dict) and p["physical_receipt"].get("true_hard_safety_violation") is True for p in self.pending):
            raise ValueError("HARD_SAFETY_STOP_CANNOT_BECOME_CENSOR")
        if not root_group_transaction_id or not reason:
            raise ValueError("EXPLICIT_GROUP_CANCELLATION_REQUIRED")
        result = {"status":"CANCELLED_GROUP_NO_BETA_UPDATE","batch_id":self.batch_id,"root_group_transaction_id":root_group_transaction_id,
                  "reason":reason,"parameter_updates":0,"RNG_not_rewound":True,"physical_proposals_and_costs":copy.deepcopy(self.pending)}
        self.finished_batches.append(result)
        self.pending = []
        self.batch_id += 1
        return copy.deepcopy(result)

    def snapshot(self):
        self._validate_identity()
        return {"schema":"v8.continuous_beta_arm_checkpoint.v1","policy":copy.deepcopy(self.policy),"algorithm":self.algorithm,
                "policy_behavior_sha256":beta.policy_sha256(self.policy),"batch_policy_sha256":self.batch_policy_sha256,
                "frozen_axis_sha256":self.axis_sha256,"training_contract_sha256":self.training_contract_sha256,
                "gate1_pass_receipt_sha256":self.gate1_pass_receipt_sha256,"case_split_sha256":self.case_split_sha256,
                "dependency_sha256":dict(self.dependencies),"expected_context_counts":dict(self.expected_context_counts),
                "local_stop_unix":self.local_stop_unix,"original_global_deadline_unix":GLOBAL_DEADLINE,"optimizer":copy.deepcopy(self.optimizer),
                "rng":self.rng.getstate(),"pending":copy.deepcopy(self.pending),"seen_attempt_ids":sorted(self.seen_attempt_ids),
                "finished_batches":copy.deepcopy(self.finished_batches),"numerical_no_proposal":copy.deepcopy(self.numerical_no_proposal),
                "failed_private_updates":copy.deepcopy(self.failed_private_updates),"batch_id":self.batch_id,
                "automatic_env_or_physics_dispatch":False}

    @classmethod
    def restore(cls, snapshot, *, frozen_axis_sha256, approved_training_contract_sha256,
                gate1_pass_receipt_sha256, case_split_sha256, dependency_sha256):
        bindings = {"frozen_axis_sha256":frozen_axis_sha256,"training_contract_sha256":approved_training_contract_sha256,
                    "gate1_pass_receipt_sha256":gate1_pass_receipt_sha256,"case_split_sha256":case_split_sha256,
                    "dependency_sha256":dependency_sha256,"original_global_deadline_unix":GLOBAL_DEADLINE}
        if snapshot.get("schema")!="v8.continuous_beta_arm_checkpoint.v1" or any(snapshot.get(k)!=v for k,v in bindings.items()):
            raise ValueError("FROZEN_BETA_RESTORE_CONTRACT_OR_DEPENDENCY")
        if beta.policy_sha256(snapshot["policy"])!=snapshot["policy_behavior_sha256"] or snapshot["policy_behavior_sha256"]!=snapshot["batch_policy_sha256"]:
            raise ValueError("RESTORE_CURRENT_POLICY_DENSITY_IDENTITY")
        opt = snapshot["optimizer"]
        arm = cls(snapshot["policy"],algorithm=snapshot["algorithm"],seed=0,frozen_axis_sha256=frozen_axis_sha256,
                  approved_training_contract_sha256=approved_training_contract_sha256,gate1_pass_receipt_sha256=gate1_pass_receipt_sha256,
                  case_split_sha256=case_split_sha256,dependency_sha256=dependency_sha256,expected_context_counts=snapshot["expected_context_counts"],
                  local_stop_unix=snapshot["local_stop_unix"],learning_rate=opt["learning_rate"],max_gradient_norm=opt["max_gradient_norm"],ppo_clip_range=opt["ppo_clip_range"])
        if opt["kind"]!="MANUAL_SGD_NO_MOMENTUM" or opt["epochs_per_batch"]!=(3 if arm.algorithm=="PPO" else 1):
            raise ValueError("RESTORE_OPTIMIZER_SEMANTICS")
        arm.optimizer = copy.deepcopy(opt)
        arm.rng.setstate(_tuple_tree(snapshot["rng"]))
        for key in ("pending","finished_batches","numerical_no_proposal","failed_private_updates"):
            setattr(arm,key,copy.deepcopy(snapshot[key]))
        arm.seen_attempt_ids = set(snapshot["seen_attempt_ids"])
        arm.batch_id = snapshot["batch_id"]
        if any(p["sample"]["policy_sha256"]!=arm.batch_policy_sha256 for p in arm.pending):
            raise ValueError("RESTORE_PENDING_BETA_SOURCE_POLICY")
        return arm
