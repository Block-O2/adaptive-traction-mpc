"""Freeze authorized resource-only revision and preserve pre-resume evidence."""
from pathlib import Path
import json,hashlib,shutil,time,sys
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';S=Path('/home/hank/ihear-lab/representation_execution_v3/runtime/source/stages/stage5_personalized_motion_learning');D=S/'docs/dagger_anchored_sac_v2';sys.dont_write_bytecode=True
from resource_policy_v2 import POLICY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(L/'PREREGISTRATION.json')==old['config'];assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')]
archive=L/'before_resource_continuation_21283';archive.mkdir(exist_ok=False)
for p in L.iterdir():
 if p.is_file():shutil.copy2(p,archive/p.name)
source=P/'source_history/resource_continuation_21283';source.mkdir(parents=True,exist_ok=False)
for p in (S/'scripts/dagger_anchored_sac_v2').glob('*.py'):shutil.copy2(p,source/p.name)
revision=dict(unix=time.time(),user_authorized='Continue same v2 from paused state21283 to total50000; only resource stopping criterion may change',old_resource_source_sha256=old['sources'][str(P/'common.py')],old_policy={'new_swap_over_128_MiB':'STOP alone','WSL_available_GiB':1.5,'commit_headroom_GiB':2},new_policy=POLICY,scientific_config_sha256=old['config'],train_source_unchanged=True,evaluate_source_unchanged=True,budget_initial=21283,budget_target=50000,pending_10k_confirmation_before_updates=True,old_lock=old,original_started_and_wall_deadline_unchanged=True)
for f in (L,D):
 (f/'RESOURCE_POLICY_V2.json').write_text(json.dumps(POLICY,indent=2)+'\n');(f/'RESOURCE_POLICY_REVISION.json').write_text(json.dumps(revision,indent=2)+'\n')
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='RESOURCE_POLICY_V2.json',old_lock_archived=str(archive/'LOCK.json'))
for f in (L,D):(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print(json.dumps(dict(status='RESOURCE_ONLY_REVISION_FROZEN',config_sha256=old['config'],budget=21283,deadline=json.loads((L/'STATE.json').read_text())['hard_cutoff_unix'])))
