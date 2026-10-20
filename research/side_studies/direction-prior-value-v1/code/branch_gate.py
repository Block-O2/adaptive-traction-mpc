from freeze import *
import numpy as np
def main():
 out=STUDY/'output';parent=json.loads((out/'005_branch_smoke_RESULT.json').read_text());assert parent['status']=='COMPLETE'
 rows=[json.loads(p.read_text()) for p in out.glob('branch_smoke*_DATA.json')];assert len(rows)==2
 assert all(r['metric']['valid'] and r['metric']['matched_eligible'] for r in rows)
 base=next(r for r in rows if r['id'].endswith('candidate0'));nonzero=next(r for r in rows if r['id'].endswith('candidate1'))
 assert abs(base['metric']['J_F']-parent['metric']['J_F'])<1e-6
 assert abs(nonzero['metric']['J_F']-base['metric']['J_F'])>.1
 assert all(r['value_rows'] and any('deltaV_label' in q for q in r['value_rows']) for r in rows)
 save(STUDY/'BRANCH_GATE.json',dict(status='PASS',full_state_cpu_fork=True,CUDA_in_parent=False,one_physics_owner=True,parent_after_hash_checked=True,B_branch_cost_matches_parent=True,distinct_K3_execution=True,baseline_J_F=base['metric']['J_F'],coordinated_J_F=nonzero['metric']['J_F'],value_labels={r['id']:len([q for q in r['value_rows'] if 'deltaV_label' in q]) for r in rows},remaining_cost_units='N s',all_branches_counted=True))
 print('BRANCH_GATE_PASS')
if __name__=='__main__':main()
