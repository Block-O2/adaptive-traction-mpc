"""Sequential, single-writer launcher for pre-registered simulation cases."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
from freeze_tools import check_source

ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/"stages/stage5_personalized_motion_learning"
DOC=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--stage",choices=("representative","development49"),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--count",type=int,required=True)
    args=p.parse_args()
    manifest=json.loads((DOC/"PREREGISTRATION.json").read_text())
    rows=manifest[args.stage]
    assert check_source()==manifest["source_fingerprint"]
    for row in rows[args.start:args.start+args.count]:
        assert check_source()==manifest["source_fingerprint"]
        output=STAGE/"results/simulation_research_baseline_v1"/args.stage/row["id"]
        command=[sys.executable,str(STAGE/"scripts/high_rom_v1/run_dev_case.py"),
                 "--plant-mode",row["plant"],"--case",str(ROOT/row["case"]),
                 "--output",str(output),"--host-monitor-limit-s","300"]
        run=subprocess.run(command,env=os.environ.copy(),capture_output=True,text=True)
        print("RUN",row["id"],run.returncode,run.stdout[-500:],run.stderr[-400:],flush=True)
        if run.returncode: raise SystemExit("runner process failed; retain original")
        scored=subprocess.run([sys.executable,str(DOC/"freeze_tools.py"),"score",
                               "--stage",args.stage,"--id",row["id"]],
                              env=os.environ.copy(),capture_output=True,text=True)
        print("SCORE",row["id"],scored.returncode,scored.stdout[-500:],scored.stderr[-400:],flush=True)
        if scored.returncode: raise SystemExit("scorer process failed; retain original")
        record=json.loads((DOC/"cases"/args.stage/(row["id"]+".json")).read_text())
        if not record["pass_all"]: raise SystemExit("frozen case FAIL; stop without replacement")
if __name__=="__main__":main()
