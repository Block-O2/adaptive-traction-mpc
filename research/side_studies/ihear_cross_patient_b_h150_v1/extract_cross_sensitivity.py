"""Pure-offline patient sensitivity snapshot; JSON only, no simulator imports.

Preserves all preregistered identities, including absent and failed evidence.
No gate, controller, criterion, trajectory or physical outcome is recomputed.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
sys.dont_write_bytecode = True


def mean_or_none(values):
    return statistics.mean(values) if values else None


def difference(a, b):
    if a is None or b is None: return None
    if isinstance(a, list) and isinstance(b, list):
        return [difference(x,y) for x,y in zip(a,b)] if len(a)==len(b) else None
    if isinstance(a, (float,int)) and isinstance(b, (float,int)):
        return a-b if math.isfinite(a) and math.isfinite(b) else None
    return None


def extract(package):
    p=Path(package).resolve();sources={};warnings=[]
    def read(rel, default=None):
        path=p/rel
        if not path.exists():return default
        raw=path.read_bytes()
        try:value=json.loads(raw)
        except ValueError as e:warnings.append({"path":rel,"error":str(e)});return default
        sources[rel]={"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
        return value
    cohort=read("VIRTUAL_PATIENT_COHORT.json",{});patients=cohort.get("patients",[])
    static={r["patient_id"]:r for r in read("STATIC_PATIENT_AUDIT.json",{}).get("records",[])}
    if not patients:raise ValueError("Registered patient cohort required")
    rows=[]
    for patient in patients:
        pid=patient["patient_id"];pair=read(pid+"_COMPARISON.json",{});done=read(pid+"_DONE.json",{})
        parent=read(pid+"_PARENT_RESULT.json",{});arms={}
        for arm in ("B","H150"):
            ev=pair.get(arm) or read("reports/"+pid+"_"+arm+"_CROSS_EVALUATION.json",{})
            measured=read(ev["measured_path"],{}) if ev.get("measured_path") else {}
            motion=ev.get("motion_extra") or {};axes=ev.get("axes",{})
            arms[arm]={"qualification":ev.get("qualification","NOT_EVALUATED"),"labels":ev.get("labels",[]),
                "complete_task":ev.get("complete_task"),"integration":ev.get("integration","NOT_EVALUATED"),
                "task":axes.get("task","NOT_EVALUATED"),"absolute_safety":axes.get("absolute_safety","NOT_EVALUATED"),
                "causal_execution":axes.get("causal_execution","NOT_EVALUATED"),
                "absolute_task_execution_qualified":ev.get("absolute_task_execution_qualified"),
                "J_F_N_s":ev.get("J_F_N_s"),"moment_integral_Nm_s":ev.get("moment_integral_Nm_s"),
                "force_peak_N":measured.get("force_peak_N"),"moment_peak_Nm":measured.get("moment_peak_Nm"),
                "tracking_RMS_deg":measured.get("tracking_RMS_deg"),
                "true_excursion_deg":measured.get("dose",{}).get("excursion_deg"),
                "true_return_undershoot_from_issued_reference_deg":motion.get("return_undershoot_deg"),
                "true_outbound_overshoot_from_issued_reference_deg":motion.get("outbound_overshoot_deg"),
                "true_return_undershoot_from_nominal_target_deg":motion.get("return_undershoot_from_nominal_start_deg"),
                "actual_endpoint_deg":motion.get("actual_endpoint_deg"),
                "final_issued_return_reference_deg":motion.get("final_issued_return_reference_deg"),
                "return_terminal_error_from_issued_reference_deg":motion.get("return_terminal_error_from_issued_reference_deg"),
                "velocity_total_variation_deg_s":motion.get("velocity_total_variation_deg_s"),
                "acceleration_total_variation_deg_s2":motion.get("acceleration_total_variation_deg_s2"),
                "true_motion_raw":measured.get("motion",{}).get("raw"),
                "phase_durations":ev.get("phase_durations"),"phase_cost":ev.get("phase_cost"),
                "observed_prefix":ev.get("observed_prefix"),"abort_reason":ev.get("abort_reason"),
                "intervention_status":ev.get("interventions",{}).get("status"),
                "failed_safety_checks":[k for k,v in axes.get("absolute_safety_checks",{}).items() if v is False],
                "failed_task_checks":[k for k,v in axes.get("task_checks",{}).items() if v is False],
                "failed_execution_checks":[k for k,v in axes.get("causal_execution_checks",{}).items() if v is False]}
        physical=patient["physical"];h=physical["height_m"];m=physical["body_mass_kg"]
        l1=.254*h*physical["thigh_length_scale"];l2=.233*h*physical["shank_length_scale"]
        m1=.099*m*physical["thigh_mass_scale"];m2=.060*m*physical["shank_mass_scale"]
        resolved={"thigh_length_m":l1,"shank_length_m":l2,"thigh_mass_kg":m1,"shank_mass_kg":m2,
            "total_leg_mass_kg":m1+m2,"thigh_com_m":physical["thigh_com_fraction"]*l1,
            "shank_com_m":physical["shank_com_fraction"]*l2,
            "thigh_Iy_kg_m2":m1*(physical["thigh_inertia_radius_fraction"]*l1)**2,
            "shank_Iy_kg_m2":m2*(physical["shank_inertia_radius_fraction"]*l2)**2,
            "knee_to_cuff_m":physical["cuff_fraction_of_shank"]*l2}
        valid=pair.get("full_integral_comparison_valid",False)
        motion_comparison=pair.get("H150",{}).get("motion_comparison") or {}
        row={"patient_id":pid,"label":patient["label"],"future_learning_split":patient["future_learning_split"],
            "physical":physical,"resolved":resolved,"engineering_factors":patient.get("engineering_factors"),
            "static_valid":static.get(pid,{}).get("model_static_valid"),
            "execution_status":done.get("status","PAIR_AVAILABLE_PARENT_PENDING" if pair else "NO_COMPLETED_PATIENT_RECORD"),
            "cold_commissioning_reached":done.get("cold_commissioning_reached"),
            "parent_failure":done.get("error"),"parent_qualification":parent.get("qualification"),
            "pair_identity_valid":pair.get("pair_identity_valid"),"full_integral_comparison_valid":valid,
            "qualified_B_reference":pair.get("qualified_B_reference"),
            "complete_qualified_H150":pair.get("complete_qualified_H150"),
            "motion_relative":pair.get("motion_relative","NOT_EVALUATED"),
            "motion_failed_requirements":motion_comparison.get("failed_requirements",[]),
            "motion_burden_ratios":motion_comparison.get("burden_ratios"),
            "gain_percent":pair.get("gain_percent") if valid else None,
            "gain_N_s":pair.get("gain_N_s") if valid else None,"arms":arms,
            "evidence_level":"PHYSICAL_LEVEL1" if pair or parent else "NO_COMPLETED_PHYSICAL_EVIDENCE"}
        if valid:
            row["H150_minus_B"]={key:difference(arms["H150"].get(key),arms["B"].get(key)) for key in (
                "moment_integral_Nm_s","force_peak_N","moment_peak_Nm","tracking_RMS_deg","true_excursion_deg",
                "true_return_undershoot_from_issued_reference_deg","true_outbound_overshoot_from_issued_reference_deg",
                "velocity_total_variation_deg_s","acceleration_total_variation_deg_s2")}
            bm=arms["B"]["moment_integral_Nm_s"];hm=arms["H150"]["moment_integral_Nm_s"]
            row["moment_change_percent"]=100*(hm-bm)/bm if bm is not None and bm>0 and hm is not None else None
        else:row["H150_minus_B"]=None;row["moment_change_percent"]=None
        rows.append(row)
    raw=[r for r in rows if r["full_integral_comparison_valid"] and r["gain_percent"] is not None]
    qualified=[r for r in raw if r["complete_qualified_H150"]]
    def stats(selected):
        x=[r["gain_percent"] for r in selected]
        return {"n":len(x),"patient_ids":[r["patient_id"] for r in selected],"mean_gain_percent":mean_or_none(x),
            "minimum_gain_percent":min(x) if x else None,"maximum_gain_percent":max(x) if x else None,
            "positive_count":sum(v>0 for v in x),"negative_count":sum(v<0 for v in x),"zero_count":sum(v==0 for v in x)}
    index={r["label"]:r for r in rows};ref=index.get("reference")
    sensitivities={}
    for factor,low,high in [("mass","mass_low","mass_high"),("length","length_short","length_long"),
                            ("stiffness","stiffness_low","stiffness_high"),("damping","damping_low","damping_high")]:
        trio=[index.get(low),ref,index.get(high)]
        record={"patient_ids":[r["patient_id"] if r else None for r in trio],"status":"INSUFFICIENT_EVIDENCE",
            "interpretation":"Engineering sensitivity for the registered frozen study; not a clinical effect or statistically significant population estimate."}
        if all(r and r["full_integral_comparison_valid"] and r["gain_percent"] is not None for r in trio):
            lo,mid,hi=trio;dx=hi["engineering_factors"][factor]-lo["engineering_factors"][factor]
            record.update(status="DESCRIPTIVE_THREE_POINT_PHYSICAL_LEVEL1",factor_values=[r["engineering_factors"][factor] for r in trio],
                gain_percent=[r["gain_percent"] for r in trio],fully_qualified_H150=[r["complete_qualified_H150"] for r in trio],
                high_minus_low_gain_percentage_points=hi["gain_percent"]-lo["gain_percent"],
                secant_gain_percentage_points_per_unit_factor=(hi["gain_percent"]-lo["gain_percent"])/dx,
                H150_high_minus_low_return_undershoot_deg=difference(hi["arms"]["H150"]["true_return_undershoot_from_issued_reference_deg"],lo["arms"]["H150"]["true_return_undershoot_from_issued_reference_deg"]))
        else:
            record["available_valid_ids"]=[r["patient_id"] for r in trio if r and r["full_integral_comparison_valid"]]
            record["unavailable_or_invalid_ids"]=[r["patient_id"] if r else None for r in trio if not r or not r["full_integral_comparison_valid"]]
        sensitivities[factor]=record
    outcome={"all_valid_pairs":stats(raw),"fully_qualified_pairs":stats(qualified),
        "force_reduced_but_motion_failed":[r["patient_id"] for r in raw if r["gain_percent"]>0 and r["motion_relative"]=="FAIL"],
        "H150_force_worse":[r["patient_id"] for r in raw if r["gain_percent"]<0],
        "B_qualified_H150_not_qualified":[r["patient_id"] for r in rows if r["qualified_B_reference"] and r["complete_qualified_H150"] is False],
        "both_executed_task_fail":[r["patient_id"] for r in rows if all(r["arms"][a]["task"]=="FAIL" for a in ["B","H150"])],
        "parent_not_formed":[r["patient_id"] for r in rows if r["cold_commissioning_reached"] is False],
        "arm_qualification_counts":{a:dict(Counter(r["arms"][a]["qualification"] for r in rows)) for a in ["B","H150"]}}
    return {"schema":"IHEAR_OFFLINE_SENSITIVITY_SNAPSHOT_V1","generated_utc":datetime.now(timezone.utc).isoformat(),
        "registered_patient_count":len(rows),"rows":rows,"summary":outcome,"single_factor_sensitivity":sensitivities,
        "source_inputs":sources,"warnings":warnings,"physics_starts":0,
        "notes":["Every registered patient retained. Absent evidence is null/NOT_EVALUATED, never a zero or inferred controller failure.",
            "Only full-integral valid same-patient pairs have gains. Invalid B is never a qualified relative-motion reference.",
            "Actual-issued-reference extrema and nominal-target deviations are separately named.",
            "No estimator fitting, parameter tuning, hypothesis test or learning is performed."]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--package",type=Path,required=True);parser.add_argument("--mirror",type=Path)
    args=parser.parse_args();result=extract(args.package);out=args.package/"derived/CROSS_SENSITIVITY_SNAPSHOT.json"
    out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix(".json.tmp");tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n");tmp.replace(out)
    if args.mirror:
        args.mirror.mkdir(parents=True,exist_ok=True);shutil.copy2(out,args.mirror/out.name)
    print(json.dumps(result["summary"],ensure_ascii=False))


if __name__=="__main__":main()
