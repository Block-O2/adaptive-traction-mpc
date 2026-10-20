from pathlib import Path
import json,time,hashlib,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
R=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
owner=read('dev_OWNER.json');assert owner['joined'] and owner['returncode']!=0
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];ss=[x for x in events if x['event']=='START'];ee=[x for x in events if x['event']=='END'];assert len(ss)==len(ee)==2
assert next(x for x in ee if x['id']=='W1_B')['returncode']==0
assert 'dev_B' in read('reports/dev_parent_ERROR.json')['error']
for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items():assert hashlib.sha256((P/rel).read_bytes()).hexdigest()==h
assert not (P/'W1dev_PLAN.json').exists()
plan=read('dev_PLAN.json');plan.update(frozen_unix=time.time(),metadata_repair='group name now equals condition display name; seed, prefix and arms unchanged');plan['condition']['name']='W1dev';put('W1dev_PLAN.json',plan)
assert (P/'PHYSICS_STOP.json').exists() and not (P/'audit/dev_INFRASTRUCTURE_STOP.json').exists()
(P/'PHYSICS_STOP.json').rename(P/'audit/dev_INFRASTRUCTURE_STOP.json')
put('audit/INFRASTRUCTURE_RECOVERY.json',dict(status='REGISTERED_BEFORE_NEW_START',unix=time.time(),cause='Inherited fork IDs use condition.name; collector uses STUDY_GROUP. Initial dev group used W1 display name. Complete W1_B kept; cold parent failed during result collection. No candidate intervention was run.',new_group='W1dev',physics_parameters_unchanged=True,execution_manifest_unchanged=True,original_failures_preserved=True,physical_starts_already_consumed=2,no_new_candidate_selection=True))
for n in ['results.py','audit_execution.py']:shutil.copy2(R/'analysis'/n,P/'analysis'/n)
shutil.copy2(P.parent/'m2_18d_w1_d_qualification_v1/analysis/independent.py',P/'analysis/independent.py')
shutil.copy2(R/'analysis/recover_infrastructure.py',P/'analysis/recover_infrastructure.py')
print('INFRASTRUCTURE_RECOVERY_REGISTERED',flush=True)
