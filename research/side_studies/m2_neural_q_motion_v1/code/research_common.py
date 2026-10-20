import os,sys,json,hashlib,gzip,time
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
import numpy as np
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OUT=ROOT/'m2_neural_q_motion_v1'
MATRIX=ROOT/'b_native_learning_matrix_v1'
FROZEN=ROOT/'m2_host_generalization_attribution_v1/weights/frozen_Q_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(name,j):
 def clean(x):
  if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
  if isinstance(x,(list,tuple)):return [clean(v) for v in x]
  if isinstance(x,np.ndarray):return clean(x.tolist())
  if isinstance(x,(np.integer,np.bool_)):return x.item()
  if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
  return x
 (OUT/name).write_text(json.dumps(clean(j),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def budget():
 b=load(OUT/'PRESERVATION_BEFORE.json')
 if time.time()>b['deadline_unix']-300:raise RuntimeError('EXPORT_RESERVE_DEADLINE')
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
def stats(v):
 v=np.asarray(v);a=np.abs(v)
 return {'n':len(a),'max_abs':np.max(a,axis=0),'p95_abs':np.quantile(a,.95,axis=0),'p99_abs':np.quantile(a,.99,axis=0),'rms':np.sqrt(np.mean(v*v,axis=0)),'mean_abs':np.mean(a,axis=0)} if len(a) else {'n':0,'status':'NOT_EVALUABLE'}
def unique_trace(p):
 with np.load(p,allow_pickle=False) as z:a={k:z[k].copy() for k in z.files}
 task=np.flatnonzero(a['stage']=='TASK');t=a['time_s'][task]
 # Keep the last recorded boundary value per physical timestamp. Original samples remain intact.
 _,rev=np.unique(t[::-1],return_index=True);ix=task[np.sort(len(t)-1-rev)]
 return a,ix,{'original_TASK_samples':len(task),'unique_TASK_samples':len(ix),'duplicate_timestamp_count':len(task)-len(ix),'min_dt_s':np.min(np.diff(a['time_s'][ix])),'max_dt_s':np.max(np.diff(a['time_s'][ix]))}
