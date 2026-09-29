"""Forensic-only exact checkpoint replay; does not modify production controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in ("stages/stage5_personalized_motion_learning/src", "stages/stage4_adaptive_control/src", "stages/stage3_full3d/src", "stages/stage5_personalized_motion_learning/scripts/high_rom_v1"):
    sys.path.insert(0, str(ROOT / relative))
from zero_value_30rep_checkpoint import load_checkpoint
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import advance_inter_rep_boundary, run_executed_case, _jsonable

FORMAL = STAGE / "results/zero_value_30rep_baseline_v2/formal_session_02"
OUTPUT = STAGE / "results/rep14_clearance_forensic_v1"
CASE = STAGE / "configs/high_rom_v1/low_rom_regression_cases/balanced_ordinary_r01.json"
OPTIONS = STAGE / "configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json"
BASELINE = STAGE / "docs/scientific_execution_architecture_v1/WSL_LEARNING_SCIENTIFIC_BASELINE.json"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True, allow_nan=False) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-index", type=int, default=1)
    args = parser.parse_args()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        assert os.environ.get(key) == "1", key
    prov = json.loads((FORMAL / "session_provenance.json").read_text())
    baseline = json.loads(BASELINE.read_text())
    assert prov["session_seed"] == 20260918
    assert prov["frozen_production_fingerprint"] == baseline["production_fingerprint"]
    assert sha(CASE) == prov["case_sha256"]
    assert sha(OPTIONS) == prov["options_sha256"]
    assert hashlib.sha256((sha(CASE) + sha(OPTIONS)).encode()).hexdigest() == prov["config_hash"]
    source = prov["source_file_sha256"]
    assert sha(STAGE / "src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py") == source["runtime"]
    assert sha(STAGE / "src/traction_mpc_stage5/full3d_adaptive_integration_v1/session_state.py") == source["session_state"]
    assert sha(STAGE / "scripts/high_rom_v1/run_zero_value_30rep_baseline_v2.py") == source["harness"]
    manifest = json.loads((FORMAL / "session_checkpoints_manifest.json").read_text())
    receipt = next(x for x in manifest if x["repetition_index"] == 13)
    checkpoint = FORMAL / receipt["path"]
    assert sha(checkpoint) == receipt["sha256"]
    assert sha(FORMAL / "session_provenance.json") == receipt["provenance_sha256"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for i in (args.start_index, args.start_index + 1):
        replay = OUTPUT / f"replay_{i:02d}"
        if replay.exists():
            raise FileExistsError(replay)
        replay.mkdir()
        context, rows = load_checkpoint(checkpoint, receipt["sha256"], receipt["provenance_sha256"])
        assert len(rows) == 13 and context["repetition_index"] == 13
        pre = {"repetition_index": context["repetition_index"], "end_time_s": context["end_time_s"],
               "updater_sequence": context["updater"].sequence, "model": context["final_belief"].value_state_record(),
               "physical_time_s": float(context["runtime"]["plant"].data.time)}
        save(replay / "restored_state.json", pre)
        boundary = advance_inter_rep_boundary(context, max_wait_s=2.0, stop_check=lambda: None)
        save(replay / "boundary_13_to_14.json", boundary)
        summary = run_executed_case(replay / "rep_14", qualification_case=json.loads(CASE.read_text()),
            qualification_arm="continual_adaptive", simulate_planning_latency=True,
            formal_qualification=False, dev_a_recovery=True, dev_c_bumpless_transfer=False,
            dev_d_rigid_table_reference=True, autonomous_recovery_options=json.loads(OPTIONS.read_text()),
            task_timeout_s=30.0, runtime_capture={"stop_check": lambda: None},
            execution_mode="SCIENTIFIC_SIMULATION", scientific_host_delay_s=0.0,
            session_context=context)
        save(replay / "replay_result.json", {"status": summary["status"], "abort_reason": summary.get("abort_reason"),
            "checkpoint_sha256": receipt["sha256"], "provenance_sha256": receipt["provenance_sha256"],
            "source_sha256": source, "case_sha256": sha(CASE), "options_sha256": sha(OPTIONS),
            "production_fingerprint": prov["frozen_production_fingerprint"]})
        print(i, summary["status"], summary.get("abort_reason"), flush=True)

if __name__ == "__main__":
    main()
