"""SOURCE_ONLY GateK V2 identity adaptation: numerical decomposition of closed gradients, no learner API."""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

PACKAGE = Path(__file__).resolve().parents[5]
HERE = "families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/context_kernel_diagnostic_v1/"
GLOBAL_STOP = 1793114740.0
GROUPS = ("DEVELOPMENT_HEAVY035", "DEVELOPMENT_LIGHT065")
ENDPOINT_KEYS = {"DEVELOPMENT_HEAVY035":"V8BETA01H", "DEVELOPMENT_LIGHT065":"V8BETA01L"}
ATTEMPT_IDS = {"DEVELOPMENT_HEAVY035":["V8BETA01H_OP_BETA_RF_RAW_01","V8BETA01H_OP_BETA_RF_RAW_02"],
               "DEVELOPMENT_LIGHT065":["V8BETA01L_OP_BETA_RF_RAW_01","V8BETA01L_OP_BETA_RF_RAW_02"]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def preflight_closed_metadata(inputs, contract, counts):
    """Value/schema checks only, before any normalization or numerical dot."""
    def require(value, error):
        if not value: raise ValueError("V2_PREFLIGHT:"+error)
    def finite_number(value):
        return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    def matrix52(value):
        return isinstance(value,list) and len(value)==2 and all(isinstance(row,list) and len(row)==26 and all(finite_number(v) for v in row) for row in value)
    expected_bindings = [{"context_group_evaluation_only":g,"closed_endpoint_key":ENDPOINT_KEYS[g],"ordered_attempt_ids":ATTEMPT_IDS[g]} for g in GROUPS]
    require(contract["context_endpoint_identity_binding"]==expected_bindings,"EXACT_ACTUAL_CONTEXT_VS_PHYSICAL_ENDPOINT_BINDING")
    behavior = inputs["behavior_exact_export"]["policy"]
    require(inputs["behavior_exact_export"].get("pending")==[],"EXACT_PENDING_FREE_G0_EXPORT")
    require(behavior["schema"]=="v8.scalar_beta_linear25.v1" and len(behavior["feature_names"])==25 and matrix52(behavior["weights"]),"BEHAVIOR_SCHEMA_NAMES_WEIGHTS")
    norm = behavior["normalization"]
    require(len(norm["mean"])==len(norm["scale"])==25 and all(finite_number(v) for v in norm["mean"]) and all(finite_number(v) and v>0 for v in norm["scale"]),"NORMALIZATION_25_FINITE_POSITIVE_METADATA_NO_NORMALIZE")
    ids = [ident for g in GROUPS for ident in ATTEMPT_IDS[g]]
    contexts = {}; causal_hashes = {}
    for i,ident in enumerate(ids):
        proposal=inputs["proposal_"+str(i)]; group=next(g for g in GROUPS if ident in ATTEMPT_IDS[g])
        require(proposal["attempt_id"]==ident and proposal["context_group_evaluation_only"]==group and proposal["baseline_evaluation_only"]["context_group_evaluation_only"]==group,"PROPOSAL_CONTEXT_BASELINE_AND_ORDERED_ACTUAL_ATTEMPT")
        require(proposal["feature_names"]==behavior["feature_names"] and proposal["qa_validated"] is True and len(proposal["commissioned25"])==25 and all(finite_number(v) for v in proposal["commissioned25"]),"ACTUAL_CAUSAL25_NAMES_QA_FINITE_VALUES")
        require(inputs["replay_input"]["original_closed_proposal_exact_exports_by_id"][ident]==contract["input_refs"]["proposal_"+str(i)],"EXACT_EXPORTED_REPLAY_REFERENCE")
        if group in contexts:
            require(contexts[group]==proposal["commissioned25"] and causal_hashes[group]==proposal["causal_features_sha256"],"SAME_CONTEXT_TWO_DRAW_EXACT_RAW25_AND_SHA")
        contexts[group]=proposal["commissioned25"];causal_hashes[group]=proposal["causal_features_sha256"]
        sample=proposal["sample"]
        require(sample["alpha"]==sample["beta"]==2.0 and isinstance(sample["raw_shape_logits"],list) and len(sample["raw_shape_logits"])==2 and all(finite_number(v) for v in sample["raw_shape_logits"]),"SAVED_INITIAL_SHAPES_AND_RAW_LOGITS")
        counts["preflight_context_binding_checks"] += 1
    for family,key in [("GLOBAL","global_result"),("CONTEXT_LOO","loo_result")]:
        result=inputs[key]
        schema="v8.beta_feasibility_context_loo_private_result.v1" if family=="CONTEXT_LOO" else "v8.beta_feasibility_counterfactual_private_result.v1"
        require(result["schema"]==schema and result["target"]=="FEASIBILITY_ONLY" and result["data_semantics"]=="FIXED_BEHAVIOR_COUNTERFACTUAL_REPLAY_NOT_NEW_ON_POLICY","CLOSED_RESULT_SCHEMA_SCOPE")
        require(len(result["rewards"])==len(result["advantages"])==4 and all(finite_number(v) for v in result["rewards"]+result["advantages"]),"FOUR_STORED_REWARDS_AND_ADVANTAGES")
        for algorithm,steps in [("REINFORCE",1),("PPO",3)]:
            traces=result["traces"][algorithm]; require(len(traces)==steps and matrix52(traces[0]["gradient"]),"STORED_TRACE_LENGTH_AND_INITIAL_GRADIENT")
            require(finite_number(traces[0]["gradient_clip_scale"]) and 0<traces[0]["gradient_clip_scale"]<=1,"STORED_INITIAL_CLIP_SCALE")
            rows=traces[0]["rows"]; require([row["id"] for row in rows]==ids,"EXACT_INITIAL_TRACE_DRAW_ORDER")
            for i,row in enumerate(rows):
                sample=inputs["proposal_"+str(i)]["sample"]
                require(row["lambda_sample"]==sample["lambda_sample"] and row["old_logprob"]==sample["old_logprob"] and row["advantage"]==result["advantages"][i],"EXACT_STORED_TRACE_LAMBDA_DENSITY_ADVANTAGE_WITHOUT_REEVALUATION")
            policy=result["private_policies"][algorithm]
            require(matrix52(policy["weights"]) and policy["normalization"]==norm and policy["axis_contract"]==behavior["axis_contract"] and policy["feature_names"]==behavior["feature_names"] and policy["counters"]["parameter_updates"]==steps,"FIXED_FINAL_POLICY_SCHEMA_NORM_AXIS_STEPS")
            endpoints=result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"][algorithm]
            require(set(endpoints)==set(ENDPOINT_KEYS.values()),"ACTUAL_CLOSED_ENDPOINT_KEYS_ARE_PHYSICAL_JOB_LABELS")
            for endpoint_key in ENDPOINT_KEYS.values():
                saved=endpoints[endpoint_key]
                require(all(finite_number(saved[field]) for field in ("lambda","alpha","beta")) and 0<saved["lambda"]<1 and saved["alpha"]>0 and saved["beta"]>0,"STORED_ENDPOINT_FIELDS_NO_MEAN_RECOMPUTATION")
                counts["preflight_endpoint_records"] += 1
        require(result["traces"]["REINFORCE"][0]["gradient"]==result["traces"]["PPO"][0]["gradient"],"SAME_INITIAL_RF_PPO_GRADIENT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    counts = {"normalized_scalar_features":0,"augmented_contexts":0,"dot26":0,"dot2":0,
              "dot_scalar_products":0,"two_by_two_decomposition_solves":0,
              "recovered_context_gradient_scalar_values":0,"aggregate_reconstruction_scalar_checks":0,
              "scalar_sigmoid_evaluations":0,"analytic_mean_jacobian_shape_pairs":0,
              "analytic_mean_jacobian_context_assignments":0,"mean_directional_derivatives":0,
              "stored_RF_weight_delta_scalar_subtractions":0,"stored_RF_step_binding_scalar_checks":0,
              "stored_RF_mean_ratio_checks":0,"preflight_context_binding_checks":0,"preflight_endpoint_records":0,"source_or_data_SHA_reads":0,"JSON_decodes":0,
              "learner_model_init_restore_copy_forward_score_density_gradient_fit_update_RNG_physics_calls":0}
    identities = {}; cache = {}; paid = {}; output = None; created_output = False; deadline = None

    def clock():
        if deadline is None or time.time() >= min(deadline,GLOBAL_STOP):
            raise TimeoutError("GATEK_SEPARATE_OFFLINE_AUTHORITY_EXPIRED_OR_GLOBAL_STOP")

    def bounded(relative):
        target = (PACKAGE/relative).resolve()
        if not target.is_relative_to(PACKAGE) or "real_runs" in target.parts or "results" in target.relative_to(PACKAGE).parts:
            raise ValueError("ONLY_REGISTERED_CLOSED_METADATA_NO_RAW_OR_ACTUAL_RUN")
        return target

    def sha(relative):
        if relative not in identities:
            identities[relative] = hashlib.sha256(bounded(relative).read_bytes()).hexdigest()
            counts["source_or_data_SHA_reads"] += 1
        return identities[relative]

    def read(relative):
        if relative not in cache:
            sha(relative); cache[relative] = json.loads(bounded(relative).read_text()); counts["JSON_decodes"] += 1
        return cache[relative]

    def write(name, value):
        with (output/name).open("x") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")

    def dot(left, right, *, retain_terms=False):
        clock()
        if len(left)!=len(right) or len(left) not in (2,26): raise ValueError("DECLARED_DOT_DIMENSIONS_ONLY")
        counts["dot"+str(len(left))] += 1; counts["dot_scalar_products"] += len(left)
        terms = [a*b for a,b in zip(left,right)]
        return (sum(terms),terms) if retain_terms else sum(terms)

    try:
        approval_relative = str(Path(args.approval).resolve().relative_to(PACKAGE))
        auth = read(approval_relative)
        if (auth.get("schema")!="v8.beta_context_kernel_diagnostic_main_approval.v2" or
                auth.get("status")!="APPROVED_BY_MAIN_ONCE_V2_NUMERICAL_DIAGNOSTIC_ONLY" or
                auth.get("model_or_score_or_training_or_physics_calls_permitted")!=0 or
                auth.get("global_stop_unix")!=GLOBAL_STOP or auth.get("local_budget_s")!=60 or
                auth.get("AS_limit_bytes")!=1073741824 or auth.get("CPU_affinity")!=[0]):
            raise ValueError("SEPARATE_EXACT_GATESTAGE_MAIN_AUTHORITY_REQUIRED")
        deadline = auth["local_stop_unix"]
        if not auth["approved_unix"]<=time.time() or not 0<deadline-auth["local_start_unix"]<=60:
            raise ValueError("INDEPENDENT_OFFLINE_CLOCK_NOT_OLD_BETA_TRAINING_CLOCK_RENEWAL")
        clock()
        manifest_ref = auth["source_manifest"]; manifest = read(manifest_ref["path"])
        if sha(manifest_ref["path"])!=manifest_ref["sha256"]: raise ValueError("EXACT_APPROVED_SOURCE_MANIFEST")
        for relative, expected in manifest["files_sha256"].items():
            if sha(relative)!=expected: raise ValueError("SOURCE_CONTRACT_OR_METADATA_TEMPLATE_CHANGED:"+relative)
        own = str(Path(__file__).resolve().relative_to(PACKAGE))
        if manifest["candidate_source_sha256"]!=sha(own): raise ValueError("EXACT_APPROVED_CANDIDATE_SOURCE")
        tree = ast.parse(bounded(own).read_text())
        if hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()!=manifest["candidate_source_AST_sha256"]:
            raise ValueError("SOURCE_AST_NOT_APPROVED")
        contract = read(HERE+"EXPERIMENT_CONTRACT_SOURCE_ONLY_V2.json")
        if auth["input_refs_object_sha256"]!=digest(contract["input_refs"]): raise ValueError("EXACT_CLOSED_INPUT_SET")
        output = Path(args.output).resolve()
        if output!=bounded(auth["output_relative_path"]) or not output.is_relative_to(bounded(HERE+"diagnostics")):
            raise ValueError("EXCLUSIVE_PRIVATE_DIAGNOSTIC_OUTPUT_ONLY")
        output.parent.mkdir(exist_ok=True); output.mkdir(exist_ok=False); created_output = True
        os.sched_setaffinity(0,{0}); resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824))
        resource.setrlimit(resource.RLIMIT_CPU,(60,60))
        signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("GATEK_LOCAL_WALL_STOP")))
        signal.setitimer(signal.ITIMER_REAL,max(.001,min(deadline,GLOBAL_STOP)-time.time()))
        initial = resource.getrusage(resource.RUSAGE_SELF); start = time.time()
        write("START.json",{"schema":"v8.beta_context_kernel_diagnostic_start.v2","unix":start,"pid":os.getpid(),
                            "startticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),
                            "CPU_affinity":sorted(os.sched_getaffinity(0)),"source_SHA_AST_manifest":manifest_ref,
                            "approval_sha256":sha(approval_relative),"AS_limit_bytes":1073741824,"local_stop_unix":deadline,
                            "global_stop_unix":GLOBAL_STOP,"counts_initial":dict(counts),"CPU_user_s":initial.ru_utime,
                            "CPU_system_s":initial.ru_stime,"peak_RSS_KiB":initial.ru_maxrss,
                            "binary":str(Path(sys.executable).resolve()),
                            "binary_sha256":hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest()})
        inputs = {}
        for key, reference in contract["input_refs"].items():
            clock()
            if sha(reference["path"])!=reference["sha256"]: raise ValueError("FROZEN_CLOSED_DATA_CHANGED:"+key)
            inputs[key] = read(reference["path"])
        for relative, expected in contract["source_proof_only_sha256"].items():
            if sha(relative)!=expected: raise ValueError("FROZEN_MATHEMATICAL_SOURCE_PROOF_CHANGED")
        preflight_closed_metadata(inputs,contract,counts)
        global_result, loo = inputs["global_result"], inputs["loo_result"]
        behavior = inputs["behavior_exact_export"]["policy"]
        fields = ("schema","feature_names","normalization","weights","axis_contract","axis_contract_sha256")
        behavior_density = digest({key:behavior[key] for key in fields})
        if any(result["behavior_density_sha256"]!=behavior_density for result in (global_result,loo)) or global_result["rewards"]!=loo["rewards"]:
            raise ValueError("BASELINE_ONLY_IDENTICAL_BEHAVIOR_AND_REWARD")
        for key, result_key in [("global_DONE","global_result"),("loo_DONE","loo_result")]:
            if inputs[key].get("status")!="COMPLETED_EXACT_APPROVED_OFFLINE_STAGE" or inputs[key]["result_sha256"]!=contract["input_refs"][result_key]["sha256"]:
                raise ValueError("CLOSED_SOURCE_RESULT_DONE_BINDING")
        if inputs["replay_input"]["behavior_checkpoint_exact_export"]!=contract["input_refs"]["behavior_exact_export"]:
            raise ValueError("SAME_EXACT_EXPORTED_G0_REQUIRED")
        proposals = [inputs["proposal_"+str(i)] for i in range(4)]
        behavior_policy_sha = digest({key:behavior[key] for key in (*fields,"seed","arm_id","gain","version")})
        contexts = {}; sample_ids = []; raw_pair = None; shapes = None
        for i,proposal in enumerate(proposals):
            group = proposal["context_group_evaluation_only"]; sample_ids.append(proposal["attempt_id"])
            if group not in GROUPS or proposal["feature_names"]!=behavior["feature_names"] or proposal["qa_validated"] is not True or len(proposal["commissioned25"])!=25:
                raise ValueError("REGISTERED_ACTUAL_LEGAL25_CONTEXT_ONLY")
            context = proposal["commissioned25"]
            if group in contexts and contexts[group]!=context: raise ValueError("WITHIN_CONTEXT_RAW25_MUST_BE_EXACTLY_IDENTICAL")
            contexts[group] = context
            sample = proposal["sample"]
            if (inputs["replay_input"]["original_closed_proposal_exact_exports_by_id"][proposal["attempt_id"]]!=contract["input_refs"]["proposal_"+str(i)] or
                    sample["policy_sha256"]!=behavior_policy_sha):
                raise ValueError("EXACT_CLOSED_PROPOSAL_EXPORT_AND_BEHAVIOR_POLICY_IDENTITY")
            for result in (global_result,loo):
                old_row = result["traces"]["REINFORCE"][0]["rows"][i]
                if old_row["id"]!=proposal["attempt_id"] or old_row["lambda_sample"]!=sample["lambda_sample"] or old_row["old_logprob"]!=sample["old_logprob"]:
                    raise ValueError("CLOSED_RF_TRACE_MUST_BIND_THIS_DRAW_WITHOUT_DENSITY_RECOMPUTATION")
            if digest({"names":proposal["feature_names"],"values":context})!=proposal["causal_features_sha256"]:
                raise ValueError("EXACT_EXPORTED_CAUSAL_FEATURE_IDENTITY")
            if raw_pair is None: raw_pair=sample["raw_shape_logits"]; shapes=(sample["alpha"],sample["beta"])
            if sample["raw_shape_logits"]!=raw_pair or (sample["alpha"],sample["beta"])!=shapes or shapes!=(2.0,2.0):
                raise ValueError("SAME_SAVED_ALPHA2_BETA2_INITIAL_MEAN_JACOBIAN_ONLY")
        if len(set(sample_ids))!=4 or any(sum(p["context_group_evaluation_only"]==g for p in proposals)!=2 for g in GROUPS):
            raise ValueError("EXACT_FOUR_DISTINCT_TWO_BY_TWO_DRAW_IDENTITIES")
        if any(any(value!=0.0 for value in row[1:]) for row in behavior["weights"]) or [row[0] for row in behavior["weights"]]!=raw_pair:
            raise ValueError("SAVED_G0_SYMMETRIC_INTERCEPT_ONLY_PARAMETERS_REQUIRED")
        z = {}
        norm = behavior["normalization"]
        for group in GROUPS:
            if any(not math.isfinite(s) or s<=0 for s in norm["scale"]): raise ValueError("ORIGINAL_POSITIVE_FROZEN_SCALES")
            z[group]=[1.0]+[(v-m)/s for v,m,s in zip(contexts[group],norm["mean"],norm["scale"])]
            counts["normalized_scalar_features"] += 25; counts["augmented_contexts"] += 1
        h,l = GROUPS; hh=dot(z[h],z[h]); hl,cross_terms=dot(z[h],z[l],retain_terms=True); ll=dot(z[l],z[l])
        det=hh*ll-hl*hl; relative_det=det/(hh*ll)
        gram={h:{h:hh,l:hl},l:{h:hl,l:ll}}
        paid["augmented_feature_Gram"] = gram; paid["relative_Gram_determinant"] = relative_det
        if not math.isfinite(relative_det) or relative_det<=1e-12:
            raise ValueError("CONTEXT_GRAM_NONIDENTIFIABLE_NO_PSEUDOINVERSE_OR_NEW_SCORE_FALLBACK")
        alpha,beta=shapes; jac=[]
        for index,u in enumerate(raw_pair):
            clock(); sigmoid=1/(1+math.exp(-u)) if u>=0 else math.exp(u)/(1+math.exp(u))
            counts["scalar_sigmoid_evaluations"] += 1
            jac.append((beta if index==0 else -alpha)*sigmoid/(alpha+beta)**2)
        counts["analytic_mean_jacobian_shape_pairs"] += 1
        counts["analytic_mean_jacobian_context_assignments"] += 2
        results = {}
        for family,result in [("GLOBAL",global_result),("CONTEXT_LOO",loo)]:
            clock(); trace=result["traces"]["REINFORCE"][0]; gradient=trace["gradient"]
            if trace["gradient"]!=result["traces"]["PPO"][0]["gradient"] or [r["id"] for r in trace["rows"]]!=sample_ids:
                raise ValueError("SAME_INITIAL_RF_PPO_GRADIENT_AND_EXACT_ROW_ORDER")
            y={group:[dot(z[group],gradient[head]) for head in range(2)] for group in GROUPS}
            c={h:[],l:[]}
            for head in range(2):
                c[h].append((ll*y[h][head]-hl*y[l][head])/det)
                c[l].append((hh*y[l][head]-hl*y[h][head])/det)
                counts["two_by_two_decomposition_solves"] += 1
            components={group:[[coefficient*value for value in z[group]] for coefficient in c[group]] for group in GROUPS}
            counts["recovered_context_gradient_scalar_values"] += 104
            residual=max(abs(gradient[head][j]-components[h][head][j]-components[l][head][j]) for head in range(2) for j in range(26))
            counts["aggregate_reconstruction_scalar_checks"] += 52
            tolerance=1e-12+1e-9*max(abs(v) for row in gradient for v in row)
            if residual>tolerance: raise ValueError("GRADIENT_NOT_IDENTIFIABLE_IN_DECLARED_CONTEXT_SPAN")
            factor=.15*trace["gradient_clip_scale"]
            directional={}; direct={}; endpoint_checks={}
            for target in GROUPS:
                directional[target]={}
                for source in GROUPS:
                    directional[target][source]=factor*dot(jac,c[source])*gram[target][source]
                    counts["mean_directional_derivatives"] += 1
                direct[target]=factor*dot(jac,y[target]); counts["mean_directional_derivatives"] += 1
                if abs(sum(directional[target].values())-direct[target])>1e-12:
                    raise ValueError("LOCAL_CROSS_MEAN_DIRECTION_DECOMPOSITION_MISMATCH")
            final_weights=result["private_policies"]["REINFORCE"]["weights"]
            delta=[[a-b for a,b in zip(new,old)] for new,old in zip(final_weights,behavior["weights"])]
            counts["stored_RF_weight_delta_scalar_subtractions"] += 52
            for target in GROUPS:
                delta_raw=[dot(row,z[target]) for row in delta]
                for actual,expected in zip(delta_raw,[factor*v for v in y[target]]):
                    counts["stored_RF_step_binding_scalar_checks"] += 1
                    if abs(actual-expected)>1e-12: raise ValueError("CLOSED_RF1_WEIGHT_DELTA_NOT_THE_STORED_GRADIENT_STEP")
                actual_first_order=dot(jac,delta_raw); counts["mean_directional_derivatives"] += 1
                saved=result["endpoint_mean_predictions_NOT_PHYSICALLY_EVALUATED"]["REINFORCE"][ENDPOINT_KEYS[target]]
                counts["stored_RF_mean_ratio_checks"] += 1
                if saved["lambda"]!=saved["alpha"]/(saved["alpha"]+saved["beta"]): raise ValueError("STORED_CLOSED_ENDPOINT_MEAN_METADATA")
                observed_delta=saved["lambda"]-.5
                endpoint_checks[target]={"actual_context_group_evaluation_only":target,"closed_endpoint_key":ENDPOINT_KEYS[target],"closed_RF1_mean":saved["lambda"],"closed_mean_delta":observed_delta,
                    "actual_weight_delta_first_order_mean_projection":actual_first_order,
                    "direct_gradient_first_order_mean_projection":direct[target],
                    "first_order_and_closed_endpoint_same_sign":actual_first_order*observed_delta>0 or actual_first_order==observed_delta==0,
                    "nonlinear_remainder_stored_mean_minus_first_order":observed_delta-actual_first_order}
            support=(hl<0 and directional[h][h]>0 and directional[l][l]>0 and directional[l][h]<0 and
                     abs(directional[l][h])>abs(directional[l][l]) and direct[l]<0 and
                     endpoint_checks[l]["closed_mean_delta"]<0 and endpoint_checks[h]["closed_mean_delta"]>0)
            results[family]={"context_gradient_recovery":"UNIQUE_RANK2_AGGREGATE_LINEAR_REPRESENTATION_NOT_NEW_SCORE",
                "context_coefficients_two_shape_heads":c,"context_gradient_components":components,
                "aggregate_reconstruction_max_residual":residual,"local_cross_first_order_mean_change":directional,
                "direct_first_order_mean_change":direct,"RF1_closed_endpoint_checks":endpoint_checks,
                "negative_crosskernel_dominates_light_in_this_fixed_batch":support,
                "negative_kernel_hypothesis_rejected_if_cross_Gram_nonnegative":hl>=0,
                "sampling_variance_estimate_or_population_causal_claim":"NOT_IDENTIFIABLE_FROM_TWO_DRAW_PER_CONTEXT"}
            paid[family]=results[family]
        exact={"normalized_scalar_features":50,"augmented_contexts":2,"dot26":19,"dot2":16,"dot_scalar_products":526,
               "two_by_two_decomposition_solves":4,"recovered_context_gradient_scalar_values":208,
               "aggregate_reconstruction_scalar_checks":104,"scalar_sigmoid_evaluations":2,
               "analytic_mean_jacobian_shape_pairs":1,"analytic_mean_jacobian_context_assignments":2,
               "mean_directional_derivatives":16,"stored_RF_weight_delta_scalar_subtractions":104,
               "stored_RF_step_binding_scalar_checks":8,"stored_RF_mean_ratio_checks":4,"preflight_context_binding_checks":4,"preflight_endpoint_records":8}
        if any(counts[key]!=value for key,value in exact.items()): raise ValueError("NUMERICAL_WORK_EXACT_COUNTS_NOT_CONTRACT")
        clock(); final=resource.getrusage(resource.RUSAGE_SELF)
        report={"schema":"v8.beta_context_kernel_closed_gradient_diagnostic.v2","status":"COMPLETED_FIXED_BEHAVIOR_NUMERICAL_DIAGNOSTIC_NO_MODEL_CALLS",
                "augmented_feature_Gram":gram,"relative_Gram_determinant":relative_det,"cross_feature_product_terms_including_intercept":cross_terms,
                "cross_feature_term_labels":["intercept",*behavior["feature_names"]],
                "cross_feature_term_accounting":"Reuse the26 products already paid in the single cross-Gram dot; no recomputation",
                "initial_saved_shape_mean_Jacobian":jac,"results":results,
                "counts":counts,"source_and_input_sha256":identities,"behavior_density_sha256":behavior_density,
                "context_endpoint_identity_binding":contract["context_endpoint_identity_binding"],
                "retained_V1_failed_identity":contract["retained_V1_failed_identity"],
                "interpretation":"Test signed local/cross mechanism in four fixed observed draws, not expected policy gradient variance, new reward branch, fresh onpolicy, qualification/JF/JM success, or clinical transfer.",
                "new_model_or_real_checkpoint_or_four_mean_freeze_mutation":False,"wall_s":time.time()-start,
                "CPU_s":final.ru_utime+final.ru_stime-initial.ru_utime-initial.ru_stime,"peak_RSS_KiB":final.ru_maxrss}
        write("RESULT.json",report); write("DONE.json",{"status":report["status"],"result_sha256":hashlib.sha256((output/"RESULT.json").read_bytes()).hexdigest(),"counts":counts})
    except BaseException as error:
        if created_output:
            write("FAILED.json",{"error_type":type(error).__name__,"error":str(error),"paid_counts":counts,"completed_private_decompositions":paid,"source_and_input_sha256":identities,"no_model_or_physical_calls":True})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)


if __name__ == "__main__":
    main()
