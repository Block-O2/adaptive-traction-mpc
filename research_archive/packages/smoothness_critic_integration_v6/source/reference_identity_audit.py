"""Exact trace/native/receipt equality of diagnostic-only runs vs historical originals."""
from pathlib import Path
import os,sys,json,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'runtime/control'),str(P/'runtime/code'),str(P/'source')]
import base_campaign as bc
from acl2_shared import put
O=P.parent/'representation_execution_v3';mapping={'DEV_B':'P1_B','DEV_H150':'P1_H150','DEV_OLD_STRONG':'P1_OLD_STRONG','DEV_BEST':'P1_BEST','DEV_C19':'P2_C19','DEV_NEG':'P2_NEG'};rows=[];start=time.time()
for a,b in mapping.items():
 out=P/'audit/historical_identity'/(a+'.json')
 if out.exists():rows.append(json.loads(out.read_text()));continue
 pa=P/'runtime/source/results'/a;pb=O/'runtime/source/results'/b
 if not (pa/'runtime_artifacts.json.gz').exists():continue
 r=bc.compare_raw(pa,pb);r.update(id=a,historical_id=b);put('audit/historical_identity/'+a+'.json',r);rows.append(r);print(a,r['status'],flush=True)
# The L1D1 factorial is the exact original new-compiler control, not just similar cost.
for name in ['BEST','C19']:
 a=f'FACT_{name}_L1_D1';pa=P/'runtime/source/results'/a;pb=P/'runtime/source/results'/('DEV_'+name);out=P/'audit/factor_control_identity'/(a+'.json')
 if out.exists():r=json.loads(out.read_text());rows.append(r);continue
 if not (pa/'runtime_artifacts.json.gz').exists():continue
 r=bc.compare_raw(pa,pb);r.update(id=a,historical_id='DEV_'+name);put('audit/factor_control_identity/'+a+'.json',r);rows.append(r);print(a,r['status'],flush=True)
put('audit/DIAGNOSTIC_AND_FACTOR_CONTROL_IDENTITY.json',dict(status='PASS' if rows and all(r['status']=='PASS' for r in rows) else 'REVIEW_REQUIRED',completed_comparisons=len(rows),expected_final_comparisons=8,rows=rows,wall_s=time.time()-start,scope='All NPZ trace fields plus full native q/qvel/torque/contact/command identity and scientific receipt/source/reference fields. Host timing and extra diagnostic metadata excluded.'))
