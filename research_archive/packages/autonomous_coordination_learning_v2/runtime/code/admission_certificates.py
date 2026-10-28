"""Off-worker mechanics preparation keyed by ALL original mathematical inputs.

Current-state clearance/motion/phase/age/goal and command checks still execute
in native admission. A changed model or schedule performs native recomputation.
"""
import json,hashlib,pickle,time,copy
CACHE={};ROWS=[]
def key(screen,belief,candidate,schedule):
 import study_common as sc
 return hashlib.sha256(json.dumps(sc.clean([screen,belief,candidate,schedule]),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def prepare(payload,decision):
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
 planner,args=pickle.loads(payload);belief=args['belief'];screen=AdaptiveMechanicsScreenV22();primary=decision.executed.schedule
 schedules=[primary];escape=getattr(primary,'safe_escape',None)
 if escape is not None:schedules.extend([escape.bridge,escape.stop])
 started=time.monotonic_ns();proofs={}
 for schedule in schedules:proofs[key(screen,belief,schedule.candidate,schedule)]=screen.evaluate(belief,schedule.candidate,schedule)
 return dict(proofs=proofs,prepare_start_ns=started,prepare_finish_ns=time.monotonic_ns(),model_sequence=belief.sequence,mathematics='original unmodified AdaptiveMechanicsScreenV22.evaluate')
def install():
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22 as C
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 import slow_owner
 original=C.evaluate;original_result=op.PlanLifecycle.result
 op._process_task_snapshot=slow_owner.task_with_certificates
 def result(self,future):
  value=original_result(self,future)
  raw=future.result() if self.process_worker else {}
  cert=raw.get('multirate_mechanics_certificates')
  if cert:
   CACHE.clear();CACHE.update(cert['proofs'])
   ROWS.append(dict(event='RECEIVE',received_ns=time.monotonic_ns(),**{k:v for k,v in cert.items() if k!='proofs'},proof_count=len(cert['proofs'])))
  return value
 op.PlanLifecycle.result=result
 def evaluate(self,belief,candidate,schedule):
  started=time.monotonic_ns();k=key(self,belief,candidate,schedule);matched=k in CACHE
  out=copy.deepcopy(CACHE[k]) if matched else original(self,belief,candidate,schedule)
  ROWS.append(dict(event='CURRENT_MODEL_CHECK',start_ns=started,finish_ns=time.monotonic_ns(),input_sha256=k,current_model_sequence=belief.sequence,candidate_label=candidate.label,exact_all_input_match=matched,native_recompute=not matched,feasible=out['feasible']))
  return out
 C.evaluate=evaluate
