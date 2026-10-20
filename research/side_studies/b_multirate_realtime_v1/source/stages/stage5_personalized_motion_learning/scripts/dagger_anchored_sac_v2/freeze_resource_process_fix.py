from pathlib import Path
import json,time,hashlib,shutil,sys
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_multirate_realtime_v1/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2');S=D.parents[1]/'scripts/dagger_anchored_sac_v2';sys.dont_write_bytecode=True
from resource_policy_v2 import POLICY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')];assert sha(L/'PREREGISTRATION.json')==old['config'];flag=json.loads((L/'RESOURCE_PAUSE_FLAG_V2.json').read_text());diag=dict(unix=time.time(),reason='PSS trend compared separate cold evaluation worker identities; normal evaluation working set rather than persistent within-process runaway',observed=flag,classification='OPERATIONAL_PROCESS_IDENTITY_FALSE_POSITIVE',resource_policy_new=POLICY,scientific_changes=[],saved_and_spent_collection_steps=26283,actor_and_critic_state_not_rolled_back=True,previous_native_2_of_2_preserved_and_reused=True,old_lock=old)
for f in (L,D):
 shutil.copy2(f/'RESOURCE_POLICY_V2.json',f/'RESOURCE_POLICY_V2_1_before_process_fix.json');shutil.copy2(f/'CONTINUATION_EXCEPTION.json',f/'process_intercept_CONTINUATION_EXCEPTION.json');(f/'RESOURCE_PAUSE_FLAG_V2.json').replace(f/'RESOURCE_PAUSE_FLAG_V2_1_process_false_positive.json');(f/'RESOURCE_PROCESS_IDENTITY_DIAGNOSIS.json').write_text(json.dumps(diag,indent=2)+'\n');(f/'RESOURCE_POLICY_V2.json').write_text(json.dumps(POLICY,indent=2)+'\n')
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='RESOURCE_POLICY_V2_2_PROCESS_WORKSET_FIX')
for f in (L,D):(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print('PROCESS_WORKSET_RESOURCE_FIX_FROZEN_NO_SCIENTIFIC_CHANGE')
