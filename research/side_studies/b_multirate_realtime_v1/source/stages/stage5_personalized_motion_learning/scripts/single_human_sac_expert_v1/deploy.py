from pathlib import Path
import subprocess,sys,shutil
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_multirate_realtime_v1/source/stages/stage5_personalized_motion_learning/scripts/single_human_sac_expert_v1')
subprocess.run([sys.executable,str(W/'build_runtime.py')],check=True)
for name in ('sac_env.py','qualify.py','deploy.py'):
    shutil.copy2(W/name,P/name)
subprocess.run([sys.executable,str(P/'qualify.py'),'freeze'],check=True)
subprocess.run([sys.executable,str(P/'qualify.py'),'run','reference','.05','NATIVE'],check=True)
