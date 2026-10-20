from pathlib import Path
import json,time,hashlib,copy
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(n):return hashlib.sha256((P/n).read_bytes()).hexdigest()
assert not (P/'REPAIR_FROZEN_SELECTION.json').exists()
assert read('repair_OWNER.json')['joined'] and read('repair_OWNER.json')['returncode']==0
assert read('audit/INTERVENTION_EXECUTION_AUDIT.json')['status']=='PASS'
rs=read('EXPERIMENT_RESULTS.json')['rows'];eligible=[r for r in rs if r.get('eligible_primary')]
eligible.sort(key=lambda r:(sum(x['duration_factor']-1 for x in r['candidate']['early']),r['id']))
primary=eligible[0] if eligible else None
selection=dict(frozen_unix=time.time(),status='PRIMARY_FROZEN' if primary else 'NO_QUALIFIED_PRIMARY',primary=None if primary is None else primary['candidate']['id'],primary_development_run=None if primary is None else primary['id'],candidate=None if primary is None else primary['candidate'],original_selection_rule_sha256=sha('REPAIR_SELECTION_RULE.json'),execution_manifest_sha256=sha('EXECUTION_CODE_MANIFEST.json'),development_results_sha256=sha('EXPERIMENT_RESULTS.json'),development_eligible=[r['id'] for r in eligible],no_validation_observed_before_freeze=True,no_validation_reselection=True,baseline_promoted=False)
put('REPAIR_FROZEN_SELECTION.json',selection)
if primary:
 base=copy.deepcopy(read('repair_PLAN.json'));base['condition']['name']='repeat';base['condition']['role']='frozen repair deterministic repetition on W1, no new state claim';base['frozen_unix']=time.time();base['arms']=base['arms'][:3]+[copy.deepcopy(primary['candidate'])];rep=copy.deepcopy(primary['candidate']);rep['id']+='_repeat';rep['repeat_of']=primary['candidate']['id'];base['arms'].append(rep);base['selection_sha256']=sha('REPAIR_FROZEN_SELECTION.json');put('repeat_PLAN.json',base)
 holdout=read('HOLDOUT_REGISTRATION.json');w=copy.deepcopy(base);w['condition']=copy.deepcopy(holdout['condition']);w['condition']['role']='unused legal prefix validation of frozen early RETURN repair; old source-plan D qualification text is historical metadata, superseded by current approved protocol';w['frozen_unix']=time.time();w['reproduce_W1']=False;w['arms']=w['arms'][:-1];w['holdout_registration_sha256']=sha('HOLDOUT_REGISTRATION.json');put('W2_PLAN.json',w)
 put('VALIDATION_CODE_AND_PARAMETER_FREEZE.json',dict(frozen_unix=time.time(),execution_manifest_sha256=sha('EXECUTION_CODE_MANIFEST.json'),primary=selection['primary'],frozen_files={n:sha(n) for n in ['REPAIR_FROZEN_SELECTION.json','repeat_PLAN.json','W2_PLAN.json','HOLDOUT_REGISTRATION.json','BOUNDED_REPAIR_PROTOCOL.json','audit/BOUNDED_REPAIR_PRECHECK.json']},remaining_physical_START=24-sum(json.loads(x)['event']=='START' for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()),no_future_parameter_changes=True))
print(json.dumps(selection),flush=True)
