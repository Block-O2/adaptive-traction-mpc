"""Elapsed-time instrumentation only. Events are buffered, never critical I/O."""
import time,threading,functools,collections
EVENTS=[];INSTALLED=False
LOCAL=threading.local()
def scope(name):
 return getattr(LOCAL,'scope','native')
def wrap(owner,name,label=None,minimum_ns=0):
 original=getattr(owner,name)
 @functools.wraps(original)
 def instrumented(*args,**kwargs):
  start=time.monotonic_ns();parent=scope(name);previous=parent;LOCAL.scope=label or name;error=None
  try:return original(*args,**kwargs)
  except BaseException as e:error=type(e).__name__+':'+str(e);raise
  finally:
   finish=time.monotonic_ns();LOCAL.scope=previous
   if finish-start>=minimum_ns:
    event=dict(name=label or name,parent=parent,start_ns=start,finish_ns=finish,elapsed_ms=(finish-start)/1e6,thread=threading.get_ident(),error=error)
    if name in ('request','submit','activate','finish','discard','expired'):
     request=kwargs.get('request',args[1] if len(args)>1 else None)
     if hasattr(request,'request_id'):event.update(request_id=request.request_id,stage=request.stage,source_capture_ns=request.sensor_capture_ns,source_sample_time_s=request.source_sample_time_s)
     if name=='finish' and len(args)>2:event['outcome']=args[2]
    if name=='catch_up' and len(args)>1:event['reason']=args[1]
    EVENTS.append(event)
 setattr(owner,name,instrumented)
def install():
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as ph
 from traction_mpc_stage5 import human_waypoint_feedback_mpc as fb,human_waypoint_scheduler as hs
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op,activation_validation as av,runtime_coordination_residual_v2 as rt,runtime_sac_expert_v1 as original,wall_physics as wall,terminal_reference as terminal
 for obj,name,label in [(ph.AdaptiveHumanWaypointHWMPCV22,'decide','adaptive_B_decide'),(ph.AdaptiveMechanicsScreenV22,'evaluate','mechanics'),(fb.HumanWaypointFeedbackMPCV1,'_evaluate','native_candidate_evaluate'),(terminal.TerminalSetHumanWaypointPlannerV1,'decide','terminal_B_decide'),(hs.QuinticHumanWaypointSchedulerV1,'plan_reference_contract','scheduler_certificate'),(av,'validate_activation','activation_revalidation'),(av,'validate_rolling_composite','rolling_revalidation')]:wrap(obj,name,label)
 wrap(op,'snapshot_task_call','snapshot_serialize')
 for mod in (rt,original):
  mod.snapshot_task_call=op.snapshot_task_call
  mod.validate_activation=av.validate_activation;mod.validate_rolling_composite=av.validate_rolling_composite
 import coordination_adapter as ca,native_core as nc
 ca.snapshot_task_call=nc.snapshot_task_call=op.snapshot_task_call
 for name in ('request','submit','activate','finish','discard'):wrap(op.PlanLifecycle,name,'lifecycle_'+name)
 wrap(wall.WallPhysicsSession,'catch_up','physics_catch_up',minimum_ns=500000)
 wrap(wall.WallPhysicsSession,'prepare_apply','receipt_prepare');wrap(wall.WallPhysicsSession,'apply','actual_command_apply')
 import native_method as nm,interfaces
 wrap(interfaces.TableInterface,'context','research_context')
 wrap(nm.NativeInterface,'choose','research_coordinator')
def evidence():
 groups=collections.defaultdict(list)
 for e in EVENTS:groups[e['name']].append(e['elapsed_ms'])
 import numpy as np
 return dict(events=EVENTS,summary={k:dict(n=len(v),sum_ms=sum(v),p50_ms=float(np.quantile(v,.5)),p90_ms=float(np.quantile(v,.9)),p95_ms=float(np.quantile(v,.95)),max_ms=max(v)) for k,v in groups.items()},clock='monotonic_ns elapsed',timestamp_values_not_modified=True,nested_durations_not_additive=True,critical_path_disk_writes=0)
