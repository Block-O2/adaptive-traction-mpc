from common import *
import shutil
def run():
 old=read('LOCK.json');assert sha(L/'PREREGISTRATION.json')==old['config']
 for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
 log('IMPLEMENTATION_REPAIRS.jsonl',dict(changes=['frozen parameter optimizer groups need constructed-model set_parameters restore','independent child RNG seed indexed by evaluation call rather than training/evaluation budget','fixed cold environment seed separate from policy sampling RNG','two old duplicate-RNG calibration episodes retained and counted; distinct-RNG verification required'],old_sources=old['sources'],scientific_config_unchanged=True,actor_critic_updates_at_repair=0))
 save('LOCK.json',dict(config=old['config'],sources={str(p):sha(p) for p in P.glob('*.py')}));state('FULL_STATE_RESTORED_CONTINUE',total_online_steps=2996,error=None)
if __name__=='__main__':run()
