"""Approved <=60s synthetic optimizer checks; never loads research outcomes."""
from pathlib import Path
import argparse
import copy
from datetime import datetime
import hashlib
import json
import math
import random
import signal
import sys
import time
import types

sys.dont_write_bytecode = True
import axis_mapping
from axis_mapping import digest
import beta_policy as beta
import beta_optimizer_candidate_v2 as optimizer


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-synthetic-60s", action="store_true")
    args = parser.parse_args()
    if not args.main_agent_approved_synthetic_60s:
        raise ValueError("EXPLICIT_MAIN_SYNTHETIC_APPROVAL_REQUIRED")
    here = Path(__file__).resolve().parent
    package = here.parents[2]
    activation = json.loads((package / "ACTIVATION.json").read_text())
    deadline = datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if deadline != optimizer.GLOBAL_DEADLINE or time.time() >= deadline - 60:
        raise ValueError("ORIGINAL_GLOBAL_DEADLINE")
    manifest = json.loads((here / "OPTIMIZER_SYNTHETIC_SOURCE_MANIFEST_V1.json").read_text())
    for relative, expected in manifest["local_files_sha256"].items():
        assert sha(here / relative) == expected, relative
    for relative, expected in manifest["original_source_files_sha256"].items():
        assert sha(package / relative) == expected, relative
    out = here / "optimizer_synthetic_fixture_v1"
    if out.exists():
        raise ValueError("REFUSE_SYNTHETIC_FIXTURE_OVERWRITE")
    out.mkdir()
    start = time.time()
    cpu_start = time.process_time()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("SYNTHETIC_OPTIMIZER_LOCAL_60S")))
    signal.alarm(60)
    api = {}
    completed = {}
    original_beta = {}
    names = ("initialize", "_forward", "sample", "deploy_mean", "score_for_weights", "log_density",
             "raw_shape_score", "shapes_from_raw", "surrogate_coefficient", "single_force_feedback")
    for name in names:
        original_beta[name] = getattr(beta, name)
        def counted(*args, _name=name, **kwargs):
            api[_name] = api.get(_name, 0) + 1
            result = original_beta[_name](*args, **kwargs)
            completed[_name] = completed.get(_name, 0) + 1
            return result
        setattr(beta, name, counted)
    class_api = {}
    original_methods = {}
    for name in ("__init__", "sample_math_fixture", "propose", "accept_physical_receipt", "preflight_batch_metadata", "finish_batch", "snapshot", "cancel_pending_batch"):
        original_methods[name] = getattr(optimizer.BetaArm, name)
        def counted_method(self, *args, _name=name, **kwargs):
            class_api[_name] = class_api.get(_name, 0) + 1
            return original_methods[_name](self, *args, **kwargs)
        setattr(optimizer.BetaArm, name, counted_method)
    restoration_calls = 0
    assertions = []
    gradients = []
    successful = []
    expected_failures = []
    private_failures = []
    start_doc = {"status": "RUNNING_SYNTHETIC_MATH_ONLY", "start_unix": start, "new_physics": 0,
                 "real_fits": 0, "physical_receipts_created": 0,
                 "source_manifest_sha256": sha(here / "OPTIMIZER_SYNTHETIC_SOURCE_MANIFEST_V1.json")}
    (out / "START.json").write_text(json.dumps(start_doc, indent=2, sort_keys=True))
    def save_failure_state(error):
        (out / "FAILURE.json").write_text(json.dumps({**start_doc, "error_type": type(error).__name__, "error": str(error),
            "api_attempted": api, "api_completed": completed, "arm_api_attempted": class_api,
            "successful_updates": successful, "private_failures": private_failures, "gradient_checks": gradients,
            "expected_failure_checks": expected_failures, "all_partial_work_preserved": True}, indent=2, sort_keys=True))
    try:
        axis = json.loads((here / "gate0_math_v1/AXIS_CONTRACT.json").read_text())
        axis_sha = digest(axis)
        contract_sha = sha(here / "OPTIMIZER_SYNTHETIC_CONTRACT_V1.json")
        deps = {name: sha(here / name) for name in ("beta_policy.py", "axis_mapping.py", "beta_optimizer_candidate_v2.py")}
        norm = {"mean": [0.0] * 25, "scale": [1.0] * 25, "fit_scope": "SYNTHETIC_OPTIMIZER_FIXTURE_NOT_RESEARCH"}
        local_stop = min(start + 55, deadline)
        common = dict(frozen_axis_sha256=axis_sha, approved_training_contract_sha256=None,
                      gate1_pass_receipt_sha256=None, case_split_sha256=None, dependency_sha256=deps,
                      math_fixture_contract_sha256=contract_sha)
        def restore(snapshot):
            nonlocal restoration_calls
            restoration_calls += 1
            return optimizer.BetaArm.restore(copy.deepcopy(snapshot), **common)
        def expect_error(name, fn, substring):
            try:
                fn()
            except Exception as error:
                assert substring in str(error), (name, str(error), substring)
                expected_failures.append({"check": name, "error": str(error), "type": type(error).__name__})
            else:
                raise AssertionError("EXPECTED_ERROR_NOT_RAISED:" + name)

        # Exact full-weight objective differentiation. Each branch uses synthetic
        # old scalar density chosen to exercise a known mathematical ratio.
        policy = beta.initialize(beta.FEATURE_NAMES, norm, axis, axis_sha256=axis_sha, seed=41,
                                 arm_id="SYNTHETIC_GRADIENT_ONLY", gain=1.0)
        features = [(i - 12) / 17 for i in range(25)]
        policy["weights"][0][0] += .2
        policy["weights"][1][0] -= .15
        lam = .27
        density_kwargs = dict(qa_validated=True, frozen_axis_sha256=axis_sha)
        cases = [("REINFORCE", 1.0, .7), ("REINFORCE", 1.0, -.7)]
        cases += [("PPO", ratio, advantage) for ratio in (1.0, 1.5, .5) for advantage in (.7, -.7)]
        for algorithm, target_ratio, advantage in cases:
            score = beta.score_for_weights(policy, beta.FEATURE_NAMES, features, lam, **density_kwargs)
            old_lp = score["logprob"] - math.log(target_ratio)
            coefficient = beta.surrogate_coefficient(algorithm=algorithm, new_logprob=score["logprob"],
                        old_logprob=old_lp, advantage=advantage)
            analytic = [[coefficient["score_coefficient"] * v for v in row] for row in score["score_gradient"]]
            numeric = [[0.0] * 26 for _ in range(2)]
            def objective(candidate):
                _, _, a, b = beta._forward(candidate, beta.FEATURE_NAMES, features, **density_kwargs)
                lp = beta.log_density(lam, a, b)
                return beta.surrogate_coefficient(algorithm=algorithm, new_logprob=lp, old_logprob=old_lp,
                                                 advantage=advantage)["objective"]
            for head in range(2):
                for j in range(26):
                    plus, minus = copy.deepcopy(policy), copy.deepcopy(policy)
                    plus["weights"][head][j] += 1e-6
                    minus["weights"][head][j] -= 1e-6
                    numeric[head][j] = (objective(plus) - objective(minus)) / 2e-6
            error = max(abs(a - b) for ar, br in zip(analytic, numeric) for a, b in zip(ar, br))
            assert error < 2e-6, (algorithm, target_ratio, advantage, error)
            gradients.append({"algorithm": algorithm, "target_ratio": target_ratio, "advantage": advantage,
                              "coefficient": coefficient, "analytic_gradient": analytic, "numeric_gradient": numeric,
                              "max_error": error, "central_difference_components": 52,
                              "perturbed_objective_calls": 104})

        # Four arms start at exactly the same weights and RNG. Rewards below are
        # handwritten synthetic raw/scaled values, not stored outcome receipts.
        arms = {}
        pre = {}
        initial_weight_hashes = []
        reward_values = {1.0: [-.01, .01, -1.0, -.005], 20.0: [-.2, .2, -1.0, -.1]}
        sample_features = [[(i + 1) * .01 * sign for i in range(25)] for sign in (1, -.5, .3, -.8)]
        for name, algorithm, gain in (("RF_RAW", "REINFORCE", 1.0), ("PPO_RAW", "PPO", 1.0),
                                      ("RF_SCALED", "REINFORCE", 20.0), ("PPO_SCALED", "PPO", 20.0)):
            p = beta.initialize(beta.FEATURE_NAMES, norm, axis, axis_sha256=axis_sha, seed=72,
                                arm_id="SYNTHETIC_" + name, gain=gain)
            initial_weight_hashes.append(digest(p["weights"]))
            arm = optimizer.BetaArm(p, algorithm=algorithm, seed=72, expected_context_counts={"SYNTHETIC_A": 2, "SYNTHETIC_B": 2},
                                    local_stop_unix=local_stop, max_gradient_norm=.001, **common)
            for i in range(4):
                arm.sample_math_fixture(fixture_id="SYNTHETIC_" + name + "_" + str(i),
                    context_group="SYNTHETIC_A" if i < 2 else "SYNTHETIC_B",
                    commissioned25=sample_features[i], synthetic_reward=reward_values[gain][i])
            arms[name] = arm
            pre[name] = json.loads(json.dumps(arm.snapshot()))
        assert len(set(initial_weight_hashes)) == 1
        for i in range(4):
            assert len({arm.pending[i]["sample"]["lambda_sample"] for arm in arms.values()}) == 1
        assertions.append("FOUR_ARM_IDENTICAL_INITIAL_WEIGHTS_AND_COLLECTION_RNG")
        for name, arm in arms.items():
            replay = restore(pre[name])
            assert digest(replay.snapshot()) == digest(pre[name])
            left = arm.finish_batch(root_group_transaction_id="SYNTHETIC_ORIGINAL_" + name)
            right = replay.finish_batch(root_group_transaction_id="SYNTHETIC_RESTORED_" + name)
            assert arm.policy == replay.policy and arm.rng.getstate() == replay.rng.getstate()
            assert left["epochs"] == right["epochs"] and left["new_parameter_steps"] == (3 if arm.algorithm == "PPO" else 1)
            assert all(row["gradient_clip_scale"] < 1.0 for row in left["epochs"])
            assert left["action_index_used"] is False and left["logdensity_measure"] == "scalar d_lambda"
            assert arm.pending == [] and arm.policy["counters"]["parameter_updates"] == left["new_parameter_steps"]
            post = json.loads(json.dumps(arm.snapshot()))
            post_replay = restore(post)
            assert digest(post_replay.snapshot()) == digest(post)
            random_a, random_b = random.Random(), random.Random()
            random_a.setstate(arm.rng.getstate()); random_b.setstate(post_replay.rng.getstate())
            assert [random_a.random() for _ in range(8)] == [random_b.random() for _ in range(8)]
            for label, result, snapshot in (("original", left, arm.snapshot()), ("restored", right, replay.snapshot())):
                successful.append({"arm": name, "instance": label, "result": result, "snapshot": snapshot})
        assertions.append("FULL_JSON_ROUNDTRIP_PENDING_POSTUPDATE_RNG_AND_REPLAY_MATCH")

        # Density failure records work but never mutates live weights or pending.
        bad = restore(pre["PPO_RAW"])
        bad.pending[0]["sample"]["old_logprob"] += .05
        changed = copy.deepcopy(bad.pending[0]); changed.pop("proposal_identity_sha256")
        bad.pending[0]["proposal_identity_sha256"] = digest(changed)
        before = copy.deepcopy(bad.policy)
        expect_error("OLD_DENSITY_MISMATCH", lambda: bad.finish_batch(root_group_transaction_id="SYNTHETIC_DENSITY_ERROR"), "OLD_SCALAR_LOGDENSITY")
        assert bad.policy == before and len(bad.pending) == 4 and bad.failed_private_updates[-1]["consumed_private_parameter_steps"] == 0
        private_failures.append(copy.deepcopy(bad.failed_private_updates[-1]))

        # Fail on the first score of epoch2 after exactly one private SGD step.
        bad = restore(pre["PPO_RAW"])
        before = copy.deepcopy(bad.policy)
        counted_score = beta.score_for_weights
        injection_calls = 0
        def injected(*args, **kwargs):
            nonlocal injection_calls
            injection_calls += 1
            if injection_calls == 5:
                raise ArithmeticError("SYNTHETIC_INJECTED_SCORE_FAILURE_SECOND_EPOCH")
            return counted_score(*args, **kwargs)
        beta.score_for_weights = injected
        try:
            expect_error("PRIVATE_SECOND_EPOCH_EXCEPTION", lambda: bad.finish_batch(root_group_transaction_id="SYNTHETIC_PRIVATE_ERROR"), "SYNTHETIC_INJECTED_SCORE_FAILURE")
        finally:
            beta.score_for_weights = counted_score
        assert bad.policy == before and len(bad.pending) == 4
        assert bad.failed_private_updates[-1]["consumed_private_parameter_steps"] == 1
        private_failures.append(copy.deepcopy(bad.failed_private_updates[-1]))
        assertions.append("PRIVATE_ONE_SGD_STEP_RETAINED_WITH_ZERO_LIVE_COMMIT")

        bad = restore(pre["PPO_RAW"])
        before_weights = copy.deepcopy(bad.policy["weights"])
        bad.pending[0]["physical_receipt"] = {"true_hard_safety_violation": True, "synthetic_branch_test_only": True}
        bad.pending.pop()  # Incomplete and changed: hard stop must still win.
        expect_error("HARD_FLAG_BEFORE_CENSOR_OR_COUNT", lambda: bad.finish_batch(root_group_transaction_id="SYNTHETIC_HARD"), "HARD_SAFETY_STOP_BEFORE")
        assert bad.policy["weights"] == before_weights

        bad = restore(pre["PPO_RAW"])
        before = copy.deepcopy(bad.policy)
        bad.local_stop_unix = time.time() - 1
        expect_error("LOCAL_CLOCK_REJECTION", lambda: bad.finish_batch(root_group_transaction_id="SYNTHETIC_LOCAL_CLOCK"), "ORIGINAL_GLOBAL_OR_LOCAL")
        assert bad.policy == before
        bad = restore(pre["PPO_RAW"])
        real_clock = optimizer.time
        optimizer.time = types.SimpleNamespace(time=lambda: optimizer.GLOBAL_DEADLINE + 1)
        try:
            expect_error("GLOBAL_CLOCK_REJECTION", lambda: bad.finish_batch(root_group_transaction_id="SYNTHETIC_GLOBAL_CLOCK"), "ORIGINAL_GLOBAL_OR_LOCAL")
        finally:
            optimizer.time = real_clock
        assert bad.policy["weights"] == pre["PPO_RAW"]["policy"]["weights"]

        bad = restore(pre["PPO_RAW"])
        expect_error("MATH_MODE_FORBIDS_PHYSICAL_RECEIPT", lambda: bad.accept_physical_receipt({}), "MATH_FIXTURE_CANNOT_ACCEPT")
        expect_error("MATH_MODE_FORBIDS_PHYSICAL_PROPOSAL", lambda: bad.propose(attempt_id="SYNTHETIC_X", context_group_evaluation_only="SYNTHETIC_A",
            feature_names=beta.FEATURE_NAMES, commissioned25=[0.0]*25, qa_validated=True, completed_B_receipt={}), "MATH_FIXTURE_CANNOT_PROPOSE")
        altered = copy.deepcopy(pre["PPO_RAW"]); altered["policy"]["weights"][0][0] += .01
        expect_error("RESTORE_POLICY_TAMPER", lambda: restore(altered), "RESTORE_CURRENT_POLICY_DENSITY_IDENTITY")
        wrong_deps = copy.deepcopy(common); wrong_deps["dependency_sha256"] = {**deps, "beta_policy.py": "0" * 64}
        expect_error("RESTORE_DEPENDENCY_TAMPER", lambda: optimizer.BetaArm.restore(pre["PPO_RAW"], **wrong_deps), "FROZEN_BETA_RESTORE_CONTRACT")
        real_mode = {k: v for k, v in common.items() if k != "math_fixture_contract_sha256"}
        expect_error("MATH_CHECKPOINT_CANNOT_RESTORE_REAL_MODE", lambda: optimizer.BetaArm.restore(pre["PPO_RAW"], **real_mode), "FROZEN_BETA_RESTORE_CONTRACT")
        expect_error("EXTREME_RATIO_STOP_NO_REWRITE", lambda: beta.surrogate_coefficient(algorithm="PPO", new_logprob=51.0, old_logprob=0.0, advantage=1.0), "DENSITY_RATIO_EXTREME_STOP")

        for relative, expected in manifest["local_files_sha256"].items():
            assert sha(here / relative) == expected
        for relative, expected in manifest["original_source_files_sha256"].items():
            assert sha(package / relative) == expected
        committed = sum(item["result"]["new_parameter_steps"] for item in successful)
        private_steps = sum(item["consumed_private_parameter_steps"] for item in private_failures)
        end = {**start_doc, "status": "PASS_SYNTHETIC_OPTIMIZER_ONLY_NOT_REAL_FIT", "end_unix": time.time(),
               "wall_s": time.time()-start, "cpu_s": time.process_time()-cpu_start,
               "api_attempted": api, "api_completed": completed, "arm_api_attempted": class_api,
               "restore_wrapper_calls_including_expected_error": restoration_calls,
               "direct_restore_expected_error_calls": 2,
               "finite_difference_components": sum(g["central_difference_components"] for g in gradients),
               "finite_difference_objective_calls": sum(g["perturbed_objective_calls"] for g in gradients),
               "max_gradient_error": max(g["max_error"] for g in gradients), "gradient_checks": gradients,
               "synthetic_committed_SGD_steps_across_original_and_replay": committed,
               "synthetic_private_uncommitted_SGD_steps": private_steps,
               "synthetic_total_executed_SGD_steps": committed+private_steps,
               "synthetic_action_samples": completed.get("sample", 0),
               "auxiliary_RNG_replay_uniform_draws": 64,
               "synthetic_failed_score_injection_attempts": injection_calls,
               "successful_updates": successful, "private_failures": private_failures,
               "expected_failure_checks": expected_failures, "assertions": assertions,
               "real_training_updates": 0, "real_onpolicy_rollouts": 0, "env_initializations": 0,
               "real_research_results_read": 0, "original_sources_and_fixture_sources_unchanged": True}
        (out / "END.json").write_text(json.dumps(end, indent=2, sort_keys=True))
        print(json.dumps({k: end[k] for k in ("status", "wall_s", "cpu_s", "max_gradient_error", "api_attempted", "api_completed", "arm_api_attempted",
            "finite_difference_components", "synthetic_total_executed_SGD_steps", "synthetic_private_uncommitted_SGD_steps", "new_physics", "real_training_updates")}))
    except BaseException as error:
        save_failure_state(error)
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
