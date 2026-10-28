"""No physics, no training: syntax, relocatable assets and runtime checks."""
from pathlib import Path
import ast,hashlib,importlib.metadata as metadata,json,platform,sys
R=Path(__file__).resolve().parent
def runtime():
 return {'platform':sys.platform,'python':platform.python_version(),'packages':{n:metadata.version(n) for n in ('mujoco','numpy','scipy','gymnasium','stable-baselines3','torch')}}
def main():
 from common import load_config,SOURCE
 from ready_env import ReadyEnv
 from checkpoints import contract
 from resource_guard import sample
 errors=[];py=0
 for p in R.rglob('*.py'):
  if any(x in p.parts for x in ('.venv','runs','__pycache__','test_outputs')):continue
  try:ast.parse(p.read_text(encoding='utf-8'));py+=1
  except BaseException as e:errors.append({'path':p.relative_to(R).as_posix(),'error':str(e)})
 assets=json.loads((R/'audit/VENDOR_COPY_MANIFEST.json').read_text())
 for item in assets:
  p=R/item['copy']
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:errors.append({'asset':item['copy'],'error':'MISSING_OR_CHANGED'})
 case,options=load_config();env=ReadyEnv(R/'runs/never_reset');spaces={'observation':env.observation_space.shape,'action':env.action_space.shape};env.close()
 report={'category':'STATIC_AND_IMPORT_PREFLIGHT_NO_PHYSICS','pass':not errors,'errors':errors,'python_files':py,'vendor_assets':len(assets),'source_is_packaged':SOURCE==R/'source','spaces':spaces,'runtime':runtime(),'resource_sample':sample(),'contract_sha256':contract(),'cloud_runtime_physics':'NOT_RUN','install_network_dependencies':'wheels must be obtained by install.sh; no venv bundled'}
 (R/'PACKAGE_PREFLIGHT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
