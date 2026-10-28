"""Source-only v8 persistent-session adapter; no execution at import.

This does not grant permission to start physics. It takes the orchestrator's
already initialized runtime and callbacks; the orchestrator retains the single
PHYSICS.lock, source freeze, task/scorer, timeout, and process ownership.
"""
from contextlib import contextmanager
import math
import time
import numpy as np


class PersistentSessionBridge:
    def __init__(self, rt, sc, *, emit, hard_deadline_unix, stop_check,
                 model_counter=lambda: None):
        self.rt=rt;self.sc=sc;self.emit=emit;self.deadline=float(hard_deadline_unix)
        self.stop_check=stop_check;self.model_counter=model_counter
        self.context={};self.latest_runtime=None;self.latest_capture=None;self.running=False;self.completed=[]

    def observe_existing_runtime(self,b):
        """Called from the existing boundary hook, with no refresh or step."""
        self.latest_runtime=b['runtime']

    def _guard(self):
        if time.time()>=self.deadline:raise TimeoutError('ORIGINAL_V8_HARD_DEADLINE')
        self.stop_check()

    def stamp(self):
        # During a failed resumed task, context['runtime'] can still name the
        # previous epoch while boundary already observed the new epoch. Both
        # share the same plant, but wall/lifecycle audit must use the latest.
        captured=None if self.latest_capture is None else self.latest_capture.get('runtime')
        runtime=captured if captured is not None else (self.latest_runtime if self.latest_runtime is not None else self.context.get('runtime'))
        if runtime is None:return None
        return dict(plant_identity=id(runtime['plant']),
            observer_identity=id(runtime['observer']),
            measurement_layer_identity=id(runtime['measurement_layer']),
            physical_time_s=float(runtime['plant'].data.time),
            updater_identity=id(self.context['updater']) if 'updater' in self.context else None,
            updater_sequence=self.context['updater'].sequence if 'updater' in self.context else None,
            repetition_index=self.context.get('repetition_index'),
            wall_active=runtime['wall_session'].active,
            planner_request_outstanding=runtime['plan_lifecycle']._outstanding is not None)

    def _steps(self,start,end):
        steps=(end-start)/float(self.rt.NOMINAL_PHYSICS_DT_S)
        rounded=round(steps)
        if steps<0. or not math.isclose(steps,rounded,abs_tol=1e-4,rel_tol=0.):
            raise ValueError('NON_NATIVE_ALIGNED_INCREMENT')
        return rounded

    @contextmanager
    def bind(self):
        if self.running:raise RuntimeError('NESTED_PERSISTENT_INVOCATION')
        self.running=True;original=self.rt.run_executed_case
        def persistent(*args,**kwargs):
            if kwargs.get('execution_mode')!='SCIENTIFIC_SIMULATION':
                raise ValueError('PERSISTENT_SIMULATION_ONLY')
            # sc.run creates an empty session argument on each call; replace
            # that argument with the same actual process-local native session.
            kwargs['session_context']=self.context
            # The original runtime populates this capture immediately after
            # initialization. Keep the reference so failure during commissioning
            # before any TASK callback still has observable real native time.
            self.latest_capture=kwargs.get('runtime_capture')
            return original(*args,**kwargs)
        self.rt.run_executed_case=persistent
        try:yield
        finally:self.rt.run_executed_case=original;self.running=False

    def invoke(self,ident,interface):
        """Invoke one original full task and report NEW, not absolute, cost.

        `interface` must implement the orchestrator-reviewed direct recipe
        semantics or an actual full-address-space fork. Fake child markers
        are forbidden. No task/reference/score threshold is changed here.
        """
        self._guard();before=self.stamp();start_s=0. if before is None else before['physical_time_s']
        counter_before=self.model_counter();started=time.time();status='FAILED_PRESERVED';error=None
        metric=None
        try:
            with self.bind():metric=self.sc.run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
            if metric.get('task_valid') is not True:
                raise RuntimeError('ORIGINAL_COMPLETE_TASK_NOT_VALID')
            after=self.stamp()
            if after is None:raise RuntimeError('NATIVE_SESSION_NOT_CAPTURED')
            if before is not None:
                for key in ['plant_identity','observer_identity','measurement_layer_identity','updater_identity']:
                    if after[key]!=before[key]:raise RuntimeError('PERSISTENT_OBJECT_REPLACED:'+key)
                if after['repetition_index']!=before['repetition_index']+1:
                    raise RuntimeError('PERSISTENT_REPETITION_INDEX')
            if after['wall_active'] or after['planner_request_outstanding']:
                raise RuntimeError('COMPLETED_TASK_SESSION_NOT_QUIESCENT')
            status='COMPLETED_ORIGINAL_TASK_WITH_PERSISTENT_OBJECTS';self.completed.append(ident)
            return metric
        except BaseException as exc:error=str(exc);raise
        finally:
            after=self.stamp();counter_after=self.model_counter()
            new_steps=None if after is None else self._steps(start_s,after['physical_time_s'])
            delta=dict(id=ident,kind='PERSISTENT_TASK_INCREMENT',status=status,error=error,
                before=before,after=after,actual_new_native_steps=new_steps,
                actual_new_simulation_seconds=None if new_steps is None else new_steps*self.rt.NOMINAL_PHYSICS_DT_S,
                actual_new_main_model_calls=None if counter_before is None or counter_after is None else counter_after-counter_before,
                task_JF_unchanged=None if metric is None else metric.get('J_F'),
                preparation_in_new_native_count=True,boundary_counted_separately=True,
                wall_s=time.time()-started,human_state_assignment=False)
            # Preserve this delta beside raw original metric; never sum its
            # absolute trace physics_steps with the persistent delta again.
            self.emit('PERSISTENT_DELTA_ACCOUNTING/'+ident,delta)

    def advance_boundary(self,ident,*,max_wait_s=2.):
        """Observe unchanged original inter-repetition native settle/hold."""
        self._guard()
        if not self.completed:raise RuntimeError('NO_PREVIOUS_COMPLETE_TASK')
        before=self.stamp()
        if before['wall_active'] or before['planner_request_outstanding']:
            raise RuntimeError('PREVIOUS_TASK_STILL_OPEN')
        runtime=self.context['runtime'];plant=runtime['plant'];cls=type(plant);original=cls.step_native
        last=next(r for r in reversed(runtime['wall_session'].applied_commands)
                  if r.get('applied') and r.get('native_steps',0)>0)
        held=np.asarray(plant.data.ctrl).copy();steps=[];result=None;error=None
        def observe(instance,*args,**kwargs):
            self._guard();start=float(instance.data.time)
            ctrl=np.asarray(instance.data.ctrl).copy()
            answer=original(instance,*args,**kwargs)
            if instance is plant:
                steps.append(dict(start_s=start,end_s=float(instance.data.time),
                    command=ctrl.tolist(),inherited_receipt_index=last['receipt_index']))
                if not np.array_equal(ctrl,held):raise RuntimeError('BOUNDARY_HELD_COMMAND_CHANGED')
            return answer
        cls.step_native=observe
        try:
            result=self.rt.advance_inter_rep_boundary(self.context,max_wait_s=max_wait_s,stop_check=self._guard)
            if result['physical_object_unchanged'] is not True:
                raise RuntimeError('INTER_REP_NATIVE_OBJECT_REPLACED')
            # Return only completed causal boundary costs/status. Original
            # result contains evaluation-only qpos/qvel; no learner receives it.
            return {k:result[k] for k in ['schema','status','from_repetition','to_repetition',
                'start_time_s','end_time_s','settle_duration_s','hold_duration_s','cost','physical_object_unchanged','updater_sequence']}
        except BaseException as exc:error=str(exc);raise
        finally:
            cls.step_native=original;after=self.stamp()
            count=self._steps(before['physical_time_s'],after['physical_time_s'])
            self.emit('PERSISTENT_BOUNDARY/'+ident,dict(id=ident,kind='ORIGINAL_INTER_REP_BOUNDARY',
                before=before,after=after,error=error,actual_new_native_steps=count,
                observed_native_steps=len(steps),counter_matches_observation=count==len(steps),
                held_command=held.tolist(),prior_positive_receipt=last['receipt_index'],steps=steps,
                task_cost_excludes_boundary=True,cumulative_exploration_cost_includes_boundary=True,
                human_state_assignment=False,policy_received_native_truth=False))
