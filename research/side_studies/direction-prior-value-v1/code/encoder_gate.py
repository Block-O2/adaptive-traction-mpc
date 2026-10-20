from freeze import *
def main():
 parent=json.loads((STUDY/'output/013_encoder_v3_late_gate_RESULT.json').read_text());branch=json.loads((STUDY/'output/encoder_v3_gate_RETURN_1_candidate0_DATA.json').read_text())
 assert parent['status']=='COMPLETE' and parent['metric']['valid'] and branch['metric']['valid'];assert abs(parent['metric']['J_F']-branch['metric']['J_F'])<1e-6
 assert (STUDY/'source'/branch['metric']['trace']).parent.joinpath('runtime_artifacts.json.gz').exists()
 save(STUDY/'ENCODER_V3_GATE.json',dict(status='PASS',late_B_fork_full_state_verified=True,B_parent_child_J_F_equal=True,J_F=parent['metric']['J_F'],branch_archive_separate=True,loaded_source=parent['loaded_code_manifest_sha256']));print('ENCODER_V3_GATE_PASS')
if __name__=='__main__':main()
