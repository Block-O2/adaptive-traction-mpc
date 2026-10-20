"""Logging-only native function wrappers and an explicit P execution firewall."""
import sys,traceback,functools,threading
COUNTS={};STACKS={};LOCK=threading.Lock()
def wrap(cls,name,role):
 original=getattr(cls,name)
 @functools.wraps(original)
 def counted(*a,**kw):
  with LOCK:
   COUNTS[role]=COUNTS.get(role,0)+1
   if role not in STACKS:STACKS[role]=traceback.format_stack(limit=8)
  return original(*a,**kw)
 setattr(cls,name,counted)
def install():
 from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22,AdaptiveMechanicsScreenV22
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
 wrap(HumanWaypointFeedbackMPCV1,'_evaluate','B_existing_local_candidate_evaluate')
 wrap(AdaptiveHumanWaypointHWMPCV22,'decide','B_native_adaptive_decide')
 wrap(AdaptiveMechanicsScreenV22,'evaluate','B_necessary_mechanics_certificate')
 wrap(QuinticHumanWaypointSchedulerV1,'plan_reference_contract','B_native_schedule_certificate')
def evidence():
 forbidden=[n for n in sys.modules if n in ('planning','known_model')]
 assert not forbidden,'P_FIREWALL_VIOLATION'
 return dict(counts=COUNTS,first_call_stacks=STACKS,forbidden_P_modules_loaded=forbidden,P_full_repetition_predict_calls=0,P_search_interface_calls=0,P_V_base_calls=0,basis='P modules planning.py/known_model.py are absent from this isolated harness and their import is rejected; native function stacks identify preserved required local/safety calls')
