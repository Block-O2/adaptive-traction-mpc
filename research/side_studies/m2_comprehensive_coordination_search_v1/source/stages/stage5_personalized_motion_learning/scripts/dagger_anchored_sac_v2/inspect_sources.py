from pathlib import Path
import json,gzip,numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1/source');S=R/'stages/stage5_personalized_motion_learning';O=S/'results/dagger_to_sac_expert_v1'
for rel,words in [('src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py',['reference_ready','schedule_complete','transition_allowed']),('src/traction_mpc_stage5/full3d_adaptive_integration_v1/online_reference.py',['array_equal','schedule_epoch','complete']),('src/traction_mpc_stage5/task.py',['hold_elapsed','reference_ready'])]:
 p=S/rel;lines=p.read_text().splitlines();ids=set()
 for i,line in enumerate(lines):
  if any(w in line for w in words):ids.update(range(max(0,i-8),min(len(lines),i+12)))
 print('\nSOURCE',p)
 for i in sorted(ids):print(i+1,lines[i])
print((S/'scripts/single_human_sac_expert_v1_r2/campaign_r2.py').read_text()[:15000])
p=O/'round_04/evaluation_1/episode_00001';print('FILES',[x.name for x in p.iterdir()])
z=np.load(p/'trace.npz');print('TRACE',z.files)
for f in ['summary.json','runtime_artifacts.json.gz']:
 if (p/f).exists():
  v=json.loads(gzip.open(p/f,'rt').read() if f.endswith('gz') else (p/f).read_text());print(f,'KEYS',list(v))
  for k in ['task','online_reference_records']:print(k,str(v.get(k))[:4000])
z=np.load(S/'results/demo_assisted_sac_task_acquisition_v1/NATIVE_DEMO.npz');print('DEMO',[(k,z[k].shape) for k in z.files])
