"""Metadata-only root review after separate independent original raw replay.

Only complete balanced batches. Motion failures remain valid -1 samples.
Partial/cancel review needs a separate explicitly scoped review, never this one.
"""
from pathlib import Path
import argparse
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
ARMS = ["BETA_RF_RAW", "BETA_PPO_RAW", "BETA_RF_SCALED", "BETA_PPO_SCALED"]
HARD = ["force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed",
        "session_clearance", "true_clearance", "measured_sleeve_clearance", "no_shank_table_contact",
        "no_human_rom_violation"]


def sha(relative):
    h = hashlib.sha256()
    with (P / relative).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 2**20), b""):
            h.update(block)
    return h.hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def dead(pid, ticks):
    path = Path("/proc") / str(pid) / "stat"
    if path.exists():
        values = path.read_text().rsplit(")", 1)[1].split()
        assert int(values[19]) != ticks, "ORIGINAL_OWNED_PROCESS_NOT_EXITED_INCLUDING_ZOMBIE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", nargs=2, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    assert len(set(args.groups)) == 2
    assert args.run == "families/ppo_reward/continuous_scale_v1/real_runs/GENUINE_BETA_V1"
    target = (P / args.output).resolve()
    assert target.is_relative_to(P) and not target.exists()
    rows = [json.loads(line) for line in (P / "runtime/ATTEMPTS.jsonl").read_text().splitlines() if line]
    all_sources, safety, jobs = {}, {}, []
    final_pending = None
    for group in args.groups:
        config_rel = "experiments/" + group + ".json"
        config = load(config_rel)
        assert config["onpolicy_sampling"]["schema"] == "v8.continuous_beta_sampling_job.v1"
        assert config["onpolicy_sampling"]["output_directory"].startswith(args.run + "/sampling/")
        sup = load("owned/" + group + "_SUPERVISOR.json")
        end = load("owned/" + group + "_SUPERVISOR_END.json")
        exit_row = load("owned/" + group + "_EXIT.json")
        done = load("jobs/" + group + "/WORKER_DONE.json")
        assert end["state"] == "STOP" and end["worker_exit_code"] == 0 and end["survivors"] == []
        assert exit_row["active_child"] is None and exit_row["pid"] == sup["worker"]["pid"]
        assert done["status"] == "PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS" and done["all_children_joined"] is True
        for original in [sup["identity"], sup["worker"], *end["known_owned"].values()]:
            dead(original["pid"], original["start_ticks"])
        manifest_rel = "jobs/" + group + "/SOURCE_MANIFEST.json"
        manifest = load(manifest_rel)
        assert manifest["config_sha256"] == sha(config_rel)
        for relative, expected in manifest["files"].items():
            assert sha(relative) == expected, relative
        parent_gate_rel = "audit/" + group + "_PARENT_RAW_GATE.json"
        assert load(parent_gate_rel)["status"] == "PASS"
        starts = [row for row in rows if row.get("event") == "START" and row.get("group") == group]
        assert len(starts) == 10 and len({row["id"] for row in starts}) == 10
        assert {row["id"] for row in starts} == {row["id"] for row in rows if row.get("event") == "END" and row["id"].startswith(group + "_")}
        for start in starts:
            ident = start["id"]
            finishes = [row for row in rows if row.get("id") == ident and row.get("event") == "END"]
            assert len(finishes) == 1
            finish = finishes[0]
            assert finish["joined"] is True and finish["returncode"] == 0 and finish.get("parent_hash_equal") is not False
            assert start["config_sha256"] == sha(config_rel) and start["job_source_sha256"] == sha(manifest_rel)
            dead(start["pid"], start["start_ticks"])
            raw_rel = "runtime/output/" + ident + "_DATA.json"
            data = load(raw_rel)
            assert data["metric"]["task_valid"] is True
            original = data["metric"]["physical_audit"]["unchanged_evaluator"]
            conditions = {key: original["physical_task_result"]["scorer_v2_common_conditions"].get(key) for key in HARD}
            assert all(value is True for value in conditions.values()), "ORIGINAL_HARD_FALSE_OR_UNKNOWN:" + ident
            replay_rel = "audit/scorer_replay/" + ident + ".json"
            replay = load(replay_rel)
            assert replay["status"] == "SCORER_REPLAY_PASS" and replay["original_result_exact_reproduced"] is True
            assert replay["case_identity_chain"]["status"] == "PASS" and replay["motion_replay"] is not None
            evidence = {raw_rel: sha(raw_rel), replay_rel: sha(replay_rel)}
            for relative, expected in replay["input_sha256"].items():
                assert sha(relative) == expected
                evidence[relative] = expected
            row_rel = "attempts/" + ident + "_RESULT.json"
            if (P / row_rel).exists():
                row = load(row_rel)
                assert row["complete"] is True and row["qualified"] == replay["qualified_replay"]
                evidence[row_rel] = sha(row_rel)
            safety[ident] = {"true_hard_safety_violation": False, "hard_safety_conditions": conditions,
                "original_evidence_files_sha256": evidence,
                "START_record_sha256": digest(start), "END_record_sha256": digest(finish),
                "complete": True, "original_motion_qualified": replay["qualified_replay"]}
            all_sources.update(evidence)
        output = config["onpolicy_sampling"]["output_directory"]
        pending_rel = output + "/PENDING_CHECKPOINTS.json"
        pending = load(pending_rel)
        assert pending["stage"] == "ALL_EIGHT_FRESH_CHILD_RECEIPTS_COLLECTED_NO_UPDATE"
        assert pending["parameter_updates_in_this_job"] == 0 and set(pending["snapshots"]) == set(ARMS)
        for arm in ARMS:
            direct_rel = output + "/" + arm + "_PENDING.json"
            assert digest(load(direct_rel)) == digest(pending["snapshots"][arm])
            all_sources[direct_rel] = sha(direct_rel)
        for relative in [config_rel, manifest_rel, parent_gate_rel, pending_rel,
                         "owned/" + group + "_SUPERVISOR.json", "owned/" + group + "_SUPERVISOR_END.json",
                         "owned/" + group + "_EXIT.json", "jobs/" + group + "/WORKER_DONE.json"]:
            all_sources[relative] = sha(relative)
        jobs.append({"group": group, "config_sha256": sha(config_rel), "actual_started_closed": 10})
        final_pending = pending
    value = {"schema": "v8.beta_four_arm_root_closure_review.v1",
        "status": "READY_FULL_TWO_CASE_RECEIPTS_FOR_ALL_FOUR_ARMS", "created_unix": time.time(),
        "true_hard_safety_violation": False, "all_started_children_joined": True,
        "all_parent_prefixes_unchanged": True, "all_started_attempts_hard_safety_reviewed": True,
        "pending_snapshot_object_sha256": {arm: digest(final_pending["snapshots"][arm]) for arm in ARMS},
        "started_attempt_safety": safety, "original_evidence_files_sha256": all_sources,
        "jobs": jobs, "source_sha256": sha(str(Path(__file__).relative_to(P))),
        "motion_failures_retained_as_registered_negative_rewards": True,
        "new_actor_adapter_fit_physics_calls": 0}
    with target.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": value["status"], "path": args.output, "sha256": sha(args.output),
                      "original_started_closed": len(safety), "actor_adapter_fit_physics_calls": 0}))


if __name__ == "__main__":
    main()
