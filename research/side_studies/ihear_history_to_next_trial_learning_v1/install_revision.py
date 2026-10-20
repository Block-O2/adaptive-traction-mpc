"""Versioned installation between workers only; never discard executed source identities."""
from pathlib import Path
import json,hashlib,shutil,sys,time,ast
R=Path(__file__).resolve().parent;P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
version=sys.argv[1]
active=json.loads((P/'OWNED_ACTIVE_PROCESS.json').read_text());assert active.get('active') is False,'WORKER_ACTIVE'
archive=P/'versions'/('before_'+version);archive.mkdir(parents=True,exist_ok=False)
manifest=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text())
for n in ['continuous_runner.py','EXECUTION_CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST_v6.json','PREPHYSICAL_CHECKS.json']:shutil.copy2(P/n,archive/n)
for name in ['continuous_runner.py','learning_models.py','train_models.py','install_revision.py']:
    f=R/name;ast.parse(f.read_text(encoding='utf-8'));shutil.copy2(f,P/name)
for n in ['continuous_runner.py','learning_models.py']:
    manifest['files'][n]=hashlib.sha256((P/n).read_bytes()).hexdigest()
manifest.update(frozen_unix=time.time(),revision=version,change='strict no-history input for ablation, explicit bootstrap logging, H150 native-ownership evaluator path',
    prior_manifest_sha256=hashlib.sha256((archive/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest())
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copy2(P/'EXECUTION_CODE_MANIFEST.json',P/'EXECUTION_CODE_MANIFEST_v6.json')
for f in R.iterdir():
    if f.suffix=='.md' or f.name=='METHODOLOGY_SOURCES.json':shutil.copy2(f,P/f.name)
print('INSTALLED',version,flush=True)
