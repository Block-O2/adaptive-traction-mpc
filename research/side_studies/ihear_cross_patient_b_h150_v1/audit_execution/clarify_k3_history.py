"""Resolve inherited 2-knot names to actual frozen K3 context positions."""
from pathlib import Path
import json,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
R=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
p=P/'LEARNING_DATA_SCHEMA.json';old=p.read_bytes();d=json.loads(old)
x=d['STATE']['legacy_normalized55D'];f=x['features'][50]
assert f['name']=='previous_residual_knot_2'
f['inherited_two_knot_contract_name']=f['name'];f['name']='previous_residual_knot_3'
x['K3_history_note']='Frozen TableInterface.context temporarily maps K3 previous[[0,2]] into legacy55D slots49 and50: first and third knots, respectively. richer_previous_residual stores all3 knots separately. Inherited two-knot observation_contract named slot50 knot2; this actual K3 writer supplies knot3.'
new=(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
for root in [P,R]:
    backup=root/'audit/LEARNING_DATA_SCHEMA_BEFORE_K3_NAME_CLARIFICATION.json'
    assert not backup.exists();backup.write_bytes(old)
    (root/'LEARNING_DATA_SCHEMA.json').write_bytes(new)
receipt=dict(status='PASS',old_sha256=hashlib.sha256(old).hexdigest(),new_sha256=hashlib.sha256(new).hexdigest(),
             authority='code/interfaces.py:8-13 and25, actual previous[[0,2]]',raw_execution_modified=False)
for root in [P,R]:(root/'audit/LEARNING_K3_SCHEMA_CLARIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
