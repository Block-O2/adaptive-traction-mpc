"""Exact scientific P00 vs exposed historical W1 raw-data regression. No physics."""
from pathlib import Path
import os,sys,json,time
P=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(P/'control'),str(P/'code')]
import base_campaign as bc
old=P.parent/'ihear_overnight_control_learning_transition_v1'
rows=[]
for arm in ['B','H150']:
    record=bc.compare_raw(P/'source/results'/('P00_'+arm),old/'source/results'/('D01R_'+arm))
    rows.append(record)
result=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',rows=rows,unix=time.time(),new_physical_starts=0,scope='P00 nominal patient W1 prefix full trace/native/receipt exact historical reproduction')
(P/'audit/REFERENCE_REPRODUCTION.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],flush=True)
assert result['status']=='PASS'
