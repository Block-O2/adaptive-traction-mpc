from pathlib import Path
import shutil,subprocess,sys
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work');P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1/source/stages/stage5_personalized_motion_learning/scripts/single_human_sac_expert_v1')
for name in ('sac_env.py','qualify.py','qualification_batch.py','run_batch.py'):shutil.copy2(W/name,P/name)
subprocess.run([sys.executable,'-u',str(P/'qualification_batch.py')],check=True)
