"""C4: timer sleep may end on the original TASK socket's actual readability.

The timer bounds the wait. No result/future is waited for, no additional request
is created, and an unread/unfinished packet leaves the ordinary timer intact.
Admission and feedback run only at the resulting real current service.
"""
import select
ROWS=[]
ORIGINAL_NEXT=None
def eligible(self):
    import fast_task_ipc
    life=self.runtime.get('plan_lifecycle')
    if life is None or life.closed:return None
    request=life._outstanding;future=life._future
    if request is None or request.stage!='TASK' or not request.asynchronous:return None
    if type(future) is not fast_task_ipc.ReadyFuture or future.warm:return None
    if future.finished:return None
    if life._future_requests.get(future) is not request:return None
    if not self.phase_records or self.phase_records[-1]['phase']!='TASK':return None
    if self.clock()-request.sensor_capture_ns>=life.maximum_age_ns:return None
    return request,future,life
def next_control_tick(self):
    import completed_result_service as completed
    target=self.epoch_ns+(self._last_poll_grid+1)*self.sensor_steps*self.dt_ns
    context=eligible(self)
    if context is None or self.clock()>=target:return ORIGINAL_NEXT(self)
    request,future,life=context
    # Integrate real elapsed past using the existing receipt, before sleeping.
    self.catch_up('C4_existing_command_before_bounded_timer_sleep')
    now=self.clock()
    deadline=min(target,request.sensor_capture_ns+life.maximum_age_ns)
    if now>=deadline:return ORIGINAL_NEXT(self)
    begin=now
    readable=select.select([future.executor.sock],[],[],(deadline-now)/1e9)[0]
    observed=self.clock()
    if readable and observed<target:
        ready=completed.completed_task(self)
        if ready is not None:
            ROWS.append(dict(event='ACTUAL_SOCKET_READINESS_ENDED_TIMER_SLEEP',request_id=request.request_id,
                packet_identity=future.identity,timer_begin_ns=begin,timer_deadline_ns=target,
                socket_observed_ns=observed,source_capture_ns=request.sensor_capture_ns,
                future_result_wait=False,new_request=False))
            self.catch_up('C4_completed_original_TASK_actual_service')
            ROWS[-1]['actual_return_ns']=self.clock()
            return
    return ORIGINAL_NEXT(self)
def install():
    global ORIGINAL_NEXT
    import service_clock
    ORIGINAL_NEXT=service_clock.next_control_tick
    service_clock.next_control_tick=next_control_tick
