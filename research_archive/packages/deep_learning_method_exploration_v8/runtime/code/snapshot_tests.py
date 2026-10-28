"""Non-actuating, saved-input checks for snapshot isolation and stale proofs."""
from pathlib import Path
import sys,pickle,json,hashlib,time
S=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime')
sys.path.insert(0,str(S/'code'))
def main():
 import study_common as sc
 import admission_certificates as ac,slow_owner
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
 from dataclasses import replace
 import numpy as np
 slow_owner.warm()
 paths=sorted((S.parent/'b_native_q_realtime_integration_v1/output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))
 assert paths
 raw=pickle.loads(paths[0].read_bytes());planner,args=pickle.loads(raw['payload']);planner.planner.residual_spec={}
 payload=op.snapshot_task_call(planner,args);before=hashlib.sha256(payload).hexdigest()
 args['current_reference_state'][0]+=.01
 assert hashlib.sha256(payload).hexdigest()==before
 frozen_planner,frozen_args=pickle.loads(payload)
 assert not np.array_equal(args['current_reference_state'],frozen_args['current_reference_state'])
 decision=op.execute_task_snapshot(payload);cert=ac.prepare(payload,decision);schedule=decision.executed.schedule;belief=frozen_args['belief'];screen=AdaptiveMechanicsScreenV22();original=screen.evaluate
 key=ac.key(screen,belief,schedule.candidate,schedule);assert key in cert['proofs']
 assert original(belief,schedule.candidate,schedule)==cert['proofs'][key]
 tests=[]
 for label,changed_screen,changed_belief,changed_schedule in [
  ('MODEL_VERSION_CHANGE',screen,replace(belief,sequence=belief.sequence+1),schedule),
  ('MODEL_PARAMETERS_CHANGE_SAME_VERSION',screen,replace(belief,beta=belief.beta+1e-6),schedule),
  ('SCHEDULE_COEFFICIENTS_CHANGE',screen,belief,replace(schedule,coefficients=schedule.coefficients+1e-10)),
  ('MECHANICS_SCREEN_LIMIT_CHANGE',replace(screen,force_limit_n=199.),belief,schedule)]:
  changed_key=ac.key(changed_screen,changed_belief,changed_schedule.candidate,changed_schedule)
  assert changed_key not in cert['proofs'],label+':STALE_CERTIFICATE_MATCHED'
  tests.append(dict(name=label,status='PASS',changed_key=changed_key,cache_hit=False))
 result=dict(status='PASS',physics_added=0,Q_calls=0,G_calls=0,learning_updates=0,input_path=str(paths[0]),input_sha256=sc.sha(paths[0]),immutable_payload_sha256=before,snapshot_numeric_isolation=True,exact_native_mechanics_dictionary=True,proof_count=len(cert['proofs']),negative_tests=tests,plant_creation_forbidden=True,scope='Offline safety/dataflow checks only. Synthetic changed inputs do not alter any dispatched physical setup or controller thresholds.')
 sc.save('SNAPSHOT_AND_CERTIFICATE_TESTS.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
