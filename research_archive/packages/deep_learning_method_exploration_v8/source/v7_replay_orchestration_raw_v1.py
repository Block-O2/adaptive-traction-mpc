"""Replay saved complete raw despite missing orchestration measurement/result."""
from pathlib import Path
import json
import sys
import time

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'source'))
from acl2_shared import put
from v7_scorer_replay import replay, summary

ident, group = 'HOLDSS01_B', 'HOLDSS02'
target = P / 'audit/scorer_replay' / (ident + '.json')
assert not target.exists(), 'IMMUTABLE_EXISTING_REPLAY'
assert not (P / 'attempts' / (ident + '_RESULT.json')).exists()
closed = json.loads((P / 'owned/HOLDSS02_SUPERVISOR_END.json').read_text())
assert closed['state'] == 'STOP' and not closed['survivors']
evidence = json.loads((P / 'audit/HOLDSS02_ENGINEERING_RAW_PRESERVATION.json').read_text())
assert evidence['exact_B_reproduction_control'] == 'audit/HOLDSS03_B_HISTORICAL_IDENTITY.json'
assert json.loads((P / evidence['exact_B_reproduction_control']).read_text())['status'] == 'PASS'
r = replay(ident, group)
assert r['status'] == 'SCORER_REPLAY_PASS' and r['original_result_exact_reproduced']
assert r['motion_replay'] is None, 'DO_NOT_INVENT_ORIGINAL_MEASURED_RESULT'
r['orchestration_failure_preserved'] = True
r['formal_force_rank_allowed'] = False
r['qualified_replay_false_interpretation'] = 'Default non-ranking false because original MEASURED/RESULT absent; original fullmotion qualification was not executed in this failed orchestration. Do not interpret as a newly observed motion failure.'
r['separate_exact_raw_reproduction_to_original_qualified_B'] = evidence['exact_B_reproduction_control']
r['recovery_raw_index'] = 'audit/HOLDSS02_ENGINEERING_RAW_PRESERVATION.json'
r['new_model_env_training_physics'] = 0
r['posthoc_created_unix'] = time.time()
put('audit/scorer_replay/' + ident + '.json', r)
print('ORCHESTRATION_RAW_ORIGINAL_SCORER', ident, r['status'], 'fullmotion_unexecuted', 'unranked', flush=True)
summary()
