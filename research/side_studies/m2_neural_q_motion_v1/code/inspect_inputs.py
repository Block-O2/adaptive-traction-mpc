import os,sys,json,hashlib,subprocess,time
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
import numpy as np
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OUT=ROOT/'m2_neural_q_motion_v1'
OUT.mkdir(exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git_state(p):
 def run(*a):
  r=subprocess.run(['git','-C',str(p),*a],capture_output=True,text=True)
  return {'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
 return {'branch':run('branch','--show-current'),'head':run('rev-parse','HEAD'),'status':run('status','--porcelain=v1','--untracked-files=all'),'staged':run('diff','--cached','--binary'),'diff':run('diff','--binary'),'index_sha256':sha(p/'.git/index') if (p/'.git/index').is_file() else None}
if not (OUT/'PRESERVATION_BEFORE.json').exists():
 files=[]
 for pkg in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1','b_native_learning_matrix_v1']:
  for p in (ROOT/pkg).rglob('*'):
   if p.is_file() and (p.suffix in ('.py','.md','.npz') or p.name in ('TRAINING.json','DATASET_AUDIT.json','PACKAGE_VERIFICATION.json','PAIRED_RESULTS.json','PAIRED_HOST_RESULTS.json','EXECUTION_LINEAGE.json','Q_RANKING_ATTRIBUTION.json')):
    files.append({'path':str(p),'size':p.stat().st_size,'sha256':sha(p)})
 before={'start_unix':time.time(),'deadline_unix':time.time()+9000,'git':{str(p):git_state(p) for p in [Path('/home/hank/coding/adaptive-traction-mpc-learning'),Path('/home/hank/coding/adaptive-traction-mpc-human-closeout-git')]},'files':files}
 (OUT/'PRESERVATION_BEFORE.json').write_text(json.dumps(before,indent=2))
print('PRESERVATION',len(json.loads((OUT/'PRESERVATION_BEFORE.json').read_text())['files']))
for name in ['m2_host_generalization_attribution_v1/weights/frozen_Q_v1/DATASET.npz','m2_host_generalization_attribution_v1/weights/frozen_Q_v1/weights.npz','m2_host_generalization_attribution_v1/source/results/001_deviation_P1_seed1_B/trace.npz']:
 p=ROOT/name
 with np.load(p,allow_pickle=False) as z:
  print('\nNPZ',name,[(k,z[k].shape,str(z[k].dtype)) for k in z.files])
  if 'DATASET' in name:
   for k in z.files:
    a=z[k]
    if a.dtype.kind in 'US' or a.size<20:print(k,str(a)[:6000])
 print('SHA',sha(p))
for rel in ['b_native_learning_matrix_v1/DATASET_AUDIT.json','b_native_learning_matrix_v1/weights/v1/TRAINING.json','m2_host_generalization_attribution_v1/EXECUTION_LINEAGE.json']:
 p=ROOT/rel
 if p.exists():
  j=json.loads(p.read_text());print('JSON',rel,'KEYS',list(j));print(json.dumps(j)[:4000])
print('WEIGHTS',list((ROOT/'b_native_learning_matrix_v1/weights').glob('*')))
