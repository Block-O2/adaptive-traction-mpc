"""C3: a completed original TASK packet permits one extra actual service.

No wait on a future, synthetic callback, phase projection, or new request is
introduced. The original runtime consumes and admits the result at its next
real boundary. All unfinished past intervals still use the existing command.
"""
ROWS=[]
ORIGINAL_NEXT=None
PRECATCH=False
def completed_task(self):
    import fast_task_ipc
    life=self.runtime.get('plan_lifecycle')
    if life is None or life.closed:return None
    request=life._outstanding
    future=life._future
    if request is None or request.stage!='TASK' or not request.asynchronous:return None
    if type(future) is not fast_task_ipc.ReadyFuture or future.warm:return None
    if life._future_requests.get(future) is not request:return None
    if not self.phase_records or self.phase_records[-1]['phase']!='TASK':return None
    if self.clock()-request.sensor_capture_ns>=life.maximum_age_ns:return None
    notified=getattr(self,'_c3_notified_requests',None)
    if notified is not None and request.request_id in notified:return None
    # Atomic SOCK_SEQPACKET readiness; done() never waits or sees a partial packet.
    if not future.done() or life._outstanding is not request:return None
    if self.clock()-request.sensor_capture_ns>=life.maximum_age_ns:return None
    if notified is None:self._c3_notified_requests=notified=set()
    notified.add(request.request_id)
    return request,future

def next_control_tick(self):
    target=self.epoch_ns+(self._last_poll_grid+1)*self.sensor_steps*self.dt_ns
    now=self.clock()
    life=self.runtime.get('plan_lifecycle')
    request=None if life is None else life._outstanding
    precatch_begin=None
    if PRECATCH and now<target and request is not None and request.stage=='TASK' and request.asynchronous:
        # Existing committed command, original .25ms events; only real elapsed
        # physics is integrated before the ordinary deadline wait.
        precatch_begin=self.clock()
        self.catch_up('C3b_existing_command_real_elapsed_physics_before_deadline_wait')
    ready=completed_task(self) if self.clock()<target else None
    if ready is None:
        return ORIGINAL_NEXT(self)
    request,future=ready
    ROWS.append(dict(request_id=request.request_id,packet_identity=future.identity,
        ready_observed_ns=self.clock(),scheduled_deadline_ns=target,
        source_capture_ns=request.sensor_capture_ns,source_sample_time_s=request.source_sample_time_s,
        event='EXTRA_ACTUAL_SERVICE_FOR_ALREADY_COMPLETED_TASK',waited_for_future=False,precatch_begin_ns=precatch_begin,
        physical_before_s=float(self.plant.data.time),active_receipt_index=self.active_receipt_index))
    self.catch_up('next_control_tick_C3_completed_task_extra_actual_service')
    ROWS[-1].update(actual_return_ns=self.clock(),physical_after_s=float(self.plant.data.time))

def install(precatch=False):
    # service_clock C2b invokes the module's next_control_tick at runtime.
    global ORIGINAL_NEXT,PRECATCH
    import service_clock
    ORIGINAL_NEXT=service_clock.next_control_tick
    PRECATCH=bool(precatch)
    service_clock.next_control_tick=next_control_tick
