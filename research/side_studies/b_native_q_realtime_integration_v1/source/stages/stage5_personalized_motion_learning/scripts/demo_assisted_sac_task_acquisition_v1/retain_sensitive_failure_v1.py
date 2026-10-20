"""Preserve the informative A50k pre/final-update positional discontinuity."""
from pathlib import Path
import json,shutil,hashlib
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_q_realtime_integration_v1/source');S=R/'stages/stage5_personalized_motion_learning';NAME='demo_assisted_sac_task_acquisition_v1'
D=S/'docs'/NAME;O=S/'results'/NAME;P=S/'scripts'/NAME;L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/NAME/'output'
rows=[]
for scope in ('NATIVE','MATCHED'):
    r=json.loads((D/f'EVALUATION_A_0050000_{scope}_periodic.json').read_text());src=R/r['trace'];assert src.is_file()
    folder=O/'important_failure_archive'/r['rollout_id'];folder.mkdir(parents=True,exist_ok=False)
    files={}
    for original,new in [('trace.npz','IMPORTANT_FAILURE_TRACE.npz'),('runtime_artifacts.json.gz','IMPORTANT_FAILURE_RUNTIME.json.gz')]:
        p=src.parent/original
        if p.exists():
            target=folder/new;shutil.copy2(p,target);h=hashlib.sha256(target.read_bytes()).hexdigest();assert h==hashlib.sha256(p.read_bytes()).hexdigest();files[str(target)]=h
            if original=='trace.npz':assert h==r['trace_sha256']
    rows.append(dict(source_rollout=r['rollout_id'],source_trace=str(src),archived_files=files,training_step=50000,updates=44999,VALID=False,reason='Informative positional discontinuity after exactly one ordinary SAC update; not a prior VALID task or a success-regression claim.'))
out=dict(status='PRESERVED_IMPORTANT_FAILURE',rows=rows,scientific_changes=[],new_online_steps=0,new_updates=0)
for root in (D,L):(root/'SENSITIVE_A50K_FAILURE_RETENTION.json').write_text(json.dumps(out,indent=2)+'\n')
shutil.copy2(Path(__file__),P/Path(__file__).name)
print(json.dumps(out))
