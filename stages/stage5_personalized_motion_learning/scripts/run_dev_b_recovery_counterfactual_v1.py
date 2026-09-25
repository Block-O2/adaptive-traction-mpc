"""NONDEPLOYABLE full-recovery continuation; stops before any task decision.

Reconstruct the identical saved pre-command state through the unchanged prefix,
then optionally change only the first 100 ms action application. All subsequent
recovery logic, state feedback and safety checks are the original DEV-A code.
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
import pickle
from time import perf_counter
import numpy as np
from dev_b_matched_diagnostics_v1 import (production, load_checkpoint, integration_state,
    evaluate_chain, physics_record, save_json, sha, serial, SCHEMA)


class RecoveryFinished(BaseException):pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir",type=Path,required=True)
    parser.add_argument("--arm",choices=["production_replay","action_transfer_100ms"],required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    cp=load_checkpoint(args.checkpoint_dir/"checkpoint.pkl.gz")
    manifest=json.loads((args.checkpoint_dir/"capture_manifest.json").read_text())
    historical=json.loads((Path(manifest["historical_path"])/"summary.json").read_text())
    delays=[x["runtime_ms"] for x in historical["dev_a_recovery"]["planner_decisions"]]
    if any(int(np.ceil(x/5))!=1 for x in delays):
        raise ValueError("this narrow counterfactual requires historical one-interval waits")
    original_execute=production._execute_interval
    original_recovery=production._run_dev_a_active_recovery
    original_timer=production.perf_counter
    first=True; offset=None; start=None; timer_n=0; real_start=0.0
    commands=[]; timings=[]; matched={}

    def timer():
        nonlocal timer_n,real_start
        index=timer_n//2
        if timer_n%2==0:
            real_start=perf_counter(); value=100+index
        else:
            actual_ms=1000*(perf_counter()-real_start)
            timings.append({"request_index":index,"actual_compute_ms":actual_ms,
                "replayed_ms":delays[min(index,len(delays)-1)],"replayed_age_s":0.005})
            if actual_ms>100:
                raise RuntimeError("diagnostic host exceeded unchanged 100 ms deadline")
            value=100+index+delays[min(index,len(delays)-1)]/1000
        timer_n+=1
        return value

    def execute(runtime,**kwargs):
        nonlocal first,offset,start,matched
        candidate=kwargs["candidate"]
        is_recovery=candidate.label.startswith("recovery_")
        fitted=kwargs["observation"].human_model_version.startswith("belief_")
        if not (is_recovery and fitted):return original_execute(runtime,**kwargs)
        now=float(runtime["plant"].data.time)
        if first:
            first=False;start=now
            original=cp["runtime"]
            matched={"integration_state_max_abs_delta":float(np.max(np.abs(integration_state(runtime["plant"])-integration_state(original["plant"])))),
                "qacc_warmstart_max_abs_delta":float(np.max(np.abs(runtime["plant"].data.qacc_warmstart-original["plant"].data.qacc_warmstart))),
                "observation_equal":asdict(kwargs["observation"])==asdict(cp["execute_kwargs"]["observation"]),
                "reference_history_pickle_equal":pickle.dumps(runtime["contract"].reference_motion_history)==pickle.dumps(original["contract"].reference_motion_history),
                "observer_cache_pickle_equal":pickle.dumps(runtime["observer"].__dict__)==pickle.dumps(original["observer"].__dict__),
                "measurement_history_rng_pickle_equal":pickle.dumps(runtime["measurement_layer"].__dict__)==pickle.dumps(original["measurement_layer"].__dict__),
                "monitor_pickle_equal":pickle.dumps(runtime["monitor"].__dict__)==pickle.dumps(original["monitor"].__dict__),
                "authority_pickle_equal":pickle.dumps(runtime["authority"].__dict__)==pickle.dumps(original["authority"].__dict__),
                "supervisor_pickle_equal":pickle.dumps(runtime["supervisor"].__dict__)==pickle.dumps(original["supervisor"].__dict__)}
            save_json(args.output/"matched_checkpoint_validation.json",matched)
            # Pickle encodes alias/layout details as well as values. Preserve
            # that audit result; compare complete named supervisor state values
            # when its byte representation differs after deep-copy restoration.
            supervisor_current=serial(runtime["supervisor"].__dict__)
            supervisor_saved=serial(original["supervisor"].__dict__)
            matched["supervisor_complete_value_equal"]=(supervisor_current==supervisor_saved)
            save_json(args.output/"supervisor_state_comparison.json",{"current":supervisor_current,"saved":supervisor_saved})
            for item in (supervisor_current,supervisor_saved):
                item.pop("computation_ms",None)
                if item.get("last_safety_filter") is not None:
                    item["last_safety_filter"].pop("computation_ms",None)
            matched["supervisor_action_state_equal"]=(supervisor_current==supervisor_saved)
            matched["excluded_nondeterministic_metadata_paths"]=["computation_ms","last_safety_filter/computation_ms"]
            save_json(args.output/"matched_checkpoint_validation.json",matched)
            if matched["integration_state_max_abs_delta"]!=0 or matched["qacc_warmstart_max_abs_delta"]!=0 or not all(v for k,v in matched.items() if k.endswith("equal") and k not in ("supervisor_pickle_equal","supervisor_complete_value_equal")):
                raise AssertionError("full-recovery counterfactual prefix not exactly matched")
            old,new=cp["recovery"]["old_model"],runtime["model"]
            interface=kwargs["interface"]
            xo=old.geometry.estimate_state(interface.human_position_world_m,interface.human_rotation_world,
                interface.human_velocity_world_m_s,interface.human_angular_velocity_world_rad_s)
            xn=kwargs["observation"].as_array()
            kp,kd=runtime["contract"].position_gain,runtime["contract"].velocity_gain
            ao=kp*(candidate.q_waypoint_rad-xo[:2])+kd*(candidate.dq_waypoint_rad_s-xo[2:])
            an=kp*(candidate.q_waypoint_rad-xn[:2])+kd*(candidate.dq_waypoint_rad_s-xn[2:])
            offset=old.inverse_dynamics(xo[:2],xo[2:],ao)-new.inverse_dynamics(xn[:2],xn[2:],an)
        before=physics_record(runtime["plant"])
        if args.arm=="action_transfer_100ms" and now-start<0.1-1e-12:
            s=float(np.clip((now-start)/0.1,0,1));alpha=1-(10*s**3-15*s**4+6*s**5)
            model=runtime["model"];state=kwargs["observation"].as_array()
            ddq=runtime["contract"].position_gain*(candidate.q_waypoint_rad-state[:2])+runtime["contract"].velocity_gain*(candidate.dq_waypoint_rad_s-state[2:])
            action=model.inverse_dynamics(state[:2],state[2:],ddq)+alpha*offset
            command,row=evaluate_chain(runtime,kwargs["measurement"],kwargs["interface"],kwargs["mapped_override"],model,state,action_override=action)
            plant=runtime["plant"];plant.apply_executable_command(command)
            for _ in range(round(production.CONTROL_DT_S/production.NOMINAL_PHYSICS_DT_S)):
                plant.step()
                runtime["true_physics_monitor"].observe(plant)
            runtime["last_command"]=command
            result=(command,{"generalized_action_nm":action,"desired_acceleration_rad_s2":ddq,
                "safety_mode":row["safety_mode"],"safety_filter":row["filter_diagnostics"],
                "brake":row["safety_mode"]=="BRAKE","force_gate":command.margin_to_force_gate_n<=0})
        else:result=original_execute(runtime,**kwargs)
        commands.append({"time_s":now,"physics_before":before,"command_nm":result[0].joint_torque_command_nm,
            "estimated_state":kwargs["observation"].as_array(),"generalized_action_nm":result[1]["generalized_action_nm"]})
        return result

    def recovery(runtime,**kwargs):
        result=original_recovery(runtime,**kwargs)
        save_json(args.output/"recovery_result.json",{"schema":SCHEMA,"arm":args.arm,"recovery":result,
            "commands":commands,"planner_timing":timings,"source_script_sha256":sha(__file__),
            "stop":"before task entry; no task planning or qualification", "model_laws_changed":False})
        trace=kwargs["trace"]
        save_json(args.output/"recovery_trace.json",[x for x in trace if x["stage"]=="ACTIVE_RECOVERY"])
        if args.arm=="production_replay":
            h=np.load(Path(manifest["historical_path"])/"trace.npz",allow_pickle=True)
            error=0.0
            for row in commands:
                idx=int(np.flatnonzero(np.isclose(h["time_s"],row["time_s"],atol=1e-10,rtol=0))[-1])
                error=max(error,float(np.max(np.abs(h["cr12_actuator_command_nm"][idx]-row["command_nm"]))))
            save_json(args.output/"historical_replay_validation.json",{"maximum_command_difference_nm":error,
                "matched_intervals":len(commands),"same_abort_reason":result["abort_reason"]==historical["dev_a_recovery"]["abort_reason"]})
            if error>1e-7:raise AssertionError("long baseline differs from historical recovery")
        print(json.dumps({"arm":args.arm,"succeeded":result["succeeded"],"abort":result["abort_reason"],"duration":result["duration_s"]}),flush=True)
        raise RecoveryFinished()

    production._execute_interval=execute;production._run_dev_a_active_recovery=recovery;production.perf_counter=timer
    try:
        production.run_executed_case(args.output/"prefix",qualification_case=manifest["case"],qualification_arm="continual_adaptive",
            simulate_planning_latency=True,dev_a_recovery=True,formal_qualification=False)
    except RecoveryFinished:pass
    finally:
        production._execute_interval=original_execute;production._run_dev_a_active_recovery=original_recovery;production.perf_counter=original_timer


if __name__=="__main__":main()
