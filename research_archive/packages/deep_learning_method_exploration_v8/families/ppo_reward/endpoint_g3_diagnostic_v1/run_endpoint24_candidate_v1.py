"""UNRUN fixed G3 4arms x frozen6contexts; reuse saved G0/G2 predictions.

Requires separate main approval. No initialization, restore, sampling, new
normalizer, context reconversion, fit or physics. First-batch labels unchanged.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import os
import resource
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]
OLD = PACKAGE/"families/ppo_reward/first_batch_diagnostic_v1"
GLOBAL_STOP = 1793114740.0
ARMS = ["RF_RAW","PPO_RAW","RF_SCALED","PPO_SCALED"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def write_new(path,value):
    with path.open("x") as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write("\n");stream.flush();os.fsync(stream.fileno())


def process():
    u=resource.getrusage(resource.RUSAGE_SELF)
    rss=int(next(row for row in Path("/proc/self/status").read_text().splitlines() if row.startswith("VmRSS:")).split()[1])
    return {"unix":time.time(),"cpu_self_s":u.ru_utime+u.ru_stime,"rss_KiB":rss,"maxrss_KiB":u.ru_maxrss,
        "pid":os.getpid(),"start_ticks":int(Path("/proc/self/stat").read_text().rsplit(")",1)[1].split()[19]),
        "sys_executable":sys.executable,"binary":str(Path(sys.executable).resolve()),"binary_sha256":sha(Path(sys.executable).resolve())}


def kl(p,q):
    if any(a>0 and b==0 for a,b in zip(p,q)):
        return {"status":"POSITIVE_MASS_OVER_ZERO","value":None}
    return {"status":"FINITE","value":sum(a*math.log(a/b) for a,b in zip(p,q) if a>0)}


def label_state(rows):
    if not rows:return "UNKNOWN"
    if any(row["complete"] is not True for row in rows):return "OBSERVED_INCOMPLETE_NO_SUCCESS_RANKING"
    qualified={row["original_qualified"] for row in rows}
    return "OBSERVED_QUALIFIED" if qualified=={True} else "OBSERVED_FAILED_ORIGINAL_QUALIFICATION" if qualified=={False} else "OBSERVED_MIXED_QUALIFICATION"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval",required=True);parser.add_argument("--approval-sha",required=True)
    args=parser.parse_args();start=process()
    if sha(args.approval)!=args.approval_sha:raise ValueError("EXACT_MAIN_APPROVAL_REQUIRED")
    approval=json.loads(Path(args.approval).read_text())
    binding_path=HERE/"SOURCE_AND_INPUT_BINDING_V1.json"
    if (approval.get("schema")!="v8.endpoint_g3_fixed_inference_authorization.v1" or approval.get("approved") is not True or
            approval.get("source_binding_sha256")!=sha(binding_path) or approval.get("planned_select_out0_calls")!=24 or
            approval.get("maximum_wall_CPU_s")!=60 or approval.get("expected_binary_sha256")!=start["binary_sha256"] or
            not approval.get("approved_unix",float("inf"))<=start["unix"]<approval["local_stop_unix"]<=min(start["unix"]+60.,GLOBAL_STOP)):
        raise ValueError("SEPARATE_FIXED_24_FORWARD_ONLY_SOURCE_AND_TIME_APPROVAL_REQUIRED")
    binding=json.loads(binding_path.read_text())
    def verify():
        for relative,expected in binding["files_sha256"].items():
            if sha(PACKAGE/relative)!=expected:raise ValueError("FROZEN_SOURCE_OR_INPUT_CHANGED:"+relative)
    verify()
    output=HERE/"inference_once"
    output.mkdir(exist_ok=False)
    allowed=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{allowed[0]})
    actual={"select_out0_entry":0,"select_out0_completed":0,"policy_forward_delta":0,"logical_policy_deepcopies":0,
        "to_context25":0,"normalizer_fit":0,"initialize":0,"restore":0,"RNG_draws":0,"fit_gradient_updates":0,
        "G0_G2_forward_recomputed":0,"new_physics":0}
    write_new(output/"START.json",{"START":start,"source_binding_sha256":sha(binding_path),"approval_sha256":args.approval_sha,
        "planned_forwards":24,"local_stop_unix":approval["local_stop_unix"],"original_global_stop_unix":GLOBAL_STOP,
        "affinity":sorted(os.sched_getaffinity(0)),"training_clock_changed":False})
    def timeout(signum,frame):raise TimeoutError("ENDPOINT_FIXED_INFERENCE_LOCAL_OR_GLOBAL_STOP")
    signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGXCPU,timeout)
    resource.setrlimit(resource.RLIMIT_CPU,(60,61))
    signal.setitimer(signal.ITIMER_REAL,max(.001,approval["local_stop_unix"]-time.time()))
    predictions=[]
    try:
        os.environ.update(OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",MKL_NUM_THREADS="1")
        sys.path.insert(0,str(PACKAGE/"families/ppo_reward"))
        import categorical_policy as categorical
        import numpy as np
        if Path(categorical.__file__).resolve()!=PACKAGE/"families/ppo_reward/categorical_policy.py" or np.__version__!="2.2.6":
            raise ValueError("APPROVED_ORIGINAL_CATEGORICAL_AND_NUMPY_ENVIRONMENT")
        write_new(output/"ENVIRONMENT_BEFORE_FIRST_POLICY_CALL.json",{"numpy_version":np.__version__,"numpy_module":np.__file__,
            "numpy_module_sha256":sha(np.__file__),"process":process(),"actual_calls":actual})
        inputs=json.loads((OLD/"INPUTS_V1.json").read_text())
        contexts=json.loads((OLD/"inference_once_v2/CAUSAL25_CONTEXTS.json").read_text())
        previous=json.loads((OLD/"inference_once_v2/RESULTS.json").read_text())
        if len(previous["predictions"])!=48 or len(contexts)!=6:raise ValueError("EXACT_SAVED_48_AND_SIX_CONTEXT_CACHE")
        lookup={(row["generation"],row["arm_id"],row["context_evaluation_only"]):row for row in previous["predictions"]}
        expected_groups=[item["group_evaluation_only"] for item in inputs["contexts"]]
        if set(expected_groups)!=set(contexts):raise ValueError("ORIGINAL_SIX_EXPOSED_CONTEXT_IDENTITIES")
        with (output/"FORWARD_TRACE.jsonl").open("x") as trace:
            for item in binding["G3_checkpoints"]:
                checkpoint=json.loads((PACKAGE/item["path"]).read_text())
                policy=copy.deepcopy(checkpoint["policy"]);actual["logical_policy_deepcopies"]+=1
                behavior=categorical.policy_sha256(policy)
                if (behavior!=item["policy_behavior_sha256"] or [digest(recipe) for recipe in policy["action_contracts"]]!=inputs["menu"]["full_recipe_sha256"] or
                        policy["action_sha256"]!=inputs["menu"]["full_recipe_sha256"]):raise ValueError("G3_ACTUAL_RECIPE_AND_POLICY_IDENTITY")
                for group in expected_groups:
                    context=contexts[group]
                    if context["causal25_numeric_identity_sha256"]!=digest({"names":context["context25"]["feature_names"],"values":context["context25"]["features"]}):
                        raise ValueError("CACHED_CAUSAL25_IDENTITY")
                    before=copy.deepcopy(policy["counters"])
                    actual["select_out0_entry"]+=1
                    try:
                        chosen=categorical.select_out0(policy,context["context25"]["feature_names"],context["context25"]["features"],qa_validated=True)
                    finally:
                        actual["policy_forward_delta"]+=policy["counters"]["forward"]-before["forward"]
                    actual["select_out0_completed"]+=1
                    if (policy["counters"]["forward"]!=before["forward"]+1 or
                            any(policy["counters"][key]!=before[key] for key in ("backward_equivalent","parameter_updates")) or
                            categorical.policy_sha256(policy)!=behavior):raise ValueError("READ_ONLY_FORWARD_COUNTER_CONTRACT")
                    labels=context["labels_by_full_recipe_sha256_evaluation_only"]
                    probabilities=chosen["probabilities"]
                    mass={key:0. for key in ("OBSERVED_QUALIFIED","OBSERVED_FAILED_ORIGINAL_QUALIFICATION","UNKNOWN","OBSERVED_INCOMPLETE_NO_SUCCESS_RANKING","OBSERVED_MIXED_QUALIFICATION")}
                    for recipe,probability in zip(inputs["menu"]["full_recipe_sha256"],probabilities):mass[label_state(labels[recipe])]+=probability
                    row={"generation":3,"arm_id":item["arm_id"],"context_evaluation_only":group,
                        "checkpoint":item,"categorical_source_sha256":binding["files_sha256"]["families/ppo_reward/categorical_policy.py"],
                        "causal25_numeric_identity_sha256":context["causal25_numeric_identity_sha256"],
                        "raw_context_file_sha256":context["raw_context_file_sha256"],"probabilities":probabilities,
                        "entropy_nats":-sum(p*math.log(p) for p in probabilities if p>0),
                        "argmax_action_index":chosen["action_index"],"argmax_action_name":inputs["menu"]["action_names"][chosen["action_index"]],
                        "argmax_full_recipe_sha256":chosen["full_recipe_sha256"],
                        "argmax_original_firstbatch_label_status":label_state(labels[chosen["full_recipe_sha256"]]),
                        "argmax_original_firstbatch_observations":labels[chosen["full_recipe_sha256"]],"observed_qualification_mass":mass,
                        "new_batch2_labels_joined":False,"control_benefit_inferred":False}
                    comparisons=[]
                    for generation in (0,2):
                        old=lookup[(generation,item["arm_id"],group)]
                        comparisons.append({"reference_generation":generation,"saved_reference_prediction_sha256":digest(old),
                            "old_argmax":old["argmax_action_name"],"new_argmax":row["argmax_action_name"],
                            "entropy_delta_nats":row["entropy_nats"]-old["entropy_nats"],"KL_G3_to_reference":kl(probabilities,old["probabilities"]),
                            "KL_reference_to_G3":kl(old["probabilities"],probabilities),
                            "total_variation":.5*sum(abs(a-b) for a,b in zip(probabilities,old["probabilities"]))})
                    row["comparisons_reusing_saved_predictions"]=comparisons
                    predictions.append(row);trace.write(json.dumps(row,allow_nan=False)+"\n");trace.flush();os.fsync(trace.fileno())
        if actual["select_out0_completed"]!=24 or actual["policy_forward_delta"]!=24:raise ValueError("EXACT_24_FORWARD_ACCOUNTING")
        verify()
        write_new(output/"RESULTS.json",{"schema":"v8.endpoint_g3_fixed_policy_diagnostic.v1","status":"PASS_24_FORWARD_ONLY_EXPOSED_DEVELOPMENT",
            "predictions":predictions,"actual_calls":actual,"references_reused_file_sha256":sha(OLD/"inference_once_v2/RESULTS.json"),
            "original_input_labels_unchanged":True,"independent_validation_or_control_gain_claim":False})
        write_new(output/"END.json",{"START":start,"END":process(),"actual_calls":actual,"results_sha256":sha(output/"RESULTS.json")})
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0.)
        write_new(output/"FAILED.json",{"START":start,"END":process(),"actual_calls":actual,
            "error_type":type(error).__name__,"error":str(error),"completed_rows":len(predictions),"automatic_retry_authorized":False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0.)


if __name__=="__main__":main()
