"""Finite cache-bypassing original-score replay over already ended attempts."""
import json,time,os,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from v7_scorer_replay_v2 import replay,summary
from acl2_shared import put,records
rows=records();ended={r['id'] for r in rows if r['event']=='END'}
count=0
for ev in rows:
 if ev['event']!='START' or ev['id'] not in ended:continue
 id=ev['id'];out=P/'audit/scorer_replay'/(id+'.json')
 if out.exists():continue
 dp=P/'runtime/output'/(id+'_DATA.json');mp=P/'runtime/reports'/(id+'_MEASURED.json')
 if dp.exists() and json.loads(dp.read_text()).get('metric',{}).get('task_valid') and not mp.exists():continue
 row=replay(id,ev['group']);put('audit/scorer_replay/'+id+'.json',row);count+=1
 print('ORIGINAL_SCORER',id,row['status'],row.get('qualified_replay'),flush=True)
print('BATCH_SUMMARY',count,summary()['status'],flush=True)
