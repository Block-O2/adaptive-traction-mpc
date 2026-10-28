"""External witness after ownership checker tool return; no process killing."""
from pathlib import Path
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
O = P / 'audit/ownership_final_v1'
dest = P / 'audit/OWNED_FINAL_V1.json'
assert not dest.exists()
result = json.loads((O / 'OWNERSHIP_RESULT.json').read_text())
end = json.loads((O / 'END.json').read_text())
assert result['status'] == 'NO_OTHER_LIVE_OWNED_IN_DECLARED_SCOPE_SELF_PENDING_TOOL_RETURN'
assert result['all_OTHER_recorded_processes_ended_or_reused'] and not result['issues']
assert not result['live_or_zombie_known'] and not result['live_known_descendants']
checker = result['self']
assert end['process']['pid'] == checker['pid'] and end['process']['start_ticks'] == checker['start_ticks']


def state(q):
    try:
        s = (Path('/proc') / str(q['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
        return 'REUSED_PID' if int(s[19]) != int(q['start_ticks']) else 'ZOMBIE' if s[0] == 'Z' else 'LIVE'
    except (FileNotFoundError, ProcessLookupError):
        return 'ENDED'


checker_state = state(checker)
assert checker_state in ['ENDED', 'REUSED_PID'], 'CHECKER_NOT_EXITED_AFTER_TOOL_RETURN'
keys = {(q['pid'], q['start_ticks']) for q in result['known_processes']}
live = [{'pid': pid, 'start_ticks': ticks, 'state': state({'pid': pid, 'start_ticks': ticks})} for pid, ticks in keys]
assert all(q['state'] in ['ENDED', 'REUSED_PID'] for q in live)
payload = {
    'status': 'PASS_RECORDED_SCOPE_WITH_DOCUMENTED_METADATA_LIMITATIONS',
    'created_unix': time.time(), 'process': {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])},
    'checker_process': {**end['process'], 'current_state_after_tool_return': checker_state},
    'checker_tool_return_exit_code_observed': 0,
    'checker_exit_proven_by_external_PID_ticks_recheck': True,
    'unique_recorded_identities_rechecked': len(keys), 'known_live_or_zombie': 0,
    'known_live_descendants': 0, 'all_recorded_prior_identities_ended_or_reused': True,
    'ownership_result_path': str((O / 'OWNERSHIP_RESULT.json').relative_to(P)),
    'ownership_result_sha256': hashlib.sha256((O / 'OWNERSHIP_RESULT.json').read_bytes()).hexdigest(),
    'inventory_path': 'audit/ACTUAL_FINAL_OWNERSHIP_INVENTORY_V2.json',
    'inventory_sha256': hashlib.sha256((P / 'audit/ACTUAL_FINAL_OWNERSHIP_INVENTORY_V2.json').read_bytes()).hexdigest(),
    'foreground_metadata_PID_gaps_or_missing_original_review_ENDs_reconstructed': False,
    'unrecorded_reparented_orphans_universally_proven_absent': False,
    'perfect_PID_metadata_compliance_claim': False,
    'current_witness_process_exit_not_self_proven': True,
    'current_witness_followup': 'Actual offline-owned END and subsequent verifier /proc check after tool return.',
    'new_env_model_fit_physics': 0,
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
with dest.open('x') as f:
    f.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
print('OWNED_FINAL_RECORDED_SCOPE_PASS', len(keys), 'checker', checker_state)
