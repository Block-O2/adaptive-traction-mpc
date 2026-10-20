CFG={}
INSTALLED_FLAGS=None
def install(cfg):
 global CFG,INSTALLED_FLAGS
 CFG=dict(cfg)
 flags=tuple((k,cfg.get(k,False)) for k in ('native_backend','native_so3','native_cross3','native_cross_expanded','native_soft_limits','native_small_kernels','native_geometry','native_intervals','native_value_tree','native_quintic','native_single_step','native_bool_reductions','admission_key','geometry_transaction_reuse','causal_metadata','deferred_receipt_prepare','causal_clock','service_clock','service_clock_telemetry','integer_grid','same_tick_reuse','numerical_reuse','loaded_context_reuse','reuse_shadow','attribution','capture_controller_full','capture_task_inputs','capture_admission','fast_task_owner','task_transport'))
 flags=flags+(('completed_result_service',cfg.get('completed_result_service',False)),('completed_result_precatch',cfg.get('completed_result_precatch',False)),('front_attribution',cfg.get('front_attribution',False)))
 flags=flags+(('readiness_service',cfg.get('readiness_service',False)),)
 flags=flags+(('committed_endpoint_service',cfg.get('committed_endpoint_service',False)),)
 flags=flags+(('committed_endpoint_precatch',cfg.get('committed_endpoint_precatch',False)),)
 flags=flags+(('bidirectional_transport_warm',cfg.get('bidirectional_transport_warm',False)),)
 flags=flags+(('committed_hold_continuous_precatch',cfg.get('committed_hold_continuous_precatch',False)),)
 flags=flags+(('hold_endpoint_handoff',cfg.get('hold_endpoint_handoff',False)),('critical_trace',cfg.get('critical_trace',False)))
 flags=flags+(('handoff_exclusive_attribution',cfg.get('handoff_exclusive_attribution',False)),)
 if INSTALLED_FLAGS is not None:
  assert flags==INSTALLED_FLAGS,'Do not change runtime implementation inside a reused interpreter'
  if cfg.get('hold_endpoint_handoff'):
   import hold_endpoint_handoff
   hold_endpoint_handoff.ROWS.clear()
  if cfg.get('critical_trace'):
   import critical_trace
   critical_trace.ROWS.clear()
  if cfg.get('committed_endpoint_service'):
   import committed_endpoint_service
   committed_endpoint_service.ROWS.clear()
  if cfg.get('readiness_service'):
   import readiness_service
   readiness_service.ROWS.clear()
   import completed_result_service
   completed_result_service.ROWS.clear()
  if cfg.get('completed_result_service'):
   import completed_result_service
   completed_result_service.ROWS.clear()
  if cfg.get('numerical_reuse'):
   import numerical_reuse
   numerical_reuse.LAST=None
   for k in numerical_reuse.ROWS:numerical_reuse.ROWS[k]=0
  if cfg.get('attribution'):
   import fast_attribution as a
   a.STACK.clear();a.TOTAL.clear();a.CALLS.clear();a.CYCLES.clear();a.INPUTS.clear();a.CURRENT=None
  if cfg.get('loaded_context_reuse'):
   import loaded_context_reuse
   for k in loaded_context_reuse.ROWS:loaded_context_reuse.ROWS[k]=0
  if cfg.get('task_transport')=='DIRECT_D1':
   import fast_task_ipc
   fast_task_ipc.ROWS.clear()
  if cfg.get('capture_controller_full'):
   import full_controller_replay as capture
   capture.CAPTURES.clear();capture.PHASES.clear()
  if cfg.get('capture_admission'):
   import admission_replay as capture
   capture.CAPTURES.clear();capture.COUNTS.clear()
  if cfg.get('capture_task_inputs'):
   import task_input_replay as capture
   capture.CAPTURES.clear();capture.COUNTS.clear()
  if cfg.get('geometry_transaction_reuse'):
   import geometry_transaction_reuse
   geometry_transaction_reuse.ROWS.clear()
  return
 INSTALLED_FLAGS=flags
 if cfg.get('native_backend'):
  import native_interface_adapter
  native_interface_adapter.install(so3=cfg.get('native_so3',False))
 if cfg.get('native_soft_limits'):
  import native_soft_limits
  native_soft_limits.install()
 if cfg.get('native_single_step'):
  assert cfg.get('native_backend') and cfg.get('native_soft_limits')
  import native_single_step
  native_single_step.install()
 if cfg.get('native_small_kernels'):
  import os,native_small_kernels
  os.environ['FAST_NATIVE_SMALL_KERNELS']='N5'
  native_small_kernels.install()
 if cfg.get('native_geometry'):
  import os,native_geometry
  os.environ['FAST_NATIVE_GEOMETRY']='N6'
  native_geometry.install()
 if cfg.get('native_intervals'):
  import os,native_intervals
  os.environ['FAST_NATIVE_INTERVALS']='N12'
  native_intervals.install()
 if cfg.get('native_value_tree'):
  import os,native_value_tree
  os.environ['FAST_NATIVE_VALUE_TREE']='N8'
  native_value_tree.install()
 if cfg.get('native_quintic'):
  import os,native_quintic
  os.environ['FAST_NATIVE_QUINTIC']='N9'
  native_quintic.install()
 if cfg.get('admission_key')=='RAW_A1':
  import os,admission_key
  os.environ['FAST_ADMISSION_KEY']='RAW_A1'
  admission_key.install()
 if cfg.get('same_tick_reuse'):
  import same_tick_reuse
  same_tick_reuse.install(shadow=cfg.get('reuse_shadow',False))
 if cfg.get('native_cross3'):
  import native_vectors
  CFG['native_vector_modules']=native_vectors.install(expanded=cfg.get('native_cross_expanded',False))
 if cfg.get('native_bool_reductions'):
  import os,native_bool_reductions
  os.environ['FAST_NATIVE_BOOL_REDUCTIONS']='N13'
  native_bool_reductions.install()
 if cfg.get('numerical_reuse'):
  import numerical_reuse
  numerical_reuse.install(shadow=cfg.get('reuse_shadow',False))
 if cfg.get('loaded_context_reuse'):
  import loaded_context_reuse
  loaded_context_reuse.install(shadow=cfg.get('reuse_shadow',False))
 if cfg.get('geometry_transaction_reuse'):
  import os,geometry_transaction_reuse
  os.environ['FAST_GEOMETRY_TRANSACTION']='GEO1'
  geometry_transaction_reuse.install(parent=True)
 if cfg.get('causal_clock'):
  import causal_clock
  causal_clock.install(integer_grid=cfg.get('integer_grid',False))
 if cfg.get('causal_metadata'):
  import causal_metadata
  causal_metadata.install()
 if cfg.get('deferred_receipt_prepare'):
  import deferred_receipt_prepare
  deferred_receipt_prepare.install()
 if cfg.get('service_clock'):
  import service_clock
  service_clock.install(telemetry=cfg.get('service_clock_telemetry',False))
 if cfg.get('attribution'):
  import fast_attribution
  fast_attribution.install(cfg)
 if cfg.get('handoff_exclusive_attribution'):
  assert cfg.get('attribution') and cfg.get('front_attribution')
  import handoff_budget
  handoff_budget.install()
 if cfg.get('completed_result_service'):
  assert cfg.get('service_clock') and cfg.get('service_clock_telemetry') and cfg.get('task_transport')=='DIRECT_D1'
  import completed_result_service
  completed_result_service.install(precatch=cfg.get('completed_result_precatch',False))
 if cfg.get('readiness_service'):
  assert not cfg.get('completed_result_service')
  assert cfg.get('service_clock') and cfg.get('service_clock_telemetry') and cfg.get('task_transport')=='DIRECT_D1'
  import readiness_service
  readiness_service.install()
 if cfg.get('committed_endpoint_service'):
  assert not cfg.get('completed_result_service')
  assert not cfg.get('readiness_service') or cfg.get('compose_readiness_and_endpoint',False)
  assert cfg.get('service_clock') and cfg.get('service_clock_telemetry')
  import committed_endpoint_service
  committed_endpoint_service.install(precatch=cfg.get('committed_endpoint_precatch',False),continuous_precatch=cfg.get('committed_hold_continuous_precatch',False))
 if cfg.get('hold_endpoint_handoff') and cfg['execution_mode']!='SCIENTIFIC_SIMULATION':
  import hold_endpoint_handoff
  hold_endpoint_handoff.install()
 if cfg.get('critical_trace'):
  import critical_trace
  critical_trace.install()
 if cfg.get('capture_controller_full'):
  import full_controller_replay
  full_controller_replay.install()
 if cfg.get('capture_task_inputs'):
  import task_input_replay
  task_input_replay.install()
 if cfg.get('capture_admission'):
  import admission_replay
  admission_replay.install()
def finish(ident):
 import study_common as sc
 if CFG.get('hold_endpoint_handoff'):
  import hold_endpoint_handoff
  sc.save(ident+'_HOLD_ENDPOINT_HANDOFF.json',dict(rows=hold_endpoint_handoff.ROWS,scientific_bypass=CFG['execution_mode']=='SCIENTIFIC_SIMULATION',original_completion_and_minimum_unchanged=True))
 if CFG.get('critical_trace'):
  import critical_trace
  critical_trace.finish(ident)
 if CFG.get('handoff_exclusive_attribution'):
  import handoff_budget
  handoff_budget.finish(ident)
 if CFG.get('committed_endpoint_service'):
  import committed_endpoint_service
  sc.save(ident+'_COMMITTED_ENDPOINT_SERVICE.json',dict(rows=committed_endpoint_service.ROWS,no_new_requests=True,no_dwell_credit=True,no_duration_change=True,original_phase_and_admission=True))
 if CFG.get('readiness_service'):
  import readiness_service,completed_result_service
  sc.save(ident+'_READINESS_SERVICE.json',dict(rows=readiness_service.ROWS,completion_notifications=completed_result_service.ROWS,timer_bounded=True,no_future_result_wait=True,no_new_requests=True))
 sc.save(ident+'_FAST_VERSION.json',dict(config=CFG,physics_algorithm_changed=False,control_law_changed=False,learning_updates=0))
 if CFG.get('fault_injection'):
  import fault_injection
  sc.save(ident+'_FAULT_INJECTION.json',dict(config=fault_injection.CONFIG,rows=fault_injection.ROWS,original_source_and_safety_unchanged=True))
 if CFG.get('completed_result_service'):
  import completed_result_service
  sc.save(ident+'_COMPLETED_RESULT_SERVICE.json',dict(rows=completed_result_service.ROWS,no_future_wait=True,original_current_admission=True,no_new_requests=True))
 if CFG.get('same_tick_reuse'):
  import same_tick_reuse
  sc.save(ident+'_SAME_TICK_REUSE.json',same_tick_reuse.ROWS)
 if CFG.get('numerical_reuse'):
  import numerical_reuse
  sc.save(ident+'_NUMERICAL_REUSE.json',numerical_reuse.ROWS)
 if CFG.get('loaded_context_reuse'):
  import loaded_context_reuse
  sc.save(ident+'_LOADED_CONTEXT_REUSE.json',loaded_context_reuse.ROWS)
 if CFG.get('geometry_transaction_reuse'):
  import geometry_transaction_reuse
  sc.save(ident+'_GEOMETRY_TRANSACTION_REUSE.json',geometry_transaction_reuse.ROWS)
 if CFG.get('attribution'):
  import fast_attribution
  fast_attribution.finish(ident)
 if CFG.get('capture_controller_full'):
  import full_controller_replay
  full_controller_replay.finish(ident)
 if CFG.get('capture_task_inputs'):
  import task_input_replay
  task_input_replay.finish(ident)
 if CFG.get('capture_admission'):
  import admission_replay
  admission_replay.finish(ident)
 if CFG.get('task_transport')=='DIRECT_D1':
  import fast_task_ipc
  sc.save(ident+'_DIRECT_IPC.json',dict(rows=fast_task_ipc.ROWS,one_original_TASK_worker=True,live_plant_owner_count=1))
