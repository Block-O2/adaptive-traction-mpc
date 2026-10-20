from pathlib import Path
import sys,json,platform,importlib.metadata,hashlib,time
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
versions={}
for n in ['numpy','scipy','mujoco','matplotlib','gymnasium']:
 try:versions[n]=importlib.metadata.version(n)
 except importlib.metadata.PackageNotFoundError:versions[n]='NOT_INSTALLED'
exe=Path(sys.executable).resolve();out=dict(python=sys.version,executable=str(exe),python_executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),platform=platform.platform(),uname=list(platform.uname()),WSL_distribution='Ubuntu-Research-Verify',package_versions=versions,scientific_execution_threads={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},execution_mode='SCIENTIFIC_SIMULATION',no_hardware=True,unix=time.time())
(P/'audit/EXECUTION_ENVIRONMENT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(versions))
