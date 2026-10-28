from gates import *
base=json.loads((S/'results/coordination_research_interface_v1/B_original/summary.json').read_text())
keys=('phase','phase_elapsed_s','phase_remaining_s','timing_request_id','executed_label','executed_action_delta_q_rad','reference_state_rad_rad_s','deployable_state_rad_rad_s','deadline_wait_physical_intervals','pass_through_prefetch','future_handoff_bridge','plan_activated','activation_outcome','reference_boundary_continuity','actual_schedule_start_physics_s','activation_timestamp_s','decision_request_time_s','activation_rejected_reason')
rows=[]
for name in ('zero_v2','zero_logging_v2','zero_history_v2'):
 art=json.loads((O/name/'summary.json').read_text());a=[{k:d.get(k) for k in keys} for d in base['decisions']];b=[{k:d.get(k) for k in keys} for d in art['decisions']]
 row=dict(name=name,native_decision_count=len(b),decision_ownership_wait_equal=a==b,safety_mode_counts_equal=base['safety_mode_counts']==art['safety_mode_counts'],reference_gate=read(name+'_GATE.json')['pass_']);row['pass_']=all(row[k] for k in ('decision_ownership_wait_equal','safety_mode_counts_equal','reference_gate'));rows.append(row)
save('ZERO_OWNERSHIP_GATE.json',dict(pass_=all(x['pass_'] for x in rows),rows=rows,compared_fields=keys,host_monotonic_timestamps_excluded='measured host compute timestamps vary; native physical ownership and wait intervals compared exactly'))
assert all(x['pass_'] for x in rows)
