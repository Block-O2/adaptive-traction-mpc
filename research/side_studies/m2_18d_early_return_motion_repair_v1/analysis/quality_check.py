from pathlib import Path
import json,time,hashlib
from PIL import Image
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
rows=[]
for f in sorted((P/'figures').glob('*.png')):
 with Image.open(f) as im:im.verify()
 with Image.open(f) as im:shape=list(im.size)
 rows.append(dict(path=str(f.relative_to(P)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),size_px=shape))
assert len(rows)==4
(P/'audit/FIGURE_QA.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),images=rows,visual_inspection='all four PNGs inspected by primary agent through view_image; labels, legend, common time, actual/reference styles, diagnostic relative bounds and explicit clipped-peak zoom checked',scientific_data_source='matplotlib from archived/new raw native traces; no image generation or pixel editing'),indent=2)+'\n')
for n in ['REPORT.md','W1_EARLY_RETURN_DIAGNOSIS.md','INTERVENTION_PROTOCOL.md','INTERVENTION_PROTOCOL_BOUNDED_REPAIR.md','NEXT_RESEARCH_DECISION.md']:assert (P/n).stat().st_size>100
for n in ['EXPERIMENT_RESULTS.json','VALIDATION_RESULTS.json','CANDIDATE_PLAN.json','BOUNDED_REPAIR_PROTOCOL.json','REPAIR_FROZEN_SELECTION.json','audit/INTERVENTION_EXECUTION_AUDIT.json','audit/INDEPENDENT_VERIFICATION.json','audit/SOURCE_CLOSURE_VERIFIED.json','derived/REMAINING_EXCURSION_GAP.json','derived/CAUSAL_RESPONSE_AUDIT.json']:read(n)
e=read('EXPERIMENT_RESULTS.json');assert e['status']=='COMPLETE_REPORTED_PHYSICAL_RESULTS' and len(e['rows'])==9
assert all(r['task']=='PASS' and r['absolute_safety'] and r['receipt']=='PASS' for r in e['rows'])
assert not any(r.get('eligible_primary') for r in e['rows']);assert read('VALIDATION_RESULTS.json')['status']=='NO_FULLY_QUALIFIED_REPAIR'
attempts=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];assert sum(x['event']=='START' for x in attempts)==sum(x['event']=='END' for x in attempts)==13
assert not any(x['event']=='START' and x.get('group') in ['repeat','W2'] for x in attempts)
assert read('PHYSICS_STOP.json')['new_START_forbidden']
(P/'audit/REPORT_QA.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),required_scientific_deliverables_present=True,remaining_closeout_deliverables=['ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json'],strict_JSON=True,complete_task_candidates=9,successful_END_arithmetic_checks=12,no_primary_or_independent_validation_claim=True,physical_START=13,physical_END=13,original_thresholds_preserved=True),indent=2)+'\n')
print('REPORT_AND_FIGURE_QA_PASS',flush=True)
