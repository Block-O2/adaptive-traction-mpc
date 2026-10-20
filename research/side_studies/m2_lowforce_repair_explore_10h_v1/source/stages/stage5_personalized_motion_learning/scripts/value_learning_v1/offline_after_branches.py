"""One frozen model-fitting snapshot after all targeted branch attempts finish."""
from datetime import datetime,timezone
import json,time
from value_dataset import D,RAW,C,save,extract_dataset,sha
from train_value_models import train

if __name__=='__main__':
 while True:
  path=D/'ONE_STEP_BRANCH_RESULTS.json'
  results=json.loads(path.read_text()) if path.exists() else []
  if len(results)==135:break
  if datetime.now(timezone.utc)>=datetime.fromisoformat(C['hard_deadline_utc']):
   raise RuntimeError('hard deadline reached before all branch attempts finished')
  time.sleep(30)
 extract_dataset('dataset_fitting_snapshot_v1')
 manifest=json.loads((D/'VALUE_DATASET_MANIFEST.json').read_text())
 save(D/'FITTING_SNAPSHOT.json',{'status':'FROZEN_BEFORE_MODEL_TRAINING','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'dataset_manifest_sha256':sha(D/'VALUE_DATASET_MANIFEST.json'),'dataset':manifest['dataset_path'],
  'all_targeted_branch_attempts_complete':True,'later_search_results_excluded_from_this_frozen_model_fit':True,
  'split_and_hyperparameter_selection_contract_unchanged':True,'test_not_used_to_revise_fit_after_evaluation':True})
 output=train()
 print(json.dumps({'offline_complete':True,'gate':output['ranking_gate'],'chosen_full':output['best_full_model']}),flush=True)
