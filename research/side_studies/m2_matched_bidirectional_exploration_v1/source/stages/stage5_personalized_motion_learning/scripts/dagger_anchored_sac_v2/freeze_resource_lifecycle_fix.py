from pathlib import Path
import json,time,hashlib,shutil,sys
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2');S=D.parents[1]/'scripts/dagger_anchored_sac_v2';sys.dont_write_bytecode=True
from resource_policy_v2 import POLICY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')];assert sha(L/'PREREGISTRATION.json')==old['config'];original=json.loads((L/'RESOURCE_POLICY_V2.json').read_text());assert all(POLICY[k]==original[k] for k in ('immediate','persistent','trends','throughput'))
flag=json.loads((L/'RESOURCE_PAUSE_FLAG_V2.json').read_text());diag=dict(unix=time.time(),reason='Restored-idle to active-physics allocation incorrectly treated as within-stage abnormal PSS growth',observed=flag,classification='OPERATIONAL_LIFECYCLE_FALSE_POSITIVE',thresholds_unchanged=True,resource_policy_new=POLICY,scientific_changes=[],saved_and_spent_collection_steps=22500,actor_and_critic_state_not_rolled_back=True,old_lock=old)
for f in (L,D):
 shutil.copy2(f/'RESOURCE_POLICY_V2.json',f/'RESOURCE_POLICY_V2_before_lifecycle_fix.json');shutil.copy2(f/'CONTINUATION_EXCEPTION.json',f/'lifecycle_intercept_CONTINUATION_EXCEPTION.json');(f/'RESOURCE_PAUSE_FLAG_V2.json').replace(f/'RESOURCE_PAUSE_FLAG_V2_lifecycle_false_positive.json');(f/'RESOURCE_LIFECYCLE_DIAGNOSIS.json').write_text(json.dumps(diag,indent=2)+'\n');(f/'RESOURCE_POLICY_V2.json').write_text(json.dumps(POLICY,indent=2)+'\n')
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='RESOURCE_POLICY_V2_1_LIFECYCLE_FIX')
for f in (L,D):(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print('LIFECYCLE_FIX_FROZEN_THRESHOLDS_SCIENCE_COUNTERS_UNCHANGED')
