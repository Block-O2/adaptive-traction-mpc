from pathlib import Path
import shutil,hashlib,json,time,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control')
for name in ['runner.py','free_planner.py']:
    target=S/'code'/name;new=C/name
    if target.read_bytes()!=new.read_bytes():
        rev=S/'preservation/code_revisions';rev.mkdir(exist_ok=True)
        shutil.copy2(target,rev/(hashlib.sha256(target.read_bytes()).hexdigest()+'.py'));shutil.copy2(new,target)
    compile(target.read_text(),str(target),'exec')
print('DEPLOYED_NO_PHYSICS')
