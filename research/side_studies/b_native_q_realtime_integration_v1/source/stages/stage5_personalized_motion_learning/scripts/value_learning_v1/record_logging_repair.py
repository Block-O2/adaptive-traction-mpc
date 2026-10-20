"""Preserve a bounded logging-only repair and the un-replayed actual checkpoint."""
import json
from datetime import datetime,timezone
from research_campaign import D,RAW,save,sha,state

def main():
 directory=RAW/'pilot_sessions/scratch_v1'
 rows=json.loads((directory/'per_repetition.json').read_text())
 path=D/'BOUNDED_REPAIR_05_SERIALIZATION_RESUME.json'
 if not path.exists():
  save(path,{'repair_cycle':5,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
   'defect':'boundary logging passed NumPy arrays to plain JSON; rep1 VALID and checkpoint/model already persisted',
   'fix':'local logging conversion through existing runner._jsonable; verified checkpoint/model resume; next original safe boundary promotes prepared immutable model',
   'source_checkpoint':rows[0]['end_checkpoint'],'source_per_repetition_sha256':sha(directory/'per_repetition.json'),
   'regression_tests':'test_pilot_resume_logging.py: nested ndarray/scalar serialization, actual checkpoint hash/provenance/state and pending model verified, corrupted hash rejected; 2 PASS',
   'completed_rep1_replayed':False,'physics_control_safety_math_changed':False,
   'pilot_resume_still_requires_current_latency_gate_PASS':True})
 state('LATENCY_GATE_REPAIR_AND_PILOT_RECOVERY',repair_cycles_used=5,
  next_action='profile separately frozen duplicate-work reduction; preserve actual moving v2 FAIL; pilot remains gated')

if __name__=='__main__':main()
