from pathlib import Path
import os,sys,pickle
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
os.environ['FAST_NATIVE_SMALL_KERNELS']='N5';os.environ['FAST_ADMISSION_KEY']='RAW_A1'
import lean_instrumentation;lean_instrumentation.prime()
import fast_task_owner as worker
rows=pickle.loads((S/'inputs/019_N4_V2_C2_science_deviation_TASK_CAUSAL.pkl').read_bytes());row=next(r for r in rows if r['phase']=='HOLD')
actual=worker.task_with_certificates(row['payload'])['value'];expected=pickle.loads(row['expected'])
def compare(a,b,path='',seen=None):
 import numpy as np,enum,struct
 if seen is None:seen=set()
 if (id(a),id(b)) in seen:return
 seen.add((id(a),id(b)))
 if type(a)!=type(b):print('TYPE',path,type(a),type(b));return
 if isinstance(a,np.ndarray):
  if a.shape!=b.shape or a.dtype!=b.dtype or a.tobytes()!=b.tobytes():print('ARRAY',path,a.shape,a.dtype,'max',np.max(np.abs(a-b)),a.tolist(),b.tolist())
 elif isinstance(a,(list,tuple)):
  for i,(v,w) in enumerate(zip(a,b)):compare(v,w,path+'/'+str(i),seen)
 elif isinstance(a,dict):
  if set(a)!=set(b):print('FIELDS',path,set(a)-set(b),set(b)-set(a))
  if list(a)!=list(b):print('ORDER',path,list(a),list(b))
  for k in set(a)&set(b):compare(a[k],b[k],path+'/'+str(k),seen)
 elif isinstance(a,enum.Enum):
  if a!=b:print('ENUM',path,a,b)
 elif hasattr(a,'__dict__'):compare(vars(a),vars(b),path,seen)
 elif isinstance(a,float):
  if struct.pack('d',a)!=struct.pack('d',b):print('FLOAT',path,a,b)
 elif a!=b:print('VALUE',path,str(a)[:80],str(b)[:80])
compare(actual.executed.schedule,expected.executed.schedule)
import admission_certificates as cert
new=cert.prepare(row['payload'],actual);old=cert.prepare(row['payload'],expected)
print('KEYS',list(new['proofs']),list(old['proofs']));print('PROOFS_VALUES_EQUAL',list(new['proofs'].values())==list(old['proofs'].values()))
