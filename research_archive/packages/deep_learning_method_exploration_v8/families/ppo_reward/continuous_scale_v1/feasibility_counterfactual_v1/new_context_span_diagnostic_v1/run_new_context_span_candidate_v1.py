"""SOURCE_ONLY bounded arithmetic audit of frozen new-context span transfer.

No learner imports or nonlinear mean evaluation. All model outputs are stored
original pre-B predictions; linear projections below are explicitly counted.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

HERE="families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/new_context_span_diagnostic_v1/"
STOP=1793114740.0
OLD=["DEVELOPMENT_HEAVY035","DEVELOPMENT_LIGHT065"]
NEW=["V8FMEAN03","V8FMEAN04"]
LABELS=["FEAS_GLOBAL_RF1","FEAS_GLOBAL_PPO3","FEAS_CONTEXT_LOO_RF1","FEAS_CONTEXT_LOO_PPO3","FEAS_SPAN_GEOMETRY_RF1","FEAS_SPAN_GEOMETRY_PPO3"]
PFIELDS=("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256","seed","arm_id","gain","version")

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument("--package",required=True);cli.add_argument("--approval",required=True);cli.add_argument("--approval-sha256",required=True);args=cli.parse_args()
    package=Path(args.package).resolve();cache={};identities={};output=None;counts={};metadata={"JSON_decodes":0,"unique_file_hashes":0};owner_pid=os.getpid()
    def path(relative):
        target=(package/relative).resolve()
        if not target.is_relative_to(package) or "real_runs" in target.parts or "results" in target.relative_to(package).parts or target.suffix in (".npz",".gz",".csv",".parquet"):raise ValueError("FROZEN_JSON_METADATA_ONLY_NO_RAW_OR_REAL_RUNS")
        return target
    def sha(relative):
        if relative not in identities:identities[relative]=hashlib.sha256(path(relative).read_bytes()).hexdigest();metadata["unique_file_hashes"]+=1
        return identities[relative]
    def read(relative):
        if relative not in cache:sha(relative);cache[relative]=json.loads(path(relative).read_text(),parse_constant=lambda v:(_ for _ in ()).throw(ValueError("NONFINITE_JSON:"+v)));metadata["JSON_decodes"]+=1
        return cache[relative]
    def ref(r):
        if sha(r["path"])!=r["sha256"]:raise ValueError("EXACT_SOURCE_OR_DATA_CHANGED:"+r["path"])
        return read(r["path"])
    def require(test,message):
        if not test:raise ValueError(message)
    def inc(key,n=1):counts[key]+=n
    def write(name,value):
        require(os.getpid()==owner_pid,"OWNER_ONLY_OUTPUT")
        with (output/name).open("x") as f:f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    ar=str(Path(args.approval).resolve().relative_to(package));require(sha(ar)==args.approval_sha256,"EXACT_MAIN_APPROVAL_SHA")
    auth=read(ar);require(auth.get("schema")=="v8.new_context_span_math_main_approval.v1" and auth.get("status")=="MAIN_APPROVED_ONCE_FROZEN_ARITHMETIC_NO_LEARNER_API" and auth.get("learner_helper_nonlinear_mean_fit_RNG_physics_calls")==0,"SEPARATE_EXACT_MATH_MAIN_AUTHORITY")
    require(0<auth["local_stop_unix"]-auth["local_start_unix"]<=60,"STRICT_MAX60S_SINGLE_NOW_AUTHORITY")
    def clock():require(auth["local_start_unix"]<=time.time()<min(auth["local_stop_unix"],STOP),"LOCAL_ORIGINAL_GLOBAL_CLOCK")
    clock();manifest=ref(auth["source_manifest"])
    require(auth["input"]==manifest["input"],"EXACT_PREREGISTERED_INPUT_ONLY")
    for relative,expected in manifest["files_sha256"].items():require(sha(relative)==expected,"EXACT_CANDIDATE_CONTRACT_SOURCE")
    contract=ref(manifest["contract"]);counts={key:0 for key in contract["successful_expected_math_counts"]}
    output=path(auth["output_relative_path"]);require(output==package/HERE/"diagnostics/NEWCTX_ONCE_V1" and not output.exists(),"EXCLUSIVE_SINGLE_RUN_OUTPUT_PRESERVE_FAILURE")
    output.parent.mkdir(exist_ok=True);output.mkdir(exist_ok=False)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    initial=resource.getrusage(resource.RUSAGE_SELF);started=time.time();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError("BOUNDED_NEW_CONTEXT_MATH_STOP")));signal.setitimer(signal.ITIMER_REAL,max(.001,min(auth["local_stop_unix"],STOP)-time.time()))
    write("START.json",{"unix":started,"pid":owner_pid,"start_ticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),"binary":str(Path(sys.executable).resolve()),"binary_sha256":hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),"CPU_user_s":initial.ru_utime,"CPU_system_s":initial.ru_stime,"RSS_peak_KiB":initial.ru_maxrss,"AS_limit_bytes":1073741824,"approval_sha256":args.approval_sha256,"source_manifest":auth["source_manifest"],"input":auth["input"],"model_calls":0})
    try:
        data=ref(auth["input"]);g0=ref(data["G0"])["policy"];names=g0["feature_names"];norm=g0["normalization"]
        require(len(names)==25 and len(norm["mean"])==len(norm["scale"])==25 and all(finite(v) for v in norm["mean"]) and all(finite(v) and v>0 for v in norm["scale"]),"EXACT_FROZEN_NORMALIZER25")
        require(digest({k:g0[k] for k in PFIELDS})==data["G0_policy_sha256"] and len(g0["weights"])==2 and all(len(w)==26 and all(finite(v) for v in w) for w in g0["weights"]),"EXACT_G0_POLICY")
        require(g0["weights"][0][0]==g0["weights"][1][0] and all(v==0 for w in g0["weights"] for v in w[1:]),"REGISTERED_CONSTANT_SYMMETRIC_G0_ONLY")
        old={};old_ids={}
        for original in data["old_proposals"]:
            q=ref(original);group=q["context_group_evaluation_only"];require(group in OLD and q["feature_names"]==names and q["qa_validated"] is True and len(q["commissioned25"])==25 and all(finite(v) for v in q["commissioned25"]),"EXACT_OLD_PROPOSAL_CAUSAL25")
            require(q["sample"]["alpha"]==q["sample"]["beta"]==2.0 and q["sample"]["raw_shape_logits"]==[g0["weights"][0][0],g0["weights"][1][0]],"SAVED_G0_SYMMETRIC_SHAPES_NO_NEW_MEAN")
            if group in old:require(old[group]==q["commissioned25"],"SAME_CONTEXT_TWO_ORIGINAL_DRAWS")
            old[group]=q["commissioned25"];old_ids.setdefault(group,[]).append(q["attempt_id"])
        require(set(old)==set(OLD) and all(len(old_ids[g])==2 for g in OLD),"FOUR_EXACT_OLD_DRAWS_TWO_CONTEXTS")
        gatek=ref(data["GateK"]);jac=gatek["initial_saved_shape_mean_Jacobian"];require(len(jac)==2 and all(finite(v) for v in jac),"EXISTING_JACOBIAN_REQUIRED_NO_SIGMOID")
        results={kind:ref(r) for kind,r in data["closed_results"].items()};require(set(results)=={"GLOBAL","CONTEXT_LOO","SPAN_GEOMETRY"},"EXACT_C_L_G")
        density=digest({k:g0[k] for k in PFIELDS[:6]});require(gatek["behavior_density_sha256"]==density and all(v["behavior_density_sha256"]==density for v in results.values()),"SAME_ACTUAL_BEHAVIOR_FOR_SAVED_JACOBIAN_AND_ENDPOINTS")
        predictions={};new={};models={};new_proofs={}
        for group,source in data["new_preB"].items():
            q=ref(source)["decisions"];context=q["context25"];a=q["actual_counts"]
            require(group in NEW and context["feature_names"]==names and len(context["features"])==25 and all(finite(v) for v in context["features"]) and digest(context)==data["new_context_canonical_sha256"][group],"EXACT_SAVED_NEW_CONTEXT25_ONLY")
            require(q["all_choices_before_B"] is True and list(q["decisions"])==LABELS and a["deploy_mean_returned"]==a["beta_internal_forward_counter_delta"]==6 and a["deploy_mean_numerical_rejection"]==0 and a["restore_initialize_fit_gradient_RNG_sampling_physics"]==0,"ACTUAL_PREB_12_PREDICTIONS_REQUIRED")
            new[group]=context["features"];new_proofs[group]=q["proof_audit"];predictions[group]={}
            for label,decision in q["decisions"].items():
                require(decision["status"]=="FROZEN_MEAN_NOT_PHYSICALLY_QUALIFIED","NO_MISSING_OR_REJECTED_PREDICTION_FILL")
                item=decision["model"];algorithm="PPO" if label.endswith("PPO3") else "REINFORCE";kind="SPAN_GEOMETRY" if "SPAN_GEOMETRY" in label else "CONTEXT_LOO" if "CONTEXT_LOO" in label else "GLOBAL"
                require(item["closed_result"]==data["closed_results"][kind] and item["policy_json_path"]==["private_policies",algorithm],"ACTUAL_FIXED_FINAL_ENDPOINT_ONLY")
                policy=results[kind]["private_policies"][algorithm];pred=decision["prediction"]
                require(policy["normalization"]==norm and policy["feature_names"]==names and len(policy["weights"])==2 and all(len(w)==26 and all(finite(v) for v in w) for w in policy["weights"]),"FROZEN_NORMALIZATION_AND_HEADS_ONLY")
                require(digest({k:policy[k] for k in PFIELDS})==item["policy_sha256"]==pred["policy_sha256"] and digest(policy["weights"])==item["weights_sha256"],"EXACT_FINAL_POLICY_WEIGHT_BINDING")
                require(len(pred["raw_shape_logits"])==2 and all(finite(v) for v in pred["raw_shape_logits"]) and finite(pred["lambda"]) and 0<pred["lambda"]<1,"STORED_LOGIT_LAMBDA_FIELDS_ONLY")
                if label in models:require(models[label]["identity"]==item,"SAME_FROZEN_MODEL_BOTH_CONTEXTS")
                models[label]={"identity":item,"policy":policy,"trace":results[kind]["traces"][algorithm]};predictions[group][label]={k:pred[k] for k in ["raw_shape_logits","alpha","beta","lambda","policy_sha256"]}
        require(set(new)==set(NEW),"BOTH_FIXED_NEW_CONTEXTS_NOT_BEST_SELECTED")
        def dot(a,b,category):
            require(len(a)==len(b) and len(a) in (2,26),"REGISTERED_DOT_DIMENSION");inc(category);inc("dot"+str(len(a)));inc("dot_scalar_products",len(a));return sum(x*y for x,y in zip(a,b))
        def normalize(values):
            v=[1.0]
            for x,m,s in zip(values,norm["mean"],norm["scale"]):v.append((x-m)/s);inc("normalized_scalar_features")
            require(all(finite(x) for x in v),"NONFINITE_FROZEN_NORMALIZATION");return v
        z={g:normalize(old[g]) for g in OLD};zn={g:normalize(new[g]) for g in NEW};clock()
        frozen=results["SPAN_GEOMETRY"]["frozen_span_geometry"]
        for g in OLD:
            for a,b in zip(z[g],frozen["z"][g]):require(abs(a-b)<=1e-12,"EXACT_SAVED_OLD_SPAN");inc("old_span_scalar_binding_checks")
        HH=dot(z[OLD[0]],z[OLD[0]],"gram_dot26");HL=dot(z[OLD[0]],z[OLD[1]],"gram_dot26");LL=dot(z[OLD[1]],z[OLD[1]],"gram_dot26")
        for key,value in [("HH",HH),("HL",HL),("LL",LL)]:require(abs(value-frozen[key])<=1e-10,"OLD_GRAM_IDENTITY")
        det=HH*LL-HL*HL;inc("rank_determinant_evaluations");require(HH>0 and LL>0 and det/(HH*LL)>1e-12,"RANK_FAILURE_STOP_NO_PSEUDOINVERSE")
        def solve(b):inc("two_by_two_solves");return [(LL*b[0]-HL*b[1])/det,(HH*b[1]-HL*b[0])/det]
        def projection(coef):
            v=[]
            for h,l in zip(z[OLD[0]],z[OLD[1]]):v.append(coef[0]*h+coef[1]*l);inc("span_reconstruction_scalar_coordinates");inc("span_reconstruction_scalar_products",2)
            return v
        def residual(a,b):
            v=[]
            for x,y in zip(a,b):v.append(x-y);inc("span_residual_scalar_subtractions")
            return v
        new_span={}
        for g in NEW:
            cross=[dot(z[t],zn[g],"new_context_cross_dot26") for t in OLD];coef=solve(cross);proj=projection(coef);res=residual(zn[g],proj)
            n2=dot(zn[g],zn[g],"new_context_norm_dot26");r2=dot(res,res,"new_context_norm_dot26");inc("squared_residual_ratios")
            orth=[dot(z[t],res,"new_context_orthogonality_dot26") for t in OLD]
            require(all(abs(v)<=1e-10*(1+abs(k)) for v,k in zip(orth,cross)),"NEW_CONTEXT_PROJECTION_ORTHOGONALITY")
            new_span[g]={"old_span_coefficients":coef,"cross_kernel":cross,"squared_norm":n2,"squared_residual_norm":r2,"squared_relative_residual":r2/n2,"orthogonality_dots":orth,"residual":res}
        endpoint={}
        for label in LABELS:
            clock();m=models[label];trace=m["trace"];require(len(trace)==(3 if label.endswith("PPO3") else 1),"EXACT_FIXED_TRACE_LENGTH")
            previous=digest(g0["weights"]);from_trace=[[0.0]*26 for _ in range(2)]
            for row in trace:
                require(row["weights_before_sha256"]==previous and len(row["gradient"])==2 and all(len(v)==26 and all(finite(g) for g in v) for v in row["gradient"]) and finite(row["gradient_clip_scale"]) and 0<row["gradient_clip_scale"]<=1,"SAVED_TRACE_GRADIENT_AND_CHAIN_ONLY")
                previous=row["weights_after_sha256"];inc("saved_gradient_chain_steps_read");factor=.15*row["gradient_clip_scale"]
                for h in range(2):
                    for j in range(26):from_trace[h][j]+=factor*row["gradient"][h][j];inc("saved_gradient_scaled_scalar_terms")
            require(previous==digest(m["policy"]["weights"]),"TRACE_CHAIN_FINAL_IDENTITY")
            heads=[]
            for h in range(2):
                delta=[]
                for w,w0,t in zip(m["policy"]["weights"][h],g0["weights"][h],from_trace[h]):
                    v=w-w0;delta.append(v);inc("endpoint_weight_delta_scalar_subtractions");require(abs(v-t)<=1e-12,"SAVED_GRADIENT_DELTA_PARITY_NO_NEW_STEP");inc("saved_gradient_delta_parity_checks")
                rhs=[dot(z[t],delta,"weight_old_span_dot26") for t in OLD];coef=solve(rhs);res=residual(delta,projection(coef));d2=dot(delta,delta,"weight_norm_dot26");r2=dot(res,res,"weight_norm_dot26");require(d2>0,"ZERO_HEAD_DISPLACEMENT_RATIO_UNDEFINED_STOP");inc("squared_residual_ratios")
                require(r2<=1e-22+1e-18*d2,"WEIGHT_DISPLACEMENT_NOT_IN_OLD_SPAN_WITHIN_REGISTERED_TOLERANCE")
                heads.append({"delta":delta,"old_span_coefficients":coef,"span_residual":res,"squared_delta_norm":d2,"squared_span_residual_norm":r2,"squared_relative_residual":r2/d2 if d2 else None})
            transferred={}
            for g in NEW:
                head_effects=[]
                for h,head in enumerate(heads):
                    direct=dot(head["delta"],zn[g],"endpoint_delta_logit_dot26");sp=[c*k for c,k in zip(head["old_span_coefficients"],new_span[g]["cross_kernel"])];inc("transferred_span_scalar_products",2)
                    res=dot(head["span_residual"],zn[g],"weight_residual_new_context_dot26");stored=predictions[g][label]["raw_shape_logits"][h]-g0["weights"][h][0];inc("saved_delta_logit_scalar_subtractions")
                    require(abs(direct-stored)<=1e-10 and abs(direct-sum(sp)-res)<=1e-10,"DELTA_LOGIT_SAVED_AND_SPAN_ALIGNMENT");inc("saved_delta_logit_parity_checks")
                    head_effects.append({"direct":direct,"old_H_component":sp[0],"old_L_component":sp[1],"weight_residual_component":res,"saved_delta_logit":stored})
                inc("diagnostic_two_head_linear_endpoint_projections")
                first={}
                for key in ["direct","old_H_component","old_L_component","weight_residual_component"]:first[key]=dot(jac,[v[key] for v in head_effects],"mean_directional_derivatives")
                stored_delta=predictions[g][label]["lambda"]-.5;inc("saved_mean_delta_scalar_subtractions");error=first["direct"]-stored_delta;inc("firstorder_vs_saved_mean_error_subtractions")
                transferred[g]={"head_delta_logits":head_effects,"firstorder_delta_mean":first,"saved_actual_mean":predictions[g][label]["lambda"],"saved_delta_mean_from_symmetric_G0":stored_delta,"firstorder_minus_saved_delta_mean":error,"not_a_new_nonlinear_mean":True}
            endpoint[label]={"model":m["identity"],"weight_displacement_heads":heads,"new_context_transfer":transferred}
        contrasts={}
        for g in NEW:
            contrasts[g]={}
            for suffix in ["RF1","PPO3"]:
                a=endpoint["FEAS_SPAN_GEOMETRY_"+suffix]["new_context_transfer"][g];b=endpoint["FEAS_CONTEXT_LOO_"+suffix]["new_context_transfer"][g]
                first=a["firstorder_delta_mean"]["direct"]-b["firstorder_delta_mean"]["direct"];inc("geometry_LOO_firstorder_scalar_differences")
                stored=a["saved_actual_mean"]-b["saved_actual_mean"];inc("geometry_LOO_saved_mean_scalar_differences");error=first-stored;inc("geometry_LOO_alignment_error_subtractions")
                contrasts[g][suffix]={"firstorder_geometry_minus_LOO":first,"saved_mean_geometry_minus_LOO":stored,"firstorder_minus_saved_contrast":error,"direction_not_preregistered_as_positive":True}
        require(counts==contract["successful_expected_math_counts"],"EXACT_ACTUAL_MATH_COUNTS_NOT_CONTRACT");clock();final=resource.getrusage(resource.RUSAGE_SELF)
        result={"schema":"v8.new_context_span_transfer_arithmetic_result.v1","status":"COMPLETED_FROZEN_ARITHMETIC_NOT_NEW_MODEL_EVALUATION","old_contexts":OLD,"new_contexts":NEW,"normalization_fitted":False,"augmented_Gram":{"HH":HH,"HL":HL,"LL":LL,"det":det},"new_context_span":new_span,"saved_G0_mean_Jacobian_reused":jac,"endpoint_displacement_transfer":endpoint,"geometry_LOO_contrasts":contrasts,"source_proofs_copied_not_recomputed":new_proofs,"counts":counts,"metadata_counts":metadata,"source_and_input_sha256":identities,"nonlinear_mean_recomputed":False,"new_TASK_cost_or_qualification_read":False,"new_training_or_control_gain_or_generalization_claim":False,"raw_or_real_runs_or_active_C4_read":False,"wall_s":time.time()-started,"CPU_s":final.ru_utime+final.ru_stime-initial.ru_utime-initial.ru_stime,"peak_RSS_KiB":final.ru_maxrss}
        write("RESULT.json",result);write("DONE.json",{"status":result["status"],"result_sha256":hashlib.sha256((output/"RESULT.json").read_bytes()).hexdigest(),"math_counts":counts,"learner_API_or_physics_calls":0})
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0);write("FAILED.json",{"error_type":type(error).__name__,"error":str(error),"paid_math_counts":counts,"paid_metadata_counts":metadata,"source_and_input_sha256":identities,"learner_API_or_physics_calls":0,"retry_authorized":False});raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

if __name__=="__main__":main()
