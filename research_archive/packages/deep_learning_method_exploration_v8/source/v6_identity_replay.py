from pathlib import Path
import os,sys,json,ast,itertools,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5';sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
src=P/'runtime/control/base_campaign.py';tree=ast.parse(src.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw');scope=dict(np=np,itertools=itertools,array_items=array_items);exec(compile(ast.Module(body=[fn],type_ignores=[]),str(src),'exec'),scope)
rows=[]
for tag in ['B','COMPOSE']:
 new=P/'runtime/source/results'/('TRAIN_O2_'+tag);old=V/'runtime/source/results'/('VAL03_'+tag)
 if not (new/'summary.json').exists():continue
 out=scope['compare_raw'](new,old);out['pair']='TRAIN_O2_'+tag+' vs VAL03_'+tag;rows.append(out);print('EXACT_REPRODUCTION',tag,out['status'],flush=True)
(P/'audit/V5_MATCHED_RAW_REPRODUCTION.json').write_text(json.dumps({'status':'PASS' if len(rows)==2 and all(r['status']=='PASS' for r in rows) else 'REVIEW_REQUIRED','rows':rows,'new_physical_attempts':0,'same_actual_legal_prefix':'VAL03 reused as development intentionally, not an unseen test','scope':'every original trace field, native qpos/qvel/applied torque/contact, scientific receipt/reference/source fields'},indent=2)+'\n')
