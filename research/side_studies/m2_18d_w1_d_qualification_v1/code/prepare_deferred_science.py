"""Preregister B5 evaluator-only observer relocation, never public scheduling repair3."""
from prepare_tasks import *
from prepare_next_versions import frozen_sources
import ast
def main():
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ends={x['id'] for x in events if x['event']=='END'}
 assert all(any(id.startswith(str(k)+'_LEGAL_STABILITY') for id in ends) for k in range(260,276)),'LEGAL_SCI_QUEUE_MUST_JOIN_FIRST'
 assert sum(x['event']=='START' for x in events)+3<=160 and time.time()+1800<START+8.25*3600
 p=STUDY/'code/worker.py';text=p.read_text()
 if "request.get('deferred_evaluation')" not in text:
  anchor=" if request.get('mode')=='consecutive':";assert anchor in text
  text=text.replace(anchor," if request.get('deferred_evaluation'):\n  import deferred_evaluation\n  deferred_evaluation.install()\n"+anchor,1)
  anchor=" if 'profile' in locals():save(request['id']+'_TIMING_PROFILE.json',profile.evidence())";assert anchor in text
  text=text.replace(anchor,anchor+"\n if request.get('deferred_evaluation'):\n  deferred_evaluation.finish(request['id'])",1);ast.parse(text)
  save(STUDY/'versions/E7_WORKER_PRIOR_SOURCE.json',dict(path=str(p),sha256_before=sha(p),original_text=text if False else p.read_text(),scope='Optional research-only observer flag; all other dispatch paths retain original behavior.'))
  p.write_text(text)
 sources=frozen_sources()
 for f in ('worker.py','deferred_evaluation.py','lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 save(STUDY/'versions/E7_DEFERRED_EVALUATION_CONTRACT.json',dict(version='E7_B5_DEFERRED_EVALUATION',phase='B5_RESEARCH_ONLY_CRITICAL_PATH_RELOCATION',public_B_scheduling_repairs=2,new_public_B_scheduling_repairs=0,control_or_safety_change=False,original_evaluation_source=str(STUDY/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/fast_physics_monitor.py'),original_evaluation_only_contract='Original TruePhysicsMonitor explicitly never used by estimation, waypoint planning, or safety control. All references in frozen runtime are observe/stage assignment/terminal record.',mandatory_gate='Full original B/M2/legal deviation trajectory and original qualification.true_physics aggregate equality; no host dispatch until all pass.',additional_science_attempts=3,maximum_followup_actual_pairs=4,algorithm_sources=sources,Q_updates=0))
 for id,method,prefix,seed,original in [('280_E7_DEFERRED_science_B','M0',{},2026100621,True),('281_E7_DEFERRED_science_M2','M2',{},2026100621,False),('282_E7_DEFERRED_science_deviation','M2',{'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]},2026100623,False)]:
  enqueue(id,method=method,original=original,prefix=prefix,seed=seed,timing_version='E5_LEAN_v1',execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=method=='M2',research_profile=False,deferred_evaluation=True,algorithm_sources=sources)
 print('E7_B5_DEFERRED_EVALUATION_THREE_SCI_REGRESSIONS_QUEUED')
if __name__=='__main__':main()
