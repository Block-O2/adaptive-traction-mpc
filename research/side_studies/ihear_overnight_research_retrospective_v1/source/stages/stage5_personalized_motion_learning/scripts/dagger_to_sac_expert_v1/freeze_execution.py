from common import *
def run():
    prior=read('EXPERIMENT_SOURCE_LOCK.json')
    for name,h in prior.items():assert sha(P/name)==h
    current={p.name:sha(p) for p in P.glob('*.py')}
    save('EXECUTION_SOURCE_FREEZE_ADDITIONS.json',dict(existing_unchanged=True,added={k:v for k,v in current.items() if k not in prior},
        scientific_preregistration_unchanged=True,dagger_training_started=False,sac_training_started=False))
    save('EXPERIMENT_SOURCE_LOCK.json',current)
    dest=S/'scripts'/NAME;dest.mkdir(exist_ok=True)
    for p in P.glob('*.py'):shutil.copy2(p,dest/p.name)
    check();print('EXECUTION_SOURCE_FROZEN',flush=True)
if __name__=='__main__':run()
