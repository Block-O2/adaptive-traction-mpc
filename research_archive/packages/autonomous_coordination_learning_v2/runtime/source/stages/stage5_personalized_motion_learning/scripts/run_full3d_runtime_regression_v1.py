#!/usr/bin/env python3
"""Existing nominal CR12 regression with request snapshots, no scientific changes."""
import argparse
from pathlib import Path
from time import perf_counter_ns, process_time_ns
import time

from study_full3d_planner_runtime_v1 import (
    ROOT, save, provenance, AdaptiveHumanWaypointHWMPCV22,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case
import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime_module


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',required=True)
    parser.add_argument('--inject-planner-delay-ms',type=float,default=0.)
    args=parser.parse_args()
    folder=ROOT/args.name
    provenance(folder/'study_provenance')
    calls=[]
    original=AdaptiveHumanWaypointHWMPCV22.decide
    original_execute=runtime_module._execute_interval
    pending_ready=[]
    def capture(self,**kwargs):
        request_started=perf_counter_ns()
        # No file IO on the critical path; inputs are copied before the call.
        request=dict(belief=kwargs['belief'].value_state_record(),
            previous_action=self.planner.previous_executed_delta_q_rad.copy(),
            inputs={k:v for k,v in kwargs.items() if k not in ('belief','value_evaluator')})
        request['inputs']['phase']=kwargs['phase'].value
        start=perf_counter_ns();cpu=process_time_ns()
        try:
            result=original(self,**kwargs)
            if args.inject_planner_delay_ms:
                time.sleep(args.inject_planner_delay_ms/1000.)
            request['outcome']='RESULT';request['selected']=result.executed.label
            return result
        except Exception as error:
            request['outcome']=type(error).__name__;request['exception']=str(error)
            raise
        finally:
            request['wall_ms']=(perf_counter_ns()-start)/1e6
            request['cpu_ms']=(process_time_ns()-cpu)/1e6
            request['request_capture_and_call_ms']=(perf_counter_ns()-request_started)/1e6
            calls.append(request)
            pending_ready[:]=[(request,request_started)]
    def execution_capture(*a,**k):
        if pending_ready:
            request,begin=pending_ready.pop()
            request['request_to_first_execution_entry_ms']=(perf_counter_ns()-begin)/1e6
        return original_execute(*a,**k)
    AdaptiveHumanWaypointHWMPCV22.decide=capture
    runtime_module._execute_interval=execution_capture
    try:
        result=run_executed_case(folder/'run',task_timeout_s=30.,simulate_planning_latency=True)
        print(result['status'],result['abort_reason'],result['timing']['high_level_planning_runtime_ms'],flush=True)
    finally:
        AdaptiveHumanWaypointHWMPCV22.decide=original
        runtime_module._execute_interval=original_execute
        save(folder/'planner_requests.json',calls)


if __name__=='__main__':main()
