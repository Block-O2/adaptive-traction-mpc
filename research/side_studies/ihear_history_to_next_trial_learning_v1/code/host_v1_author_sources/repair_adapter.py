from pathlib import Path
import json,shutil,hashlib,time,difflib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_history_to_next_trial_learning_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
p=S/'code/host_adapter.py';before=p.read_text();after=(W/'host_adapter.py').read_text()
assert not (S/'versions/host_adapter_v1_failed.py').exists(),'one repair only'
shutil.copy2(p,S/'versions/host_adapter_v1_failed.py');p.write_text(after)
(S/'reports/ADAPTER_REPAIR.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='M2_adapter_v1_failed',tofile='M2_adapter_v2')))
(S/'reports/ADAPTER_REPAIR.json').write_text(json.dumps(dict(status='REGISTERED',unix=time.time(),repair_count=1,failed_attempts=['002_M2_guard_on_smoke','003_M2_guard_off_smoke'],cause='Original initial TASK capture has no modifiable Q boundary and sends original tuple2; adapter incorrectly required envelope3',change='Detect validated original tuple2 and route through unchanged C13 fast_task_owner; envelope3 reserved for actual native modifiable boundaries',native_safety_changed=False,Q_count_or_training_changed=False,before_sha256=hashlib.sha256(before.encode()).hexdigest(),after_sha256=hashlib.sha256(after.encode()).hexdigest()),indent=2))
for old,new in [('002_M2_guard_on_smoke','004_M2_guard_on_retry'),('003_M2_guard_off_smoke','005_M2_guard_off_retry')]:
 cfg=json.loads((S/'queue'/(old+'.json')).read_text());cfg.update(id=new,adapter_version='M2_C13_ENVELOPE_v2',required_gates=cfg['required_gates']+['reports/OFFLINE_INTERFACE_GATE.json'])
 (S/'queue'/(new+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
print('Adapter v2 preserves initial unmodifiable native-B TASK route; one repair registered')
