"""Lightweight read-only provenance capture; imports no training/physics packages."""
from pathlib import Path
import sys, platform, json, hashlib, importlib.metadata, shutil
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source/stages/stage5_personalized_motion_learning')
D=S/'docs/demo_assisted_sac_task_acquisition_v1'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
data=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),kernel=platform.release(),packages={p:importlib.metadata.version(p) for p in ('stable-baselines3','torch','mujoco','gymnasium','numpy','scipy','casadi')},command='wsl -d Ubuntu -- bash /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1/launch.sh',launch_sha256=digest(W/'launch.sh'),launch_text=(W/'launch.sh').read_text(),failed_launch=dict(phase='before any formal online step or gradient update',reason='orchestration syntax error, repaired and compileall checked',log_sha256=digest(W/'output/LAUNCH_SYNTAX_FAILURE_BEFORE_TRAINING.log')),scientific_changes=False)
for p in (D,W/'output'):(p/'ENVIRONMENT_AND_COMMAND.json').write_text(json.dumps(data,indent=2)+'\n')
shutil.copy2(Path(__file__),S/'scripts/demo_assisted_sac_task_acquisition_v1'/Path(__file__).name)
shutil.copy2(W/'launch.sh',S/'scripts/demo_assisted_sac_task_acquisition_v1/launch.sh')
shutil.copy2(W/'output/LAUNCH_SYNTAX_FAILURE_BEFORE_TRAINING.log',D/'LAUNCH_SYNTAX_FAILURE_BEFORE_TRAINING.log')
print(json.dumps(dict(status='PROVENANCE_SAVED',packages=data['packages'])))
