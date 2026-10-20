from pathlib import Path
import json,hashlib,time,shutil
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2');S=D.parents[1]/'scripts/dagger_anchored_sac_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=json.loads((L/'LOCK.json').read_text());assert sha(P/'train.py')==old['sources'][str(P/'train.py')];assert sha(P/'evaluate.py')==old['sources'][str(P/'evaluate.py')];assert sha(L/'PREREGISTRATION.json')==old['config']
for name in ('CONTINUATION_RESUME_AUDIT.json','CONTINUATION_EXCEPTION.json'):
 for folder in (L,D):
  if (folder/name).exists():shutil.copy2(folder/name,folder/('diagnostic_intercept_'+name))
change=dict(unix=time.time(),repair='A newly constructed actor for mean diagnosis consumed Torch CPU RNG after restore; intercepted before any actor/critic update or new collection. Use deepcopy without random initialization and compare all restored global/sampler RNG hashes after diagnostics. Completed independent10k confirmation reused only after exact actor and trace hash validation.',restored_original_checkpoint=True,collection_steps_before_and_after=21283,actor_updates_before_and_after=1010,critic_updates_before_and_after=30010,scientific_changes=[],resource_policy_unchanged=True,old_lock=old)
new=dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')},resource_revision='RESOURCE_POLICY_V2.json')
for folder in (L,D):
 (folder/'RESUME_DIAGNOSTIC_REPAIR.json').write_text(json.dumps(change,indent=2)+'\n');(folder/'LOCK.json').write_text(json.dumps(new,indent=2)+'\n')
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/p.name)
print('RESUME_DIAGNOSTIC_FIX_FROZEN_NO_COLLECTION_OR_UPDATE')
