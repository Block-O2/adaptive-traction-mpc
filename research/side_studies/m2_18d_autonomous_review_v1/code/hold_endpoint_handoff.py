"""C7: one CURRENT service after an actually committed HOLD endpoint.

No endpoint, sensor sample, clock credit, phase or planner request is invented.
The unchanged original loop decides whether to create the next HOLD request or
to transition. Scientific simulation keeps its original scheduled loop.
"""
ROWS=[]
ORIGINAL_NEXT=None
def register(runtime,governor,schedule,proposal,receipt,was_complete):
 wall=runtime.get('wall_session')
 if wall is None or was_complete or not governor.is_complete(schedule):return False
 if schedule.candidate.phase.value!='HOLD':return False
 if not receipt.get('applied') or receipt.get('apply_ns') is None:return False
 if not wall.phase_records or wall.phase_records[-1]['phase']!='TASK':return False
 assert governor.schedule is schedule and proposal['selected_progress_s']>=schedule.duration_s-1e-12
 item=dict(event='ACTUAL_COMMITTED_HOLD_ENDPOINT',receipt_index=receipt['receipt_index'],apply_ns=receipt['apply_ns'],physical_time_s=receipt['start_physics_s'],selected_progress_s=proposal['selected_progress_s'],duration_s=schedule.duration_s,authority='original governor commit after actual command write',consumed=False)
 runtime['_c7_endpoint_service']=item;ROWS.append(item)
 return True
def next_control_tick(self):
 item=self.runtime.get('_c7_endpoint_service')
 if item is None or item['consumed']:return ORIGINAL_NEXT(self)
 item['consumed']=True
 if not self.phase_records or self.phase_records[-1]['phase']!='TASK':return ORIGINAL_NEXT(self)
 # Mark actual owner work before this extra current service, just as C2b.
 import multirate
 row=multirate.ROWS['fast'][-1] if multirate.ROWS['fast'] else None
 if row is not None and row.get('service_finish_ns') is None:
  row.update(service_finish_ns=self.clock(),physics_before_wait_s=float(self.plant.data.time),command_currently_applied=self.plant.last_joint_torque.copy(),receipt_index=self.active_receipt_index,service_finish_semantics='C7 actual committed endpoint triggers one current service')
 begin=self.clock();steps=self.steps
 self.catch_up('C7_actual_committed_HOLD_endpoint_current_service')
 ROWS.append(dict(event='CURRENT_SERVICE_AFTER_COMMITTED_ENDPOINT',receipt_index=item['receipt_index'],begin_ns=begin,finish_ns=self.clock(),physics_before_step=steps,physics_after_step=self.steps,physical_time_s=float(self.plant.data.time),future_wait=False,new_request=False))
def install():
 global ORIGINAL_NEXT
 import study_common as sc,service_clock,multirate
 from traction_mpc_stage5.full3d_adaptive_integration_v1.receipt_reference_governor import ReceiptReferenceGovernor as C
 ORIGINAL_NEXT=service_clock.next_control_tick;service_clock.next_control_tick=next_control_tick
 original=C.commit
 def commit(self,schedule,proposal,receipt):
  before=self.is_complete(schedule);result=original(self,schedule,proposal,receipt)
  runtime=multirate.RUNTIME
  if runtime is not None:register(runtime,self,schedule,proposal,receipt,before)
  return result
 C.commit=commit
