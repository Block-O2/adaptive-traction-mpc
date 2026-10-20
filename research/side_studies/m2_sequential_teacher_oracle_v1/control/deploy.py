from pathlib import Path
import sys,json,time,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1');C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_sequential_teacher_oracle_v1_control')
rev=S/'preservation/code_revisions';rev.mkdir(exist_ok=True)
target=S/'code/sequential_runner.py';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if sha(target)!=sha(C/'runner.py'):
 shutil.copy2(target,rev/(sha(target)+'.py'));shutil.copy2(C/'runner.py',target)
if len(sys.argv)>1 and sys.argv[1]=='repair':
 src=S.parent/'m2_lowforce_repair_explore_10h_v1/output/HISTORICAL_K3_DESIGN_REFERENCE.json';dst=S/'output'/src.name;shutil.copy2(src,dst)
 cat={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']};q=dict(registered_unix=time.time(),candidates=[dict(id='B0_repeat_1',stage='REFERENCE',phases={}),cat['NATIVE_SCALAR_18'],dict(id='Frozen_M2',stage='REFERENCE',parameters={'frozen_Q':True})])
 (S/'queue/baseline_recovery.json').write_text(json.dumps(q,indent=2)+'\n')
 (S/'WRAPPER_REPAIR_REGISTERED.json').write_text(json.dumps(dict(unix=time.time(),reason='missing copied static historical candidate pool reference',source=str(src),sha256=sha(src),attempts_not_reset=True,t0_unchanged=True,thresholds_unchanged=True,physics_semantics_unchanged=True,original_stop_record_preserved=True),indent=2)+'\n')
print(json.dumps(dict(runner_sha256=sha(target))))
