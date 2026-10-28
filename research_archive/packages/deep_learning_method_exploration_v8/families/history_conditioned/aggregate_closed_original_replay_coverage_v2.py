#!/usr/bin/env python3
"""SOURCE CANDIDATE V2: aggregate existing closed metadata; no scorer or raw replay."""
import argparse
import collections
import hashlib
import json
import math
import os
import pathlib
import resource
import time
import traceback

CROSSWALK = "families/history_conditioned/audit/ORIGINAL_SCORER_26_MISSING_COMMON_COVERAGE_CROSSWALK_V1.json"
CROSSWALK_SHA = "7c5a276bf7991c3eac0de790a5363d4bfe95d8c57a0e2ce68878e195eb28ff22"
GLOBAL_STOP = 1793114740
BASE = "families/history_conditioned/"
PREFIX_SCOPE = "PARTIAL_PREFIX_NO_FULL_TASK_NO_SCORER_APPLICABLE"
PREFIX_CACHE_SHA = {
    "V8FROZENENG01_parent": "6a0e81204a1758e1f2df304c1c876373ff822630f65e6c4b1763900dc2cfa561",
    "V8OP01H_parent": "e7d5e843cef15510bc31901ef1b5646c367e6b9cbb1c5eff005ce04e6550e76f",
    "V8BETA02L_parent": "1c2cf573314ee5e5ba7a66efa2bd5cd115dec15d806155f00b6aa0868ae1d3da",
}
PREFIX_ARTIFACT_SHA = "66e87b698040d1bf3c0fcd64ee7c296081712fcf000225a9e63a5bb38d5b1bb6"
BETA_QUARANTINE = "freeze/BETA_EXTERNAL_BATCH02_QUARANTINE_V1.json"
BETA_QUARANTINE_SHA = "7e8d1727e97dd655bbd6d4620586d7930f2cb37cebf39958c7d8386c114c01e3"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(row):
    return digest(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())


def pointer(doc, text):
    for item in text.split("/")[1:]:
        item = item.replace("~1", "/").replace("~0", "~")
        doc = doc[int(item)] if isinstance(doc, list) else doc[item]
    return doc


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class Aggregation:
    def __init__(self, args):
        self.args = args
        self.root = pathlib.Path(args.package).resolve()
        self.started = time.monotonic()
        self.cpu_started = time.process_time()
        self.refs, self.cache, self.gaps = {}, {}, []
        self.deadline = self.started + 60
        self.authority = self.unpinned(args.approval, args.approval_sha256)
        a = self.authority
        assert a["schema"] == "v8.final_original_replay_coverage.main_approval.v2"
        assert a["status"] == "ROOT_APPROVED_ONE_CLOSED_METADATA_AGGREGATION_V2"
        assert a["main_all_physical_jobs_closed_verified"] is True
        assert a["original_global_stop_unix"] == GLOBAL_STOP
        assert 0 < a["budget"]["wall_seconds"] <= 60
        assert a["budget"]["CPU_threads"] == 1 and a["budget"]["address_space_bytes"] <= 1073741824
        assert a["new_scorer_raw_model_fit_physics"] == 0
        remaining = min(a["expires_unix"], GLOBAL_STOP) - time.time()
        assert remaining > 0
        self.deadline = min(self.deadline, time.monotonic() + remaining,
                            self.started + a["budget"]["wall_seconds"])
        manifest = self.unpinned(args.source_manifest, a["source_manifest_sha256"])
        self.contract = self.unpinned(args.contract, a["contract_sha256"])
        own_rel = str(pathlib.Path(__file__).resolve().relative_to(self.root))
        assert manifest["source_files_sha256"][own_rel] == digest(pathlib.Path(__file__).read_bytes())
        for rel, sha in manifest["source_files_sha256"].items():
            self.unpinned_bytes(rel, sha)
        assert self.contract["schema"] == "v8.final_original_replay_coverage.contract.v2"
        assert a["physical_snapshot"]["path"] == args.physical_snapshot
        assert a["output"] == args.output
        self.pins = a["inputs_sha256"]
        assert self.pins[args.physical_snapshot] == a["physical_snapshot"]["sha256"]
        assert self.pins[CROSSWALK] == CROSSWALK_SHA
        assert "runtime/ATTEMPTS.jsonl" in self.pins
        self.output = self.path(args.output)
        assert self.output.is_relative_to(self.root / BASE / "audit/coverage_runs")
        assert not self.output.exists()
        resource.setrlimit(resource.RLIMIT_AS, (a["budget"]["address_space_bytes"], a["budget"]["address_space_bytes"]))
        if hasattr(os, "sched_getaffinity"):
            os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})

    def clock(self):
        assert time.monotonic() < self.deadline, "FIXED_DEADLINE_EXHAUSTED_NO_RESET"

    def path(self, rel):
        assert isinstance(rel, str) and not pathlib.Path(rel).is_absolute()
        p = (self.root / rel).resolve()
        assert p.is_relative_to(self.root) and ".." not in pathlib.Path(rel).parts
        return p

    def unpinned_bytes(self, rel, sha):
        self.clock()
        data = self.path(rel).read_bytes()
        assert digest(data) == sha, "SHA_MISMATCH:" + rel
        self.refs[rel] = {"path": rel, "sha256": sha, "bytes": len(data)}
        return data

    def unpinned(self, rel, sha):
        return json.loads(self.unpinned_bytes(rel, sha))

    def metadata(self, rel):
        assert rel in self.pins, "UNPINNED_METADATA:" + rel
        assert pathlib.Path(rel).suffix in (".json", ".jsonl")
        assert not rel.startswith("runtime/") or rel == "runtime/ATTEMPTS.jsonl"
        assert "/models/" not in rel and "/fits/" not in rel
        if rel not in self.cache:
            data = self.unpinned_bytes(rel, self.pins[rel])
            self.cache[rel] = data if rel.endswith(".jsonl") else json.loads(data)
        return self.cache[rel]

    def source_ref(self, rel, ptr=""):
        return {**self.refs[rel], "json_pointer": ptr}

    def gap(self, ident, reason, detail=None):
        self.gaps.append({"id": ident, "reason": reason, "detail": detail})

    def increment(self, row, expected):
        values = [row[k] for k in ("new_native_count", "new_native_steps", "incremental_metric", "actual_new_native_steps") if integer(row.get(k))]
        assert values and all(x == expected for x in values), "NATIVE_INCREMENT_MISSING_OR_CONFLICT"

    def physical_universe(self):
        snap = self.metadata(self.args.physical_snapshot)
        assert snap["schema"] == "v8.actual_physical_increment_snapshot.v1" and snap["status"] == "CLOSED_EXACT"
        assert not snap["open_attempt_ids"] and not snap["unknown_counts_not_imputed_zero"]
        rows = {x["id"]: x for x in snap["rows"]}
        assert len(rows) == len(snap["rows"]) == snap["original_start_count"] == snap["original_end_count"]
        events = {"START": {}, "END": {}}
        for line, raw in enumerate(self.metadata("runtime/ATTEMPTS.jsonl").splitlines(), 1):
            self.clock()
            event = json.loads(raw)
            if event.get("event") in events:
                target = events[event["event"]]
                assert event["id"] not in target, "DUPLICATE_PHYSICAL_EVENT"
                target[event["id"]] = (event, digest(raw), line)
        assert events["START"].keys() == events["END"].keys() == rows.keys(), "SNAPSHOT_NOT_EXACT_CURRENT_ALL_CLOSED_UNIVERSE"
        for ident, row in rows.items():
            start, sh, sl = events["START"][ident]
            end, eh, el = events["END"][ident]
            assert row["START_raw_line_sha256"] == sh and row["END_raw_line_sha256"] == eh
            assert row["joined"] is end["joined"] is True and start["group"] == row["group"]
            assert integer(row["actual_new_native_steps"]) and row["evidence"]
            assert all(x["actual_increment"] == row["actual_new_native_steps"] for x in row["evidence"])
            row["START_line_number"] = sl
            row["END_line_number"] = el
            row["boundary_no_TASK"] = "BOUNDARY" in str(start.get("kind", "")) or "BOUNDARY" in ident
        assert sum(x["actual_new_native_steps"] for x in rows.values()) == snap["actual_new_native_steps_closed"]
        for group, value in snap["groups"].items():
            rel = "owned/" + group + "_SUPERVISOR_END.json"
            end = self.metadata(rel)
            assert self.pins[rel] == value["supervisor"]["evidence_sha256"]
            assert end["state"] == "STOP" and end["survivors"] == [] and end["worker_exit_code"] is not None
        return snap, rows

    def paid_parent_prefix(self, row, rel, doc):
        ident = row["id"]
        assert ident in PREFIX_CACHE_SHA and self.pins[rel] == PREFIX_CACHE_SHA[ident]
        assert set(doc) == {"id", "status", "formal_force_rank_allowed"}
        assert doc["id"] == ident and doc["status"] == "PARTIAL_NOT_RANKED" and doc["formal_force_rank_allowed"] is False
        assert self.authority["approved_partial_parent_prefix_scope"] == PREFIX_SCOPE
        approved = self.authority["approved_partial_parent_prefix_no_TASK_scorer_ids"]
        assert ident in approved and set(approved) <= PREFIX_CACHE_SHA.keys()
        assert row["group"] == ident.removesuffix("_parent") and row["kind"] == "LEGAL_COLD_PARENT"
        assert not row["boundary_no_TASK"] and row["original_returncode"] == 1
        assert row["complete_original_result"] is None and row["original_qualified"] is None
        assert row["actual_new_native_steps"] == 40200
        expected = "runtime/output/" + ident + "_PARTIAL_COMPUTE.json"
        assert any(x["path"] == expected and x.get("sha256") == PREFIX_ARTIFACT_SHA and
                   x["field"] == "actual_new_native_physics_steps" and x["actual_increment"] == 40200 for x in row["evidence"])
        assert not any(x["path"].endswith("_DATA.json") for x in row["evidence"])
        unknown = {"training_hard_safety": "UNKNOWN_NOT_ESTABLISHED_BY_MINIMAL_PREFIX_CACHE"}
        if ident == "V8BETA02L_parent":
            assert self.pins[BETA_QUARANTINE] == BETA_QUARANTINE_SHA
            quarantine = self.metadata(BETA_QUARANTINE)
            assert quarantine["hard_status"] == "UNKNOWN_NOT_FALSE" and quarantine["true_hard_safety_violation"] is None
            names = quarantine["unresolved_prefix_condition_names"]
            assert set(names) == {"human_acceleration", "session_clearance", "measured_sleeve_clearance"}
            unknown.update({"hard_status": quarantine["hard_status"], "true_hard_safety_violation": None,
                            "original_unresolved_prefix_conditions": {k: "UNKNOWN" for k in names},
                            "quarantine": self.source_ref(BETA_QUARANTINE),
                            "original_prefix_review_link_not_opened": quarantine["original_prefix_review"],
                            "metadata_coverage_does_not_resolve_training_safety_or_commit_permission": True})
        return {"source": self.source_ref(rel), "scope": PREFIX_SCOPE,
                "partial_parent_prefix_no_TASK_scorer": True, "complete_task": None, "original_qualified": None,
                "original_evaluator_overall": "NOT_APPLICABLE_PAID_PREFIX_NO_FULL_TASK_SCORER",
                "native_scope": "PAID_INCREMENT_METADATA_ONLY_NOT_INDEPENDENT_NATIVE_REBUILD",
                "original_evaluator_reproduction": "NOT_ESTABLISHED_NOT_CLAIMED",
                "formal_force_rank_allowed": False, "paid_prefix_origin_declared_not_reopened": row["evidence"],
                "actual_START_kind_preserved": row["kind"], "hard_safety_scope": unknown,
                "producer_source": self.source_ref("source/v7_scorer_replay_v2.py"),
                "producer_scope_limit": "cache stores no producer hash; pinned source documents minimal early-return schema before evaluate; not an original evaluator execution receipt"}

    def common(self, row):
        rel = "audit/scorer_replay/" + row["id"] + ".json"
        if rel not in self.authority["scorer_replay_files_sha256"]:
            return None
        assert self.pins[rel] == self.authority["scorer_replay_files_sha256"][rel]
        doc = self.metadata(rel)
        if doc.get("status") == "PARTIAL_NOT_RANKED" and row["id"] in PREFIX_CACHE_SHA:
            return self.paid_parent_prefix(row, rel, doc)
        assert doc["id"] == row["id"] and doc["group"] == row["group"]
        assert not doc["errors"] and doc["original_result_exact_reproduced"] is True
        assert doc["status"] in ("SCORER_REPLAY_PASS", "PARTIAL_NOT_RANKED")
        assert isinstance(doc["input_sha256"], dict) and doc["input_sha256"]
        assert doc["source_sha256"] and doc["unchanged_scorer_sources"]
        assert not row["boundary_no_TASK"], "BOUNDARY_CANNOT_USE_TASK_SCORER"
        full = all(finite(doc.get(k)) for k in ("independent_JF", "independent_JM"))
        if full:
            assert isinstance(doc["independent_native_dose"], dict) and doc["independent_native_dose"]
            assert isinstance(doc["independent_native_motion"], dict) and doc["independent_native_motion"]
            assert isinstance(doc["motion_replay"]["acceptance_pass"], bool)
            assert isinstance(doc["qualified_replay"], bool)
            if doc["qualified_replay"]:
                assert doc["original_mode_result"] == doc["original_physical_result"] == doc["original_scientific_result"] == "PASS"
                assert doc["motion_replay"]["acceptance_pass"] is True
            assert row.get("complete_original_result") is not False
            scope = "COMPLETE_TASK_ORIGINAL_EVALUATOR_NATIVE_MOTION_AND_JF_JM_REPLAY"
        else:
            assert all(doc.get(k) is None for k in ("independent_JF", "independent_JM", "independent_native_dose", "independent_native_motion", "motion_replay"))
            assert doc["qualified_replay"] is False
            assert doc["original_mode_result"] == doc["original_physical_result"] == "FAIL"
            assert row.get("complete_original_result") is not True
            scope = "PARTIAL_ORIGINAL_EVALUATOR_REPLAY_NATIVE_INCREMENT_FROM_EXACT_SNAPSHOT_NO_FULL_MOTION_OR_COST_RANK"
        return {"source": self.source_ref(rel), "scope": scope, "complete_task": full,
                "original_qualified": doc["qualified_replay"], "original_evaluator_overall": doc["original_mode_result"],
                "native_scope": "FULL_TASK_NATIVE_REBUILD" if full else "PAID_INCREMENT_METADATA_ONLY_NO_FULL_NATIVE_TRAJECTORY_IMPUTED",
                "original_raw_input_sha256_declared_not_rehashed": doc["input_sha256"]}

    def historical(self, x, row):
        assert x["START_raw_line_sha256"] == row["START_raw_line_sha256"] and x["END_raw_line_sha256"] == row["END_raw_line_sha256"]
        rel = x["receipt_path"]
        assert self.pins[rel] == x["receipt_sha256"]
        doc = self.metadata(rel)
        stored = pointer(doc, x["json_pointer"])
        assert canonical(stored) == x["stored_row_canonical_sha256"] and stored["id"] == row["id"]
        assert not stored.get("errors")
        boundary = x["complete_task"] is None
        assert boundary == row["boundary_no_TASK"]
        if boundary:
            assert x["counter_matches_observation"] is True and x["task_cost_excludes_boundary"] is True
            self.increment(stored.get("record", stored), row["actual_new_native_steps"])
        else:
            original = pointer(doc, x["evaluator_pointer"])
            assert original["overall_result_for_mode"] == x["original_evaluator_overall"]
            assert original["physical_task_result"]["status"] == x["original_physical_task_status"]
            assert isinstance(x["original_qualified"], bool)
            self.increment(stored, row["actual_new_native_steps"])
            if x["complete_task"] is False:
                assert x["full_motion_and_full_cost_rank_available"] is False and len(x["hard11"]) == 11
        return {"source": self.source_ref(rel, x["json_pointer"]), "crosswalk_source": self.source_ref(CROSSWALK),
                "scope": x["actual_scope"], "complete_task": x["complete_task"],
                "original_qualified": x["original_qualified"], "original_evaluator_overall": x["original_evaluator_overall"],
                "stored_row_canonical_sha256": x["stored_row_canonical_sha256"],
                "original_raw_input_sha256_declared_not_rehashed": x.get("original_raw_input_sha256_carried_from_receipt", {})}

    def c4_entries(self, universe):
        entries = collections.defaultdict(list)
        for binding in self.authority["c4_results"]:
            group = binding["group"]
            assert group in ("V8CONVAL01", "V8CONVAL02")
            rel, endrel = binding["result"], binding["end"]
            doc, end = self.metadata(rel), self.metadata(endrel)
            assert doc["status"] == end["status"] == "C4_INDEPENDENT_CLOSED_AUDIT_PASS" and not doc["errors"]
            assert end["result_sha256"] == self.pins[rel] and doc["counts"]["group"] == group
            assert doc["model_fit_forward_from_audit"] == doc["physical_steps_from_audit"] == 0
            for i, trial in enumerate(doc["trials"]):
                ident = trial["id"]
                if ident not in universe:
                    self.gap(ident, "C4_ACTUAL_TRIAL_OUTSIDE_PHYSICAL_SNAPSHOT")
                    continue
                row = universe[ident]
                assert row["group"] == group and not row["boundary_no_TASK"] and not trial["errors"]
                self.increment(trial, row["actual_new_native_steps"])
                full = trial["complete_original"]
                assert isinstance(full, bool)
                if full:
                    q = trial["fresh_original_evaluator"]
                    assert all(finite(trial[k]) for k in ("JF_N_s", "JM_Nm_s"))
                    assert trial["native_mapping"] and trial["independent_motion_vs_same_stage_B"]
                    qualified = trial["independent_qualified"]
                    assert isinstance(qualified, bool)
                    scope = "C4_COMPLETE_TASK_ORIGINAL_EVALUATOR_NATIVE_MOTION_5MS_JF_JM"
                else:
                    partial = trial["C4_partial_original_replay"]
                    q = partial["original_evaluator"]
                    assert partial["complete"] is False and partial["full_motion_arrays"] is None
                    assert partial["full_force_or_moment_rank_allowed"] is False and partial["full_qualification_imputed"] is False
                    assert len(partial["hard11"]) == 11
                    assert q["overall_result_for_mode"] == q["physical_task_result"]["status"] == "FAIL"
                    assert trial["worker_result"]["qualified"] is False
                    qualified = False
                    scope = "C4_PARTIAL_ORIGINAL_EVALUATOR_HARD11_NATIVE_INCREMENT_NO_FULL_MOTION_NO_RANK"
                entries[ident].append({"source": self.source_ref(rel, "/trials/" + str(i)), "end_source": self.source_ref(endrel),
                                       "scope": scope, "complete_task": full, "original_qualified": qualified,
                                       "original_evaluator_overall": q["overall_result_for_mode"],
                                       "hard11_original_partial": None if full else partial["hard11"],
                                       "native_scope": "TASK_NATIVE_REBUILD" if full else "PAID_INCREMENT_NO_FULL_NATIVE_MOTION_IMPUTED",
                                       "original_raw_input_sha256_declared_not_rehashed": trial.get("source_hashes", {}),
                                       "stored_row_canonical_sha256": canonical(trial)})
            for i, boundary in enumerate(doc["boundaries"]):
                ident = boundary["id"]
                assert ident in universe and universe[ident]["boundary_no_TASK"] and not boundary["errors"]
                record = boundary["record"]
                self.increment(record, universe[ident]["actual_new_native_steps"])
                assert record["observed_native_steps"] == universe[ident]["actual_new_native_steps"]
                assert record["counter_matches_observation"] is True and record["task_cost_excludes_boundary"] is True
                entries[ident].append({"source": self.source_ref(rel, "/boundaries/" + str(i)), "end_source": self.source_ref(endrel),
                                       "scope": "C4_BOUNDARY_NATIVE_SESSION_NO_TASK_SCORER_APPLICABLE", "complete_task": None,
                                       "original_qualified": None, "original_evaluator_overall": "NOT_APPLICABLE_NO_TASK",
                                       "stored_row_canonical_sha256": canonical(boundary)})
        return entries

    def run(self):
        snap, universe = self.physical_universe()
        crosswalk = self.metadata(CROSSWALK)
        assert not crosswalk["real_coverage_gaps"] and len(crosswalk["crosswalk"]) == 26
        old = {x["id"]: x for x in crosswalk["crosswalk"]}
        assert len(old) == 26
        for ident in old.keys() - universe.keys():
            self.gap(ident, "ORIGINAL26_ID_OUTSIDE_ALL_PHYSICAL_SNAPSHOT")
        c4 = self.c4_entries(universe)
        rows = []
        for ident, physical in universe.items():
            self.clock()
            evidence = []
            for label, operation in (("ordinary", lambda: self.common(physical)),
                                     ("original26", lambda: self.historical(old[ident], physical) if ident in old else None)):
                try:
                    item = operation()
                    if item:
                        evidence.append(item)
                except Exception as exc:
                    self.gap(ident, "REJECTED_" + label.upper() + "_RECEIPT", type(exc).__name__ + ":" + str(exc))
            evidence.extend(c4.get(ident, []))
            signatures = {(x["complete_task"], x["original_qualified"], x["original_evaluator_overall"]) for x in evidence}
            if not evidence:
                self.gap(ident, "NO_EXISTING_SCOPE_APPROPRIATE_ORIGINAL_EVALUATOR_OR_BOUNDARY_NATIVE_RECEIPT")
            if len(signatures) > 1:
                self.gap(ident, "OVERLAPPING_RECEIPT_SCOPE_OR_QUALIFICATION_CONFLICT", sorted(map(str, signatures)))
            complete, qualified, original_mode = next(iter(signatures)) if len(signatures) == 1 else (None, None, "UNKNOWN")
            prefix = any(x.get("partial_parent_prefix_no_TASK_scorer") is True for x in evidence)
            if physical["boundary_no_TASK"] and complete is not None:
                self.gap(ident, "BOUNDARY_MISCLASSIFIED_AS_TASK")
            if not physical["boundary_no_TASK"] and not prefix and evidence and complete is None:
                self.gap(ident, "TASK_MISCLASSIFIED_AS_BOUNDARY")
            rows.append({"id": ident, "group": physical["group"], "actual_new_native_steps_original_job": physical["actual_new_native_steps"],
                         "physical_increment_evidence_declared_by_exact_snapshot_not_reopened": physical["evidence"],
                         "START": {"path": "runtime/ATTEMPTS.jsonl", "file_sha256": self.pins["runtime/ATTEMPTS.jsonl"], "line_number": physical["START_line_number"], "raw_line_without_newline_sha256": physical["START_raw_line_sha256"]},
                         "END": {"path": "runtime/ATTEMPTS.jsonl", "file_sha256": self.pins["runtime/ATTEMPTS.jsonl"], "line_number": physical["END_line_number"], "raw_line_without_newline_sha256": physical["END_raw_line_sha256"]},
                         "boundary_no_TASK": physical["boundary_no_TASK"], "partial_parent_prefix_no_TASK_scorer": prefix,
                         "TASK_scorer_applicable": not physical["boundary_no_TASK"] and not prefix, "complete_task": complete,
                         "original_qualified": qualified, "original_evaluator_overall": original_mode,
                         "evidence": evidence, "overlap_receipt_count": len(evidence),
                         "physical_count_contribution": 1, "repeated_receipts_add_no_physics_or_independent_trials": True})
        # Exact metadata identities must still hold at output, including the mutable
        # append-only ledger frozen by this one approval. No CURRENT pointer is read.
        for rel, receipt in list(self.refs.items()):
            self.unpinned_bytes(rel, receipt["sha256"])
        self.clock()
        return {"schema": "v8.final_original_replay_closed_coverage.v2",
                "status": "COMPLETE_SCOPE_APPROPRIATE_METADATA_COVERAGE" if not self.gaps else "EXPLICIT_COVERAGE_GAPS",
                "physical_snapshot": self.source_ref(self.args.physical_snapshot), "created_unix": time.time(),
                "physical_id_count": len(rows), "rows": rows, "gaps": self.gaps,
                "counts": {"boundary_ids": sum(x["boundary_no_TASK"] for x in rows),
                           "partial_parent_prefix_no_TASK_scorer": sum(x["partial_parent_prefix_no_TASK_scorer"] for x in rows),
                           "complete_qualified_TASK_ids": sum(x["complete_task"] is True and x["original_qualified"] is True for x in rows),
                           "complete_unqualified_TASK_ids": sum(x["complete_task"] is True and x["original_qualified"] is False for x in rows),
                           "partial_TASK_ids_not_ranked": sum(x["complete_task"] is False for x in rows),
                           "IDs_with_overlapping_evidence_counted_once": sum(x["overlap_receipt_count"] > 1 for x in rows)},
                "original_job_native_steps_observation_not_new_execution": snap["actual_new_native_steps_closed"],
                "auditPASS_is_not_qualPASS": True, "boundary_TASK_evaluator": "NOT_APPLICABLE",
                "registered_but_NOT_RUN_roles_or_choice_aliases_not_added_to_physical_universe": True,
                "source_references": list(self.refs.values()),
                "all_opened_metadata_source_SHA_rechecked_before_output": True,
                "scope_limits": ["Metadata only: no original raw input rehash or new evaluator/native recomputation.",
                                 "Three exact main-approved paid parent prefixes are neither full TASK nor boundary; qualification/evaluator N/A, no independent native rebuild, no training hard-safety clearance; Beta02L three UNKNOWNs retained.",
                                 "Partial ordinary replay may prove original evaluator reproduction and snapshot paid native increment only; no full native motion, full JF/JM, hard11 detail or qualification imputed.",
                                 "Original26 full/partial/boundary evidence is reused by exact path/SHA/pointer/canonical hash, not replayed again.",
                                 "No independent patient count or global model/GPU cost inferred."],
                "operations": {"scorer_raw_model_fit_physics": 0},
                "resource": {"CPU_s": time.process_time() - self.cpu_started, "wall_s": time.monotonic() - self.started,
                             "ru_maxrss_raw_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                             "RSS_attribution": "PROCESS_HIGH_WATER_MARK_NOT_INCREMENTAL_MEMORY; external launcher remains separate/inclusive"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("package", "physical-snapshot", "approval", "approval-sha256", "source-manifest", "contract", "output"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    job = Aggregation(args)
    job.output.mkdir(parents=True)
    try:
        result = job.run()
        target = job.output / "RESULT.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        end = {"status": result["status"], "result_sha256": digest(target.read_bytes()),
               "gap_count": len(result["gaps"]), "operations": result["operations"], "resource": result["resource"]}
        (job.output / "END.json").write_text(json.dumps(end, indent=2) + "\n")
        print(json.dumps(end))
        return 0 if not result["gaps"] else 2
    except Exception as exc:
        failure = {"status": "FAILED_METADATA_AGGREGATION_NOT_COVERAGE_PASS", "exception": type(exc).__name__ + ":" + str(exc),
                   "traceback": traceback.format_exc(), "references_read": list(job.refs.values()),
                   "CPU_s": time.process_time() - job.cpu_started, "wall_s": time.monotonic() - job.started,
                   "operations": {"scorer_raw_model_fit_physics": 0}}
        (job.output / "FAILURE.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
