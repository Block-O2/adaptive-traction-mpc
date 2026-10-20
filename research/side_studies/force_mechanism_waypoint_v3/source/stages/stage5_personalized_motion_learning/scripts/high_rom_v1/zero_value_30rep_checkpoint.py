"""Crash-recoverable end-of-repetition snapshot for the frozen zero-value session.

Only the contracted persistent runtime fields are serialized. A small terminal
stub supplies the already-closed episode facts needed by the boundary gate.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pickle
from types import SimpleNamespace
import zlib

from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import carryover_runtime_fields


class _ReferenceHistory:
    def __init__(self, final_reference):
        self.final_reference = final_reference

    def last_reference(self):
        return self.final_reference


def snapshot(context: dict, rows: list[dict], provenance_sha256: str) -> dict:
    old = context["runtime"]
    if old["wall_session"].active or old["plan_lifecycle"]._outstanding is not None:
        raise RuntimeError("cannot checkpoint an open episode")
    terminal = dict(carryover_runtime_fields(old))
    terminal.update({
        "wall_session": SimpleNamespace(active=False),
        "plan_lifecycle": SimpleNamespace(_outstanding=None),
        "trace": [{"ddq_ref_rad_s2": old["trace"][-1]["ddq_ref_rad_s2"]}],
        "contract": SimpleNamespace(reference_motion_history=_ReferenceHistory(
            old["contract"].reference_motion_history.last_reference())),
        "autonomous_recovery_options": old["autonomous_recovery_options"],
    })
    # These keys are present only for the fresh-object lifecycle audit. Their
    # values are never used as control inputs after an episode has closed.
    for key in ("supervisor", "monitor", "authority", "true_physics_monitor",
                "task_decisions"):
        terminal[key] = SimpleNamespace()
    return {
        "schema": "zero_value_30rep_checkpoint_v1",
        "session_id": rows[-1]["session_id"],
        "completed_repetitions": len(rows),
        "provenance_sha256": provenance_sha256,
        "rows": rows,
        "context": {key: context[key] for key in (
            "updater", "fit", "spec", "config", "repetition_index",
            "end_time_s", "final_belief")},
        "runtime": terminal,
    }


def save_checkpoint(path: Path, context: dict, rows: list[dict], provenance_sha256: str) -> dict:
    value = snapshot(context, rows, provenance_sha256)
    payload = zlib.compress(pickle.dumps(value, protocol=5), level=6)
    digest = hashlib.sha256(payload).hexdigest()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)
    return {"repetition_index": len(rows), "path": path.name,
            "sha256": digest, "compressed_bytes": len(payload),
            "provenance_sha256": provenance_sha256}


def load_checkpoint(path: Path, expected_sha256: str, provenance_sha256: str) -> tuple[dict, list]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError("checkpoint hash mismatch")
    value = pickle.loads(zlib.decompress(payload))
    if value["schema"] != "zero_value_30rep_checkpoint_v1":
        raise RuntimeError("checkpoint schema mismatch")
    if value["provenance_sha256"] != provenance_sha256:
        raise RuntimeError("checkpoint provenance mismatch")
    if value["completed_repetitions"] != len(value["rows"]):
        raise RuntimeError("checkpoint repetition count mismatch")
    context = value["context"]
    context["runtime"] = value["runtime"]
    return context, value["rows"]
