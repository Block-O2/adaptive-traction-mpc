"""Compare exact recorded physical outputs across the two complete batches."""
from pathlib import Path
import os,sys,json,time
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.path[:0]=[str(P/'control'),str(P/'code')]
import interface_base as ib
assert ib.P==P
pairs=[('development1_B0','development2_B0'),('development1_E0','development2_E0'),('development1_E_O_smooth','development2_E_O_repeat'),('development1_E_R_smooth','development2_E_R_repeat')]
rows=[]
for a,b in pairs:
 if not (P/'reports'/(b+'_MEASURED.json')).exists():continue
 gate=ib.compare_raw(a,b,True)
 sa=json.loads((P/'reports'/(a+'_FORK_RESTORED.json')).read_text());sb=json.loads((P/'reports'/(b+'_FORK_RESTORED.json')).read_text());gate['fork_restore_hash_equal_across_batches']=sa['after']==sb['after'];gate['same_parent_process']=False;gate['scope']='new cold parent in same seeded development condition, matched B/18D reproduced; not new-prefix validation';rows.append(gate)
(P/'REPEAT_GATES.json').write_text(json.dumps(dict(rows=rows,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',unix=time.time(),new_validation_states=0),indent=2)+'\n')
print([(r['a'],r['b'],r['status'],r['fork_restore_hash_equal_across_batches']) for r in rows])
