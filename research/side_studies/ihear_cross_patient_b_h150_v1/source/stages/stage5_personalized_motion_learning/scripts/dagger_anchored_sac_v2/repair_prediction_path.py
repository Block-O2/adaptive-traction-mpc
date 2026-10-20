from common import *
import shutil
def run():
 history=L/'implementation_history';history.mkdir(exist_ok=True)
 for name in ('EXCEPTION.json','STATE.json','IMPLEMENTATION_REVISION_BEFORE_TRAINING.json','LOCK.json'):
  if (L/name).exists():shutil.copy2(L/name,history/('before_predict_repair_'+name))
 for p in P.glob('*.py'):compile(p.read_text(),str(p),'exec');shutil.copy2(p,S/'scripts/dagger_anchored_sac_v2'/p.name)
 old=read('LOCK.json');new={str(p):sha(p) for p in P.glob('*.py')};assert sha(L/'PREREGISTRATION.json')==old['config'];log('IMPLEMENTATION_REPAIRS.jsonl',dict(action='Restore exact v1 BasePolicy.predict proposal mapping in evaluation and collection',diagnosis=read('PREDICTION_PATH_DIAGNOSIS.json'),old_sources=old['sources'],new_sources=new,old_failure_preserved=True,physics_edits=0,scientific_parameters_changed=False));save('LOCK.json',dict(config=old['config'],sources=new));state('REPRODUCTION_REPAIRED_CONTINUE',error=None)
if __name__=='__main__':run()
