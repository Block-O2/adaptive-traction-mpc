from pathlib import Path
import sys,ast,itertools,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
src=P/'runtime/control/base_campaign.py';tree=ast.parse(src.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw');scope=dict(np=np,itertools=itertools,array_items=array_items);exec(compile(ast.Module(body=[fn],type_ignores=[]),str(src),'exec'),scope);rows=[]
for tag in ['B','COMPOSE']:
 a=P/'runtime/source/results'/('COORD_R1_'+tag);b=P/'runtime/source/results'/('DEV_O1_'+tag);r=scope['compare_raw'](a,b);r['pair']='coordinated return '+tag+' vs whole-policy '+tag;rows.append(r);print('COORDINATED_IDENTITY',tag,r['status'],flush=True)
(P/'audit/COORDINATED_UPSTREAM_FULL_RAW_IDENTITY.json').write_text(json.dumps({'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL','rows':rows,'purpose':'show corrected return parent restores the exact established global COMPOSE and exact original B, without changing contract or reference quality','new_physical_attempts':0},indent=2)+'\n')
