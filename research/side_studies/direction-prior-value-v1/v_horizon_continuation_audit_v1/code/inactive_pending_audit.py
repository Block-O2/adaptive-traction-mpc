from audit_common import *
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,importlib.util
spec=importlib.util.spec_from_file_location('frozen_inactive_networks',OLD/'code/inference.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def inspect(pred,net,source):
 terminal=pred['terminal'];x=np.asarray(terminal['feature'],np.float32)
 if terminal['phase']!='RETURN' or terminal['interior_opportunities']>=3:return None
 count=terminal['count'];mask=np.zeros((2,5,3),bool)
 for i,p in enumerate(('OUTBOUND','RETURN')):mask[i,count[p]:]=True;x[58:88].reshape(2,5,3)[i,:count[p]]=0.
 idx=58+np.flatnonzero(mask.ravel());original=net.value(x);values=[]
 for fill in (0.,-.75,.75):
  y=x.copy();y[idx]=fill;values.append(dict(unexecutable_rows_fill=fill,DeltaV=net.value(y)))
 return dict(source=source,phase='RETURN',progress=float(x[51]),counts=count,inactive_features=len(idx),original_DeltaV=original,modified_values=values,DeltaV_span_Ns=max([original]+[r['DeltaV'] for r in values])-min([original]+[r['DeltaV'] for r in values]),structural_truth_invariance='at predicted RETURN endpoint there are no remaining authorized K3 requests; only native B completion/static wait; these table rows cannot be applied',scope='offline input sensitivity; not an alternative validated model; no masking/training/label change')
def main():
 rows=[]
 for case in read(STUDY/'AUDIT_CONTRACT.json')['cases']:
  path=STUDY/'output'/(case['state']+'_POOL.json')
  if not path.exists():continue
  net=mod.Networks(case['weights'])
  for row in read(path)['rows']:
   found=inspect(row['KNOWN']['prediction'],net,row['item']['identity'])
   if found:rows.append(found)
 net=mod.Networks(OLD/'weights_v2_seed2026100602/networks.npz')
 for path in (OLD/'output').glob('*_DATA.json'):
  data=read(path)
  for i,row in enumerate(data.get('value_rows',[])):
   if 'model_prediction' not in row:continue
   found=inspect(row['model_prediction'],net,str(path)+':'+str(i))
   if found:rows.append(found)
 save(STUDY/'INACTIVE_PENDING_SENSITIVITY.json',dict(rows=rows,source_reason='feature masks executed past, not authority-unreachable future rows; current frozen contract explicitly promises past-row masking only',automatic_implementation_bug_claim=False,interpretation='superfluous conditioning plus learned non-invariance; representation/data adequacy limitation, not proof of a stale applied row or wrong cost label',no_fix_no_refit=True));print(json.dumps(dict(RETURN_endpoint_samples=len(rows),max_DeltaV_span_Ns=max([r['DeltaV_span_Ns'] for r in rows] or [0.]))))
if __name__=='__main__':main()
