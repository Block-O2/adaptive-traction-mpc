"""Fresh actual moving snapshot; original stationary captures remain evidence."""
import json
from research_campaign import D,RAW,launch,save
from online_pilot import BANK

if __name__=='__main__':
 gate=json.loads((D/'OFFLINE_MODEL_PROMOTION_GATE.json').read_text());indices=[0,2,3,6]
 spec={'mode':'VALUE_PATTERN','proposal_descriptors':[BANK[i] for i in indices],
  'descriptor':{'parameters':[0.,.5],'horizon':'H3'},'matched_duration_factor':1.3,
  'model_path':gate['chosen_model'],'model_version':'OFFLINE_ACTUAL_MOVING_PROFILE',
  'legacy_candidate_limit':1,'proposal_source_indices':indices,
  'capture_snapshot_dir':str(RAW/'latency_actual_moving_snapshots_v1')}
 result=launch({'condition':'sync_120','run_id':'latency_actual_moving_capture_v1','spec':spec})
 save(D/'LATENCY_ACTUAL_MOVING_CAPTURE_PROVENANCE.json',{'status':result['status'],'run_id':result['run_id'],
  'chosen_model':gate['chosen_model'],'proposal_source_indices':indices,'extra_capture_file_io':True,
  'purpose':'actual committed OUTBOUND moving reference snapshot; distinguishes stationary RETURN proxy from moving handoff',
  'directory':spec['capture_snapshot_dir'],'full_host_latency_perturbed_by_capture_io':True})
