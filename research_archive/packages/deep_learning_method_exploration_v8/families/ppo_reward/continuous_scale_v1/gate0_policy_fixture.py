"""Approved Gate0 synthetic API fixture, zero training or physics.

This is separate from the direct mathematical density gate so its actual actor
initialization/forward/sample/score calls remain explicit synthetic accounting.
"""
from pathlib import Path
import argparse
import hashlib
import json
import random
import signal
import sys
import time

sys.dont_write_bytecode = True
import beta_policy as beta
from axis_mapping import digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-agent-approved-gate0",action="store_true")
    args = parser.parse_args()
    if not args.main_agent_approved_gate0:
        raise ValueError("EXPLICIT_GATE0_APPROVAL_REQUIRED")
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    from datetime import datetime
    activation = json.loads((root/"ACTIVATION.json").read_text())
    deadline = datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if time.time()>=deadline-20:
        raise ValueError("ORIGINAL_GLOBAL_DEADLINE")
    manifest = json.loads((here/"SOURCE_MANIFEST.json").read_text())
    for rel,expected in manifest["local_files_sha256"].items():
        assert hashlib.sha256((here/rel).read_bytes()).hexdigest()==expected
    for rel,expected in manifest["read_only_source_sha256"].items():
        assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected
    out = here/"gate0_policy_fixture_v1"
    if out.exists():
        raise ValueError("REFUSE_FIXTURE_OVERWRITE")
    out.mkdir()
    start = time.time()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("SYNTHETIC_GATE0_20S")))
    signal.alarm(20)
    start_doc = {"status":"RUNNING_SYNTHETIC_GATE0_ONLY","start_unix":start,"new_physics":0,"real_training_updates":0,
                 "original_manifest_sha256":hashlib.sha256((here/"SOURCE_MANIFEST.json").read_bytes()).hexdigest(),
                 "fixture_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/"START.json").write_text(json.dumps(start_doc,sort_keys=True,indent=2))
    try:
        axis = json.loads((here/"gate0_math_v1/AXIS_CONTRACT.json").read_text())
        proof = json.loads((here/"gate0_math_v1/END.json").read_text())
        assert digest(axis)==proof["axis_sha256"]
        calls = {"log_density":0,"raw_shape_score":0,"shapes_from_raw":0}
        originals = {name:getattr(beta,name) for name in calls}
        def wrap(name):
            def counted(*a,**kw):
                calls[name] += 1
                return originals[name](*a,**kw)
            return counted
        for name in calls:
            setattr(beta,name,wrap(name))
        norm = {"mean":[0.0]*25,"scale":[1.0]*25,"fit_scope":"SYNTHETIC_ZERO_FIXTURE_ONLY"}
        policy = beta.initialize(beta.FEATURE_NAMES,norm,axis,axis_sha256=digest(axis),seed=20261027,arm_id="SYNTHETIC_MATH_FIXTURE_NOT_FOR_DEPLOYMENT",gain=1.0)
        initial = beta.policy_sha256(policy)
        rng = random.Random(20261027)
        kwargs = {"qa_validated":True,"frozen_axis_sha256":digest(axis)}
        samples = []
        for _ in range(32):
            sample = beta.sample(policy,beta.FEATURE_NAMES,[0.0]*25,rng=rng,**kwargs)
            assert 0.0<sample["lambda_sample"]<1.0 and sample["post_sampling_clip"] is False
            assert sample["alpha"]==2.0 and sample["beta"]==2.0
            assert sample["old_logprob"]==beta.log_density(sample["lambda_sample"],sample["alpha"],sample["beta"])
            assert sample["physical_action_sha256"]==digest(sample["proposal_action"])
            assert sample["full_recipe_sha256"]==digest(sample["full_recipe"])
            samples.append(sample)
        mean = beta.deploy_mean(policy,beta.FEATURE_NAMES,[0.0]*25,**kwargs)
        assert mean["lambda"]==.5 and mean["old_logprob"] is None and mean["training_sample_eligible"] is False
        score = beta.score_for_weights(policy,beta.FEATURE_NAMES,[0.0]*25,samples[0]["lambda_sample"],**kwargs)
        assert len(score["score_gradient"])==2 and all(len(row)==26 for row in score["score_gradient"])
        assert beta.policy_sha256(policy)==initial
        end = {**start_doc,"status":"PASS_SYNTHETIC_ONLY_NO_TRAINING_OR_PHYSICS","end_unix":time.time(),"wall_s":time.time()-start,
               "synthetic_beta_actor_initializations":1,"synthetic_beta_actor_forward":policy["counters"]["forward"],
               "synthetic_beta_action_samples":32,"synthetic_mean_deployments":1,"synthetic_score_for_weights":1,
               "math_function_calls_including_internal":calls,"synthetic_parameter_updates":0,"real_model_fit":0,
               "policy_weights_and_behavior_unchanged":True,"axis_sha256":digest(axis),"synthetic_policy":policy,
               "sample_records":samples,"mean_deployment":mean,"score_receipt":score,"rng_final":rng.getstate()}
        (out/"END.json").write_text(json.dumps(end,sort_keys=True,indent=2))
        print(json.dumps({k:end[k] for k in ("status","wall_s","synthetic_beta_actor_initializations","synthetic_beta_actor_forward","math_function_calls_including_internal","real_model_fit","new_physics")}))
    except BaseException as error:
        (out/"FAILURE.json").write_text(json.dumps({"error":str(error),"type":type(error).__name__,"preserve_partial":True,"time_unix":time.time()},sort_keys=True,indent=2))
        raise


if __name__=="__main__":
    main()
