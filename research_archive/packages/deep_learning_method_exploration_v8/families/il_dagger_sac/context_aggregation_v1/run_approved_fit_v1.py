"""One approved <=60s CPU fit; no physics or sealed-validation reader exists."""
from pathlib import Path
import ast
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
import resource
import signal
import sys
import time

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def put(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")


def resource_record():
    stat=Path("/proc/self/stat").read_text().split(") ",1)[1].split()
    status=Path("/proc/self/status").read_text().splitlines()
    rss=next(int(line.split()[1]) for line in status if line.startswith("VmRSS:"))
    return {"pid":os.getpid(),"start_ticks":int(stat[19]),"cpu_process_s":time.process_time(),
            "RSS_KiB":rss,"peak_RSS_KiB":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    invocation_start=time.time();invocation_cpu=time.process_time()
    here=Path(__file__).resolve().parent
    package=here.parents[2]
    approval=load(here/"MAIN_APPROVAL.json")
    manifest=load(here/"FIT_SOURCE_MANIFEST_V1.json")
    if approval["data_file_sha256"]!="50feef0643aa4b5fb8ce0b75fbd3fb5ce7178de71bb7a45b92196261c16e335a" or approval["physics_authorized"] is not False:
        raise ValueError("EXACT_MAIN_APPROVAL_SCOPE")
    for relative,expected in manifest["local_files_sha256"].items():
        if sha(here/relative)!=expected: raise ValueError("FROZEN_FIT_SOURCE_CHANGED:"+relative)
    for relative,expected in approval["read_only_file_sha256"].items():
        if sha(package/relative)!=expected: raise ValueError("APPROVED_READ_ONLY_INPUT_CHANGED:"+relative)
    for relative,expected in load(here/"read_only_preparation_v1/INPUT_SOURCE_MANIFEST.json")["source_files_sha256"].items():
        if sha(package/relative)!=expected: raise ValueError("ONE_OF_99_DATA_SOURCES_CHANGED:"+relative)
    data=load(here/"read_only_preparation_v1/DATASET_DRAFT.json")
    if sha(here/"read_only_preparation_v1/DATASET_DRAFT.json")!=approval["data_file_sha256"] or data["training_ready"] is not True:
        raise ValueError("EXACT_COMPLETE_DATA_FREEZE")
    if len(data["contexts_evaluation_only"])!=10 or len(data["rows"])!=48 or len(data["closed_new_groups_evaluation_only"])!=4:
        raise ValueError("APPROVED_CONTEXT_AND_ROW_COUNTS")
    if any(os.environ.get(name)!="1" for name in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")):
        raise ValueError("SINGLE_CPU_THREAD_ENV_REQUIRED")
    activation=load(package/"ACTIVATION.json")
    global_stop=datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if time.time()>=global_stop-60: raise ValueError("ORIGINAL_GLOBAL_DEADLINE")
    out=here/"approved_fit_v1"
    if out.exists(): raise ValueError("REFUSE_FIT_OUTPUT_OVERWRITE")
    out.mkdir()
    start=invocation_start;cpu_start=invocation_cpu;stop=min(start+60,global_stop)
    if time.time()>=stop:raise TimeoutError("READ_ONLY_PREFLIGHT_CONSUMED_LOCAL_WINDOW")
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("APPROVED_LOCAL_OR_GLOBAL_FIT_DEADLINE")))
    signal.setitimer(signal.ITIMER_REAL,stop-time.time())
    start_doc={"status":"STARTED_APPROVED_OFFLINE_BC_AND_RULE_SEARCH","start_unix":start,"local_deadline_unix":stop,
               "global_deadline_unix":global_stop,"resources":resource_record(),"approval_sha256":sha(here/"MAIN_APPROVAL.json"),
               "source_manifest_sha256":sha(here/"FIT_SOURCE_MANIFEST_V1.json"),"data_file_sha256":approval["data_file_sha256"],
               "read_only_preflight_wall_s":time.time()-invocation_start,"read_only_preflight_cpu_s":time.process_time()-invocation_cpu,
               "model_fits_requested":3,"preprocessing_fits_requested":1,"rule_searches_requested":6,"new_physics":0}
    put(out/"START.json",start_doc)
    counters={"logical_BC3_to5_shared_policy_constructions":0,"independent_training_policy_copies":0,
              "normalization_preprocessing_fits":0,"BC_fits_started":0,"BC_fits_completed":0,"rule_searches_started":0,
              "rule_searches_completed":0,"new_API_BC_calls":0,"new_API_rule_calls":0,
              "direct_logit_forward_evaluations":0,"verification_only_reparameterized_views":0,
              "analytical_reparameterizations_initialization":0,"normalization_scalar_statistics":0}
    api_attempted={};api_completed={};policies={};traces={};rules={};diagnostics={};rule_counts={}
    original={}
    try:
        sys.path.insert(0,str(package/"families/ppo_reward"))
        import categorical_policy as categorical
        if Path(categorical.__file__).resolve()!=package/"families/ppo_reward/categorical_policy.py":
            raise ValueError("WRONG_CATEGORICAL_DEPENDENCY")
        import context_aggregation_api_v1 as api
        if sha(Path(api.__file__))!=manifest["local_files_sha256"]["context_aggregation_api_v1.py"]:
            raise ValueError("WRONG_NEW_DEPLOYMENT_SOURCE")
        for name in ("initialize","probabilities","design","choose","select_out0","update","policy_sha256"):
            original[name]=getattr(categorical,name)
            def counted(*args,_name=name,**kwargs):
                api_attempted[_name]=api_attempted.get(_name,0)+1
                result=original[_name](*args,**kwargs)
                api_completed[_name]=api_completed.get(_name,0)+1
                return result
            setattr(categorical,name,counted)
        def clock_guard():
            if time.time()>=stop: raise TimeoutError("APPROVED_LOCAL_OR_GLOBAL_FIT_DEADLINE")
        contexts=data["contexts_evaluation_only"]
        groups=sorted(contexts)
        old_groups=[g for g in groups if contexts[g]["origin"]=="HISTORICAL_EXPOSED_DEVELOPMENT"]
        new_groups=data["closed_new_groups_evaluation_only"]
        teachers={r["context_group_evaluation_only"]:r for r in data["teacher_labels_training_only"]}
        menu=data["menu"];hashes=menu["full_recipe_sha256"]
        if [digest(c) for c in menu["action_contracts"]]!=hashes: raise ValueError("ACTUAL_FIVE_MENU_DIGEST")
        features=data["feature_names"]
        if features!=api.FEATURE_NAMES or len(old_groups)!=6 or len(new_groups)!=4: raise ValueError("REGISTERED_CAUSAL_FEATURES_AND_GROUPS")
        parent=load(package/data["parent_BC_reference"]["path"])["policy"]
        if parent["action_sha256"]!=hashes[:3] or [digest(c) for c in parent["action_contracts"]]!=hashes[:3]:
            raise ValueError("ACTUAL_THREE_RECIPE_PARENT")
        old_norm=copy.deepcopy(parent["normalization"])
        counters["normalization_preprocessing_fits"]+=1
        matrix=[contexts[g]["features"] for g in new_groups]
        mean=[math.fsum(row[j] for row in matrix)/4 for j in range(25)]
        raw_std=[math.sqrt(math.fsum((row[j]-mean[j])**2 for row in matrix)/4) for j in range(25)]
        scale=[1.0 if s<1e-12 else s for s in raw_std]
        counters["normalization_scalar_statistics"]=50
        new_norm={"mean":mean,"scale":scale,"fit_scope":"NEW_FOUR_EXPOSED_DEVELOPMENT_CONTEXTS_ONLY",
                  "training_groups_evaluation_metadata":list(new_groups),"raw_population_std":raw_std,
                  "std_floor_rule":"IF_STD_LT_1e-12_REPLACE_WITH_1"}
        put(out/"NEW_DEVELOPMENT_NORMALIZATION.json",new_norm)
        lifted=copy.deepcopy(parent)
        lifted["action_contracts"]=copy.deepcopy(menu["action_contracts"]);lifted["action_sha256"]=list(hashes)
        phase_row=[.5*(a+b) for a,b in zip(parent["weights"][1],parent["weights"][2])]
        lifted["weights"]=[*copy.deepcopy(parent["weights"]),list(phase_row),list(phase_row)]
        lifted["version"]=0;lifted["counters"]={"forward":0,"backward_equivalent":0,"parameter_updates":0}
        lifted["training_data_semantics"]="APPROVED_DETERMINISTIC_BC3_TO5_INITIALIZATION"
        counters["logical_BC3_to5_shared_policy_constructions"]+=1
        def reparameterize_weights(weights,source_norm,target_norm):
            mapped=[]
            for row in weights:
                bias=row[0]+math.fsum(w*(m1-m0)/s0 for w,m1,m0,s0 in zip(row[1:],target_norm["mean"],source_norm["mean"],source_norm["scale"]))
                mapped.append([bias]+[w*s1/s0 for w,s1,s0 in zip(row[1:],target_norm["scale"],source_norm["scale"])])
            return mapped
        names=["OLD_ONLY_5_OLD_NORM","AGGREGATE_5_OLD_NORM","AGGREGATE_5_NEW_DEV_NORM"]
        for name in names:
            policies[name]=copy.deepcopy(lifted);counters["independent_training_policy_copies"]+=1
        policies[names[2]]["weights"]=reparameterize_weights(lifted["weights"],old_norm,new_norm)
        policies[names[2]]["normalization"]=copy.deepcopy(new_norm)
        counters["analytical_reparameterizations_initialization"]+=1
        categorical_sha=approval["read_only_file_sha256"]["families/ppo_reward/categorical_policy.py"]
        def bundle(name,model):
            return {"schema":"v8.context_aggregation_policy_bundle.v1","method_name":name,"feature_names":features,
                    "menu":copy.deepcopy(menu),"model":model,"training_data_file_sha256":approval["data_file_sha256"],
                    "source_dependency_sha256":{"categorical_policy.py":categorical_sha},
                    "sealed_validation_opened":False,"original_full_gate_is_final":True}
        def direct_logits(policy,x):
            counters["direct_logit_forward_evaluations"]+=1
            design=categorical.design(policy,x)
            logits=[math.fsum(w*v for w,v in zip(row,design)) for row in policy["weights"]]
            peak=max(logits);e=[math.exp(v-peak) for v in logits];denom=sum(e)
            return {"logits":logits,"probabilities":[v/denom for v in e]}
        def inspect_policy(name,policy,stage):
            result={}
            b=bundle(name,{"kind":"BC_LINEAR","policy":policy});bsha=digest(b)
            for group in groups:
                clock_guard();x=contexts[group]["features"]
                identity=digest(b)
                choice=api.select_out0(b,features,x,qa_validated=True,expected_bundle_sha256=bsha,frozen_recipe_sha256=hashes)
                counters["new_API_BC_calls"]+=1
                if digest(b)!=identity: raise ValueError("DEPLOYMENT_API_MUTATED_INPUT_BUNDLE")
                raw=direct_logits(policy,x)
                if max(abs(a-b) for a,b in zip(raw["probabilities"],choice["probabilities"]))>1e-9:
                    raise ValueError("MANUAL_LOGIT_AND_FROZEN_API_PROBABILITY_DIFFER")
                teacher=teachers[group]["teacher_action_index"]
                result[group]={"choice":choice,**raw,"teacher_index":teacher,"teacher_probability":choice["probabilities"][teacher],
                    "smallest_probability":min(choice["probabilities"]),"exact_zero_probability_count":sum(v==0.0 for v in choice["probabilities"])}
            diagnostics.setdefault(stage,{})[name]=result
            return result
        for name in names: inspect_policy(name,policies[name],"BEFORE_TRAINING")
        before_error={"max_abs_logit_error":0.0,"max_abs_probability_error":0.0,"per_context":[]}
        for group in groups:
            a=diagnostics["BEFORE_TRAINING"][names[1]][group];b=diagnostics["BEFORE_TRAINING"][names[2]][group]
            logerr=max(abs(x-y) for x,y in zip(a["logits"],b["logits"]));perr=max(abs(x-y) for x,y in zip(a["probabilities"],b["probabilities"]))
            tolerance=1e-9+1e-9*max(abs(v) for v in a["logits"])
            if logerr>tolerance or perr>1e-9: raise ValueError("INITIAL_RAW_INPUT_LOGIT_FUNCTION_NOT_NUMERICALLY_EQUIVALENT")
            before_error["max_abs_logit_error"]=max(before_error["max_abs_logit_error"],logerr)
            before_error["max_abs_probability_error"]=max(before_error["max_abs_probability_error"],perr)
            before_error["per_context"].append({"group":group,"logit_error":logerr,"probability_error":perr,"tolerance":tolerance})
        for name in names:
            selected=old_groups if name==names[0] else groups
            records=[{"features":contexts[g]["features"],"teacher_action_index":teachers[g]["teacher_action_index"],
                      "teacher_complete_and_qualified":True} for g in selected]
            policy=policies[name];traces[name]=[];counters["BC_fits_started"]+=1
            for step in range(240):
                clock_guard();before=copy.deepcopy(policy["weights"])
                update=categorical.update(policy,records,algorithm="BC",data_semantics=categorical.OFFLINE,
                    learning_rate=.15,epochs=1,max_gradient_norm=1.0,allow_offline_table=True)
                delta=math.sqrt(math.fsum((a-b)**2 for ar,br in zip(policy["weights"],before) for a,b in zip(ar,br)))
                if not all(math.isfinite(v) for row in policy["weights"] for v in row): raise ValueError("NONFINITE_BC_PARAMETER_STEP")
                traces[name].append({"step":step,**update["steps"][0],"actual_parameter_delta_norm":delta,
                                     "weights_before_sha256":digest(before),"weights_after_sha256":digest(policy["weights"]),
                                     "source_policy_sha256":update["source_policy_sha256"],"result_policy_sha256":update["result_policy_sha256"]})
            counters["BC_fits_completed"]+=1
            put(out/(name+"_TRAINING.json"),{"fit_scope":"EXPOSED_DEVELOPMENT_ONLY","training_groups_evaluation_metadata":selected,
                "trace":traces[name],"policy_counters":policy["counters"],"policy":policy,"data_file_sha256":approval["data_file_sha256"]})
        for name in names: inspect_policy(name,policies[name],"AFTER_TRAINING")
        # A post-training change of coordinates of the SAME new-norm model.
        # This view is not trained and is not an additional fit/checkpoint.
        view={"feature_names":features,"normalization":old_norm,"weights":reparameterize_weights(policies[names[2]]["weights"],new_norm,old_norm)}
        counters["verification_only_reparameterized_views"]+=1
        after_error={"max_abs_logit_error":0.0,"max_abs_probability_error":0.0,"per_context":[]}
        for group in groups:
            original_row=diagnostics["AFTER_TRAINING"][names[2]][group];mapped=direct_logits(view,contexts[group]["features"])
            logerr=max(abs(a-b) for a,b in zip(original_row["logits"],mapped["logits"]));perr=max(abs(a-b) for a,b in zip(original_row["probabilities"],mapped["probabilities"]))
            tolerance=1e-9+1e-9*max(abs(v) for v in original_row["logits"])
            if logerr>tolerance or perr>1e-9: raise ValueError("POSTTRAINING_RAW_INPUT_REPARAMETERIZATION_IDENTITY_FAILED")
            after_error["max_abs_logit_error"]=max(after_error["max_abs_logit_error"],logerr)
            after_error["max_abs_probability_error"]=max(after_error["max_abs_probability_error"],perr)
            after_error["per_context"].append({"group":group,"logit_error":logerr,"probability_error":perr,"tolerance":tolerance})
        diagnostics["NORMALIZATION_FUNCTION_EQUIVALENCE"]={"before_training":before_error,"after_training_same_function_view":after_error,
            "arbitrary_raw_input_identity":"Exact affine algebra for every finite input; numerical checks above only on exposed dev values",
            "does_not_claim_trained_old_and_new_norm_optimizers_converged_to_same_policy":True}

        # All traditional selectors use the same ten teacher labels. Each exact
        # depth2 child is independently optimized; caching repeated subsets does
        # not alter the exhaustive candidate class.
        x=[contexts[g]["features"] for g in groups];y=[teachers[g]["teacher_action_index"] for g in groups]
        all_indices=tuple(range(len(groups)))
        def new_rule_counter():
            return {"threshold_candidates":0,"feature_value_partition_comparisons":0,"leaf_scores":0,
                    "leaf_teacher_label_visits":0,"cache_hits":0,"candidate_model_comparisons":0,
                    "cost_row_availability_checks":0,"cost_row_qualification_checks":0,"cost_row_JF_accumulations":0,"nearest_point_feature_transforms":0}
        def signature(tree):
            return (0,tree["action_index"]) if "action_index" in tree else (1,tree["feature_index"],tree["threshold"],signature(tree["left"]),signature(tree["right"]))
        def leaf(indices,c):
            c["leaf_scores"]+=1;c["leaf_teacher_label_visits"]+=len(indices)
            counts=[0]*5
            for i in indices:counts[y[i]]+=1
            action=max(range(5),key=lambda a:(counts[a],-a))
            return {"error":len(indices)-counts[action],"nodes":0,"tree":{"action_index":action}}
        def key(row): return (row["error"],row["nodes"],signature(row["tree"]))
        def splits(indices,c):
            for j in range(25):
                values=sorted({x[i][j] for i in indices})
                for low,high in zip(values,values[1:]):
                    threshold=low+.5*(high-low)
                    c["threshold_candidates"]+=1;c["feature_value_partition_comparisons"]+=len(indices)
                    left_list=[];right_list=[]
                    for i in indices:
                        (left_list if x[i][j]<=threshold else right_list).append(i)
                    left=tuple(left_list);right=tuple(right_list)
                    yield j,threshold,left,right
        def best_stump(indices,c,cache):
            if indices in cache: c["cache_hits"]+=1;return cache[indices]
            best=leaf(indices,c)
            for j,threshold,left,right in splits(indices,c):
                a,b=leaf(left,c),leaf(right,c)
                candidate={"error":a["error"]+b["error"],"nodes":1,"tree":{"feature_index":j,"threshold":threshold,"left":a["tree"],"right":b["tree"]}}
                c["candidate_model_comparisons"]+=1
                if key(candidate)<key(best):best=candidate
            cache[indices]=best;return best
        name="MAJORITY_TEACHER_CONSTANT";counters["rule_searches_started"]+=1;c=new_rule_counter()
        best=leaf(all_indices,c);rules[name]={"kind":"CONSTANT","tree":best["tree"]};rule_counts[name]=c;counters["rule_searches_completed"]+=1
        name="COST_TABLE_QUALIFIED_COMMON_SUPPORT_CONSTANT";counters["rule_searches_started"]+=1;c=new_rule_counter()
        table={(r["context_group_evaluation_only"],r["action_index"]):r["labels_evaluation_only"] for r in data["rows"]}
        common=[]
        for action in range(5):
            available=True
            for group in groups:
                c["cost_row_availability_checks"]+=1
                if (group,action) not in table or table[group,action]["complete"] is not True:
                    available=False;break
            if available:common.append(action)
        eligible=[];constant_audit=[]
        for action in common:
            qualified=[]
            for group in groups:c["cost_row_qualification_checks"]+=1;qualified.append(table[group,action]["original_qualified"] is True)
            total=None
            if all(qualified):
                c["cost_row_JF_accumulations"]+=len(groups);total=math.fsum(table[g,action]["JF_N_s"] for g in groups);eligible.append((total,action))
            constant_audit.append({"action_index":action,"all_training_contexts_qualified":all(qualified),"total_JF_if_all_qualified":total})
        if not eligible:raise ValueError("NO_COMPLETE_QUALIFIED_COMMON_SUPPORT_CONSTANT")
        action=min(eligible)[1];rules[name]={"kind":"CONSTANT","tree":{"action_index":action},"cost_table_selection_audit":constant_audit};rule_counts[name]=c;counters["rule_searches_completed"]+=1
        name="EXHAUSTIVE_STUMP";counters["rule_searches_started"]+=1;c=new_rule_counter();best=best_stump(all_indices,c,{})
        rules[name]={"kind":"STUMP","tree":best["tree"],"training_0_1_errors":best["error"]};rule_counts[name]=c;counters["rule_searches_completed"]+=1
        name="DEPTH2_TREE";counters["rule_searches_started"]+=1;c=new_rule_counter();cache={};best=leaf(all_indices,c)
        for j,threshold,left,right in splits(all_indices,c):
            clock_guard();a,b=best_stump(left,c,cache),best_stump(right,c,cache)
            candidate={"error":a["error"]+b["error"],"nodes":1+a["nodes"]+b["nodes"],"tree":{"feature_index":j,"threshold":threshold,"left":a["tree"],"right":b["tree"]}}
            c["candidate_model_comparisons"]+=1
            if key(candidate)<key(best):best=candidate
        rules[name]={"kind":"TREE_DEPTH2","tree":best["tree"],"training_0_1_errors":best["error"],"exact_search_with_subset_cache":True};rule_counts[name]=c;counters["rule_searches_completed"]+=1
        for name,norm in (("NEAREST_OLD_NORM",old_norm),("NEAREST_NEW_DEV_NORM",new_norm)):
            counters["rule_searches_started"]+=1;c=new_rule_counter();points=[]
            for group in groups:
                points.append({"standardized_features":[(v-m)/s for v,m,s in zip(contexts[group]["features"],norm["mean"],norm["scale"])],"teacher_action_index":teachers[group]["teacher_action_index"]})
                c["nearest_point_feature_transforms"]+=25
            rules[name]={"kind":"NEAREST","normalization":copy.deepcopy(norm),"training_points":points,
                         "training_tie_order_evaluation_metadata":groups};rule_counts[name]=c;counters["rule_searches_completed"]+=1
        bundles={name:bundle(name,{"kind":"BC_LINEAR","policy":policy}) for name,policy in policies.items()}
        bundles.update({name:bundle(name,rule) for name,rule in rules.items()})
        predictions={name:{g:diagnostics["AFTER_TRAINING"][name][g]["choice"] for g in groups} for name in names}
        for name in rules:
            predictions[name]={}
            for group in groups:
                clock_guard();b=bundles[name];identity=digest(b)
                predictions[name][group]=api.select_out0(b,features,contexts[group]["features"],qa_validated=True,expected_bundle_sha256=identity,frozen_recipe_sha256=hashes)
                counters["new_API_rule_calls"]+=1
                if digest(b)!=identity:raise ValueError("RULE_API_MUTATED_INPUT")
        evaluations={}
        table={(r["context_group_evaluation_only"],r["action_index"]):r for r in data["rows"]}
        for name,choices in predictions.items():
            records=[]
            for group,choice in choices.items():
                row=table.get((group,choice["action_index"]));base=table[group,0]["labels_evaluation_only"]
                label=None if row is None else row["labels_evaluation_only"]
                qualified=label is not None and label["complete"] is True and label["original_qualified"] is True
                records.append({"group_evaluation_only":group,"action_name":choice["action_name"],"action_index":choice["action_index"],
                    "teacher_match":choice["action_index"]==teachers[group]["teacher_action_index"],"observed_outcome_available":row is not None,
                    "complete":None if label is None else label["complete"],"qualified":qualified,
                    "JF_N_s":None if label is None or label["complete"] is not True else label["JF_N_s"],
                    "JM_Nm_s":None if label is None or label["complete"] is not True else label["JM_Nm_s"],
                    "qualified_delta_JF_vs_B":label["JF_N_s"]-base["JF_N_s"] if qualified else None,
                    "qualified_delta_JM_vs_B":label["JM_Nm_s"]-base["JM_Nm_s"] if qualified else None,
                    "original_motion_failures":None if label is None else label.get("motion_failed_requirements"),
                    "original_source_row_id":None if row is None else row["id"]})
            evaluations[name]={"scope":"EXPOSED_DEVELOPMENT_REUSE_NOT_INDEPENDENT_TEST","records":records,
                "teacher_matches":sum(r["teacher_match"] for r in records),"qualified":sum(r["qualified"] for r in records),
                "available_labels":sum(r["observed_outcome_available"] for r in records),
                "qualified_sum_delta_JF":math.fsum(r["qualified_delta_JF_vs_B"] for r in records if r["qualified"]),
                "qualified_sum_delta_JM":math.fsum(r["qualified_delta_JM_vs_B"] for r in records if r["qualified"]),
                "missing_or_failed_outcomes_not_imputed":True}
        normalization_diagnostics={"teacher_class_counts":[sum(teachers[g]["teacher_action_index"]==a for g in groups) for a in range(5)],
             "new_context_teacher_class_counts":[sum(teachers[g]["teacher_action_index"]==a for g in new_groups) for a in range(5)],
             "unobserved_teacher_classes":[a for a in range(5) if not any(teachers[g]["teacher_action_index"]==a for g in groups)],
             "new_raw_std":raw_std,"std_replacement_feature_names":[features[j] for j,s in enumerate(raw_std) if s<1e-12],
             "tiny_raw_std_lt_1e_8_feature_names":[features[j] for j,s in enumerate(raw_std) if s<1e-8],
             "scale_ratio_new_over_old":[a/b for a,b in zip(scale,old_norm["scale"])],"standardized_ranges":{}}
        for norm_name,norm in (("OLD_PARENT",old_norm),("NEW_DEV_FOUR",new_norm)):
            normalization_diagnostics["standardized_ranges"][norm_name]={}
            for subset_name,subset in (("HISTORICAL",old_groups),("NEW_EXPOSED_DEV",new_groups)):
                z=[[(v-m)/s for v,m,s in zip(contexts[g]["features"],norm["mean"],norm["scale"])] for g in subset]
                normalization_diagnostics["standardized_ranges"][norm_name][subset_name]={"max_abs_z":max(abs(v) for row in z for v in row),
                    "per_feature_max_abs_z":[max(abs(row[j]) for row in z) for j in range(25)],
                    "feature_scalar_count_abs_z_gt3":sum(abs(v)>3 for row in z for v in row),
                    "feature_scalar_count_abs_z_gt10":sum(abs(v)>10 for row in z for v in row),
                    "scope":"EXPOSED_CONTEXT_SCALE_DIAGNOSTIC_NOT_INDEPENDENT_OOD_TEST"}
        for name,b in bundles.items():
            put(out/"models"/(name+".json"),{"bundle":b,"bundle_object_sha256":digest(b),"scope":"FROZEN_EXPOSED_DEVELOPMENT_FIT_NOT_VALIDATION"})
        for filename,doc in (("DIAGNOSTICS.json",diagnostics),("NORMALIZATION_AND_RARE_CLASS_DIAGNOSTICS.json",normalization_diagnostics),
                             ("RULE_SEARCH_COUNTS.json",rule_counts),("DEVELOPMENT_EVALUATIONS.json",evaluations)):
            put(out/filename,doc)
        if api_attempted.get("initialize",0)!=0 or sum(p["counters"]["parameter_updates"] for p in policies.values())!=720 or sum(p["counters"]["forward"] for p in policies.values())!=6240:
            raise ValueError("APPROVED_MODEL_UPDATE_OR_FORWARD_ACCOUNTING_MISMATCH")
        if counters["normalization_preprocessing_fits"]!=1 or counters["BC_fits_completed"]!=3 or counters["rule_searches_completed"]!=6 or counters["new_API_BC_calls"]!=60 or counters["new_API_rule_calls"]!=60 or counters["direct_logit_forward_evaluations"]!=70:
            raise ValueError("APPROVED_PREPROCESSING_RULE_OR_DIAGNOSTIC_ACCOUNTING_MISMATCH")
        for relative,expected in manifest["local_files_sha256"].items():
            if sha(here/relative)!=expected:raise ValueError("SOURCE_CHANGED_DURING_FIT")
        for relative,expected in approval["read_only_file_sha256"].items():
            if sha(package/relative)!=expected:raise ValueError("READ_ONLY_SOURCE_CHANGED_DURING_FIT")
        end={**start_doc,"status":"PASS_EXACT_APPROVED_OFFLINE_FITS_DEVELOPMENT_ONLY","end_unix":time.time(),"wall_s":time.time()-start,
             "cpu_s":time.process_time()-cpu_start,"resources_end":resource_record(),"counters":counters,"categorical_api_attempted":api_attempted,
             "categorical_api_completed":api_completed,"actual_BC_fits":3,"actual_rule_searches":6,"normalization_fit":1,
             "training_forward":6240,"manual_backward_equivalent":6240,"SGD_parameter_steps":720,"adam_steps":0,
             "categorical_probability_forward_including_API_validation":6300,"direct_logit_diagnostic_forward":70,
             "total_linear_forward_evaluations_including_numerical_diagnostics":6370,
             "nearest_API_queries":20,"nearest_point_distance_evaluations":200,"nearest_squared_difference_terms":5000,
             "actual_initialization_work":"1 shared logical five-action lift + 3 independent training copies; categorical.initialize API=0",
             "initialization_equivalence":before_error,"posttrained_function_coordinate_equivalence":after_error,
             "new_physics":0,"sealed_validation_opened":False,"independent_test_claim":False,
             "primary_frozen_before_fit":"AGGREGATE_5_OLD_NORM","complete_rule_search_counts":rule_counts}
        put(out/"END.json",end)
        files={str(f.relative_to(out)):sha(f) for f in out.rglob("*") if f.is_file()}
        put(out/"DEPLOYMENT_FREEZE.json",{"schema":"v8.context_aggregation_deployment_freeze.v1","frozen_unix":time.time(),
            "files_sha256":files,"bundle_object_sha256":{name:digest(b) for name,b in bundles.items()},
            "primary":"AGGREGATE_5_OLD_NORM","API":"context_aggregation_api_v1.select_out0(document['bundle'],feature_names,commissioned25,qa_validated=True,expected_bundle_sha256=document['bundle_object_sha256'],frozen_recipe_sha256=frozen_five_menu)",
            "API_source_sha256":sha(here/"context_aggregation_api_v1.py"),"runner_source_sha256":sha(Path(__file__)),
            "no_further_fit_or_physics_authorized":True,"sealed_validation_opened":False})
        print(json.dumps({k:end[k] for k in ("status","wall_s","cpu_s","actual_BC_fits","actual_rule_searches","normalization_fit","training_forward","manual_backward_equivalent","SGD_parameter_steps","total_linear_forward_evaluations_including_numerical_diagnostics","new_physics")}))
    except BaseException as error:
        put(out/"FAILURE.json",{"status":"FAILED_PRESERVE_ALL_CONSUMED_COMPUTATION_NO_RETRY","error_type":type(error).__name__,"error":str(error),
            "created_unix":time.time(),"wall_s":time.time()-start,"resources":resource_record(),"counters":counters,
            "categorical_api_attempted":api_attempted,"categorical_api_completed":api_completed,"policies_after_failure":policies,
            "partial_training_traces":traces,"partial_rules":rules,"partial_rule_counts":rule_counts,"partial_diagnostics":diagnostics,
            "new_physics":0,"sealed_validation_opened":False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)


if __name__=="__main__":
    try:
        main()
    except BaseException as error:
        here=Path(__file__).resolve().parent
        if not (here/"approved_fit_v1/FAILURE.json").exists():
            target=here/("FIT_PREFLIGHT_OR_FINALIZATION_FAILURE_"+str(os.getpid())+".json")
            if not target.exists():
                put(target,{"status":"FAILED_PRESERVE_NO_RETRY","error_type":type(error).__name__,"error":str(error),
                    "created_unix":time.time(),"resources":resource_record(),"new_physics":0})
        raise
