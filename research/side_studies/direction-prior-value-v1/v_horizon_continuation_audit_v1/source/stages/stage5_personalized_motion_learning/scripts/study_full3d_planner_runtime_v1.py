#!/usr/bin/env python3
"""Deterministic planner replay and opt-in instrumentation; no plant truth inputs."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import functools
import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter_ns, process_time_ns

import numpy as np
import mujoco

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import (
    AdaptiveHumanBeliefV22, AdaptiveHumanWaypointHWMPCV22, AdaptiveMechanicsScreenV22,
)
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1, HumanWaypointFeedbackMPCConfigV1
import traction_mpc_stage5.human_waypoint_scheduler as scheduler_module
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract, _jsonable
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[1]
ROOT = STAGE / 'results/full3d_adaptive_integration_v1/runtime_study_v1'
SOURCES = [
    'src/traction_mpc_stage5/human_waypoint_scheduler.py',
    'src/traction_mpc_stage5/human_waypoint_feedback_mpc.py',
    'src/traction_mpc_stage5/architecture_recovery_v2/phase3_human_waypoint.py',
    'src/traction_mpc_stage5/architecture_recovery_v2/functional_benchmark.py',
    'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py',
    'scripts/study_full3d_planner_runtime_v1.py',
    'scripts/run_full3d_runtime_regression_v1.py',
    'configs/full3d_adaptive_integration_v1/runtime_study_v1/contract.json',
]

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True) + '\n')

def provenance(folder):
    folder.mkdir(parents=True, exist_ok=False)
    env = dict(python=sys.version, platform=platform.platform(), machine=platform.machine(),
               numpy=np.__version__, mujoco=mujoco.__version__, argv=sys.argv,
               command=' '.join(sys.orig_argv), executable=sys.executable)
    for key, command in [('branch',['git','branch','--show-current']), ('head',['git','rev-parse','HEAD']),
                         ('status',['git','status','--short','--untracked-files=all'])]:
        env[key] = subprocess.check_output(command,cwd=REPO,text=True)
    env['sources'] = {}
    for name in SOURCES:
        data=(STAGE/name).read_bytes()
        target=folder/'source'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        env['sources'][name]=hashlib.sha256(data).hexdigest()
    save(folder/'provenance.json',env)

def historical_cases():
    cases=[]
    for attempt in (12,13,14):
        path=STAGE/f'results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_{attempt}/summary.json'
        data=json.loads(path.read_text())
        beliefs={data['commissioning']['handoff_belief']['sequence']: data['commissioning']['handoff_belief']}
        for row in data['learning_records']:
            for key in ('adaptive_state','next_adaptive_state'):
                if isinstance(row.get(key),dict):
                    beliefs[row[key]['sequence']]=row[key]
        previous=np.zeros(2); phase=None
        for i,d in enumerate(data['decisions']):
            if phase!=d['phase']:
                previous=np.zeros(2); phase=d['phase']
            belief=beliefs.get(d['belief_sequence_used'])
            if belief is None:
                raise ValueError(f'missing belief for {attempt}/{i}')
            cases.append(dict(id=f'attempt_{attempt}_decision_{i:02d}', source=str(path),
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                belief=belief, previous_action=previous.tolist(), historical=d,
                inputs=dict(current_deployable_state=d['deployable_state_rad_rad_s'],
                    current_reference_state=d['reference_state_rad_rad_s'],phase=d['phase'],
                    phase_elapsed_s=d['phase_elapsed_s'],phase_remaining_s=d['phase_remaining_s'])))
            previous=np.array(d['executed_action_delta_q_rad'])
    return cases

def construct(case):
    b=dict(case['belief']); b.pop('schema',None)
    g=b.pop('effective_geometry')
    g={k:(np.asarray(v) if isinstance(v,list) else v) for k,v in g.items()}
    belief=AdaptiveHumanBeliefV22(geometry=PlanarCuffGeometry(**g),**b)
    scheduler=scheduler_module.QuinticHumanWaypointSchedulerV1(PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        belief.human_model(),reference_period_s=.005,
        clearance_evaluator=SessionClearanceContract(belief.geometry).evaluate,
        clearance_source='ONLINE_EFFECTIVE_GEOMETRY_CONSERVATIVE_SHANK_SET',
        preserve_task_endpoint_clearance_floor=True)
    planner=HumanWaypointFeedbackMPCV1(PROVISIONAL_LOW_MODERATE_GOAL_TASK,scheduler,
        HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True))
    planner.previous_executed_delta_q_rad=np.array(case['previous_action'])
    args=dict(case['inputs']); args['phase']=TaskPhase(args['phase']); args['belief']=belief
    return AdaptiveHumanWaypointHWMPCV22(planner),args

class Profile:
    """Nested inclusive/exclusive high-resolution timings, opt-in outside production.

    Every original function is called once with unchanged inputs. Timed exceptions
    are propagated. Duration-trial count is coefficient-construction count.
    """
    def __init__(self,line_regions=True):
        self.events=[]; self.stack=[]; self.patches=[]; self.candidate=None
        self.line_times={}; self.frames={}; self.line_stages={}
        self.enable_line_regions=line_regions
    def line_regions(self, function, regions):
        lines,start=inspect.getsourcelines(function)
        for first,last,label in regions:
            a=next(i for i,s in enumerate(lines) if first in s)
            b=next(i for i,s in enumerate(lines[a+1:],a+1) if last in s)
            for i in range(a,b): self.line_stages[(function.__code__,start+i)]=label
    def trace(self,frame,event,arg):
        if event not in ('line','return'): return self.trace
        key=id(frame); now=perf_counter_ns()
        previous=self.frames.pop(key,None)
        if previous:
            label,begin,candidate=previous
            k=(candidate,label);self.line_times[k]=self.line_times.get(k,0)+(now-begin)
        if event=='line':
            label=self.line_stages.get((frame.f_code,frame.f_lineno))
            if label:self.frames[key]=(label,perf_counter_ns(),self.candidate)
        return self.trace if frame.f_code in self.traced_codes else None
    def wrap(self,owner,name,stage):
        original=getattr(owner,name)
        @functools.wraps(original)
        def wrapped(*args,**kwargs):
            previous=self.candidate
            if stage=='candidate': self.candidate=kwargs['label']
            record=dict(stage=stage,candidate=self.candidate,children_ns=0)
            if stage=='polynomial_coefficients': record['duration_s']=float(args[4])
            self.stack.append(record); start=perf_counter_ns(); cpu=process_time_ns()
            try:
                result=original(*args,**kwargs)
                if stage=='candidate':
                    record.update(feasible=result.feasible,rejection_reason=result.rejection_reason,
                        duration_s=None if result.schedule is None else result.schedule.duration_s)
                    record['evaluation']=result.record()
                if stage=='path_clearance': record['valid']=bool(result)
                if stage=='mechanics_screen':
                    record.update(result)
                if stage=='wrench_allocation':
                    model,action,q=args
                    projected=model.geometry.translational_jacobian_world(q) @ (np.ones(2)/np.sqrt(2))
                    record['allocation_denominator']=float(projected@projected)
                return result
            except Exception as error:
                record['exception']=type(error).__name__+': '+str(error)
                raise
            finally:
                record['wall_ns']=perf_counter_ns()-start; record['cpu_ns']=process_time_ns()-cpu
                record['self_ns']=record['wall_ns']-record['children_ns']
                self.stack.pop()
                if self.stack:self.stack[-1]['children_ns']+=record['wall_ns']
                self.events.append(record); self.candidate=previous
        self.patches.append((owner,name,original));setattr(owner,name,wrapped)
    def __enter__(self):
        self.line_regions(scheduler_module.QuinticHumanWaypointSchedulerV1._plan,[
            ('samples = []','task_bounds =','sampled_polynomial_kinematics'),
            ('task_bounds =','clearance =','sampled_rom_checks'),
            ('if np.any(maximum_velocity >','samples = []','velocity_acceleration_checks'),
        ])
        self.line_regions(HumanWaypointFeedbackMPCV1._evaluate,[
            ('normalized_goal_error =','future_value =','local_cost'),
            ('future_value =','return FeedbackCandidateEvaluationV1(','value_hook'),
        ])
        self.line_regions(HumanWaypointFeedbackMPCV1.decide,[
            ('feasible = sorted(','if not feasible:','sorting_ranking'),
        ])
        self.traced_codes={code for code,line in self.line_stages}
        self.old_trace=sys.gettrace()
        if self.enable_line_regions:sys.settrace(self.trace)
        for owner,name,stage in [
            (HumanWaypointFeedbackMPCV1,'candidate_actions','candidate_generation'),
            (HumanWaypointFeedbackMPCV1,'_evaluate','candidate'),
            (scheduler_module.QuinticHumanWaypointSchedulerV1,'_plan','scheduler_search'),
            (scheduler_module.QuinticHumanWaypointSchedulerV1,'plan_fixed_duration_reference_contract','scheduler_fixed'),
            (scheduler_module.QuinticHumanWaypointSchedulerV1,'_validate_request','rom_boundary_validation'),
            (scheduler_module.QuinticHumanWaypointSchedulerV1,'_clearance_m','clearance_evaluation'),
            (scheduler_module.QuinticHumanWaypointSchedulerV1,'_path_clearance_is_valid','path_clearance'),
            (scheduler_module,'_quintic_coefficients','polynomial_coefficients'),
            (scheduler_module,'_polynomial_extrema','polynomial_extrema'),
            (scheduler_module,'_maximum_causal_reference_acceleration','causal_acceleration'),
            (AdaptiveMechanicsScreenV22,'evaluate','mechanics_screen'),
            (AdaptiveHumanBeliefV22,'human_model','model_construction'),
            (StateResidualHumanModel,'inverse_dynamics','inverse_dynamics'),
            (StateResidualHumanModel,'allocate_generalized_action','wrench_allocation'),
        ]: self.wrap(owner,name,stage)
        return self
    def __exit__(self,*exc):
        sys.settrace(self.old_trace)
        for owner,name,original in reversed(self.patches):setattr(owner,name,original)
        for (candidate,stage),ns in self.line_times.items():
            self.events.append(dict(candidate=candidate,stage=stage,wall_ns=ns,
                                    self_ns=ns,line_region_inclusive=True))

def invoke(case,profile=False):
    planner,args=construct(case)
    p=Profile(line_regions=profile!='functions')
    from contextlib import nullcontext
    with p if profile else nullcontext():
        start=perf_counter_ns(); cpu=process_time_ns()
        try:
            decision=planner.decide(**args)
            elapsed=perf_counter_ns()-start; cpu_elapsed=process_time_ns()-cpu
            ser=perf_counter_ns(); record=decision.record()
            record['coefficient_matrices']={e.label:e.schedule.coefficients.tolist() for e in decision.evaluations if e.schedule}
            serialization_ns=perf_counter_ns()-ser
            error=None
        except ValueError as exc:
            elapsed=perf_counter_ns()-start;cpu_elapsed=process_time_ns()-cpu
            record=None;error=str(exc);serialization_ns=0
    return dict(case_id=case['id'],wall_ms=elapsed/1e6,cpu_ms=cpu_elapsed/1e6,
                record_serialization_ms=serialization_ns/1e6,decision=record,error=error,events=p.events)

def stats(values):
    x=np.asarray(values,dtype=float)
    return dict(count=len(x),mean=float(x.mean()),median=float(np.median(x)),
                p90=float(np.percentile(x,90)),p95=float(np.percentile(x,95)),
                p99=float(np.percentile(x,99)),maximum=float(x.max()),deadline_misses=int(np.sum(x>100)))

def corpus():
    cases=json.loads((ROOT/'baseline/inputs.json').read_text())
    # All synthetic inputs are explicitly development stress, never sensor truth.
    # Keep task/limits fixed; vary only legitimate planner input state/belief.
    base=next(c for c in cases if c['id']=='attempt_13_decision_10')
    for i,(phase,q,dq) in enumerate([
        ('OUTBOUND',[19.8,34.8],[0,0]), ('OUTBOUND',[20,35],[0,0]),
        ('HOLD',[20,35],[0,0]), ('RETURN',[79.9,99.9],[0,0]),
        ('OUTBOUND',[.05,.05],[0,0]), ('RETURN',[.05,99.9],[0,0]),
        ('RETURN',[5.01,10.01],[0,0]), ('RETURN',[10.49,20.08],[0,0]),
        ('OUTBOUND',[14,19],[0,0]), ('RETURN',[9,27],[0,0]),
        ('RETURN',[16,22],[0,0]), ('OUTBOUND',[5,10],[0,0]),
    ]):
        c=copy.deepcopy(base);c['id']=f'development_edge_{i:02d}';c.pop('historical')
        state=np.radians(q+dq).tolist()
        c['inputs']=dict(current_deployable_state=state,current_reference_state=state,
            phase=phase,phase_elapsed_s=0.,phase_remaining_s=10.)
        c['previous_action']=[0,0];c['category']='synthetic_development_planner_input'
        if i%2==0:c['belief']=copy.deepcopy(cases[0]['belief'])
        cases.append(c)
    return cases

@contextmanager
def baseline_scheduler():
    global scheduler_module
    original=scheduler_module
    name='traction_mpc_stage5._runtime_study_baseline_scheduler'
    path=ROOT/'baseline/source/src/traction_mpc_stage5/human_waypoint_scheduler.py'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    scheduler_module=module
    try:yield
    finally:scheduler_module=original

def compare(a,b,path=''):
    errors=[]
    if isinstance(a,dict) and isinstance(b,dict):
        for key in a.keys()|b.keys():
            if key=='runtime_ms':continue
            if key not in a or key not in b:errors.append(path+'/'+key)
            else:errors+=compare(a[key],b[key],path+'/'+key)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return [path+'/length']
        for i,(x,y) in enumerate(zip(a,b)):errors+=compare(x,y,path+'/'+str(i))
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if not np.isclose(a,b,atol=1e-10,rtol=1e-10):errors.append(path)
    elif a!=b:errors.append(path)
    return errors

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['baseline','repaired','forensics','reconstruction_v2','function_profiles'],required=True)
    args=ap.parse_args()
    folder=ROOT/args.mode;provenance(folder)
    if args.mode=='function_profiles':
        profiles=[];rejected_comparisons=[]
        for case in corpus():
            row=invoke(case,'functions');profiles.append(row)
            if row['error']:
                with baseline_scheduler():old=invoke(case,'functions')
                a=[e['evaluation'] for e in old['events'] if e['stage']=='candidate']
                b=[e['evaluation'] for e in row['events'] if e['stage']=='candidate']
                rejected_comparisons.append(dict(case_id=case['id'],old_evaluations=a,new_evaluations=b,
                    differences=compare(a,b)))
        save(folder/'profiles.json',profiles)
        save(folder/'infeasible_candidate_equivalence.json',rejected_comparisons)
        groups={stage:[] for row in profiles for stage in [e['stage'] for e in row['events']]}
        for stage in groups:
            for row in profiles:
                entries=[e['wall_ns']/1e6 for e in row['events'] if e['stage']==stage]
                if entries:groups[stage].append(sum(entries))
        save(folder/'stage_distributions.json',{k:stats(v) for k,v in groups.items()})
        return
    if args.mode=='reconstruction_v2':
        original=next(c for c in corpus() if c['id']=='attempt_13_decision_10')
        first=json.loads((ROOT/'forensics/attempt12_reconstruction.json').read_text())
        reconstructed=copy.deepcopy(first['case'])
        data=json.loads((STAGE/'results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_12/summary.json').read_text())
        preceding=data['decisions'][-1]
        schedule=next(e['schedule'] for e in preceding['evaluations'] if e['label']==preceding['executed_label'])
        coefficients=scheduler_module._quintic_coefficients(np.array(schedule['start_q_rad']),
            np.array(schedule['start_dq_rad_s']),np.array(schedule['target_q_rad']),
            np.array(schedule['target_dq_rad_s']),schedule['duration_s'])
        reference=np.r_[coefficients@np.ones(6),coefficients@np.arange(6)/schedule['duration_s']]
        reconstructed['inputs']['current_reference_state']=reference.tolist()
        with baseline_scheduler():old=invoke(reconstructed)
        new=invoke(reconstructed)
        save(folder/'reconstruction.json',dict(case=reconstructed,preceding_schedule=schedule,
            correction='Terminal attempt12 reference is contaminated by rejected plan; use preceding executed polynomial endpoint.',
            comparisons={key:compare(reconstructed[key],original[key],key) for key in ('belief','previous_action','inputs')},
            old=old,new=new,old_new_differences=compare(old['decision'],new['decision']),
            historical_semantic_differences=compare(original['historical']['evaluations'],old['decision']['evaluations'])))
        return
    if args.mode=='forensics':
        cases=corpus()
        case=next(c for c in cases if c['id']=='attempt_13_decision_10')
        with baseline_scheduler():save(folder/'baseline_detailed_profile.json',invoke(case,True))
        save(folder/'repaired_detailed_profile.json',invoke(case,True))
        retry=next(c for c in cases if c['id']=='attempt_13_decision_05')
        save(folder/'mechanics_retry_profile.json',invoke(retry,True))
        path=STAGE/'results/full3d_adaptive_integration_v1/nominal_timing_aware_attempt_12'
        data=json.loads((path/'summary.json').read_text());trace=np.load(path/'trace.npz')
        reconstructed=copy.deepcopy(case);reconstructed['id']='attempt_12_missing_terminal_reconstructed'
        reconstructed['belief']=data['learning_records'][-1]['next_adaptive_state']
        reconstructed['previous_action']=data['decisions'][-1]['executed_action_delta_q_rad']
        reconstructed['inputs']['current_deployable_state']=trace['estimated_human_state_rad_rad_s'][-1].tolist()
        reconstructed['inputs']['current_reference_state']=np.r_[trace['reference_q_rad'][-1],trace['reference_dq_rad_s'][-1]].tolist()
        # phase_elapsed is updated by repeated 5ms addition, not a subtraction
        # of large MuJoCo timestamps (which has different roundoff).
        elapsed=0.
        phase_nodes=np.sum(trace['task_phase']=='RETURN')
        for _ in range(int(phase_nodes)):elapsed+=.005
        reconstructed['inputs']['phase_elapsed_s']=elapsed
        reconstructed['inputs']['phase_remaining_s']=10.-elapsed
        reconstruction=dict(case=reconstructed,original_case=case,
            comparisons={key:compare(reconstructed[key],case[key],key) for key in ('belief','previous_action','inputs')},
            qualification='reconstructed missing request, not original saved decision')
        with baseline_scheduler():reconstruction['replay']=invoke(reconstructed)
        save(folder/'attempt12_reconstruction.json',reconstruction)
        return
    if args.mode=='repaired':
        cases=corpus();save(folder/'inputs.json',cases)
        comparisons=[]; profiles=[]; timings=[]
        for case in cases:
            with baseline_scheduler():old=invoke(case)
            new=invoke(case)
            differences=compare(old['decision'],new['decision'])+compare(old['error'],new['error'],'error')
            comparisons.append(dict(case_id=case['id'],old=old,new=new,differences=differences))
            print('equivalence',case['id'],old['wall_ms'],new['wall_ms'],differences,flush=True)
        save(folder/'equivalence.json',comparisons)
        for case in cases:
            profiles.append(invoke(case,True))
        save(folder/'profiles.json',profiles)
        # Shuffled order is reproducible. Reconstruct planner each time to retain
        # previous-action input; measure only decide, never setup/import overhead.
        order=[i for r in range(12) for i in range(len(cases))]
        np.random.default_rng(20260923).shuffle(order)
        for n,i in enumerate(order):
            row=invoke(cases[i]);row.pop('events');row.pop('decision');timings.append(row)
            if n%50==0:print('timing',n,row['wall_ms'],flush=True)
        save(folder/'timings.json',timings)
        save(folder/'summary.json',dict(wall_ms=stats([r['wall_ms'] for r in timings]),
            cpu_ms=stats([r['cpu_ms'] for r in timings]),
            equivalence_failures=[r['case_id'] for r in comparisons if r['differences']],
            worst=max(timings,key=lambda r:r['wall_ms']),
            before_wall_ms=stats([r['old']['wall_ms'] for r in comparisons]),
            after_paired_wall_ms=stats([r['new']['wall_ms'] for r in comparisons])))
        return
    cases=historical_cases();save(folder/'inputs.json',cases)
    worst=[max([c for c in cases if c['id'].startswith(f'attempt_{a}_')],key=lambda c:c['historical']['runtime_ms']) for a in (12,13)]
    results=[]
    for case in worst:
        for repeat in range(3):
            row=invoke(case);results.append(row)
            print(case['id'],repeat,row['wall_ms'],row['cpu_ms'],flush=True)
        row=invoke(case,True);save(folder/f"profile_{case['id']}.json",row)
    save(folder/'repeats.json',results)
    save(folder/'historical_replays.json',[invoke(c) for c in cases])

if __name__=='__main__': main()
