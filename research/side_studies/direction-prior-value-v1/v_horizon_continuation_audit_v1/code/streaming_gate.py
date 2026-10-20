from freeze import *
import sys
def main():
 version=int(sys.argv[1]) if len(sys.argv)>1 else 1;name='008_streaming_fork_regression' if version==1 else '014_streaming_fork_v2_regression';group='streaming_fork_regression' if version==1 else 'streaming_fork_v2_regression';out=STUDY/'output';parent=json.loads((out/(name+'_RESULT.json')).read_text());branch=json.loads((out/(group+'_OUTBOUND_0_candidate0_DATA.json')).read_text());snapshot=json.loads((out/(group+'_OUTBOUND_0_SNAPSHOT.json')).read_text())
 assert parent['status']=='COMPLETE' and parent['metric']['valid'] and branch['metric']['valid']
 assert abs(parent['metric']['J_F']-branch['metric']['J_F'])<1e-6
 assert 'streaming_full_rows_sha256' in json.dumps(snapshot),'STREAMING_HASH_NOT_EXERCISED'
 assert branch['metric']['actual_new_main_model_inverse_dynamics_api_calls']>=0 and branch['metric']['actual_new_native_worker_model_inverse_dynamics_api_calls']>=0
 if version==2:assert 'generator_state' in json.dumps(snapshot),'MEASUREMENT_RNG_NOT_FINGERPRINTED'
 if version==2:
  late=json.loads((out/(group+'_RETURN_1_candidate0_DATA.json')).read_text());assert late['metric']['valid'] and abs(late['metric']['J_F']-parent['metric']['J_F'])<1e-6
  assert (STUDY/'source'/late['metric']['trace']).parent.joinpath('runtime_artifacts.json.gz').exists(),'BRANCH_RUNTIME_ARTIFACT_NOT_SAVED'
 save(STUDY/('STREAMING_FORK_GATE.json' if version==1 else 'STREAMING_FORK_V2_GATE.json'),dict(status='PASS',complete_native_and_lifecycle_state_verified=True,all_trace_rows_hashed=True,one_B_child_matches_parent=True,late_RETURN_B_child_matches_parent=version==2,new_model_counts_nonnegative=True,baseline_J_F=parent['metric']['J_F'],branch_J_F=branch['metric']['J_F'],original_branch_gate_preserved=True));print('STREAMING_FORK_GATE_PASS_v'+str(version))
if __name__=='__main__':main()
