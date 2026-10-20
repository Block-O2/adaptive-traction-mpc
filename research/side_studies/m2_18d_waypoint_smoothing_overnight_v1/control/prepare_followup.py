"""Freeze a single finite follow-up batch after first-batch evidence review."""
from pathlib import Path
import json,time,hashlib,shutil,copy
P=Path(__file__).resolve().parents[1]
assert (P/'development1_PHYSICAL_DONE.json').exists()
assert not (P/'FOLLOWUP_PLAN.json').exists(),'Never overwrite a registered followup'
review=json.loads((P/'SELECTION_REVIEW.json').read_text());rows=json.loads((P/'ALL_ANALYZED_RESULTS.json').read_text())['rows']
# B's individual half/repeat contrasts already exist in the previous study;
# this study reproduced its complete baseline/smooth/opposite outcomes exactly.
# Prioritize new combination information, not another redundant B repetition.
selected=[c for c in review['registered_followup_candidates'] if c['base']=='E' or c['id']=='B_OR_smooth']
for r in rows:
 if r['status']=='COMPLETE' and r['candidate']['id'].startswith('E_') and r['candidate']['id'].endswith('_smooth') and not r['motion_pass'] and r['full_J_F_delta']<0:
  if all(x['candidate']['TV_v']<x['baseline']['TV_v'] for x in r['local']):
   c=copy.deepcopy(r['candidate']);c['id']=c['id'].replace('_smooth','_repair_half')
   for ch in c['changes']:ch['spec']['deltas_deg']=[[v*.5 for v in pair] for pair in ch['spec']['deltas_deg']]
   selected.append(c)
assert len(selected)<=7
out=dict(frozen_unix=time.time(),decision='one bounded follow-up; exact E repeats and half-scale, only individually supported O/R combined; no additional random candidates',skip_B_redundant_repeats='previous archived half/repeat plus this exact reproduction; not new-state validation',development_repair_rule='at most one half-scale for E arm with force lower, actual local TV lower but original motion FAIL; no gate changed',coarse=[dict(id='B0',base='B',changes=[]),dict(id='E0',base='E',changes=[])]+selected,selection_review_sha256=hashlib.sha256((P/'SELECTION_REVIEW.json').read_bytes()).hexdigest(),validation_not_started=True)
assert selected,'No informative followups: end campaign'
(P/'FOLLOWUP_PLAN.json').write_text(json.dumps(out,indent=2)+'\n')
for name in ['EXECUTABLE_PLAN.json','EXECUTION_CODE_MANIFEST.json']:
 shutil.copy2(P/name,P/'audit'/('development1_'+name))
(P/'EXECUTABLE_PLAN.json').write_text(json.dumps(out,indent=2)+'\n')
manifest={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for d in ['source','code','deps','weights','control','tests'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
(P/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,executable_plan_sha256=hashlib.sha256((P/'EXECUTABLE_PLAN.json').read_bytes()).hexdigest(),run_plan_sha256=hashlib.sha256((P/'RUN_PLAN.json').read_bytes()).hexdigest()),indent=2)+'\n')
print('REGISTERED_FOLLOWUP', [c['id'] for c in out['coarse']])
