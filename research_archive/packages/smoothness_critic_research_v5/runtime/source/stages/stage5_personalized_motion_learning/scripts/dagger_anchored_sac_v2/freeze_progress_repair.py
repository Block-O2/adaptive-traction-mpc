from common import *
import shutil
old=read('LOCK.json');assert sha(L/'PREREGISTRATION.json')==old['config']
for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
log('IMPLEMENTATION_REPAIRS.jsonl',dict(changes=['progress loop index named separately from predict recurrent state','full online interruption restoration verified for networks targets optimizer replay RNG','continued exact 217 already-spent interactions and 20227 critic updates; no second warm-start','failure runtime capture preserved before environment close'],scientific_config_unchanged=True,old_sources=old['sources']))
save('LOCK.json',dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')}));state('ONLINE_RESTORED_CONTINUE',total_online_steps=11500,error=None)
