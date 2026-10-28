"""Prelaunch semantic binding of the frozen short-segments validation plan."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

P = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


config_file = P / sys.argv[1]
c = read(config_file)
group = c['group']
assert group == 'HOLDSS01'
assert not (P / 'jobs' / group / 'SOURCE_MANIFEST.json').exists(), 'ALREADY_STARTED'
protocol_file = P / c['holdout_protocol']
protocol = read(protocol_file)
assert sha(protocol_file) == c['holdout_protocol_sha256']
assert group in protocol['authorized_groups'] and protocol['frozen_unix'] < time.time()
core = dict(c)
core.pop('holdout_protocol_sha256')
assert digest(core) == protocol['canonical_config_without_protocol_hash_sha256'], 'CONFIG_SEMANTICS_CHANGED'
for field in ['actions', 'condition', 'case_path', 'case_sha256', 'fork_phase', 'fork_slot',
              'required_repeat_controls', 'required_qualified_controls', 'algorithm', 'worker']:
    assert c[field] == protocol['exact_config_fields'][field], 'PROTOCOL_FIELD_MISMATCH:' + field
assert len(c['actions']) == 14 and len({x['tag'] for x in c['actions']}) == 14
assert c['actions'][0]['tag'] == 'B' and c['required_qualified_controls'] == ['B']
assert c['fork_phase'] == 'OUTBOUND' and type(c['fork_slot']) is int and c['fork_slot'] == 0
assert c['actions'][0]['action'] == {'family': 'B'}
for a in c['actions'][1:9]:
    assert type(a['action']['original_B_through_outbound_slots']) is int
    assert a['action']['original_B_through_outbound_slots'] == 1
for a in c['actions'][9:]:
    assert 'original_B_through_outbound_slots' not in a['action']
for rel, expected in protocol['frozen_artifacts'].items():
    assert sha(P / rel) == expected, 'PROTOCOL_ARTIFACT_CHANGED:' + rel
for rel, expected in c['frozen_artifacts'].items():
    assert sha(P / rel) == expected, 'CONFIG_ARTIFACT_CHANGED:' + rel
assert sha(P / c['case_path']) == c['case_sha256']
freeze_file = P / 'freeze' / (group + '.json')
freeze = read(freeze_file)
assert freeze['config_sha256'] == sha(config_file)
assert freeze['holdout_protocol_sha256'] == sha(protocol_file)
runtime_plan = P / 'runtime' / (group + '_TEST_PLAN.json')
assert runtime_plan.read_bytes() == config_file.read_bytes()
prelaunch = P / 'audit' / (group + '_PRELAUNCH.json')
assert read(prelaunch)['config_sha256'] == sha(config_file)
out = P / 'audit' / (group + '_VALIDATION_BINDING.json')
assert not out.exists(), 'REFUSE_OVERWRITE'
stat = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
record = {'status': 'PASS', 'created_unix': time.time(), 'pid': os.getpid(), 'start_ticks': int(stat[19]),
          'group': group, 'source_sha256': sha(Path(__file__)), 'config_sha256': sha(config_file),
          'protocol_sha256': sha(protocol_file), 'runtime_test_plan_sha256': sha(runtime_plan),
          'prelaunch_sha256': sha(prelaunch), 'freeze_sha256': sha(freeze_file),
          'protocol_artifact_count': len(protocol['frozen_artifacts']),
          'exact_fields_and_canonical_config_verified': True, 'new_physics': 0,
          'original_contract_unchanged': True}
temp = out.with_suffix('.tmp')
temp.write_text(json.dumps(record, indent=2) + '\n')
temp.replace(out)
print('HELDOUT_FULL_SEMANTIC_BINDING_PASS', group, sha(config_file), flush=True)
