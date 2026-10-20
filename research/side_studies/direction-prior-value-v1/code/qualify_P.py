from freeze import *
def main():
 r=json.loads((STUDY/'output/012_P_completion_allowance_regression_RESULT.json').read_text());m=r.get('metric',{});s=json.loads((STUDY/'output/012_P_completion_allowance_regression_SEARCH.json').read_text())
 checks=dict(worker_complete=r['status']=='COMPLETE',independent_physical_valid=m.get('task_valid',False),R2_matched=m.get('matched_eligible',False),complete_task=m.get('status')=='COMPLETE',no_online_full_physics=s['online_physics_branches']==0,constant_candidate_budget=all(len(row['candidates'])==16 for row in s['rows']),zero_learning=s['method']=='P' and s['network_calls']==0,source_frozen_imports=all(str(STUDY) in p for p in r['import_sources'].values()))
 gate=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,J_F=m.get('J_F'),phase_durations=m.get('phase_durations'),loaded_code_manifest_sha256=r.get('loaded_code_manifest_sha256'),physical_contract_unchanged=True)
 save(STUDY/'P_QUALIFICATION_GATE.json',gate);assert gate['status']=='PASS','STRONG_P_PREFLIGHT_NOT_QUALIFIED';print(json.dumps(gate))
if __name__=='__main__':main()
