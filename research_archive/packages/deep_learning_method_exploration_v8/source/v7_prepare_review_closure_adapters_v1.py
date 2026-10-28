"""Current-time closure adapters, never reconstructed original review ENDs."""
from pathlib import Path
import ast
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
O = P / 'audit/review_closure_adapters_v1'
assert not O.exists()
O.mkdir()
started = time.time()
identity = {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])}


def sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def put(name, data):
    with (O / name).open('x') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def pid_state(q):
    try:
        fields = (Path('/proc') / str(q['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
        return 'REUSED_PID' if int(fields[19]) != int(q['start_ticks']) else 'ZOMBIE' if fields[0] == 'Z' else 'LIVE'
    except (FileNotFoundError, ProcessLookupError):
        return 'ENDED'


put('START.json', {'process': identity, 'started_unix': started, 'scope': 'CURRENT_MAIN_ADAPTER_ONLY_NOT_ORIGINAL_REVIEW_END'})
index, checks = [], []
for name, end_name, field in [('causal_human_interface', 'END.json', 'outputs'),
                              ('interface', 'REVIEW_END.json', 'outputs'),
                              ('terminal_rule', 'END.json', 'outputs_sha256')]:
    directory = P / 'agent_reviews' / name
    end = directory / end_name
    original = json.loads(end.read_text())
    files = {rel: value if isinstance(value, str) else value['sha256'] for rel, value in original[field].items()}
    for rel, expected in files.items():
        assert sha(directory / rel) == expected, 'ORIGINAL_REVIEW_OUTPUT_CHANGED:' + name + '/' + rel
    normalized = name + '_NORMALIZED_MANIFEST.json'
    put(normalized, {'schema': 'ihear.current_manifest_schema_adapter.v1', 'status': 'ORIGINAL_ENUMERATED_HASHES_VERIFIED',
                     'created_unix': time.time(), 'original': str(end.relative_to(P)), 'original_sha256': sha(end),
                     'original_field': '/' + field, 'files': files,
                     'scope': 'Only the originally enumerated outputs; no claim of original standard manifest or later-added outputs.',
                     'original_records_not_modified': True})
    index.append({'directory': str(directory.relative_to(P)), 'end': str(end.relative_to(P)),
                  'manifest': str((O / normalized).relative_to(P))})
    checks.append({'review': name, 'original_END_absent': False, 'standard_manifest_absent_or_nonstandard': True,
                   'normalized_original_outputs': len(files), 'original_hashes_match': True})

source = P / 'agent_reviews/final_verifier/verify_final_package.py'
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'manifest_rows')
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), namespace)
for name, manifest_name in [('history', 'REVIEW_OUTPUT_MANIFEST.json'), ('local_surrogate', 'FINAL_REVIEW_MANIFEST.json')]:
    directory = P / 'agent_reviews' / name
    assert not (directory / 'END.json').exists(), 'ORIGINAL_END_NOW_EXISTS_REVIEW_REQUIRED'
    manifest = directory / manifest_name
    m = json.loads(manifest.read_text())
    for rel, expected in namespace['manifest_rows'](m):
        target = Path(rel) if Path(rel).is_absolute() else directory / rel
        assert expected and sha(target) == expected, 'ORIGINAL_MANIFEST_OUTPUT_CHANGED'
    ownership_file = directory / 'OWNED_PROCESS_AUDIT.json'
    processes = []
    if ownership_file.exists():
        for row in json.loads(ownership_file.read_text()).get('records', []):
            if 'pid' in row and 'start_ticks' in row:
                q = {'pid': int(row['pid']), 'start_ticks': int(row['start_ticks'])}
                state = pid_state(q)
                assert state in ['ENDED', 'REUSED_PID'], 'RECORDED_REVIEW_PROCESS_STILL_EXISTS'
                processes.append({**q, 'state_now': state, 'source': str(ownership_file.relative_to(P))})
    receipt = name + '_CURRENT_MAIN_CLOSURE_RECEIPT.json'
    put(receipt, {'schema': 'ihear.current_review_closure_receipt.v1',
                  'status': 'CURRENT_MAIN_VERIFIED_FILES_WITH_ORIGINAL_END_ABSENT',
                  'created_unix': time.time(), 'current_main_metadata_process': identity,
                  'original_END_absent': True, 'original_END_or_historical_end_time_reconstructed': False,
                  'manifest_sha256': sha(manifest), 'manifest': str(manifest.relative_to(P)),
                  'verified_recorded_processes': processes,
                  'original_individual_process_END_metadata_complete': False,
                  'unrecorded_original_PID_identity_reconstructed': False,
                  'limitation': 'This current-time receipt verifies existing files and available recorded PID exit only. It is not the missing original review END or proof of every historical process identity.',
                  'original_records_not_modified': True})
    index.append({'directory': str(directory.relative_to(P)), 'end': str((O / receipt).relative_to(P)),
                  'manifest': str(manifest.relative_to(P))})
    checks.append({'review': name, 'original_END_absent': True, 'original_manifest_hashes_match': True,
                   'recorded_current_exit_checks': len(processes), 'complete_original_PID_END_proven': False})

put('ADAPTER_INDEX.json', {'agent_reviews': index, 'checks': checks, 'original_records_not_modified': True,
                         'original_missing_END_reviews': ['history', 'local_surrogate'],
                         'original_nonstandard_manifest_reviews': ['causal_human_interface', 'interface', 'terminal_rule'],
                         'metadata_perfect_PASS_allowed': False,
                         'source_sha256': sha(Path(__file__)), 'created_unix': time.time()})
put('END.json', {'process': identity, 'status': 'CURRENT_ADAPTERS_COMPLETE_WITH_DOCUMENTED_ORIGINAL_METADATA_LIMITATIONS',
                 'started_unix': started, 'ended_unix': time.time(), 'original_records_not_modified': True,
                 'source_sha256': sha(Path(__file__)), 'new_env_model_fit_physics': 0})
print('REVIEW_ADAPTERS', len(index), 'original ENDs absent retained', 2)
