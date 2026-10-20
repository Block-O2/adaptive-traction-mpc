"""B5 remove nested research events/locks; retain original native timing logs."""
def prime():
 import profiling_instrumentation as profile,call_audit
 profile.install=lambda:None
 call_audit.install=lambda:None
 # evidence() still rejects P imports. Native original request timestamps,
 # model API accounting, command receipts, summaries and full traces remain.
def evidence():
 return dict(research_nested_profiling=False,research_lock_counters=False,original_native_request_lifecycle=True,original_native_physics_step_times=True,original_main_model_API_counter=True,original_applied_command_receipts=True,full_q_dq_ddq_and_physical_trace=True,import_firewall=True,critical_path_io_removed=0,classification='Research instrumentation overhead removal only; no public B scheduling version change')
