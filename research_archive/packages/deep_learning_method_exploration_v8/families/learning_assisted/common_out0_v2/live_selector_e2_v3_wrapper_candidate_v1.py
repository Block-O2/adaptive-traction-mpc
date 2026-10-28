"""SOURCE_ONLY three-positional V3 bridge; no import/call on module load.

Only the current recorded supervisor worker may request approved E2 inference.
The cutoff is converted, never extended. No file writes, fit or physics.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = 'families/learning_assisted/common_out0_v2/'
SELF = REL + 'live_selector_e2_v3_wrapper_candidate_v1.py'
MANIFEST = REL + 'LIVE_SELECTOR_E2_V3_WRAPPER_MANIFEST_V1.json'
TARGET = REL + 'frozen_live_e2_candidate_v1.py'
TARGET_SHA = '650c089fe51cc9d0b38c2ccbe94f0fb770512d9de6fb4e9e890c511fb475228f'
STOP = 1793114740.0


def need(test, reason):
    if not test:
        raise RuntimeError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def bounded(root, relative):
    path = (root / relative).resolve()
    need(path.is_relative_to(root), 'E2_V3_WRAPPER_PATH_ESCAPES_PACKAGE')
    return path


def own_start_ticks():
    stat = Path('/proc/self/stat').read_text()
    return int(stat[stat.rindex(')') + 2:].split()[19])


def predict_before_B(package, config, study):
    """Exact signature consumed by V3.parallel_selector_adapters."""
    evidence = dict(wrapper_source=SELF, stage='OWNER_AUTHORITY');result = None
    try:
        root = Path(package).resolve();need(root == ROOT, 'E2_V3_WRAPPER_UNIQUE_PACKAGE')
        group = config['group']
        need(isinstance(group, str) and re.fullmatch(r'[A-Za-z0-9_]{1,120}', group),
             'E2_V3_WRAPPER_EXACT_GROUP')
        config_path = root / 'experiments' / (group + '.json')
        need(load(config_path) == config, 'E2_V3_WRAPPER_ACTUAL_CONFIG_OBJECT')
        config_sha = sha(config_path)
        for relative in (SELF, MANIFEST):
            need(config['frozen_artifacts'].get(relative) == sha(bounded(root, relative)),
                 'E2_V3_WRAPPER_MUST_BE_FROZEN_IN_ROOT_CONFIG:' + relative)
        manifest = load(root / MANIFEST)
        for relative, expected in manifest['files_sha256'].items():
            need(sha(bounded(root, relative)) == expected, 'E2_V3_WRAPPER_SOURCE_CHANGED:' + relative)
        authorization = config['comparative_validation']['e2_readonly_authorization']
        need(set(authorization) == {'path', 'sha256'}, 'E2_V3_WRAPPER_EXACT_AUTHORIZATION_FIELDS')
        approval_path = bounded(root, authorization['path'])
        need(sha(approval_path) == authorization['sha256'], 'E2_V3_WRAPPER_ACTUAL_READONLY_APPROVAL_SHA')
        supervisor_path = root / 'owned' / (group + '_SUPERVISOR.json')
        supervisor = load(supervisor_path)
        need(supervisor['state'] == 'RUNNING' and
             supervisor['activation'] == 'deep_learning_method_exploration_v8_20261027T032540Z',
             'E2_V3_WRAPPER_EXISTING_ACTIVE_SUPERVISOR')
        need(supervisor['worker']['pid'] == os.getpid() and
             supervisor['worker']['start_ticks'] == own_start_ticks(),
             'E2_V3_WRAPPER_ONLY_ACTUAL_OWNED_WORKER')
        need(supervisor['config_sha256'] == config_sha, 'E2_V3_WRAPPER_SUPERVISOR_CONFIG_SHA')
        cutoff = supervisor['cutoff_unix']
        need(isinstance(cutoff, (int, float)) and not isinstance(cutoff, bool) and
             math.isfinite(cutoff) and cutoff <= STOP, 'E2_V3_WRAPPER_ORIGINAL_FINITE_CUTOFF')
        wall_now = time.time();monotonic_now = time.monotonic()
        need(wall_now < cutoff, 'E2_V3_WRAPPER_EXISTING_OWNER_DEADLINE_EXHAUSTED')
        owner_deadline = monotonic_now + cutoff - wall_now
        evidence.update(group=group, worker_pid=os.getpid(), worker_start_ticks=own_start_ticks(),
            config_sha256=config_sha, supervisor_path=str(supervisor_path.relative_to(root)),
            supervisor_sha256=sha(supervisor_path), supervisor_cutoff_unix=cutoff,
            conversion_wall_now=wall_now, conversion_monotonic_now=monotonic_now,
            converted_existing_owner_deadline_monotonic=owner_deadline,
            parent_time_added_seconds=0., readonly_approval_sha256=authorization['sha256'],
            stage='CANDIDATE_SOURCE_IMPORT')
        path = bounded(root, TARGET);need(sha(path) == TARGET_SHA, 'E2_V3_WRAPPER_FROZEN_CANDIDATE')
        name = '_v8_e2_v3_positional_target_' + TARGET_SHA[:20]
        if name in sys.modules:
            candidate = sys.modules[name]
            need(Path(candidate.__file__).resolve() == path, 'E2_V3_WRAPPER_PRIVATE_MODULE_PATH')
        else:
            spec = importlib.util.spec_from_file_location(name, path)
            candidate = importlib.util.module_from_spec(spec);sys.modules[name] = candidate
            try:spec.loader.exec_module(candidate)
            except BaseException:
                sys.modules.pop(name, None);raise
        need(time.monotonic() < owner_deadline, 'E2_V3_WRAPPER_NO_DEADLINE_RESET_AFTER_IMPORT')
        evidence['stage'] = 'APPROVED_FROZEN_INFERENCE'
        result = candidate.predict_before_B(root, config, study,
            approval_path=approval_path, approval_sha256=authorization['sha256'],
            owner_deadline_monotonic=owner_deadline)
        need(len(result['decisions']) == 9, 'E2_V3_WRAPPER_UNCHANGED_NINE_SELECTORS')
        need(result['counters'] == candidate.EXPECTED, 'E2_V3_WRAPPER_UNCHANGED_COUNTERS')
        need(sha(supervisor_path) == evidence['supervisor_sha256'] and
             sha(config_path) == config_sha, 'E2_V3_WRAPPER_OWNER_CONFIG_CHANGED_DURING_CALL')
        evidence['stage'] = 'COMPLETE'
        # Decisions/counters and all original receipt fields pass through intact.
        return dict(result, thin_wrapper_owner_proof=evidence)
    except BaseException as error:
        failure = dict(schema='v8.E2.v3_wrapper_failure.v1',
            error_type=type(error).__name__, error=str(error),
            original_InferenceFailure_receipt=getattr(error, 'receipt', None),
            completed_candidate_receipt_if_postcheck_failed=result,
            thin_wrapper_owner_proof=evidence, automatic_retry=False)
        raise RuntimeError('E2_V3_THIN_WRAPPER_FAILED:' +
            json.dumps(failure, sort_keys=True, separators=(',', ':'), allow_nan=False)) from error
