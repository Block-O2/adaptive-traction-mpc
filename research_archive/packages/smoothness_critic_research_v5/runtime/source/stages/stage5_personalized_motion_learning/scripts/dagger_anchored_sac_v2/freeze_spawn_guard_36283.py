"""Preserve the before-action harness failure, freeze the missing-main-guard fix."""
from pathlib import Path
import hashlib,json,shutil,time
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';S=Path('/home/hank/ihear-lab/smoothness_critic_research_v5/runtime/source/stages/stage5_personalized_motion_learning');D=S/'docs/dagger_anchored_sac_v2';O=S/'results/dagger_anchored_sac_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(L/'PREREGISTRATION.json')==old['config'];assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')]
failed=O/'legacy_predict_revision/checkpoint/a1_p25000_MATCHED_1';assert failed.exists();dest=O/'operational_failures/spawn_guard_36283_MATCHED_1';dest.parent.mkdir(exist_ok=True);assert not dest.exists();failed.rename(dest)
e=json.loads((L/'EXCEPTION_36283.json').read_text());diagnosis=dict(unix=time.time(),reason='Evaluation wrapper lacked __main__ guard. multiprocessing.spawn reexecuted evaluation before any action; preserved directory and exception. Added entry-point guard only.',failed_directory=str(dest),collection_steps_before_after=36283,critic_updates_before_after=45010,actor_updates_before_after=2510,no_budget_reset=True,no_rescue=True,exception=e,old_lock=old)
for f in (L,D):
 (f/'SPAWN_GUARD_REPAIR_36283.json').write_text(json.dumps(diagnosis,indent=2)+'\n');shutil.copy2(f/'WORKFLOW_36283.log' if f==L else L/'WORKFLOW_36283.log',f/'WORKFLOW_36283_before_spawn_guard.log')
for p in P.glob('*.py'):
 compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='V3_STREAMING_WITH_MAIN_GUARD')
for f in (L,D):(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print('SPAWN_GUARD_FIX_FROZEN; COLLECTION36283 UNCHANGED; FAILED_EVIDENCE_RETAINED')
