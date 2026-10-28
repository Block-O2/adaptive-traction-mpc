exec((Path(__file__).parent/'preflight_r2.py').read_text().split("assert git('branch'")[0]) if False else None
from pathlib import Path
import sys,json,gzip,shutil,numpy as np
R=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/single_human_sac_expert_v1';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2')
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as rt
rec=json.loads((D/'COMPARATOR_old_nominal_MATCHED.json').read_text());p=(R/rec['trace']).parent
summary=json.loads((p/'summary.json').read_text());z=np.load(p/'trace.npz');mask=z['stage']=='TASK';ts=z['time_s'][mask];ph=z['phase'][mask] if 'phase' in z else None
print('CONTROL_DT',rt.CONTROL_DT_S,'keys',list(z.keys()));print('task',json.dumps(summary['task'],default=str)[:12000])
with gzip.open(p/'runtime_artifacts.json.gz','rt') as f:art=json.load(f)
print('artifact keys',list(art));print('summary keys',list(summary));
for key in ('planned_segments','decisions','reference_governor_records','online_reference_records'):
 val=summary.get(key,art.get(key));print(key,json.dumps(val,default=str)[:18000])
ht=next(x['time_s'] for x in summary['task']['phase_transitions'] if x['to']=='HOLD');et=next(x['time_s'] for x in summary['task']['phase_transitions'] if x['to']=='RETURN')
data={k:z[k][mask][(ts>=ht-.01)&(ts<=et+.01)].tolist() for k in z.keys() if z[k].ndim>=1 and len(z[k])==len(mask) and k not in ('task_beta','task_residual_weights_nm')}
(W/'HOLD_TRACE_SLICE.json').write_text(json.dumps(data,indent=2))
(W/'OLD_MATCHED_SUMMARY.json').write_text(json.dumps(summary,indent=2));(W/'OLD_MATCHED_ARTIFACT_KEYS.json').write_text(json.dumps({k:(list(v.keys()) if isinstance(v,dict) else len(v) if isinstance(v,list) else v) for k,v in art.items()},indent=2))
for p in (S/'src').rglob('*.py'):
 text=p.read_text()
 if ('class' in text and ('robust_hold_reference' in text or 'class ReferenceGovernor' in text)) or 'hold_duration_s' in text and 'plan_fixed_duration' in text:
  shutil.copy2(p,W/p.name)
