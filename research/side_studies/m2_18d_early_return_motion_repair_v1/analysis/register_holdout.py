from pathlib import Path
import json,time,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_w1_d_qualification_v1'
condition=json.loads((A/'W2_PLAN.json').read_text())['condition'];matches=[];files=[]
for f in P.parent.glob('*/ATTEMPTS.jsonl'):
 if f.is_relative_to(P):continue
 files.append(str(f))
 for line in f.read_text().splitlines():
  r=json.loads(line)
  if r.get('event')=='START' and (r.get('seed')==condition['seed'] or r.get('condition',{}).get('seed')==condition['seed']):matches.append(dict(file=str(f),record=r))
assert not matches,'HOLDOUT_PREVIOUSLY_EXECUTED'
assert max(abs(x) for ph in condition['prefix'].values() for vals in ph for x in vals)<=.2
obj=dict(status='REGISTERED_UNUSED_CONDITIONAL_HOLDOUT',registered_unix=time.time(),condition=condition,source_plan=str(A/'W2_PLAN.json'),source_plan_sha256=hashlib.sha256((A/'W2_PLAN.json').read_bytes()).hexdigest(),prior_START_logs_checked=files,prior_seed_START_matches=matches,no_physics_started=True,scope='same Human, new actual cold commissioning and legal OUTBOUND prefix; complete live fork; prefix specifies causal graph residual, never native Human state',start_condition='only after development primary frozen and deterministic repeat verified; no validation-based primary reselection')
dest=P/'HOLDOUT_REGISTRATION.json';assert not dest.exists();dest.write_text(json.dumps(obj,indent=2)+'\n');print(json.dumps({k:obj[k] for k in ['status','condition']}),flush=True)
