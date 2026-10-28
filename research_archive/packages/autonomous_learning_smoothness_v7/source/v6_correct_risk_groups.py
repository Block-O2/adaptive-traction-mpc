from pathlib import Path
import json,time,hashlib
from v6_model import fit_risk,predict_risk
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
rows=json.loads((P/'data/LEGACY_B_CAUSAL_RISK_ROWS.json').read_text());old=json.loads((P/'models/OBSERVED_RISK_FROZEN.json').read_text());model=old['model'];cv=[]
for r in rows:r['independence_group']='TAILOT_RESCUE_SAME_STATE' if r['group'] in ['TAILOT','TAILRESCUE01'] else r['group']
for g in sorted(set(r['independence_group'] for r in rows)):
 train=[r for r in rows if r['independence_group']!=g];fitted=fit_risk(train)
 for r in rows:
  if r['independence_group']!=g:continue
  probability=predict_risk(fitted,{'local_risk_features':r['features']});cv.append(dict(id=r['id'],job_group=r['group'],independence_group=g,already_native_peak_failed=r['labels_evaluation_only']['already_native_peak_failed'],predicted_risk=probability,model_fit_available=fitted.get('available',False),reason=fitted.get('reason'),rejected=None if probability is None else probability>=.5))
x=dict(model=model,frozen_unix=time.time(),revision='V2 independence correction; numerical weights unchanged; prior job-name CV invalidated',prior_freeze_sha256=sha(P/'models/OBSERVED_RISK_FROZEN.json'),source_sha256=sha(P/'source/v6_model.py'),cross_validation=cv,unique_state_families=sorted(set(r['independence_group'] for r in rows)),positive_state_families=sorted(set(r['independence_group'] for r in rows if r['labels_evaluation_only']['already_native_peak_failed'])),positive_fold_has_no_positive_training_support=True,independent_failure_recall_established=False,warning='five positives all descend from the same TAILOT state family; holding that family out leaves no positive training rows; old 5/5 CV is not independent evidence')
put('models/OBSERVED_RISK_V2_FROZEN.json',x);put('audit/RISK_PARENT_ALIAS_CORRECTION.json',x)
p=P/'source/v6_fit_freeze.py';s=p.read_text().replace('models/OBSERVED_RISK_FROZEN.json','models/OBSERVED_RISK_V2_FROZEN.json');p.write_text(s)
# Explicit new legacy metadata revision; do not overwrite old model freezes.
oldmodel=P/'models/LEGACY_B_REVISED_V2_FROZEN.json';b=json.loads(oldmodel.read_text());b.update(frozen_unix=time.time(),risk_independence_audit='audit/RISK_PARENT_ALIAS_CORRECTION.json',risk_positive_independent_state_families=1,prior_model_sha256=sha(oldmodel),metadata_revision='V3 alias-corrected risk evidence; same numeric cost and risk weights');new=P/'models/LEGACY_B_REVISED_V3_FROZEN.json';put(str(new.relative_to(P)),b)
f=P/'experiments/LEGACY_NEW_O.json';c=json.loads(f.read_text());c.update(frozen_bundle='models/LEGACY_B_REVISED_V3_FROZEN.json',frozen_bundle_sha256=sha(new));f.write_text(json.dumps(c,indent=2)+'\n')
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps({'unix':time.time(),'hypothesis':'risk generalization must split actual parent state, not job names','correction':'old RISK_REPAIR entry 5/5 CV invalid because TAILOT and TAILRESCUE01 are the same state family; all five positives share that family','actual_result':'holding it out leaves zero positive training rows, so independent failure recall is NOT_ESTABLISHED','decision':'preserve old freeze, use V2 corrected evidence; fresh frozen LEGACY_NEW_O is independent, not used for training afterwards'},ensure_ascii=False)+'\n')
print('RISK_INDEPENDENCE_CORRECTED','unique families',len(x['unique_state_families']),'positive families',len(x['positive_state_families']),flush=True)
