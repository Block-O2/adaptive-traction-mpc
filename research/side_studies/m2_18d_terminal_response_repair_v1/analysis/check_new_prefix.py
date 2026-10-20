from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');target={'OUTBOUND':[[-.075,-.045,-.05]]};conflicts=[];checked=[];registrations=[]
def matches(x):
 if isinstance(x,dict):
  if x.get('prefix')==target:return True
  return any(matches(v) for v in x.values())
 if isinstance(x,list):return any(matches(v) for v in x)
 return False
for pkg in S.iterdir():
 if not pkg.is_dir() or pkg.name==P.name:continue
 evidence=list((pkg/'audit').glob('*FORK_CONTEXT.json'))+list(pkg.glob('*RESULTS.json'))+list(pkg.glob('*DONE.json'))
 for f in evidence:
  try:x=json.loads(f.read_text())
  except (ValueError,OSError):continue
  checked.append(dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
  if matches(x):conflicts.append(str(f))
 plan=pkg/'RUN_PLAN.json'
 if plan.exists():
  try:
   if matches(json.loads(plan.read_text())):registrations.append(str(plan))
  except ValueError:pass
out=dict(status='PASS' if not conflicts else 'FAIL',prefix=target,prior_execution_conflicts=conflicts,prior_registration_without_execution=registrations,checked_execution_records=checked,scope='All existing Side Studies top-level result/done records and audit full-fork contexts; registration alone is not physical execution; same Human remaining-suffix state validation only')
(P/'audit/NEW_PREFIX_PROVENANCE.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],'checked',len(checked),'conflicts',conflicts,'registrations',registrations)
assert not conflicts
