"""Explicit per-file Git checkpoints, production and raw-manifest provenance."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, subprocess, platform
R=Path(__file__).resolve().parents[4];S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/value_learning_research_v1';RAW=S/'results/value_learning_research_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n')
def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
def checkpoint(phase, push=True):
 source=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text());production={p:sha(R/p) for p in source['production_files_sha256']}
 evidence={p:sha(R/p) for p in source['frozen_evidence_sha256']}
 if production!=source['production_files_sha256'] or evidence!=source['frozen_evidence_sha256']:raise RuntimeError('frozen source changed')
 files={str(p.relative_to(R)):sha(p) for p in (S/'scripts/value_learning_v1').glob('*.py')}
 save(D/'FINGERPRINTS.json',{'schema':'value_research_fingerprints_v1','source_head':source['source_head'],'head_before_checkpoint':git('rev-parse','HEAD'),'production_unchanged':True,'historical_evidence_unchanged':True,'production_files_sha256':production,'research_files_sha256':files,'phase':phase,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.platform()})
 results=[]
 for p in sorted((RAW/'runs').glob('*/rollout_result.json')):
  r=json.loads(p.read_text())
  if r.get('status')=='RUNNING':continue
  results.append({'run_id':r['run_id'],'status':r['status'],'result_sha256':sha(p),'raw_files_sha256':r.get('raw_files_sha256',{}),'source_commit':r.get('source_commit')})
 save(D/'RAW_DATA_MANIFEST.json',{'schema':'value_research_raw_manifest_v1','phase':phase,'rollouts':results,'raw_directory':str(RAW.relative_to(R)),'raw_directory_git_ignored':True,'historical_source_manifest_sha256':source['frozen_evidence_sha256'].get('stages/stage5_personalized_motion_learning/docs/coordination_pacing_exploration_v1/RAW_DATA_MANIFEST.json')})
 # Stage only explicitly enumerated approved research files, one path per add.
 candidates=[R/'.gitignore']+[p for folder in (D,S/'scripts/value_learning_v1') for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.tmp')]
 for p in candidates:subprocess.run(['git','-C',str(R),'add','--',str(p.relative_to(R))],check=True)
 diff=subprocess.run(['git','-C',str(R),'diff','--cached','--quiet'])
 if diff.returncode:subprocess.run(['git','-C',str(R),'commit','-m',f'Learning research v1 checkpoint: {phase}'],check=True)
 if push:subprocess.run(['git','-C',str(R),'push','-u','origin','codex/value-learning-research-v1'],check=True)
 local=git('rev-parse','HEAD');remote=git('ls-remote','origin','refs/heads/codex/value-learning-research-v1').split()[0] if push else None
 save(RAW/f'REMOTE_VERIFICATION_{phase}.json',{'local_head':local,'remote_head':remote,'equal':local==remote,'phase':phase,'timestamp_utc':datetime.now(timezone.utc).isoformat()})
 print(json.dumps({'checkpoint':phase,'local_head':local,'remote_head':remote,'equal':local==remote,'raw_rollouts':len(results)}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('--no-push',action='store_true');a=p.parse_args();checkpoint(a.phase,not a.no_push)
