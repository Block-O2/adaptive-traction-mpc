"""Restart-safe four-case DEV-B diagnostic batch; no qualification."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import traceback
from dev_b_matched_diagnostics_v1 import ROOT, capture, analyze, save_json, sha


def main():
    base=ROOT/"results/full3d_adaptive_integration_v1"
    output=base/"dev_b_first_divergence_v1/capture_v3"
    cases=["balanced_near_upper_current_rom_r01","balanced_ordinary_r01","balanced_middle_r01","development_nominal"]
    branches=["retained_model","activated_model","activated_duplicate","new_model_old_estimate",
              "old_model_new_estimate","diagnostic_action_transfer_100ms"]
    done=[]
    def status(active):
        save_json(output/"BATCH_STATUS.json",{"schema":"DEV_B_DEVELOPMENT_ONLY","argv":sys.argv,
            "completed":done,"active":active,"remaining":[x for x in cases if x not in done],
            "script_sha256":sha(__file__)})
    for key in cases:
        status(key)
        if key=="development_nominal":
            case=ROOT/"configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json"
            historical=base/"dev_a_recovery_v1/nominal_development_v2"
        else:
            case=base/"fresh_qualification_v1/formal_case_bundle_v1/cases"/(key+".json")
            historical=base/"dev_a_recovery_v1/regression_v2"/key
        dest=output/key
        if not (dest/"capture_manifest.json").exists():
            capture(case,historical,dest)
        if not (dest/"analysis_0200ms/historical_replay_validation.json").exists():
            analyze(dest,0.2,branches)
        validation=json.loads((dest/"analysis_0200ms/clone_validation.json").read_text())
        if not validation["duplicate_physics_exact"]:
            raise AssertionError("incomplete or invalid duplicate replay")
        done.append(key)
        status(None)
    status("COMPLETE")


if __name__=="__main__":
    try:
        main()
    except Exception:
        save_json(ROOT/"results/full3d_adaptive_integration_v1/dev_b_first_divergence_v1/BATCH_FAILURE.json",
            {"argv":sys.argv,"traceback":traceback.format_exc()})
        raise
