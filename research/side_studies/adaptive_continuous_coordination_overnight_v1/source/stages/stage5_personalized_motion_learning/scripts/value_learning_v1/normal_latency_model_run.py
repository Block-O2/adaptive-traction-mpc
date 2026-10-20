"""Clean actual-model run retaining full proposal diversity, reduced comparator count."""
import json
from research_campaign import D,RAW,launch,save
from online_pilot import BANK

if __name__=='__main__':
 gate=json.loads((D/'OFFLINE_MODEL_PROMOTION_GATE.json').read_text())
 spec={'mode':'VALUE_PATTERN','proposal_descriptors':BANK,'descriptor':{'parameters':[0.,.5],'horizon':'H3'},
  'matched_duration_factor':1.3,'model_path':gate['chosen_model'],'model_version':'OFFLINE_CLEAN_CPU_PROFILE',
  'legacy_candidate_limit':1}
 result=launch({'condition':'sync_120','run_id':'latency_clean_bank10_legacy1_v1','spec':spec})
 save(D/'LATENCY_CLEAN_NORMAL_RUN_PROVENANCE.json',{'status':result['status'],'run_id':result['run_id'],
  'chosen_model':gate['chosen_model'],'proposal_count':10,'legacy_comparator_limit':1,
  'extra_capture_file_io':False,'interpretation':'clean actual-value full rollout; stationary first selection and later committed continuation roles profiled separately; no realtime claim'})
