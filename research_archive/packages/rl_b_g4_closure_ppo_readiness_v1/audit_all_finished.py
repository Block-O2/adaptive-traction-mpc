from pathlib import Path
import json
from common import put
from cloud_case_audit import audit as case_audit
from force_audit import audit as force_audit
root=Path('runs');results=[]
for guard in sorted(root.iterdir()):
 if not (guard/'END.json').exists() or not (guard/'physics/env').exists():continue
 for ep in sorted((guard/'physics/env').glob('episode_*')):
  if not (ep/'episode_summary.json').exists():continue
  idx=int(ep.name.split('_')[1]);a=case_audit(guard/'physics',idx);f=force_audit(ep);results.append({'run':guard.name,'episode':idx,'category':'TEST_ONLY_WITH_REAL_MUJOCO' if 'TEST_ONLY' in guard.name else 'NATURAL_LEGAL_INPUT','case_audit_pass':a['pass'],'force_audit_pass':f['pass'],'failed_checks':[k for k,v in a['checks'].items() if not v],'status':a['status'],'task_s':a['reward']['task_s'],'reason':a['reward']['abort_reason'],'reward':a['reward']['sum_reward'],'J_F':f['independent_J_F_N_s'],'J_M':f['independent_J_M_Nm_s'],'native_steps':a['ownership']['native_steps_all']})
put('audit/FINISHED_EPISODE_AUDITS.json',results)
print(json.dumps(results,indent=2))
