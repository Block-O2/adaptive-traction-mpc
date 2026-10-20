from pathlib import Path
import sys,json,numpy as np
from evidence import array_items
p=Path(__file__).resolve().parents[1]
ident='development_repair2_B0_original'
f=p/'key_traces'/ident
with np.load(f/'trace.npz') as z:
 print('TRACE',[(k,z[k].shape) for k in z.files])
with np.load(f/'native_reference.npz') as z:
 print('NATIVE_REFERENCE',[(k,z[k].shape) for k in z.files])
 print('NATIVE_REFERENCE_DATA',z['data'][:3])
s=json.loads((f/'summary.json').read_text());print('LEARNING_PLAN',str(s['learning_records'][0]['selected_plan'])[:1000])
for key in ['command_receipts','native_states_evaluation_only','rolling_suffix_splices','rolling_splice_events','requests']:
 g=array_items(f/'runtime_artifacts.json.gz',key)
 row=next(g,None);print('ARRAY',key, None if row is None else list(row));print('FIRST',str(row)[:1000])
