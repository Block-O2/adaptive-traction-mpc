from pathlib import Path
import sys,json,gzip,inspect,shutil
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/single_human_sac_expert_v1';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2')
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as rt
source=Path(inspect.getfile(rt.SensorSupportedTaskClock));shutil.copy2(source,W/source.name)
rec=json.loads((D/'COMPARATOR_old_nominal_MATCHED.json').read_text());p=(R/rec['trace']).parent
with gzip.open(p/'runtime_artifacts.json.gz','rt') as f:a=json.load(f)
s=json.loads((p/'summary.json').read_text());h=[d for d in s['decisions'] if d.get('phase')=='HOLD'];print('HOLD DECISIONS',json.dumps([{k:v for k,v in d.items() if k!='evaluations'} for d in h],default=str)[:12000])
for key in ('requests','activation_validations','rolling_splice_events','safe_fallback_events'):
 rows=[x for x in a[key] if 'HOLD' in json.dumps(x)];print(key,json.dumps(rows,default=str)[:8000])
dwell=a['sample_supported_dwell'];print('DWELL_FIRST',json.dumps(dwell[:4]));print('DWELL_LAST',json.dumps(dwell[-8:]));(W/'SENSOR_DWELL_EVIDENCE.json').write_text(json.dumps(dwell,indent=2))
for k in ('activation_validations','requests','task_decisions'):(W/(k.upper()+'.json')).write_text(json.dumps(a[k],indent=2))
print('source',source)
