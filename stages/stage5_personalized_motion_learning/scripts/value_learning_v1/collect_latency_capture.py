"""Real immutable deployable capture for same-epoch algorithm CPU profiling."""
import json
from research_campaign import D,RAW,launch,save
from online_pilot import BANK

if __name__=='__main__':
 gate=json.loads((D/'OFFLINE_MODEL_PROMOTION_GATE.json').read_text())
 out=RAW/'latency_snapshots_v1'
 spec={'mode':'VALUE_PATTERN','proposal_descriptors':BANK,'descriptor':{'parameters':[0,.5],'horizon':'H3'},
  'matched_duration_factor':1.3,'model_path':gate['chosen_model'],'model_version':'OFFLINE_CPU_PROFILE',
  'capture_snapshot_dir':str(out)}
 result=launch({'condition':'sync_120','run_id':'latency_real_capture_v1','spec':spec})
 save(D/'LATENCY_REAL_CAPTURE_PROVENANCE.json',{'status':result['status'],'run_id':result['run_id'],'directory':str(out),
  'extra_capture_file_io':True,'full_live_latency_not_a_clean_normal_run':True,'purpose':'immutable actual deployable snapshot for algorithm scaling, not policy-promotion evidence',
  'chosen_model':gate['chosen_model'],'offline_ranking_gate':gate['status']})
