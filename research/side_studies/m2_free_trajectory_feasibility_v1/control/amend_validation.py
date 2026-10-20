from pathlib import Path
import json,time,hashlib,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
p=S/'TRAJECTORY_OPTIMIZATION_PROTOCOL.json';old=p.read_bytes();cfg=json.loads(old)
assert not (S/'FROZEN_SELECTION.json').exists()
assert not any(p.name.startswith(('W1_','W2_')) for p in (S/'source/results').iterdir())
shutil.copy2(p,S/'preservation/PROTOCOL_BEFORE_VALIDATION_COVERAGE_AMENDMENT.json')
cfg['validation']='Two preregistered same-Human legal RETURN0 native prefix conditions unchanged. Fork at OUTBOUND0 to execute the complete frozen OUTBOUND reference as well. Both arms disable free intent during shared RETURN0 prefix, then apply frozen unconsumed RETURN1+ suffix. Audit actual native q/dq at RETURN1 request. Consumed RETURN0 is not independently validated original action.'
cfg['validation_coverage_amendment_unix']=time.time()
for name in ['TRAJECTORY_OPTIMIZATION_PROTOCOL.json','SEARCH_PROTOCOL.json','RUN_PLAN.json']:(S/name).write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n')
(S/'VALIDATION_COVERAGE_AMENDMENT.json').write_text(json.dumps(dict(unix=time.time(),old_sha256=hashlib.sha256(old).hexdigest(),new_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),reason='Include actual selected OUTBOUND in complete paired validation instead of inheriting B OUTBOUND before RETURN1 fork',no_validation_output_seen=True,parameters_not_selected_or_frozen_yet=True,same_two_conditions=True,same_thresholds_dynamics_task_and_budget=True,original_protocol_preserved=True),indent=2)+'\n')
print('VALIDATION_COVERAGE_STRENGTHENED_BEFORE_FREEZE')
