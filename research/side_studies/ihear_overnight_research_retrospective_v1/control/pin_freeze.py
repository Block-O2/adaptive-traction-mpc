"""Pin complete selection bytes before the first held-out/repeat START; no physics."""
from pathlib import Path
import json,time,hashlib
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def science(c):return {k:v for k,v in c.items() if k not in ['id','stage']}
selection=S/'FROZEN_SELECTION.json';data=json.loads(selection.read_text());p=S/'preservation/FREEZE_PIN.json'
if p.exists():
    pin=json.loads(p.read_text());assert sha(selection)==pin['selection_sha256'],'PINNED_SELECTION_CHANGED';print('FREEZE_PIN_ALREADY_EXISTS');raise SystemExit()
events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
assert not any(r['event']=='START' and r.get('mode') in ['repeat','V1','V2','V3','V4'] for r in events),'TEST_STARTED_BEFORE_PIN'
assert data['parameters_frozen'] and data['heldout_not_used']
pin=dict(pin_unix=time.time(),freeze_unix=data['unix'],selection_sha256=sha(selection),code_manifest_sha256=sha(S/'CODE_MANIFEST.json'),
         run_plan_sha256=sha(S/'RUN_PLAN.json'),candidate_scientific_fields={arm:science(data[arm]['candidate']) for arm in ['best','secondary','diagnostic']},
         excluded_identity_fields=['id','stage'],test_START_count_at_pin=0)
(S/'preservation/FROZEN_SELECTION_PINNED.json').write_bytes(selection.read_bytes())
p.write_text(json.dumps(pin,indent=2,ensure_ascii=False)+'\n');print(json.dumps(pin,ensure_ascii=False))
