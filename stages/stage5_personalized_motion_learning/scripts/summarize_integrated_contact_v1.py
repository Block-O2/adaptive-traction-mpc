"""Recompute contact metrics, preserve provenance and render review figures."""
from __future__ import annotations
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

STAGE=Path(__file__).resolve().parents[1]
REPO=STAGE.parents[1]
DOCS=STAGE/"docs/full3d_adaptive_integration_v1/integrated_recovery_v1"
OUT=STAGE/"results/full3d_adaptive_integration_v1/integrated_recovery_v1"


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUT/"review_v1")
    output=parser.parse_args().output
    if output.exists():raise FileExistsError(output)
    output.mkdir()
    assembly=json.loads((OUT/"contact_v1/assembly_and_checkpoint.json").read_text())
    baseline=json.loads((DOCS/"BASELINE_MANIFEST.json").read_text())
    changed=[p for p,h in baseline["source_config_asset_sha256"].items() if sha(REPO/p)!=h]
    assert not changed, changed
    assert sha(REPO/baseline["archive"])==baseline["archive_sha256"]
    results=[]; inputs={};fig,axs=plt.subplots(3,3,figsize=(13,8.3),sharex="col")
    keys=("balanced_near_upper_current_rom_r01","balanced_ordinary_r01","development_nominal")
    for col,key in enumerate(keys):
        folder=OUT/"contact_replay_v1"/key
        z=np.load(folder/"executed_contact_intervals.npz",allow_pickle=False);a=z["rows"]
        dt=a[:,1]-a[:,0];t=a[:,0]
        summary=json.loads((folder/"contact_summary.json").read_text())
        assert summary["exact_checkpoint_match"]
        assert np.all(dt>0) and np.allclose(dt,.00025,rtol=0,atol=1e-12)
        assert np.allclose(a[1:,0],a[:-1,1],rtol=0,atol=1e-12)
        assert np.isclose(a[-1,1]-a[0,0],dt.sum(),rtol=0,atol=1e-12)
        for j,name in enumerate(("thigh","shank")):
            value=float(np.dot(dt,a[:,2+2*j]))
            assert np.isclose(value,summary["contacts"][name]["normal_impulse_n_s"],rtol=1e-12,atol=1e-9)
            summary["contacts"][name]["positive_normal_force_duration_s"]=float(dt[a[:,2+2*j]>1e-8].sum())
        results.append(summary)
        for filename in ("executed_contact_intervals.npz","contact_summary.json","capture_manifest.json","checkpoint_mujoco.npz"):
            p=folder/filename;inputs[str(p.relative_to(REPO))]=sha(p)
        axs[0,col].plot(t,a[:,2],color="#9c2633",lw=.8);axs[0,col].set_title(key.replace("balanced_", ""),fontsize=10)
        axs[0,col].set_ylim(0,max(1,float(np.max(a[:,2]))*1.12))
        axs[0,col].ticklabel_format(axis="y",style="plain",useOffset=False)
        axs[1,col].plot(t,a[:,4],color="#237a8c",lw=.8)
        axs[2,col].plot(t,np.degrees(a[:,10]),label="q1",lw=.8)
        axs[2,col].plot(t,np.degrees(a[:,11]),label="q2",lw=.8)
        axs[2,col].set_xlabel("physical interval start (s)");axs[2,col].legend(fontsize=8)
        for row in range(3):axs[row,col].grid(alpha=.2)
    axs[0,0].set_ylabel("thigh normal force (N)")
    axs[1,0].set_ylabel("shank normal force (N)")
    axs[2,0].set_ylabel("true Human q (deg; evaluation)")
    fig.suptitle("Unchanged CR12 physical prefixes: executed-interval contact solves\nSeparate y scales; no new controller or physical model",fontsize=12)
    fig.tight_layout();fig.savefig(output/"contact_timeline.png",dpi=160);plt.close(fig)
    old=json.loads((STAGE/"results/full3d_adaptive_integration_v1/dev_a_recovery_v1/regression_v2/regression_summary_v2.json").read_text())
    oldmap={r["case_key"]:r for r in old["rows"]}; rows=[]
    for c in assembly["old24_initial_geometry"]:
        prior=oldmap[c["case_key"]]
        rows.append({"case_key":c["case_key"],"fixed_proximal_gap_mm":1000*c["immutable_proximal_thigh_gap_m"],
                     "negative_gap":c["immutable_proximal_thigh_gap_m"] < -1e-9,
                     "historical_dev_a_status":prior["status"],"historical_abort_reason":prior["abort_reason"],
                     "historical_task_entered":prior["task_entered"]})
    groups={str(flag):{"count":sum(r["negative_gap"]==flag for r in rows),
                      "historical_complete":sum(r["negative_gap"]==flag and r["historical_dev_a_status"]=="COMPLETE" for r in rows),
                      "historical_task_entered":sum(r["negative_gap"]==flag and r["historical_task_entered"] for r in rows)} for flag in (False,True)}
    save(output/"ANALYSIS.json",{"category":"DEVELOPMENT_CONTACT_VALIDITY_DIAGNOSTIC","executed_prefixes":results,
        "old24_geometry_census":rows,"historical_association_not_causal_groups":groups,
        "baseline_dependency_changes":changed,"new_controller_full_session_results":None,"fresh_qualification":None})
    fig,ax=plt.subplots(figsize=(10,6))
    ax.barh([r["case_key"].replace("near_upper_current_rom","upper") for r in rows],
            [r["fixed_proximal_gap_mm"] for r in rows],color=["#b33445" if r["negative_gap"] else "#287d8e" for r in rows])
    ax.axvline(0,color="black",lw=.7);ax.set_xlabel("fixed proximal thigh-sphere gap to bed (mm)")
    ax.set_title("All 24 consumed cases — static geometry, no exclusion or replacement")
    ax.tick_params(axis="y",labelsize=8);fig.tight_layout();fig.savefig(output/"old24_fixed_hip_gap.png",dpi=160);plt.close(fig)
    scripts=["prepare_integrated_recovery_v1.py","diagnose_integrated_contact_v1.py","replay_integrated_contact_v1.py","summarize_integrated_contact_v1.py"]
    new_sources={str((STAGE/"scripts"/s).relative_to(REPO)):sha(STAGE/"scripts"/s) for s in scripts}
    for p in (STAGE/"configs/full3d_adaptive_integration_v1/integrated_recovery_v1").glob("*.json"):
        new_sources[str(p.relative_to(REPO))]=sha(p)
    patch=[]
    for path in new_sources:
        r=subprocess.run(["git","diff","--no-index","--","/dev/null",path],cwd=REPO,capture_output=True,text=True)
        assert r.returncode==1,r.stderr
        patch.append(r.stdout)
    (output/"new_diagnostic_sources.patch").write_text("\n".join(patch))
    save(DOCS/"EXPERIMENT_MANIFEST.json",{
        "schema":"integrated_recovery_v1_experiment_manifest","command":sys.argv,
        "baseline_manifest":"BASELINE_MANIFEST.json","baseline_dependencies_unchanged":len(baseline["source_config_asset_sha256"]),
        "new_source_sha256":new_sources,"input_output_sha256":inputs,"observed_prefix_count":3,
        "full_controller_revision_count":0,"formal_fresh_episode_count":0,
        "tool_failure":{"attempt":"diagnose_integrated_contact_v1 first invocation","error":"mj_fullM signature mismatch",
                        "resolution":"diagnostic only: use installed MuJoCo signature mj_fullM(model,data,dst); rerun completed",
                        "scientific_outcome":False},
        "checkpoint_caveat":"exact integration-vector match plus capture fields; not a claim of per-interval full-state hash equality",
        "physical_properties_modified":False,"estimator_modified":False,"controller_modified":False,
        "branch":baseline["branch"],"head":baseline["head"],"clean_clone_reproducible":False})
    print(json.dumps({"baseline_dependencies_unchanged":len(baseline["source_config_asset_sha256"]),"old24_groups":groups,"output":str(output)}))


if __name__=="__main__":main()
