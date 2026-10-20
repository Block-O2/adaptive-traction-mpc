from common import *
for rel in ['BRANCH_LABELS.json','DATASET_AUDIT.json','MOTION_BURDEN_AUDIT.json']:
 j=load(OLD/rel); print(rel,type(j).__name__,list(j) if isinstance(j,dict) else len(j))
 if isinstance(j,dict):
  for k,v in j.items():
   print(k, str(v)[:1800])
   if k=='rows': break
p=next((MATRIX/'output').glob('*_SNAPSHOT.json'));j=load(p);print('SNAPSHOT',str(p),json.dumps(j)[:13000])
p=next((MATRIX/'output').glob('*_DATA.json'));j=load(p);print('DATA',str(p),json.dumps(j)[:9000]);print('METRIC',json.dumps(j['metric'])[:13000])
p=next((OLD/'motion_series').glob('*_B.npz'))
with np.load(p) as z: print('DENSE',[(k,z[k].shape) for k in z.files])
p=next((MATRIX/'source/results').glob('*candidate*/trace.npz'))
with np.load(p) as z: print('BRANCH_TRACE',str(p),[(k,z[k].shape) for k in z.files])
