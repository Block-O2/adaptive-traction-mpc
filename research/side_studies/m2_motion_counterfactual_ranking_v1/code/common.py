import os, sys, json, hashlib, time, subprocess, gzip
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
import numpy as np
ROOT = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OUT = ROOT/'m2_motion_counterfactual_ranking_v1'
OLD = ROOT/'m2_neural_q_motion_v1'
MATRIX = ROOT/'b_native_learning_matrix_v1'
def load(p): return json.loads(Path(p).read_text())
def sha(p):
 h = hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda: f.read(2**20), b''): h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x, (list,tuple)): return [clean(v) for v in x]
 if isinstance(x, np.ndarray): return clean(x.tolist())
 if isinstance(x, (np.integer,np.bool_)): return x.item()
 if isinstance(x, (float,np.floating)): return float(x) if np.isfinite(x) else None
 return x
def save(name, x):
 p = OUT/name; p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def md(name, s): (OUT/name).write_text(s.strip()+'\n')
def git_state(p):
 def run(*a):
  r=subprocess.run(['git','-C',str(p),*a],capture_output=True,text=True)
  return dict(code=r.returncode,stdout=r.stdout,stderr=r.stderr)
 idx=subprocess.run(['git','-C',str(p),'rev-parse','--git-path','index'],capture_output=True,text=True)
 ip=Path(idx.stdout.strip()); ip=ip if ip.is_absolute() else p/ip
 return dict(branch=run('branch','--show-current'),head=run('rev-parse','HEAD'),status=run('status','--porcelain=v1','--untracked-files=all'),staged=run('diff','--cached','--binary'),diff=run('diff','--binary'),index_sha256=sha(ip) if ip.is_file() else None)
def budget():
 p=load(OUT/'EXPERIMENT_PROTOCOL.json')
 if time.time()>p['deadline_unix']-300: raise RuntimeError('EXPORT_RESERVE_DEADLINE')
def stat(v):
 v=np.asarray(v); a=np.abs(v)
 return dict(max_abs=np.max(a,axis=0),p95_abs=np.quantile(a,.95,axis=0),p99_abs=np.quantile(a,.99,axis=0),rms=np.sqrt(np.mean(v*v,axis=0)))
def table(headers, rows):
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
def array_items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';decoder=json.JSONDecoder()
  while True:
   part=f.read(65536)
   if not part:return
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip()
    while not buf:buf+=f.read(65536);buf=buf.lstrip()
    if not buf.startswith('['):raise ValueError('NOT_ARRAY')
    buf=buf[1:];break
   buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:v,end=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('INCOMPLETE_ARRAY')
    buf+=part
    if len(buf)>4*2**20:raise ValueError('OVERSIZE_ITEM')
    continue
   yield v;buf=buf[end:]
