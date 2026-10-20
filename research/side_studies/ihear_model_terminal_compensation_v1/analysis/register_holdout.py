from pathlib import Path
import json,time,hashlib,copy,shutil
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
frozen=read(P/'NEW_FROZEN_SELECTION.json');assert frozen['primary']=='H150'
old=read(P.parent/'ihear_autonomous_multitrack_v1/HOLDOUT_REGISTRATION.json');cond=copy.deepcopy(old['condition']);matches=[];files=[]
def matches_value(x):
 if isinstance(x,dict):
  if x.get('seed')==cond['seed'] or x.get('prefix')==cond['prefix']:return True
  return any(matches_value(v) for v in x.values())
 if isinstance(x,list):return any(matches_value(v) for v in x)
 return False
for f in P.parent.rglob('ATTEMPTS.jsonl'):
 files.append(str(f))
 for line in f.read_text().splitlines():
  row=json.loads(line)
  if row.get('event')=='START' and matches_value(row):matches.append(dict(path=str(f),row=row))
assert not matches,'W2_ALREADY_CONSUMED'
cond.update(name='W2',role='Previously unused legal prefix; frozen H150 validation only, never tuning')
arms=copy.deepcopy([a for a in read(P/'Ctrl_PLAN.json')['arms'] if a['id'] in ['B','T','ER','H150']])
put('W2_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,reproduce_W1=False,arms=arms))
put('HOLDOUT_REGISTRATION.json',dict(status='REGISTERED_UNUSED_W2',registered_unix=time.time(),condition=cond,START_logs_checked=files,seed_or_exact_prefix_matches=matches,selection_sha=hashlib.sha256((P/'NEW_FROZEN_SELECTION.json').read_bytes()).hexdigest(),start_only_after='H150 deterministic physical/native/receipt repeat PASS; control extension outcomes cannot retune H150',same_Human=True,original_gate_frozen=True))
for n in ['W2_PLAN.json','HOLDOUT_REGISTRATION.json']:shutil.copy2(P/n,R/n)
print(json.dumps(dict(status='PASS_UNUSED',logs=len(files),condition=cond)))
