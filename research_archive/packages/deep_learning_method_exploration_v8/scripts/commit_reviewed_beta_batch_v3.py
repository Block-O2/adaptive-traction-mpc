"""Root one-shot bind/prepare/commit; no retry or implicit recovery.

Requires the complete-batch review and the unchanged original Beta window.
Each CLI output is durable before the next dependent operation starts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

P = Path(__file__).resolve().parents[1]
F = "families/ppo_reward/continuous_scale_v1/"
RUN = F + "real_runs/GENUINE_BETA_V1"


def sha(relative):
    return hashlib.sha256((P / relative).read_bytes()).hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def new(relative, value):
    with (P / relative).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", nargs=2, required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--review-sha", required=True)
    parser.add_argument("--batch-index", type=int, required=True)
    parser.add_argument("--previous-generation", type=int, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    assert sha(args.review) == args.review_sha
    review = load(args.review)
    assert review["status"] == "READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS"
    assert review["true_hard_safety_violation"] is False
    assert [row["group"] for row in review["jobs"]] == args.groups
    request = load("freeze/BETA_ROOT_ACTIVATION_REQUEST_REAL_V1.json")
    stop = request["initialized_window"]["local_stop_unix"]
    assert stop == 1793095035.1283 and time.time() < stop
    current = load(RUN + "/CURRENT.json")
    assert current["generation_index"] == args.previous_generation
    assert sha(F + "beta_root_prepare_candidate_v1.py") == "7a977f0bd1fe2f29cdfdfe624b466169f08ceee9a77a413a4c2a29ae6141f9db"
    assert sha(F + "beta_durable_transaction_candidate_v2.py") == "7ec946a4ea1a26fc7e434ce5e05c912d6039e39baafeaded671e71856e1863be"
    assert hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest() == "e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f"
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    deadline = min(started + 120., time.monotonic() + stop - time.time())
    base = "audit/BETA_BATCH" + str(args.batch_index).zfill(2)
    new(base + "_ROOT_TRANSITION_START_V3.json", {"status": "ONE_SHOT_REVIEWED_BIND_PREPARE_COMMIT",
        "pid": os.getpid(), "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
        "created_unix": time.time(), "unchanged_local_stop_unix": stop,
        "review": {"path": args.review, "sha256": args.review_sha},
        "CURRENT_before_sha256": sha(RUN + "/CURRENT.json"), "automatic_retry_or_recover": False,
        "source_sha256": sha(str(Path(__file__).relative_to(P)))})
    def call(label, arguments):
        remaining = deadline - time.monotonic()
        assert remaining > 0, "ORIGINAL_ROOT_TRANSITION_120S_STOP"
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        tick = time.monotonic()
        try:
            completed = subprocess.run([sys.executable, "-B", *arguments], cwd=P, env=env,
                                       text=True, capture_output=True, timeout=remaining)
        except subprocess.TimeoutExpired as error:
            new(base + "_" + label + "_CLI_V3.json", {"status": "TIMEOUT_PRESERVED_EXPLICIT_INTENT_REVIEW_REQUIRED",
                "stdout": str(error.stdout), "stderr": str(error.stderr),
                "wall_s": time.monotonic() - tick, "no_automatic_retry": True})
            raise
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        new(base + "_" + label + "_CLI_V3.json", {"returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr, "wall_s": time.monotonic() - tick,
            "child_CPU_user_increment_s": after.ru_utime - before.ru_utime,
            "child_CPU_system_increment_s": after.ru_stime - before.ru_stime,
            "peak_child_RSS_KiB_all_steps_so_far_not_per_step": after.ru_maxrss,
            "unchanged_local_stop_unix": stop, "no_automatic_retry": True})
        assert completed.returncode == 0, "CLI_FAILED_PRESERVE_INTENT_NO_REFIT:" + label
        return json.loads(completed.stdout.strip().splitlines()[-1])
    bound = "freeze/BETA_BOUND_PENDING_BATCH" + str(args.batch_index).zfill(2) + "_V3.json"
    bind = call("BIND", [F + "beta_root_prepare_candidate_v1.py", "bind", "--package", str(P),
        "--run", RUN, "--groups", *args.groups, "--review", args.review,
        "--review-sha", args.review_sha, "--destination", bound])
    ref = bind["metadata_output"]
    assert ref["path"] == bound and sha(bound) == ref["sha256"]
    prepared = call("PREPARE", [F + "beta_durable_transaction_candidate_v2.py", "prepare", "--package", str(P),
        "--run", RUN, "--input", ref["path"], "--input-sha256", ref["sha256"]])
    assert sha(prepared["path"]) == prepared["sha256"]
    output = call("COMMIT", [F + "beta_durable_transaction_candidate_v2.py", "commit", "--package", str(P),
        "--run", RUN, "--input", prepared["path"], "--input-sha256", prepared["sha256"]])
    final = load(RUN + "/CURRENT.json")
    assert final["generation_index"] == args.previous_generation + 1 and final["status"] == "READY_ALL_FOUR_UPDATED"
    new(base + "_ROOT_TRANSITION_END_V3.json", {"status": "ALL_FOUR_UPDATED_ONCE",
        "CURRENT_after_sha256": sha(RUN + "/CURRENT.json"), "generation_index": final["generation_index"],
        "created_unix": time.time(), "wall_s": time.monotonic() - started,
        "original_local_stop_unix": stop, "no_auto_recovery_or_refit": True, "durable_return": output})
    print(json.dumps({"status": "ALL_FOUR_UPDATED_ONCE", "generation_index": final["generation_index"],
                      "CURRENT_after_sha256": sha(RUN + "/CURRENT.json"), "wall_s": time.monotonic() - started}))


if __name__ == "__main__":
    main()
