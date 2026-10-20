"""Before final replays: freeze sources and full stopped state; no learning/physics."""
from pathlib import Path
import json,hashlib,shutil,sys,time
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1/source/stages/stage5_personalized_motion_learning');D=S/'docs/dagger_anchored_sac_v2';O=S/'results/dagger_anchored_sac_v2'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
final=json.loads((L/'FINAL_STATUS.json').read_text());assert final['total_online_steps']==50000 and final['status'] in ('COMPLETE_BUDGET','RESCUE_ABILITY_LOST')
old=json.loads((L/'LOCK.json').read_text());assert sha(L/'PREREGISTRATION.json')==old['config'];assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')]
folder=O/'checkpoints/final_attempt_state';audit=dict(unix=time.time(),collection_steps=50000,learning_stopped=True,final_training_status=final['status'],full_stopped_state={str(folder/n):sha(folder/n) for n in ('model.zip','actor.pt','resume.pt')},old_training_lock=old,protocol=dict(mean_repeats_per_scope=2,scopes=['NATIVE','MATCHED'],strategies=['frozen_DAgger_student','confirmed_best','final_50000'],additional_intermediates='every other intermediate NATIVE2/2 full VALID candidate with cost below final valid actor, excluding duplicate best/final checkpoints',stochastic_native_per_learner=1,comparators=['original_controller','CEM','fixed_hip_leading'],same_initial_condition_seed=20261003,initial_condition_changes=False,scientific_changes=[],training_updates=0,evaluation_only=True))
for p in P.glob('*.py'):
 compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
lock=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='V3_FINAL_REPLAY_FREEZE',collection_stopped=50000)
for f in (L,D):
 (f/'FINAL_VERIFICATION_FREEZE_50000.json').write_text(json.dumps(audit,indent=2)+'\n');(f/'LOCK.json').write_text(json.dumps(lock,indent=2)+'\n')
print('FINAL_REPLAY_FROZEN; COLLECTION50000; NO_NEW_LEARNING')
