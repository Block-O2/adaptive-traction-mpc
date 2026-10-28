"""SOURCE_ONLY，须主审另批后运行。只读闭合组 metadata；绝不导入模型/评分/物理。

审计不等于原 scorer replay；所有原资格、partial、UNKNOWN 均保留。
原回执计数、固定源码条件推导、未知量分别输出，不将相同结果副本重复求和。
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import resource
import sys
import time

GROUPS = {
    "V8FROZENENG02": "0b2c5cb44af40c172fed4da7edcd8454b7f58008f12a15edcb4fa96071471d74",
    "V8VAL03": "1e47772d2c4118c2a1523cb304a7684f2c8437d44941cc049060c4862ad3f6f3",
    "V8VAL04": "736b440db5d98fd71595662ca0f03a0b216d761140ee6e320594925459b673ff",
}
CORE = ["B", "LATE_H150", "EARLY_H150", "LATE_PHASE", "EARLY_PHASE"]
HISTORY = ["ACTION_ONLY", "HISTORY_ADDITIVE", "HISTORY_INTERACTION", "HISTORY_DISABLED", "COMMISSIONED25_INTERACTION"]
GRID = ["BETA_AXIS_FIXED_L000", "BETA_AXIS_FIXED_L025", "BETA_AXIS_FIXED_L050", "BETA_AXIS_FIXED_L075", "BETA_AXIS_FIXED_L100"]
HARD = ["force", "moment", "torque", "human_speed", "human_acceleration", "robot_speed", "session_clearance", "true_clearance", "measured_sleeve_clearance", "no_shank_table_contact", "no_human_rom_violation"]
ROLES = {"callback", "capture", "runtime", "observer", "observation_contract", "history_guard", "runtime_loader"}
GLOBAL_STOP = 1793114740.0
ACTIVATION = "deep_learning_method_exploration_v8_20261027T032540Z"
ACTIVATION_SHA = "6c9046e286afc923ca5b1ad9c4f4c787c95ad858e88ab8d3ec6f26e7d096694f"
CORE_SOURCE = "source/v8_comparative_validation_candidate_v4.py"
CORE_SOURCE_SHA = "d5a6684ccd787ef340943ff58f9fa5ba7d114a518312fb9787d7d3d819f64d3b"
SCOPE = "families/critic_value/analysis/inference_receipt_audit_v1/outputs"
CASE_DIGESTS_NOT_OPENED = {
    "44387b2b48a4d486d4fa5f7b980e698a3546365eea95bad2b1c2c50620342ccf",
    "cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c",
    "224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def stat_identity(pid):
    try:
        tail = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": int(pid), "start_ticks": int(tail[19]), "state": tail[0]}
    except FileNotFoundError:
        return None


class Audit:
    def __init__(self, package, group, approval, output):
        self.p = package.resolve()
        self.g = group
        self.approval = approval
        self.output = output
        self.start = time.time()
        self.mono = time.monotonic()
        self.cpu = time.process_time()
        self.refs = {}
        self.checks = []
        self.unknowns = []
        self.docs = {}
        self.bytes_read = 0
        self.opens = 0
        self.deadline = min(float(approval["expires_unix"]), GLOBAL_STOP)
        self.max_bytes = 256 * 1024 * 1024
        self.rows = {}
        self.event_map = {}
        self.config = None
        self.job = None
        self.begin = None
        self.end = None
        self.config_sha = GROUPS[group]
        self.job_sha = approval["job_source_manifest_sha256"]
        self.owner = None
        self.reference_exclusions = []
        self.checked_embedded_refs = set()

    def tick(self):
        if time.time() >= self.deadline or time.process_time() - self.cpu >= 59.8:
            raise TimeoutError("AUDIT_LOCAL_OR_GLOBAL_DEADLINE_PAID_READ_PREFIX_PRESERVED")

    def path(self, rel):
        self.tick()
        path = (self.p / rel).resolve()
        if not path.is_relative_to(self.p):
            raise ValueError("PATH_ESCAPES_PACKAGE:" + str(rel))
        name = path.name.upper()
        if path.suffix.lower() not in (".json", ".jsonl", ".py", ".md"):
            raise ValueError("NON_METADATA_OR_SOURCE_INPUT_FORBIDDEN:" + str(rel))
        if name.startswith("CURRENT") or "PENDING" in name or "SAMPLING" in name:
            raise ValueError("MUTABLE_RUN_INPUT_FORBIDDEN:" + str(rel))
        if "/runtime/source/results/" in str(path) or any(x in path.parts for x in ("pending_inputs", "sampling")):
            raise ValueError("RAW_OR_MUTABLE_RUN_INPUT_FORBIDDEN:" + str(rel))
        return path

    def raw(self, rel):
        path = self.path(rel)
        size = path.stat().st_size
        if size > 32 * 1024 * 1024 or self.bytes_read + size > self.max_bytes:
            raise ValueError("FINITE_METADATA_READ_BUDGET_EXCEEDED:" + str(rel))
        value = path.read_bytes()
        self.opens += 1
        self.bytes_read += len(value)
        self.refs[str(path.relative_to(self.p))] = hashlib.sha256(value).hexdigest()
        return value

    def sha(self, rel):
        if str(rel) in self.refs:
            return self.refs[str(rel)]
        self.raw(rel)
        return self.refs[str(rel)]

    def load(self, rel, optional=False):
        rel = str(rel)
        if rel in self.docs:
            return self.docs[rel]
        if optional and not self.path(rel).exists():
            return None
        value = json.loads(self.raw(rel))
        self.docs[rel] = value
        return value

    def check(self, name, passed, detail=None):
        row = {"check": name, "PASS": bool(passed)}
        if detail is not None:
            row["detail"] = detail
        self.checks.append(row)
        return bool(passed)

    def require(self, name, passed):
        if not self.check(name, passed):
            raise ValueError("AUDIT_PREREQUISITE_FAILED:" + name)

    def unknown(self, name, reason):
        self.unknowns.append({"field": name, "status": "UNKNOWN", "reason": reason})

    def reference(self, ref, pinned=False):
        self.check("ref_digest:" + ref["path"], self.sha(ref["path"]) == ref["sha256"])
        if pinned:
            self.check("ref_config_job_pin:" + ref["path"], self.config["frozen_artifacts"].get(ref["path"]) == self.job["files"].get(ref["path"]) == ref["sha256"])
        return self.load(ref["path"])

    def embedded_refs(self, value, scope):
        """Verify metadata/source references, retain forbidden raw/mutable refs as unknown.

        Do not recurse into external documents here: all saved output refs are checked,
        but provenance is not a license to open raw/trace or CURRENT/pending aliases.
        """
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                rel, h = value["path"], value["sha256"]
                key = (rel, h)
                if key not in self.checked_embedded_refs:
                    self.checked_embedded_refs.add(key)
                    path = Path(rel)
                    forbidden = h in CASE_DIGESTS_NOT_OPENED or path.suffix.lower() not in (".json", ".jsonl", ".py", ".md") or path.name.upper().startswith("CURRENT") or any(x in path.name.upper() for x in ("PENDING", "SAMPLING")) or "high_rom_v8_val_" in path.name or rel == self.config.get("case_path") or "/runtime/source/results/" in str(path) or any(x in path.parts for x in ("pending_inputs", "sampling"))
                    if forbidden:
                        self.reference_exclusions.append({"scope": scope, "path": rel, "original_claimed_sha256": h, "actual_bytes_rehashed": False, "status": "UNKNOWN_NOT_OPENED_BY_SCOPE", "reason": "raw/trace/case-payload/mutable reference remains original provenance, not audit replay"})
                    else:
                        self.check("embedded_metadata_ref_SHA:" + scope + ":" + rel, self.sha(rel) == h)
            for child in value.values():
                self.embedded_refs(child, scope)
        elif isinstance(value, list):
            for child in value:
                self.embedded_refs(child, scope)

    def closure(self):
        # No physical/prediction result metadata is read until these owner gates pass.
        g = self.g
        activation = self.load("ACTIVATION.json")
        self.require("original_activation_SHA_clock_not_reset", self.sha("ACTIVATION.json") == ACTIVATION_SHA and activation.get("activation_id") == ACTIVATION and activation.get("hard_stop_unix") == GLOBAL_STOP and activation.get("clock_must_not_reset") is True)
        self.config = self.load("experiments/" + g + ".json")
        self.job = self.load("jobs/" + g + "/SOURCE_MANIFEST.json")
        self.require("actual_config_and_main_approval_SHA", self.sha("experiments/" + g + ".json") == self.approval["config_sha256"] == GROUPS[g])
        self.require("actual_job_SOURCE_and_main_approval_SHA", self.sha("jobs/" + g + "/SOURCE_MANIFEST.json") == self.job_sha)
        self.require("job_config_identity", self.job["config_sha256"] == self.config_sha and self.config["group"] == self.config["condition"]["name"] == g)
        self.begin = self.load("owned/" + g + "_SUPERVISOR.json")
        self.end = self.load("owned/" + g + "_SUPERVISOR_END.json")
        self.require("supervisor_closed_group_only", self.end.get("state") == "STOP" and self.end.get("survivors") == [] and self.end.get("ended_unix", float("inf")) <= self.start)
        self.require("supervisor_frozen_identity_original_clock", self.begin.get("config_sha256") == self.config_sha and self.begin.get("activation") == ACTIVATION and self.begin.get("cutoff_unix", float("inf")) <= GLOBAL_STOP)
        exitrow = self.load("owned/" + g + "_EXIT.json", optional=True)
        worker_done = self.load("jobs/" + g + "/WORKER_DONE.json", optional=True)
        self.require("owned_exit_no_active_child", exitrow is not None and exitrow.get("active_child") is None)
        self.require("worker_done_preserved_not_supervisor_only", worker_done is not None)
        self.owner = self.begin["worker"]["pid"]
        identities = list(self.end["known_owned"].values()) + [self.begin["identity"], self.begin["worker"]]
        closed = []
        for identity in identities:
            current = stat_identity(identity["pid"])
            okay = current is None or current["start_ticks"] != identity["start_ticks"]
            self.require("original_owned_identity_closed:" + str(identity["pid"]) + ":" + str(identity["start_ticks"]), okay)
            closed.append({"original": identity, "current": current, "original_identity_closed": okay})
        return closed

    def pins(self):
        c = self.config
        self.require("frozen_core_version", c["frozen_artifacts"].get(CORE_SOURCE) == self.job["files"].get(CORE_SOURCE) == self.sha(CORE_SOURCE) == CORE_SOURCE_SHA)
        skipped = []
        case_refs = {c["case_path"]}
        for rel, expected in c["frozen_artifacts"].items():
            self.check("config_job_dependency_digest:" + rel, self.job["files"].get(rel) == expected)
            # Case payloads are not input to this audit. Their original hashes remain bound
            # by exact config + job SOURCE; never parse or reopen sealed parameter payloads.
            if expected in CASE_DIGESTS_NOT_OPENED or rel in case_refs or "high_rom_v8_val_" in Path(rel).name:
                skipped.append({"path": rel, "expected_sha256": expected, "actual_bytes_rehashed": False, "basis": "exact_config_and_job_SOURCE_maps_only_case_payload_not_opened"})
                continue
            self.check("frozen_actual_bytes_digest:" + rel, self.sha(rel) == expected)
        self.check("no_training_config", c["comparative_validation"].get("no_training") is True and c["comparative_composer_v4"].get("no_training") is True)
        return skipped

    def physical_events(self):
        # ATTEMPTS is globally appendable: bind only original scoped records + raw-line
        # digests, not a digest of the mutable global stream. Other groups are not parsed.
        rel = "runtime/ATTEMPTS.jsonl"
        path = self.path(rel)
        initial_size = path.stat().st_size
        needle = ('"' + self.g + '_').encode()
        scoped = []
        consumed = 0
        with path.open("rb") as stream:
            for n, raw in enumerate(stream, 1):
                self.tick()
                consumed += len(raw)
                self.bytes_read += len(raw)
                if consumed > initial_size:
                    break
                if self.bytes_read > self.max_bytes:
                    raise ValueError("FINITE_SCOPED_METADATA_STREAM_READ_BUDGET_EXCEEDED")
                if needle not in raw:
                    continue
                row = json.loads(raw)
                ident = row.get("id", "")
                if not ident.startswith(self.g + "_") or row.get("event") not in ("START", "END"):
                    continue
                event = {"line1": n, "raw_line_without_newline_sha256": hashlib.sha256(raw.rstrip(b"\n")).hexdigest(), "record": row}
                scoped.append(event)
                slots = self.event_map.setdefault(ident, {})
                self.check("unique_original_physical_event:" + ident + ":" + row["event"], row["event"] not in slots)
                slots[row["event"]] = event
        self.opens += 1
        for ident, slots in self.event_map.items():
            self.check("closed_START_END_pair:" + ident, set(slots) == {"START", "END"})
            start = slots.get("START", {}).get("record", {})
            end = slots.get("END", {}).get("record", {})
            self.check("physical_SOURCE_config_identity:" + ident, start.get("config_sha256") == self.config_sha and start.get("job_source_sha256") == self.job_sha)
            self.check("original_END_joined:" + ident, end.get("joined") is True)
            if ident != self.g + "_parent":
                self.check("child_original_parent_hash_equal:" + ident, end.get("parent_hash_equal") is True)
        return scoped

    def proof(self, value, label):
        p = value.get("proof_audit") if isinstance(value, dict) else None
        if not isinstance(p, dict):
            return
        self.check("original_sourceproof_identity:" + label, p.get("config_sha256") == self.config_sha and p.get("job_source_manifest_sha256") == self.job_sha and p.get("actual_in_memory_callback_code_checked") is True and p.get("current_task_B_or_candidate_result_used") is False)
        self.check("original_sourceproof_seven_roles:" + label, set(p.get("roles", {})) == ROLES)
        for role, row in p.get("roles", {}).items():
            rel = row["path"]
            h = self.sha(rel)
            self.check("original_loaded_role_chain:" + label + ":" + role, h == row.get("actual_file_sha256") == row.get("expected_profile_sha256") == row.get("job_manifest_file_sha256") == self.job["files"].get(rel) and row.get("actual_loaded_module_file") == str(self.path(rel)))
        # This audit verifies the original recorded live check; it cannot re-observe a
        # now-dead process' in-memory callback. It never fabricates a fresh proof.

    def wrapper_proof(self, value, label):
        if not isinstance(value, dict):
            return
        p = value.get("thin_wrapper_owner_proof")
        if isinstance(p, dict):
            self.check("original_thin_wrapper_owner_deadline:" + label, p.get("group") == self.g and p.get("worker_pid") == self.owner and p.get("worker_start_ticks") == self.begin["worker"]["start_ticks"] and p.get("config_sha256") == self.config_sha and p.get("supervisor_sha256") == self.sha("owned/" + self.g + "_SUPERVISOR.json") and p.get("supervisor_cutoff_unix") == self.begin["cutoff_unix"] and p.get("parent_time_added_seconds") == 0)
        p = value.get("fixed_readonly_clock")
        if isinstance(p, dict):
            self.check("original_fixed_readonly_clock_owner_no_extension:" + label, p.get("original_worker_PID") == self.owner and p.get("original_worker_start_ticks") == self.begin["worker"]["start_ticks"] and p.get("config_sha256") == self.config_sha and p.get("supervisor_sha256") == self.sha("owned/" + self.g + "_SUPERVISOR.json") and p.get("original_job_cutoff_unix") == self.begin["cutoff_unix"] and p.get("original_global_stop_unix") == GLOBAL_STOP and p.get("signal_RLIMIT_or_parent_clock_changed") is False and p.get("entered_unix", float("inf")) < p.get("local_stop_unix", float("-inf")) <= min(p["entered_unix"] + 10.0, self.begin["cutoff_unix"], GLOBAL_STOP))

    def inference(self):
        g = self.g
        rel = "analysis/" + g + "_INFERENCE_EVENTS.jsonl"
        path = self.path(rel)
        events = []
        if path.exists():
            for n, raw in enumerate(self.raw(rel).splitlines(), 1):
                row = json.loads(raw)
                self.check("inference_owner:" + str(n), row.get("owner_pid") == self.owner)
                events.append({"line1": n, "raw_line_without_newline_sha256": hashlib.sha256(raw).hexdigest(), "record": row})
        starts, returns, pending, receipts = [], [], None, []
        for event in events:
            row = event["record"]
            if row.get("event") == "START":
                self.check("serial_API_no_overlap:" + str(len(starts) + 1), pending is None)
                starts.append(row)
                pending = row
            elif row.get("event") == "RETURN":
                self.check("RETURN_matches_current_START:" + str(len(returns) + 1), pending is not None and pending["label"] == row.get("label") and pending["unix"] <= row["unix"])
                expected = "analysis/" + g + "_API_RETURN_" + str(len(starts)).zfill(3) + ".json"
                self.check("durable_receipt_sequential_path:" + str(len(starts)), row.get("receipt", {}).get("path") == expected)
                receipt = self.reference(row["receipt"])
                returns.append(row)
                counts = receipt["macro_counts_at_return"]
                self.check("receipt_original_owner_label_time_counts:" + str(len(starts)), receipt.get("schema") == "v8.completed_inference_return_receipt.v1" and receipt.get("owner_pid") == self.owner and receipt.get("label") == row.get("label") and pending is not None and pending["unix"] <= receipt["returned_unix"] <= row["unix"] and counts.get("API_started") == len(starts) and counts.get("API_returned") == len(returns) and counts.get("new_fit") == 0)
                value = receipt["original_return_value"]
                self.proof(value, row["label"])
                self.wrapper_proof(value, row["label"])
                self.embedded_refs(value, "original_API_return:" + row["label"])
                explicit = {}
                if isinstance(value, dict):
                    for key in ("API_calls", "forward_details", "actual_nested_accounting", "API_accounting", "wrapper_accounting", "logical_deepcopy_calls", "numeric_model_restores_or_array_constructions", "two_bundle_JSON_loads_not_model_forward", "inference_API_calls", "counters", "backend_kinds", "new_fit_or_physics", "new_fit_initialize_physics", "fit", "physics", "thin_wrapper_owner_proof", "fixed_readonly_clock"):
                        if key in value:
                            explicit[key] = value[key]
                    for key in ("new_fit_or_physics", "new_fit_initialize_physics", "fit", "physics"):
                        if key in value:
                            self.check("original_receipt_no_new_fit_physics:" + row["label"] + ":" + key, value[key] == 0)
                receipts.append({"label": row["label"], "receipt": row["receipt"], "returned_unix": receipt["returned_unix"], "grade_A_original_recorded_nested_fields": explicit, "nested_fields_absent": "UNKNOWN_NOT_ZERO" if not explicit else "unrecorded_lower_layers_remain_UNKNOWN", "original_return": value})
                pending = None
            else:
                self.check("known_inference_event_type", False, row.get("event"))
        error_files = {}
        for suffix in ("SELECTOR_ERROR", "SELECTOR_OWNER_CLOSE", "V4_COMPOSER_ERROR", "V4_OWNER_CLOSE"):
            rel = "analysis/" + g + "_" + suffix + ".json"
            doc = self.load(rel, optional=True)
            if doc is not None:
                error_files[suffix] = {"path": rel, "sha256": self.sha(rel), "original": doc}
                self.embedded_refs(doc, "original_error:" + suffix)
                if "counts" in doc and "new_fit" in doc["counts"]:
                    self.check("original_error_no_new_fit:" + suffix, doc["counts"]["new_fit"] == 0)
        if pending:
            self.unknown("entered_failed_API_nested_work:" + pending["label"], "START 无 RETURN；原 error 的 paid-prefix 原样保留，不把未记录内部 work 写 0")
        return {"events": events, "API_started": len(starts), "API_returned": len(returns), "entered_unreturned_API": pending, "receipts": receipts, "original_error_or_owner_close": error_files}

    def menu(self):
        rel = self.config["comparative_validation"]["menu_path"]
        menu = self.load(rel)["action_contracts"]
        hashes = [digest(r) for r in menu]
        self.require("five_unique_complete_core_recipes", len(menu) == len(set(hashes)) == 5)
        self.require("config_core_order_and_exact_actions", [a["tag"] for a in self.config["actions"]] == CORE and [a["action"] for a in self.config["actions"]] == [r["action"] for r in menu])
        for recipe in menu:
            action = recipe["action"]
            base = dict(self.config["B"] if action["family"] == "B" else self.config["H150"])
            base.update(action.get("candidate_overrides", {}))
            base.pop("id", None)
            self.check("resolved_base_candidate:" + digest(recipe), base == recipe["resolved_base_candidate"])
            self.check("frozen_18d_digest:" + digest(recipe), self.sha("runtime/FROZEN_18D.json") == recipe["frozen_18d_sha256"])
            for path, h in recipe["planner_source_sha256"].items():
                self.check("full_recipe_planner_digest:" + path, self.sha(path) == h == self.job["files"].get(path))
        return menu, hashes

    def attempt(self, tag):
        if tag in self.rows:
            return self.rows[tag]
        g = self.g
        rel = "attempts/" + g + "_" + tag + "_RESULT.json"
        row = self.load(rel, optional=True)
        events = self.event_map.get(g + "_" + tag, {})
        if row is None:
            status = "NOT_RUN_NO_ORIGINAL_START" if "START" not in events else "UNKNOWN_STARTED_NO_RESULT"
            if "START" in events:
                self.unknown("original_result:" + tag, "已付物理 START 但缺原 RESULT；不得视作零成本或成功")
            result = {"tag": tag, "status": status, "complete": None, "qualified": None, "JF": None, "JM": None, "actual_new_native_steps": None, "true_hard_safety_violation": None, "original_events": events}
            self.rows[tag] = result
            return result
        self.check("original_RESULT_identity:" + tag, row.get("id") == g + "_" + tag)
        self.check("original_RESULT_has_START_END:" + tag, set(events) == {"START", "END"})
        metric = None
        if row.get("complete") is True and row.get("metrics_path"):
            metric = self.load(row["metrics_path"])
            common = metric.get("native_physical_audit", {}).get("unchanged_evaluator", {}).get("physical_task_result", {}).get("scorer_v2_common_conditions", {})
        else:
            common = row.get("protected_task_failure", {}).get("hard_safety_conditions", {})
        conditions = {key: common.get(key) for key in HARD}
        hard = True if row.get("true_hard_safety_violation") is True or any(x is False for x in conditions.values()) else False if all(x is True for x in conditions.values()) else None
        status = "COMPLETE_ORIGINAL_QUALIFIED" if row.get("complete") is True and row.get("qualified") is True else "COMPLETE_ORIGINAL_UNQUALIFIED" if row.get("complete") is True else "PARTIAL_NOT_RANKED"
        if row.get("complete") is not True:
            self.check("partial_original_qualified_not_true:" + tag, row.get("qualified") is not True)
        result = {"tag": tag, "status": status, "complete": row.get("complete"), "qualified": row.get("qualified"), "JF": row.get("JF") if row.get("complete") is True else None, "JM": row.get("JM") if row.get("complete") is True else None, "motion_vs_B": row.get("motion_vs_B"), "actual_new_native_steps": row.get("actual_new_native_steps"), "true_hard_safety_violation": hard, "original_hard_conditions": conditions, "original_result": {"path": rel, "sha256": self.sha(rel)}, "original_events": events, "original_action": row.get("action"), "error": row.get("error"), "original_protected_task_failure": row.get("protected_task_failure"), "safety_source": {"path": row["metrics_path"], "sha256": self.sha(row["metrics_path"])} if metric is not None else {"path": rel, "sha256": self.sha(rel)}, "original_metrics_qualification_not_recomputed": True}
        self.rows[tag] = result
        return result

    def decisions(self, inference, menu, hashes):
        g = self.g
        pre = self.load("predictions/" + g + "_FROZEN_CONTEXT_DECISIONS.json", optional=True)
        allpre = self.load("predictions/" + g + "_V4_ALL_PRE_B_DECISIONS.json", optional=True)
        history = self.load("predictions/" + g + "_FROZEN_HISTORY_DECISIONS.json", optional=True)
        link = self.load("analysis/" + g + "_V4_SELECTOR_EXECUTION_LINK.json", optional=True)
        corelink = self.load("analysis/" + g + "_SELECTOR_EXECUTION_LINK.json", optional=True)
        b_events = self.event_map.get(g + "_B", {})
        bstart = b_events.get("START", {}).get("record", {}).get("unix")
        bend = b_events.get("END", {}).get("record", {}).get("unix")
        table = []
        byhash = dict(zip(hashes, CORE))
        b = self.attempt("B")
        nominal = b.get("complete") is True and b.get("qualified") is True and b.get("true_hard_safety_violation") is False
        stage = {"pre_B153": "NOT_RUN", "post_B5": "NOT_RUN", "Beta12mean_5grid": "NOT_RUN"}
        def append_choice(permission, label, tag, recipe_hash, fallback=False, unknown_prediction=False):
            original = self.attempt(tag) if tag is not None else {"status": "UNKNOWN_NO_EXECUTION_MAPPING", "qualified": None, "complete": None, "JF": None, "JM": None, "true_hard_safety_violation": None, "actual_new_native_steps": None}
            table.append({"permission": permission, "selector": label, "selected_tag": tag, "recipe_sha256": recipe_hash, "fallback_B_after_predictive_abstain": fallback, "original_prediction_unknown_or_abstain": unknown_prediction, **{k: original.get(k) for k in ("status", "complete", "qualified", "JF", "JM", "motion_vs_B", "true_hard_safety_violation", "actual_new_native_steps", "original_result")}, "shared_original_result_not_independent_rollout": True})
        if pre is not None:
            stage["pre_B153"] = "ORIGINAL_SAVED"
            self.check("preB153_count_owner_no_training", len(pre["decisions"]) == 153 and pre["owner_pid"] == self.owner and pre.get("before_any_candidate_outcome") is True and pre.get("new_training") is False and pre["counts"]["new_fit"] == 0)
            if bstart is not None:
                self.check("preB_saved_before_B_START", pre["created_unix"] < bstart)
            parallel = pre["A_source_proof_audit"]
            self.proof(parallel, "saved_A_PARALLEL")
            for label, dec in pre["decisions"].items():
                h = dec.get("choice_recipe_sha256")
                tag = byhash.get(h)
                self.check("preB_exact_recipe_action:" + label, tag is not None and dec.get("choice_tag") == tag and dec.get("choice_action") == menu[hashes.index(h)]["action"] and dec.get("original_qualification_granted") is False)
                append_choice("CORE_FIVE_RECIPE_PRE_B", label, tag, h, dec.get("fallback_B_after_predictive_abstain", False), dec.get("fallback_B_after_predictive_abstain", False))
            for item in inference["receipts"]:
                if item["label"].startswith("C_"):
                    continue
                self.check("all_core_returns_before_B_START:" + item["label"], bstart is None or item["returned_unix"] < bstart)
                val = item["original_return"]
                if isinstance(val, dict) and isinstance(val.get("decisions"), dict):
                    self.check("original_return_decisions_match_preB:" + item["label"], all(pre["decisions"].get(k) == v for k, v in val["decisions"].items()))
            self.check("preB_counts31_31", pre["counts"]["API_started"] == pre["counts"]["API_returned"] == 31)
        elif bstart is not None:
            self.check("B_requires_original_preB_freeze", False)
        if allpre is not None:
            self.reference(allpre["preserved_V3_record"])
            self.check("allpre_same_preB153", pre is not None and allpre["five_recipe_decisions"] == pre["decisions"] and allpre["owner_pid"] == self.owner and allpre.get("all_current_choices_before_B") is True)
            self.check("allpre_before_B_START", bstart is None or allpre["created_unix"] < bstart)
            beta = allpre["independent_continuous_extension"]
            means = beta["continuous_decisions"]
            grids = beta["fixed_axis_controls"]
            stage["Beta12mean_5grid"] = "ORIGINAL_SAVED"
            self.check("Beta_original12means5grid", len(means) == 12 and set(grids) == set(GRID) and beta.get("all_choices_before_any_B_result") is True)
            c = beta["actual_counts"]
            self.check("Beta_actual12forward_deepcopies_no_fit_restore_rng", c.get("deploy_mean_entry") == c.get("logical_policy_deepcopies") == 12 and all(c.get(k) == 0 for k in ("restore", "BetaArm_constructor", "initialize", "RNG_draws", "fit_gradient_or_update", "new_physics")))
            catalog = beta["full_recipe_catalog"]
            for h, item in catalog.items():
                self.check("Beta_catalog_full_recipe_action:" + h, digest(item["full_recipe"]) == h and item["full_recipe"]["action"] == item["actual_action"] and digest(item["actual_action"]) == item["physical_action_sha256"])
            plan = {x["tag"]: x for x in allpre["continuous_execution_plan"]}
            self.check("Beta_unique_physical_plan_tags", len(plan) == len(allpre["continuous_execution_plan"]))
            self.check("Beta_first_paid_L100_repeat", allpre["continuous_execution_plan"][0]["tag"] == "BETA_AXIS_L100_REPEAT" and allpre["continuous_execution_plan"][0].get("repeat_of") == "EARLY_H150")
            for name, dec in list(means.items()) + list(grids.items()):
                alias = allpre["continuous_exact_recipe_aliases"].get(name)
                corealias = allpre["explicit_core_alias_or_B_fallback"].get(name)
                h = dec.get("full_recipe_sha256")
                self.check("Beta_single_execution_mapping:" + name, (alias is not None) != (corealias is not None))
                tag = alias if alias is not None else (corealias or {}).get("tag")
                if h is None:
                    fallback = dec.get("fallback_core", {})
                    self.check("Beta_explicit_reject_B_fallback:" + name, tag == "B" and fallback.get("tag") == "B" and fallback.get("recipe_sha256") == hashes[0] and fallback.get("action") == menu[0]["action"])
                else:
                    self.check("Beta_decision_catalog_binding:" + name, h in catalog and dec.get("proposal_action") == catalog[h]["actual_action"])
                    if alias is not None:
                        self.check("Beta_exact_plan_binding:" + name, alias in plan and plan[alias]["full_recipe_sha256"] == h and plan[alias]["full_recipe"] == catalog[h]["full_recipe"] and plan[alias]["action"] == catalog[h]["actual_action"])
                    else:
                        self.check("Beta_exact_core_alias_binding:" + name, tag in CORE and h == hashes[CORE.index(tag)] and catalog[h]["full_recipe"] == menu[CORE.index(tag)])
                append_choice("BETA_CONTINUOUS_MEAN" if name in means else "BETA_FIXED_AXIS", name, tag, h, h is None, h is None)
            for tag, planrow in plan.items():
                actual = self.attempt(tag)
                if actual.get("original_action") is not None:
                    self.check("Beta_applied_exact_action:" + tag, actual["original_action"] == planrow["action"])
            if link is not None:
                self.check("final_V4_same_Beta_frozen_choices", link["continuous_decisions_and_fixed_grid"] == beta)
        elif bstart is not None:
            # Preserve root-approved gated absence explicitly; do not impute 0 calls.
            stage["Beta12mean_5grid"] = "EXPECTED_GATED_NOT_RUN" if not nominal else "UNKNOWN_ORIGINAL_GATED_ABSENCE"
            self.unknown("Beta_frozen_record_absent", "缺保存 Beta freeze；若原 B 前提不通过则保留 gated absence，仍不能从 B 资格反推未存的原内部 forward 为 0")
        if history is not None:
            stage["post_B5"] = "ORIGINAL_SAVED"
            self.check("C_original_postB_scope_and_permissions", history.get("B_complete_before_selection") is True and history.get("scope") == "COLD_REPLAY_NOT_CONTINUOUS_TRIAL" and set(history["decisions"]) == set(HISTORY) and b.get("complete") is True and b.get("qualified") is True)
            for label, dec in history["decisions"].items():
                h = dec.get("selected_recipe_sha256")
                tag = byhash.get(h)
                self.check("C_three_recipe_permission:" + label, h in hashes[:3] and dec.get("selected_tag") == tag)
                append_choice("C_THREE_RECIPE_POST_B_COLD_REPLAY", label, "HISTORY_B" if tag == "B" else tag, h)
            for item in inference["receipts"]:
                if item["label"].startswith("C_"):
                    start = next((x["record"] for x in inference["events"] if x["record"].get("event") == "START" and x["record"].get("label") == item["label"]), {})
                    self.check("C_START_strictly_after_original_B_END:" + item["label"], bend is not None and start.get("unix", float("-inf")) >= bend)
                    name = item["label"].removeprefix("C_")
                    self.check("C_saved_original_return_parity:" + name, history["decisions"].get(name) == item["original_return"])
            source_binding = self.load("predictions/" + g + "_HISTORY_MODULE_SOURCE_BINDING.json", optional=True)
            if source_binding is None:
                self.check("C_saved_actual_module_binding_present", False)
            else:
                self.check("C_source_binding_owner_no_extra_modelcalls", source_binding.get("owner_pid") == self.owner and source_binding.get("new_model_calls") == 0)
                for rel, src in source_binding["actual_modules"].items():
                    self.check("C_actual_source_pin:" + rel, src["actual_loaded_path"] == str(self.path(rel)) and src["sha256"] == self.sha(rel) == self.config["frozen_artifacts"].get(rel) == self.job["files"].get(rel))
        else:
            stage["post_B5"] = "EXPECTED_GATED_NOT_RUN" if not nominal else "UNKNOWN_ABSENT_DESPITE_NOMINAL_B_PREREQUISITES"
            if nominal:
                self.unknown("C5_not_saved", "B 原完整/合格/hardFalse；仍须原错误解释，没有伪造 C 输出")
        for tag, recipe in zip(CORE, menu):
            actual = self.attempt(tag)
            if actual.get("original_action") is not None:
                self.check("core_applied_exact_recipe_action:" + tag, actual["original_action"] == recipe["action"])
        if corelink is not None:
            self.check("core_final_link_choices_exact", pre is not None and corelink["decisions"] == pre["decisions"] and (history is None or corelink["history_decisions"] == history["decisions"]) and corelink["counts"]["new_fit"] == 0)
        if link is not None:
            self.check("V4_no_fit_reselection_original_flags", link.get("new_training") is False and link.get("no_outcome_based_reselection") is True and link["counts"].get("new_fit") == 0)
            for tag, record in link.get("original_partial_errors_and_paid_work", {}).items():
                original = self.attempt(tag)
                self.reference(record["original_result"])
                self.check("composer_branch_original_result_state:" + tag, record.get("complete") == original.get("complete") and record.get("qualified") == original.get("qualified") and record.get("true_hard_safety_violation") is original.get("true_hard_safety_violation"))
        for tag in list(self.rows):
            record = self.load("analysis/" + g + "_V4_BRANCH_" + tag + ".json", optional=True)
            if record is None:
                continue
            self.reference(record["original_result"])
            for kind, evidence in record.get("original_events", {}).items():
                actual = self.event_map.get(g + "_" + tag, {}).get(kind, {})
                self.check("branch_record_actual_scoped_event_line:" + tag + ":" + kind, evidence.get("record") == actual.get("record") and evidence.get("raw_line_without_newline_sha256") == actual.get("raw_line_without_newline_sha256"))
            self.check("branch_original_row_exact:" + tag, record.get("original_row") == self.load("attempts/" + g + "_" + tag + "_RESULT.json"))
            self.embedded_refs(record, "branch:" + tag)
        mapping_gate = self.load("analysis/" + g + "_V4_CONTINUOUS_MAPPING_GATE.json", optional=True)
        if mapping_gate is not None:
            self.embedded_refs(mapping_gate, "original_continuous_mapping_gate_not_new_raw_replay")
            if mapping_gate.get("raw_gate"):
                self.reference(mapping_gate["raw_gate"])
        if history is not None and any(d.get("selected_tag") == "B" for d in history["decisions"].values()):
            original = self.attempt("HISTORY_B")
            self.check("C_B_choice_has_separate_HISTORY_B_START", "START" in self.event_map.get(g + "_HISTORY_B", {}))
            if original.get("original_action") is not None:
                self.check("HISTORY_B_exact_action", original["original_action"] == menu[0]["action"])
        for label, doc in (("preB153", pre), ("allpreB", allpre), ("postB5", history), ("finalV4", link), ("finalCore", corelink)):
            if doc is not None:
                self.embedded_refs(doc, label)
        return {"stage_status": stage, "nominal_B_complete_qualified_hardFalse": nominal, "choice_table": table, "core5_all_complete": all(self.attempt(t).get("complete") is True for t in CORE), "continuous_plan_all_complete": all(self.attempt(x["tag"]).get("complete") is True for x in allpre["continuous_execution_plan"]) if allpre else False, "original_allpre_Beta_counts": allpre["independent_continuous_extension"]["actual_counts"] if allpre else "UNKNOWN_OR_NOT_RUN_NO_ZERO_IMPUTATION", "original_final_V4": link, "original_final_core": corelink}

    def parent_paid(self):
        # Read original small native-counter metadata only; never count inherited suffixes.
        values = []
        for suffix in ("DATA", "PARTIAL_COMPUTE"):
            rel = "runtime/output/" + self.g + "_parent_" + suffix + ".json"
            doc = self.load(rel, optional=True)
            if doc is not None:
                metric = doc.get("metric", doc)
                values.append({"path": rel, "sha256": self.sha(rel), "counter_scope": "metric" if "metric" in doc else "top_level", "status": doc.get("status"), "valid": doc.get("valid", metric.get("task_valid")), "actual_new_native_physics_steps": metric.get("actual_new_native_physics_steps"), "native_physics_steps_total_may_include_prefix": metric.get("native_physics_steps"), "actual_new_simulation_seconds": metric.get("actual_new_simulation_seconds"), "actual_new_main_model_inverse_dynamics_api_calls": metric.get("actual_new_main_model_inverse_dynamics_api_calls")})
        if len(values) != 1:
            self.unknown("parent_actual_increment", "原 DATA/PARTIAL 数量不是恰好一份；保留各原计数，不擅合并或填 0")
        return values

    def run(self):
        closed = self.closure()
        skipped = self.pins()
        physical = self.physical_events()
        infer = self.inference()
        menu, hashes = self.menu()
        choices = self.decisions(infer, menu, hashes)
        # Include any paid child that has no selector mapping, still preserving costs.
        for ident in self.event_map:
            if ident != self.g + "_parent":
                self.attempt(ident.removeprefix(self.g + "_"))
        parent = self.parent_paid()
        originals = []
        for item in infer["receipts"]:
            row = {k: v for k, v in item.items() if k != "original_return"}
            originals.append(row)
        bc = []
        for item in self.config["comparative_validation"]["BC_aggregation_bundles"]:
            # Metadata inspection of immutable JSON only: no policy module/init/restore.
            doc = self.load(item["path"])
            bc.append({"label": item["label"], "path": item["path"], "kind": doc.get("bundle", {}).get("model", {}).get("kind"), "returned": any(x["label"] == item["label"] for x in infer["receipts"])})
        returned_linear = sum(x["kind"] == "BC_LINEAR" and x["returned"] for x in bc)
        failures = [x for x in self.checks if not x["PASS"]]
        nominal_complete = choices["nominal_B_complete_qualified_hardFalse"] and choices["core5_all_complete"] and choices["continuous_plan_all_complete"] and choices["stage_status"] == {"pre_B153": "ORIGINAL_SAVED", "post_B5": "ORIGINAL_SAVED", "Beta12mean_5grid": "ORIGINAL_SAVED"} and self.end.get("worker_exit_code") == 0 and all(r.get("true_hard_safety_violation") is False for r in self.rows.values() if r.get("complete") is True)
        known_new = [x["actual_new_native_steps"] for x in self.rows.values() if isinstance(x.get("actual_new_native_steps"), int)]
        return {"schema": "v8.closed_inference_receipt_metadata_audit.v1", "status": "METADATA_INCONSISTENCY_REQUIRES_MAIN_REVIEW" if failures else "METADATA_LINKS_PASS_NOMINAL_COMPLETION_NOT_RAW_REPLAY" if nominal_complete else "METADATA_LINKS_AUDITED_GATED_OR_FAILED_NOT_FULL_INTEGRATION_PASS", "group": self.g, "created_unix": time.time(), "approval": self.approval, "config_sha256": self.config_sha, "job_source_manifest_sha256": self.job_sha, "owner_closure": closed, "original_supervisor_END": self.end, "checks": self.checks, "failed_checks": failures, "unknowns": self.unknowns, "case_payload_hash_scope": skipped, "original_physical_scoped_event_evidence": physical, "original_inference_event_evidence": infer["events"], "macro_core_API_counts_original_events": {"started": infer["API_started"], "returned": infer["API_returned"], "entered_unreturned_API": infer["entered_unreturned_API"]}, "grade_A_original_percall_recorded_nested_counts": originals, "grade_B_source_derived_not_independent_original_counters": {"basis_core_source": {"path": CORE_SOURCE, "sha256": CORE_SOURCE_SHA}, "BC_frozen_metadata_kinds": bc, "returned_BC_LINEAR_internal_categorical_calls": returned_linear, "returned_BC_LINEAR_internal_policy_restore_calls": 2 * returned_linear, "basis": "固定 select_out0 的 BC_LINEAR 返回路径；并非额外调用，也非逐次内部原 counter。缺 RETURN 的工作不由此推为 0。", "not_summed_with_grade_A_duplicate_payloads": True}, "unrecorded_nested_operations": "UNKNOWN_NOT_ZERO; 只有原回执明确字段可列 actual，总restore/forward不能用composer自身0覆盖", "original_error_and_paid_prefix_receipts": infer["original_error_or_owner_close"], "decision_alignment": choices, "unique_original_child_attempts": list(self.rows.values()), "paid_native_metadata": {"parent_original_increment_records": parent, "child_known_actual_new_native_steps_sum_lower_bound": sum(known_new), "child_unknown_increment_tags": [t for t, r in self.rows.items() if r.get("actual_new_native_steps") is None and r.get("status") != "NOT_RUN_NO_ORIGINAL_START"], "inherited_prefixes_not_added": True, "no_raw_recomputation": True}, "references_sha256": self.refs, "scope_limits": ["仅核原保存 metadata/source/digests；不执行 scorer replay 或 raw compare", "原 SOURCE proof 代表已死原进程的记录，审计不伪造 live in-memory proof", "case payload 不打开，case SHA 只由精确 config/job SOURCE 绑定", "partial/engineering 资格失败与完整 motion 不合格都不改为成功；partial JF/JM 不排名", "C 仅 B 后 COLD_REPLAY，选择 B 对齐单独 HISTORY_B；共享 recipe 不计独立 rollout/省物理", "合法 gated absence 可为 NOT_RUN；已进入失败 API 的内部付费工作缺失为 UNKNOWN", "所有 child 与 parent 原增量单列；原总计数的继承 prefix 不重复计账", "本结果不创建取消/发布/部署/训练/物理授权"], "operations": {"candidate_or_model_or_scorer_imports_calls": 0, "initialize_restore_forward_fit_physics": 0, "raw_trace_replay_reads_calls": 0, "CURRENT_pending_config_or_run_mutations": 0}, "resource": {"PID": os.getpid(), "identity": stat_identity(os.getpid()), "actual_affinity": sorted(os.sched_getaffinity(0)), "elapsed_wall_s": time.monotonic() - self.mono, "CPU_s": time.process_time() - self.cpu, "peak_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "metadata_source_bytes_read": self.bytes_read, "file_opens": self.opens, "expires_unix": self.deadline}}


def put_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--group", choices=sorted(GROUPS), required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    authority = args.approval.resolve()
    output = args.output.resolve()
    # Reading the one main approval is unavoidable before Audit exists; never create it here.
    approval_bytes = authority.read_bytes()
    approval = json.loads(approval_bytes)
    own_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if approval.get("status") != "APPROVED_BY_MAIN_AGENT_FOR_CLOSED_INFERENCE_RECEIPT_METADATA_AUDIT_V1" or approval.get("group") != args.group or approval.get("helper_sha256") != own_sha:
        raise ValueError("NO_EXACT_MAIN_AUTHORITY_FOR_THIS_SOURCE_AND_GROUP")
    if approval.get("config_sha256") != GROUPS[args.group] or approval.get("global_stop_unix") != GLOBAL_STOP or approval.get("model_scorer_physics_authorized") is not False:
        raise ValueError("MAIN_APPROVAL_SCOPE_OR_GLOBAL_CLOCK_MISMATCH")
    contract_path = Path(__file__).with_name("SOURCE_ONLY_AUDIT_CONTRACT_V1.json")
    if approval.get("contract_path") != str(contract_path.relative_to(package)) or hashlib.sha256(contract_path.read_bytes()).hexdigest() != approval.get("contract_sha256"):
        raise ValueError("MAIN_APPROVAL_MUST_BIND_EXACT_AUDIT_CONTRACT")
    now = time.time()
    if not (approval["issued_unix"] <= now < approval["expires_unix"] <= min(approval["issued_unix"] + 60.0, GLOBAL_STOP)):
        raise ValueError("EXPIRED_OR_RESET_AUDIT_CLOCK")
    if not output.is_relative_to(package / SCOPE) or str(output) != approval.get("output_absolute_path"):
        raise ValueError("OWNED_UNIQUE_OUTPUT_SCOPE_REQUIRED")
    if len(os.sched_getaffinity(0)) != 1 or resource.getrlimit(resource.RLIMIT_AS)[0] > 1024 ** 3 or resource.getrlimit(resource.RLIMIT_AS)[0] <= 0:
        raise ValueError("EXTERNAL_AFFINITY1_AS1G_REQUIRED")
    if any(os.environ.get(name) != "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")) or not sys.dont_write_bytecode:
        raise ValueError("FIVE_THREAD_ENV1_AND_B_REQUIRED")
    output.mkdir(parents=True, exist_ok=False)
    audit = Audit(package, args.group, approval, output)
    start = {"PID": os.getpid(), "identity": stat_identity(os.getpid()), "launch_unix": now, "approval_path": str(authority), "approval_sha256": hashlib.sha256(approval_bytes).hexdigest(), "helper_sha256": own_sha, "python_executable": sys.executable, "python_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)), "RLIMIT_AS": list(resource.getrlimit(resource.RLIMIT_AS)), "expires_unix": approval["expires_unix"], "operations_authorized": "METADATA_ONLY_NO_RAW_MODEL_SCORER_OR_PHYSICS"}
    start["actual_python_binary"] = str(Path(sys.executable).resolve())
    start["actual_python_binary_sha256"] = hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()
    start["NumPy_SciPy"] = "NOT_IMPORTED_STDLIB_ONLY"
    put_new(output / "START.json", start)
    try:
        result = audit.run()
        result["embedded_refs_not_opened_by_scope"] = audit.reference_exclusions
        table = result["decision_alignment"]["choice_table"]
        paid_tags = [ident.removeprefix(args.group + "_") for ident, ev in audit.event_map.items() if ident != args.group + "_parent" and "START" in ev]
        result["concise_counts"] = {
            "core_macro_API_started_returned_original_events": result["macro_core_API_counts_original_events"],
            "saved_logical_choice_rows_by_permission_not_model_API_calls": {scope: sum(row["permission"] == scope for row in table) for scope in ("CORE_FIVE_RECIPE_PRE_B", "C_THREE_RECIPE_POST_B_COLD_REPLAY", "BETA_CONTINUOUS_MEAN", "BETA_FIXED_AXIS")},
            "original_unique_paid_child_STARTs": len(paid_tags),
            "original_paid_child_tags": paid_tags,
            "original_complete_child_count": sum(audit.rows.get(t, {}).get("complete") is True for t in paid_tags),
            "original_complete_qualified_child_count": sum(audit.rows.get(t, {}).get("complete") is True and audit.rows.get(t, {}).get("qualified") is True for t in paid_tags),
            "partial_or_missing_original_child_tags": [t for t in paid_tags if audit.rows.get(t, {}).get("complete") is not True],
            "helper_model_scorer_fit_physics_calls": 0,
            "shared_aliases_not_independent_rollout_or_physics_savings": True,
        }
    except BaseException as error:
        put_new(output / "FAILED_PAID_METADATA_PREFIX.json", {"status": "FAILED_STOP_NO_AUTOMATIC_RETRY", "error_type": type(error).__name__, "error": str(error), "checks": audit.checks, "unknowns": audit.unknowns, "references_sha256": audit.refs, "resource": {"PID": os.getpid(), "wall_s": time.monotonic() - audit.mono, "CPU_s": time.process_time() - audit.cpu, "peak_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "bytes_read": audit.bytes_read}, "new_model_scorer_physics_calls": 0})
        raise
    put_new(output / "RESULT.json", result)
    lines = ["# 闭合 inference receipt metadata 审计", "", result["status"], "", "只核原保存证据，不是 raw/scorer replay；缺失付费内部工作为 UNKNOWN。", "", "```json", json.dumps(result["concise_counts"], ensure_ascii=False, indent=2), "```", "", "| 权限 | selector | 原实际 tag | 原状态 | 原 qualified | JF | JM |", "|---|---|---|---|---|---|---|"]
    for row in result["decision_alignment"]["choice_table"]:
        cells = [row.get(k) for k in ("permission", "selector", "selected_tag", "status", "qualified", "JF", "JM")]
        lines.append("| " + " | ".join("UNKNOWN" if v is None else str(v).replace("|", "\\|") for v in cells) + " |")
    with (output / "REPORT.md").open("x") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    manifest = {"schema": "v8.metadata_audit_actual_manifest.v1", "group": args.group, "created_unix": time.time(), "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}, "input_references_sha256": audit.refs, "audit_PID_requires_external_postexit_closure": os.getpid(), "no_current_or_other_output_mutation": True}
    put_new(output / "ACTUAL_MANIFEST.json", manifest)
    print(json.dumps({"status": result["status"], "failed_checks": len(result["failed_checks"]), "RESULT_sha256": hashlib.sha256((output / "RESULT.json").read_bytes()).hexdigest(), "PID": os.getpid()}, ensure_ascii=False))
    return 1 if result["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
