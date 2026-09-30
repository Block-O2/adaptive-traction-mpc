"""Clean normal measured subset retaining the actual confirmed Q-selected path."""
import json
from research_campaign import D,launch,save
from online_pilot import BANK

if __name__=='__main__':
 gate=json.loads((D/'OFFLINE_MODEL_PROMOTION_GATE.json').read_text())
 indices=[0,2,3,6]
 spec={'mode':'VALUE_PATTERN','proposal_descriptors':[BANK[i] for i in indices],
  'descriptor':{'parameters':[0.,.5],'horizon':'H3'},'matched_duration_factor':1.3,
  'model_path':gate['chosen_model'],'model_version':'OFFLINE_CLEAN_SUBSET_0236',
  'legacy_candidate_limit':1,'proposal_source_indices':indices}
 result=launch({'condition':'sync_120','run_id':'latency_clean_subset0236_legacy1_v1','spec':spec})
 save(D/'LATENCY_CLEAN_SUBSET_RUN_PROVENANCE.json',{'status':result['status'],'run_id':result['run_id'],
  'chosen_model':gate['chosen_model'],'proposal_source_indices':indices,'proposal_count':4,
  'legacy_comparator_limit':1,'extra_capture_file_io':False,
  'subset_reason':'latency-bounded baseline,+.06,+.12,+.15 H3; retains independently confirmed offline-Q-selected .15 path; development proposal repertoire, no test-label selection',
  'opposite_direction_data_retained_in_offline_common_state_branches':True,
  'interpretation':'full actual-model rollover, stationary first and moving continuation roles measured separately; no hardware/realtime qualification'})
