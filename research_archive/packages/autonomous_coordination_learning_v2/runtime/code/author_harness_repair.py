from pathlib import Path
import json,shutil,hashlib
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime');OLD=S.parent/'b_hold_return_critical_path_v1'
rows=[]
for name in ('SHARED_COORDINATION_ACTION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json'):
 p=OLD/'output'/name;shutil.copy2(p,S/'output'/name);rows.append(dict(path='output/'+name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
if (OLD/'TIMING_BASELINE.json').exists():shutil.copy2(OLD/'TIMING_BASELINE.json',S/'TIMING_BASELINE.json')
cfg=json.loads((S/'queue/001_B_confirm_nominal.json').read_text());cfg['id']='003_B_confirm_nominal_harness_retry';(S/'queue'/(cfg['id']+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
(S/'reports/HARNESS_ASSEMBLY_REPAIR.json').write_text(json.dumps(dict(status='REPAIRED',failed_attempt='001_B_confirm_nominal',failure='Missing copied immutable action contract before physics entry',native_steps=0,repaired_files=rows,science_changes=False),indent=2)+'\n')
print('Harness immutable input files copied; failed START/END retained; retry has new ID')
