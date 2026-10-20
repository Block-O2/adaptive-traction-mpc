from common import *
import shutil
old=read('LOCK.json');assert sha(L/'PREREGISTRATION.json')==old['config']
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
log('IMPLEMENTATION_REPAIRS.jsonl',dict(changes=['best comparison uses stored row.J_F schema','cached completed checkpoint results are finalized with pending independent confirmation after full-state restore'],scientific_config_unchanged=True,total_online_steps_preserved=12283,old_sources=old['sources']))
save('LOCK.json',dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')}));state('BEST_SUMMARY_REPAIRED_CONTINUE',total_online_steps=12283,error=None)
