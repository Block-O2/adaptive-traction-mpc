from pathlib import Path
import json,csv
P=Path(__file__).resolve().parents[1];p=P/'FULL_RESULTS.csv'
with p.open() as f:reader=csv.DictReader(f);rows=list(reader);fields=reader.fieldnames
extra=['complete_task','partial_JF_UNRANKED','partial_JM_UNRANKED','abort_reason'];fields+=extra
for r in rows:r['complete_task']=True
for f in sorted((P/'analysis/partials').glob('*.json')):
 d=json.loads(f.read_text());r={k:'' for k in fields};r.update(id=d['id'],qualified=False,complete_task=False,physical_task='FAIL',scientific_receipt=d['original_scorer']['scientific_validity']['status'],host='NOT_EVALUABLE',native_steps=d['actual_new_native_steps'],wall_s=d['wall_s'],partial_JF_UNRANKED=d['partial_JF_unranked'],partial_JM_UNRANKED=d['partial_JM_unranked'],abort_reason=d.get('protected_task_failure',{}).get('abort_reason'));rows.append(r)
with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print('CSV_FULL_AND_PARTIAL_CANDIDATES',len(rows))
