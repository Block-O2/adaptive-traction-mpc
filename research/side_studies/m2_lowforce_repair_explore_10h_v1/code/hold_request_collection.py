"""C12: one bounded current service after a new original HOLD request.

Use the ordinary next service deadline/socket readability while the already
validated command advances real native physics. Return to the original loop
for fresh inputs, collection, phase checks, feedback and native admission.
No plan/result is executed in this helper and no completion credit is added.
"""
import select
ROWS=[]
def observe(runtime,pending):
 import fast_task_ipc
 wall=runtime.get('wall_session');life=runtime.get('plan_lifecycle')
 if wall is None or life is None or life.closed:return False
 request=pending['request'];future=pending['future']
 if request.stage!='TASK' or not request.asynchronous or pending['phase'].value!='HOLD' or pending.get('pass_through_prefetch'):return False
 if type(future) is not fast_task_ipc.ReadyFuture or future.warm or life._outstanding is not request or life._future_requests.get(future) is not request:return False
 if not wall.phase_records or wall.phase_records[-1]['phase']!='TASK' or not wall.active:return False
 if wall.active_receipt_index is None:return False
 receipt=wall.applied_commands[wall.active_receipt_index]
 if not receipt.get('applied') or receipt.get('supervisor_mode')!='TRACK':return False
 regular_target=wall.epoch_ns+(wall._last_poll_grid+1)*wall.sensor_steps*wall.dt_ns
 begin=wall.clock();before=wall.steps
 period=wall.sensor_steps*wall.dt_ns
 current_target=wall.epoch_ns+((begin-wall.epoch_ns)//period+1)*period
 target=max(regular_target,current_target)
 deadline=min(target,request.sensor_capture_ns+life.maximum_age_ns)
 if begin>=deadline:return False
 # Integrate elapsed native events under the existing validated command.
 wall.catch_up('C11_existing_command_before_bounded_HOLD_collection_service')
 now=wall.clock()
 readable=False
 if now<deadline:readable=bool(select.select([future.executor.sock],[],[],(deadline-now)/1e9)[0])
 observed=wall.clock()
 ready=future.done() if readable else False  # Atomic, nonblocking receive only.
 wall.catch_up('C11_current_HOLD_collection_boundary')
 ROWS.append(dict(event='BOUNDED_HOLD_REQUEST_COLLECTION_SERVICE',request_id=request.request_id,packet_identity=future.identity,begin_ns=begin,deadline_ns=deadline,previous_poll_deadline_ns=regular_target,current_absolute_grid_deadline_ns=current_target,socket_observed_ns=observed,finish_ns=wall.clock(),actual_completed_packet=ready,source_capture_ns=request.sensor_capture_ns,native_before=before,native_after=wall.steps,old_command_receipt=receipt['receipt_index'],authority=False,phase_advanced=False,original_guard_and_admission_next=True))
 return True
