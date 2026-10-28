"""C5: one actual service at an already activated original HOLD endpoint.

No dwell credit, phase transition, schedule duration or request is synthesized.
The original sensor-supported clock and native admission decide what follows.
"""
ROWS=[]
ORIGINAL_NEXT=None
PRECATCH=False
CONTINUOUS_PRECATCH=False
def register_after_original_hook(runtime,hook,receipt):
    cells=dict(zip(hook.__code__.co_freevars,hook.__closure__ or ()))
    needed=('decisions','active_decision_index','suffix_schedule','request')
    if not all(k in cells for k in needed):return
    values={k:cells[k].cell_contents for k in needed}
    decision=values['decisions'][values['active_decision_index']]
    request=values['request'];schedule=values['suffix_schedule'];wall=runtime.get('wall_session')
    if wall is None or decision.get('phase')!='HOLD' or decision.get('rolling_composite') is not None:return
    if request.stage!='TASK' or schedule.duration_s!=.5:return
    if receipt.get('apply_ns') is None or not receipt.get('applied'):return
    steps=int(round(schedule.duration_s/(wall.dt_ns/1e9)))
    assert steps==2000 and wall.dt_ns==250_000
    item=dict(request_id=request.request_id,receipt_index=receipt['receipt_index'],activation_ns=receipt['apply_ns'],start_step=wall.steps,
        start_physics_s=float(wall.plant.data.time),duration_s=schedule.duration_s,target_step=wall.steps+steps,
        deadline_ns=wall.epoch_ns+(wall.steps+steps)*wall.dt_ns,consumed=False)
    runtime['_c5_committed_endpoint']=item;ROWS.append(dict(event='ORIGINAL_ACTIVATED_HOLD_ENDPOINT_REGISTERED',**item))
def next_control_tick(self):
    target=self.epoch_ns+(self._last_poll_grid+1)*self.sensor_steps*self.dt_ns
    item=self.runtime.get('_c5_committed_endpoint')
    if item is None or item['consumed'] or not self.phase_records or self.phase_records[-1]['phase']!='TASK':return ORIGINAL_NEXT(self)
    deadline=item['deadline_ns'];now=self.clock()
    if CONTINUOUS_PRECATCH and now<target:
        start=self.clock()
        self.catch_up('C5c_committed_HOLD_real_elapsed_old_command_before_every_timer')
        now=self.clock()
        ROWS.append(dict(event='COMMITTED_HOLD_REAL_ELAPSED_PRECATCH',request_id=item['request_id'],begin_ns=start,finish_ns=now,actual_steps=self.steps,next_regular_deadline_ns=target))
    if deadline>=target or now>=target:return ORIGINAL_NEXT(self)
    precatch_begin=None
    if PRECATCH:
        precatch_begin=self.clock()
        self.catch_up('C5b_existing_command_real_elapsed_physics_before_endpoint_timer')
        now=self.clock()
        if now>=target:
            item['consumed']=True
            ROWS.append(dict(event='REGULAR_SERVICE_AFTER_PRECATCH_CROSSED_DEADLINE',request_id=item['request_id'],precatch_begin_ns=precatch_begin,actual_steps=self.steps,at_ns=now,next_regular_deadline_ns=target))
            return ORIGINAL_NEXT(self)
    # An endpoint already past still receives only one CURRENT service.
    if now<deadline:self.sleeper((deadline-now)/1e9)
    self.catch_up('C5_actual_service_at_original_committed_HOLD_endpoint')
    item['consumed']=True
    ROWS.append(dict(event='ACTUAL_SERVICE_AT_COMMITTED_ENDPOINT',request_id=item['request_id'],target_step=item['target_step'],actual_steps=self.steps,
        nominal_deadline_ns=deadline,actual_return_ns=self.clock(),next_regular_deadline_ns=target,
        physical_time_s=float(self.plant.data.time),no_new_request=True,no_dwell_credit=True))
    ROWS[-1]['precatch_begin_ns']=precatch_begin
def install(precatch=False,continuous_precatch=False):
    global ORIGINAL_NEXT,PRECATCH,CONTINUOUS_PRECATCH
    PRECATCH=bool(precatch)
    CONTINUOUS_PRECATCH=bool(continuous_precatch)
    import service_clock,study_common as sc
    ORIGINAL_NEXT=service_clock.next_control_tick;service_clock.next_control_tick=next_control_tick
    original=sc.rt._execute_interval
    def interval(runtime,**kwargs):
        hook=runtime.get('actual_activation_hook')
        if hook is not None and not getattr(hook,'_c5_endpoint_wrapper',False):
            def activated(receipt):
                hook(receipt)
                register_after_original_hook(runtime,hook,receipt)
            activated._c5_endpoint_wrapper=True
            runtime['actual_activation_hook']=activated
        return original(runtime,**kwargs)
    sc.rt._execute_interval=interval
