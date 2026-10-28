"""Not yet authorized to run. Explicit main-agent flag required; no actor/env.

This future gate exercises pure mappings/distribution mathematics only. It does
not initialize a linear head, run policy forward, update parameters or launch
physics. All first-run outputs use a new directory, never overwrite failures.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import os
import random
import signal
import sys
import time
from datetime import datetime

sys.dont_write_bytecode = True
from axis_mapping import make_axis_contract, map_lambda, digest
from beta_policy import log_density, raw_shape_score, shapes_from_raw, surrogate_coefficient


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--main-agent-approved-math-only",action="store_true")
    args.add_argument("--package",required=True)
    args.add_argument("--output",required=True)
    cfg = args.parse_args()
    if cfg.main_agent_approved_math_only is not True:
        raise ValueError("EXPLICIT_MAIN_AGENT_MATH_GATE_APPROVAL_REQUIRED")
    package = Path(cfg.package).resolve()
    activation = json.loads((package/"ACTIVATION.json").read_text())
    original_deadline = datetime.fromisoformat(activation["hard_deadline_utc"]).timestamp()
    if time.time()>=original_deadline-20:
        raise ValueError("INSUFFICIENT_TIME_BEFORE_ORIGINAL_GLOBAL_DEADLINE")
    output = Path(cfg.output).resolve()
    family = package / "families/ppo_reward/continuous_scale_v1"
    if not output.is_relative_to(family) or output.exists():
        raise ValueError("UNIQUE_OUTPUT_INSIDE_CONTINUOUS_SCALE_FAMILY_REQUIRED")
    output.mkdir(parents=True)
    start = time.time()
    cpu = time.process_time()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError("MATH_GATE_20_SECONDS")))
    signal.alarm(20)
    files = ["runtime/FROZEN_18D.json","runtime/PARAMETER_MAP.json","runtime/ACTION_SET.json",
             "source/v8_worker_v1.py","runtime/control/campaign_v6.py","runtime/control/base_campaign.py",
             "runtime/code/rich_planner.py","runtime/code/terminal_repair.py","runtime/control/round_planner.py",
             "runtime/control/early_return_planner.py","runtime/control/terminal_planner.py"]
    source_hashes = {r:hashlib.sha256((package/r).read_bytes()).hexdigest() for r in files}
    receipt = {"status":"RUNNING_IF_MAIN_APPROVED","pid":os.getpid(),"start_unix":start,"timeout_s":20,
               "original_global_deadline_unix":original_deadline,
               "source_hashes":source_hashes,"new_actor_initializations":0,"model_forward":0,
               "model_backward":0,"parameter_updates":0,"env_constructs":0,"physics":0}
    (output/"START.json").write_text(json.dumps(receipt,sort_keys=True,indent=2))
    try:
        frozen = json.loads((package/files[0]).read_text())
        mapping = json.loads((package/files[1]).read_text())
        candidate = next(x for x in json.loads((package/files[2]).read_text())["arms"] if x["id"]=="H150")
        axis = make_axis_contract(frozen,mapping,candidate,source_files_sha256=source_hashes)
        axis_sha = digest(axis)
        (output/"AXIS_CONTRACT.json").write_text(json.dumps(axis,sort_keys=True,indent=2))
        mapped = {str(lam):map_lambda(axis,lam,expected_axis_sha256=axis_sha) for lam in (0.0,.5,1.0)}
        assert mapped["0.0"]["proposal_action"]["parameters"] == [0.0]*18
        assert mapped["1.0"]["proposal_action"]["parameters"] == frozen["free_parameters"]
        for lam,entry in mapped.items():
            action = entry["proposal_action"]
            assert action["legacy"]==[0.0,0.0]
            assert len(action["candidate_overrides"]["posture"])==len(candidate["posture"])
            assert len(action["candidate_overrides"]["early"])==len(candidate["early"])
            assert len(action["candidate_overrides"]["timing"])==len(candidate["timing"])
            assert entry["full_recipe"]["outbound_terminal_repair_factor"]==1.5
            assert entry["full_recipe"]["lambda_zero_is_original_B"] is False
        rejected = []
        for value in (-1e-12,1.0+1e-12,float("nan"),True):
            try:
                map_lambda(axis,value,expected_axis_sha256=axis_sha)
                raise AssertionError("INVALID_LAMBDA_ACCEPTED")
            except ValueError:
                rejected.append(repr(value))
        altered = copy.deepcopy(axis)
        altered["h150_candidate"]["early"][0]["duration_factor"] += .001
        try:
            map_lambda(altered,.5,expected_axis_sha256=axis_sha)
            raise AssertionError("MUTATED_AXIS_ACCEPTED")
        except ValueError:
            pass
        density_calls = 0
        score_calls = 0
        def density(lam,a,b):
            nonlocal density_calls
            density_calls += 1
            return log_density(lam,a,b)
        quadrature = []
        nodes = 8192
        for alpha,beta in ((1.,1.),(2.,2.),(2.,8.),(8.,2.),(50.,50.)):
            integral = sum(math.exp(density((i+.5)/nodes,alpha,beta)) for i in range(nodes))/nodes
            assert abs(integral-1.0)<1e-5
            quadrature.append({"alpha":alpha,"beta":beta,"midpoint_nodes":nodes,"density_integral":integral})
        max_error = 0.0
        epsilon = 1e-6
        for raw_a,raw_b in ((-8.,-1.),(-1.,3.),(0.,0.),(3.,-1.),(10.,10.)):
            for lam in (.0001,.05,.5,.95,.9999):
                analytic = raw_shape_score(lam,raw_a,raw_b)
                score_calls += 1
                numeric = []
                for index in range(2):
                    plus = [raw_a,raw_b];minus = [raw_a,raw_b]
                    plus[index] += epsilon;minus[index] -= epsilon
                    ap,bp = shapes_from_raw(*plus);am,bm = shapes_from_raw(*minus)
                    numeric.append((density(lam,ap,bp)-density(lam,am,bm))/(2*epsilon))
                max_error = max(max_error,max(abs(a-b) for a,b in zip(analytic,numeric)))
        assert max_error<2e-6
        rng = random.Random(20261027)
        initial_rng = rng.getstate()
        samples = [rng.betavariate(2.,2.) for _ in range(4000)]
        assert all(0.<v<1. for v in samples)
        mean = sum(samples)/len(samples)
        assert abs(mean-.5)<6.0*math.sqrt(.05/len(samples))
        state = rng.getstate()
        future = [rng.betavariate(2.,2.) for _ in range(20)]
        rng.setstate(state)
        assert future==[rng.betavariate(2.,2.) for _ in range(20)]
        assert surrogate_coefficient(algorithm="PPO",new_logprob=-.3,old_logprob=-.3,advantage=1.)["ratio"]==1.
        assert surrogate_coefficient(algorithm="PPO",new_logprob=math.log(1.5),old_logprob=0.,advantage=1.)["score_coefficient"]==0.
        assert surrogate_coefficient(algorithm="PPO",new_logprob=math.log(.5),old_logprob=0.,advantage=-1.)["score_coefficient"]==0.
        for r,h in source_hashes.items():
            assert hashlib.sha256((package/r).read_bytes()).hexdigest()==h
        end = {**receipt,"status":"PASS_MATHEMATICS_ONLY_NO_EXECUTION_QUALIFICATION","end_unix":time.time(),
               "wall_s":time.time()-start,"cpu_s":time.process_time()-cpu,"axis_sha256":axis_sha,
               "mapped_engineering_proposals":mapped,"invalid_lambda_rejections":rejected,"axis_mutation_rejected":True,
               "quadrature":quadrature,"raw_shape_score_max_finite_difference_error":max_error,
               "external_density_function_calls":density_calls,"external_score_function_calls":score_calls,
               "beta_RNG_draws":4040,"beta_2_2_sample_mean":mean,"rng_initial":initial_rng,"rng_final":rng.getstate(),
               "source_hashes_unchanged":True,"original_motion_or_task_qualification":False}
        (output/"END.json").write_text(json.dumps(end,sort_keys=True,indent=2))
        print(json.dumps({k:end[k] for k in ("status","wall_s","model_forward","parameter_updates","physics")}))
    except BaseException as error:
        (output/"FAILURE.json").write_text(json.dumps({"error":str(error),"error_type":type(error).__name__,"time_unix":time.time(),"preserve_partial":True,"physics":0},sort_keys=True,indent=2))
        raise


if __name__=="__main__":
    main()
