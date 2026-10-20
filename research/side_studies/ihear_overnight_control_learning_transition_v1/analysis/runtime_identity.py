from pathlib import Path
import sys,os,json,platform,importlib.metadata,time,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
names=['numpy','mujoco','torch','matplotlib','scipy'];versions={name:importlib.metadata.version(name) for name in names}
out=dict(unix=time.time(),python=sys.version,python_executable=sys.executable,platform=platform.platform(),WSL_distribution=os.environ.get('WSL_DISTRO_NAME'),packages=versions,physics_native_dt_s=.00025,control_dt_s=.005,scientific_execution_mode='SCIENTIFIC_SIMULATION',torch_training_in_this_study=False,all_mutations_confined_to_current_study=True)
(P/'audit/RUNTIME_VERSIONS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
