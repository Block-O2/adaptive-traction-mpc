"""Stage1G reference ownership around the original native execution chain."""
import bootstrap
import ast,inspect,textwrap
import numpy as np
from dataclasses import replace
from native_integration import model_key
from exact_runtime_reference import ExactSchedule
from event_coverage import certificate,EventCoverage
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
from traction_mpc_stage5.task import TaskPhase

def execute_adapter():
    tree=ast.parse(textwrap.dedent(inspect.getsource(rt._execute_interval)));changed=[]
    class Adapt(ast.NodeTransformer):
        def visit_If(self,node):
            self.generic_visit(node)
            if 'phase_deadline_physics_s' in ast.unparse(node.test):
                changed.append(ast.unparse(node.test))
                node.test=ast.BoolOp(ast.And(),[ast.parse("validation.get('normal_deadline_applies',True)",mode='eval').body,node.test])
            return node
    tree=Adapt().visit(tree);ast.fix_missing_locations(tree)
    expected=["float(plant.data.time) > validation['phase_deadline_physics_s'] - validation['schedule_duration_s'] + 1e-12"]
    if changed!=expected:raise RuntimeError('UPSTREAM_ACTIVATION_TIME_GUARD_CHANGED:'+repr(changed))
    ns=dict(rt._execute_interval.__globals__);exec(compile(tree,'<stage1g_native_execute>','exec'),ns)
    return ns['_execute_interval'],changed
execute_interval,changed_deadline_checks=execute_adapter()

def current_reference_certificate(s,sch,b,offset):
    if not isinstance(s,ExactSchedule):raise ValueError('EXACT_RUNTIME_SAMPLER_REQUIRED')
    return certificate(s,sch,b,offset)

class MovingTransaction:
    def __init__(self,runtime,owner,scheduler,belief):
        self.runtime=runtime;self.owner=owner;self.scheduler=scheduler;self.belief=belief
        self.journal=[];self.revoked=False;self.prepared_events=None
    def _context(self,proposal,epoch,observation,measurement,phase,expected_key):
        if self.revoked:raise ValueError('NATIVE_OWNER_REVOKED')
        if not isinstance(proposal,ExactSchedule):raise ValueError('EXACT_RUNTIME_SAMPLER_REQUIRED')
        sch=self.scheduler;runtime=self.runtime;b=self.belief
        if model_key(b,sch.clearance_evaluator)!=expected_key:raise ValueError('MODEL_OR_GEOMETRY_CHANGED')
        goal=sch.spec.start_return_target_rad if phase is TaskPhase.RETURN else sch.spec.outbound_goal_target_rad
        if proposal.candidate.phase is not phase or not np.allclose(proposal.candidate.phase_goal_rad,goal,atol=1e-12,rtol=0):raise ValueError('CURRENT_PHASE_GOAL_MISMATCH')
        if runtime.get('stage1g_phase',phase) is not phase:raise ValueError('RUNTIME_PHASE_CHANGED')
        if epoch!=float(runtime['plant'].data.time):raise ValueError('ACTUAL_EPOCH_MISMATCH')
        source=float(observation.sample_timestamp_s)
        if source!=float(measurement.sample_time_s) or not 0<=epoch-source<.100-1e-12:raise ValueError('STALE_OR_MISMATCHED_SOURCE')
        if str(observation.human_model_version)!=f'belief_{b.sequence}':raise ValueError('OBSERVATION_MODEL_MISMATCH')
        observed=observation.as_array();old=self.owner.sample(epoch)
        if observed.shape!=(4,) or not np.all(np.isfinite(observed)):raise ValueError('INVALID_OBSERVATION')
        rom=np.c_[np.maximum(np.asarray(sch.spec.q_bounds_rad)[:,0],b.human_model().q_min_rad),np.minimum(np.asarray(sch.spec.q_bounds_rad)[:,1],b.human_model().q_max_rad)]
        if np.any(observed[:2]<rom[:,0]) or np.any(observed[:2]>rom[:,1]) or sch.clearance_evaluator.evaluate(observed[:2])<0:raise ValueError('CURRENT_STATE_GEOMETRY_REJECTED')
        return old,observed,observed[:2]-old.q_rad
    def activate(self,request,proposal,*,epoch,observation,interface,measurement,observed_a,acceleration_valid,phase_elapsed_s,phase,expected_key,coverage):
        try:
            old,observed,offset=self._context(proposal,epoch,observation,measurement,phase,expected_key)
            if not acceleration_valid or np.asarray(observed_a).shape!=(2,) or not np.all(np.isfinite(observed_a)):raise ValueError('ACCELERATION_AUTHORITY_NOT_READY')
            first=proposal.sample(0)
            if max(np.max(np.abs(getattr(first,k)-getattr(old,k))) for k in ('q_rad','dq_rad_s','ddq_rad_s2'))>1e-10:raise ValueError('ACTUAL_EPOCH_C2_MISMATCH')
            cert=current_reference_certificate(proposal,self.scheduler,self.belief,offset)
            vlimit=np.asarray(self.scheduler.spec.task_joint_velocity_limit_rad_s);alimit=np.asarray(self.scheduler.spec.task_joint_acceleration_limit_rad_s2)
            state_ok=bool(np.all(np.abs(observed[2:])<=vlimit) and np.all(np.abs(observed_a)<=alimit)
                and np.all(vlimit*self.scheduler.reference_velocity_fraction+np.abs(observed[2:]-old.dq_rad_s)<=vlimit)
                and np.all(alimit*self.scheduler.reference_acceleration_fraction+np.abs(observed_a-old.ddq_rad_s2)<=alimit))
            if not cert['feasible'] or not state_ok:raise ValueError('CURRENT_STATE_REFERENCE_REJECTED')
            if not isinstance(coverage,EventCoverage):raise ValueError('BUILT_EVENT_COVERAGE_REQUIRED')
            if coverage.through_s<.100-1e-12:raise ValueError('FULL_PREFIX_EVENT_COVERAGE_REQUIRED')
            coverage.validate(proposal,expected_key,offset,epoch)
            validation={**cert,'normal_deadline_applies':phase not in (TaskPhase.OUTBOUND,TaskPhase.RETURN),
                'phase_deadline_physics_s':epoch+self.scheduler.spec.phase_timeout_s-phase_elapsed_s,'schedule_duration_s':proposal.duration_s}
            return self._execute(proposal,epoch,observation,interface,measurement,request,validation,expected_key,coverage)
        except BaseException as e:
            self._finish_failed(request,e);raise
    def _finish_failed(self,request,error):
        runtime=self.runtime;life=runtime['plan_lifecycle']
        if request is not None:
            row=life.records()[request.request_id]
            if row.get('outcome')=='PENDING':life.finish(request,'REJECTED',str(error))
        for k in ('plan_to_activate','activation_validator','validated_request_id','actual_activation_hook','reference_progress_commit','suffix_splice_apply_guard'):runtime.pop(k,None)
    def _execute(self,s,epoch,observation,interface,measurement,request,validation,key,coverage,*,ownership=True):
        runtime=self.runtime;wall=runtime['wall_session'];life=runtime['plan_lifecycle'];bound=[];committed=[]
        original_prepare=wall.prepare_apply;original_tick=wall.next_control_tick
        def capture_prepared(*args,**kwargs):
            receipt=original_prepare(*args,**kwargs);bound.append(receipt)
            if receipt['start_physics_s']!=epoch or model_key(self.belief,self.scheduler.clearance_evaluator)!=key:raise ValueError('ACTUAL_EVENT_REQUIRES_RECERTIFICATION')
            return receipt
        def commit_then_step():
            if len(bound)!=1:raise RuntimeError('NATIVE_RECEIPT_COUNT_MISMATCH')
            r=bound[0];outcome=None if request is None else life.records()[request.request_id].get('outcome')
            good=r.get('applied') and r.get('supervisor_mode')=='TRACK' and any(x is r for x in wall.applied_commands) and (request is None or outcome=='ACTIVATED')
            if good:
                r['stage1g_reference_acceleration_rad_s2']=x.ddq_rad_s2.copy()
                r['stage1g_reference_schedule_digest']=s.digest
                r['stage1g_reference_schedule_epoch_s']=epoch if ownership else self.owner.schedule_epoch_s
                if ownership:
                    if hasattr(self.owner,'install'):self.owner.install(s,epoch,key)
                    else:self.owner.schedule=s;self.owner.schedule_epoch_s=epoch;self.owner.owned_segments.append((epoch,s));self.owner.model_key=key
                    self.prepared_events=coverage
                record=dict(request=None if request is None else request.request_id,receipt=r['receipt_index'],epoch=epoch,digest=s.digest,scope='native_write_committed_before_step',receipt_object=r)
                self.journal.append(record);committed.append(record)
            else:self.revoked=True;runtime['stage1g_owner_revoked']='NON_TRACK_OR_UNCOMMITTED_RECEIPT'
            original_tick()
        wall.prepare_apply=capture_prepared;wall.next_control_tick=commit_then_step
        if request is not None:runtime['plan_to_activate']=request;runtime['activation_validator']=lambda:validation
        x=s.sample(0) if ownership else self.owner.sample(epoch)
        candidate=replace(s.candidate,q_waypoint_rad=x.q_rad,dq_waypoint_rad_s=x.dq_rad_s)
        try:
            result=execute_interval(runtime,observation=observation,interface=interface,measurement=measurement,candidate=candidate,actuation_enabled=True)
            if self.revoked or not committed:raise RuntimeError('FINAL_NATIVE_COMMIT_REJECTED')
            return result,bound[0]
        except BaseException as error:
            if any(r.get('applied') for r in bound):
                self.revoked=True;runtime['stage1g_owner_revoked']=str(error)
                runtime.setdefault('stage1g_postwrite_failures',[]).append(dict(error=repr(error),receipts=bound,owner_committed=bool(committed)))
            self._finish_failed(request,error);raise
        finally:wall.prepare_apply=original_prepare;wall.next_control_tick=original_tick
    def emit(self,*,epoch,observation,interface,measurement,phase,expected_key):
        s=self.owner.schedule
        self._context(s,epoch,observation,measurement,phase,expected_key)
        return self._execute(s,epoch,observation,interface,measurement,None,None,expected_key,self.prepared_events,ownership=False)
    def stop(self,request,primary,coverage,*,epoch,observation,interface,measurement,phase,phase_elapsed_s,expected_key):
        """Install an already certified current-event stop, never normal replan."""
        try:
            old,observed,offset=self._context(primary,epoch,observation,measurement,phase,expected_key)
            coverage.validate(primary,expected_key,offset,epoch);event=coverage.at(0.);s=event.schedule
            if coverage.through_s<.005-1e-12:raise ValueError('NEXT_EVENT_RESOURCE_COVERAGE_REQUIRED')
            first=s.sample(0)
            if max(np.max(np.abs(getattr(first,k)-getattr(old,k))) for k in ('q_rad','dq_rad_s','ddq_rad_s2'))>1e-10:raise ValueError('STOP_ACTUAL_C2_MISMATCH')
            if event.certificate['feasible'] is not True:raise ValueError('UNPREPARED_STOP')
            validation=dict(feasible=True,normal_deadline_applies=phase not in (TaskPhase.OUTBOUND,TaskPhase.RETURN),phase_deadline_physics_s=epoch+self.scheduler.spec.phase_timeout_s-phase_elapsed_s,schedule_duration_s=s.duration_s,scope='prepared resource/exception stop; original resource andHOLD clocks continue')
            return self._execute(s,epoch,observation,interface,measurement,request,validation,expected_key,coverage)
        except BaseException as e:self._finish_failed(request,e);raise
