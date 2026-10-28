"""SOURCE_ONLY metadata builder; main must separately authorize any build.

Stdlib only. No candidate/model import, numerical fit, raw/outcome analysis,
process launch or physical dispatch. No output is produced on import.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import os
import re
import resource
import signal
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = 'families/history_conditioned/'
CONTRACT = REL + 'CONTINUOUS_VALIDATION_METADATA_BUILDER_CONTRACT_V1.json'
SOURCE = REL + 'CONTINUOUS_VALIDATION_METADATA_BUILDER_SOURCE_MANIFEST_V1.json'
BASE_CONFIG = 'experiments/V8CONTILC01.json'
BASE_SOURCE = 'jobs/V8CONTILC01/SOURCE_MANIFEST.json'
REGISTRATION = 'freeze/V8_NEW_PARAMETER_CONDITIONS_V1.json'
PROTOCOL = 'freeze/CONTINUOUS_NEW_PARAMETER_PROCEDURE_V4_V1.json'
RECEIPTS = REL + 'config_builds/c4_validation_v1'
STOP = 1793114740.0
GROUPS = (
    ('V8CONVAL01', 'high_rom_v8_val_heavy065', 2026102753,
     'cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c'),
    ('V8CONVAL02', 'high_rom_v8_val_light035', 2026102754,
     '224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87'))
CASE_PREFIX = 'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/'
GATES = ('continuous_ilc_physics_authorized', 'c2b_component_bo_v2_fit_authorized',
         'c2b_component_bo_v2_candidate_physics_authorized')
WRAPPER = 'source/v8_continuous_ilc_worker_v4.py'


def need(test, reason):
    if not test:
        raise RuntimeError(reason)


def bounded(root, relative):
    need(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
         'CANONICAL_PACKAGE_RELATIVE_PIN_REQUIRED')
    need(Path(relative).as_posix() == relative and '..' not in Path(relative).parts,
         'NONCANONICAL_PIN')
    need(not any(part.upper() in ('CURRENT', 'CURRENT.JSON') for part in Path(relative).parts),
         'MUTABLE_CURRENT_POINTER_NOT_A_FROZEN_PIN')
    path = (root / relative).resolve()
    need(path.is_relative_to(root), 'PIN_ESCAPES_PACKAGE')
    return path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text())


def input_path(root, value):
    path = (root / value).resolve()
    need(path.is_relative_to(root), 'INPUT_ESCAPES_PACKAGE')
    relative = str(path.relative_to(root));bounded(root, relative)
    return path, relative


def pin_map(value, label):
    need(isinstance(value, dict) and value, 'ROOT_ACTUAL_NONEMPTY_PIN_MAP_REQUIRED:' + label)
    need(all(isinstance(path, str) and isinstance(digest, str) and
             re.fullmatch(r'[0-9a-f]{64}', digest) for path, digest in value.items()),
         'EXACT_PATH_TO_SHA256_MAP_REQUIRED:' + label)
    return value


def merge(target, incoming):
    for path, digest in incoming.items():
        need(path not in target or target[path] == digest, 'CONFLICTING_FROZEN_PIN:' + path)
        target[path] = digest


def new(path, value):
    need(not path.exists(), 'NEW_FILES_ONLY_NO_RETRY:' + str(path))
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def guard(deadline):
    need(time.monotonic() < deadline and time.time() < STOP, 'UNCHANGED_LOCAL_GLOBAL_CLOCK')


def original_closed_metadata(root):
    ending = load(root / 'owned/V8CONTILC01_SUPERVISOR_END.json')
    done = load(root / 'jobs/V8CONTILC01/WORKER_DONE.json')
    exited = load(root / 'owned/V8CONTILC01_EXIT.json')
    need(ending.get('worker_exit_code') == 0 and ending.get('survivors') == [],
         'ORIGINAL_C_JOB_NOT_CLEAN_CLOSED')
    need(done.get('all_children_joined') is True and done.get('status') ==
         'CONTINUOUS_ILC_COMPONENT_BO_V3_COMPLETED_REPORTED_RESULTS',
         'ORIGINAL_C_CLOSED_OWNER_METADATA_REQUIRED')
    need(exited.get('active_child') is None and exited.get('bridge_running') is False,
         'ORIGINAL_C_OWNER_STILL_ACTIVE')


def no_validation_launch_metadata(root, deadline):
    """Only config/filename metadata; no validation outcome contents opened."""
    validation_shas = {row[3] for row in GROUPS};matched = []
    for path in sorted((root / 'experiments').glob('*.json')):
        guard(deadline);config = load(path)
        if config.get('case_sha256') not in validation_shas:
            continue
        group = config['group'];need(re.fullmatch(r'[A-Za-z0-9_]{1,120}', group), 'REGISTERED_GROUP_NAME')
        matched.append(dict(group=group, config_sha256=sha(path)))
        need(not (root / 'owned' / (group + '_SUPERVISOR.json')).exists(),
             'VALIDATION_OWNER_ALREADY_LAUNCHED:' + group)
        need(not (root / 'jobs' / group).exists(), 'VALIDATION_JOB_ALREADY_STARTED:' + group)
        need(not list((root / 'runtime/source/results').glob(group + '*')),
             'VALIDATION_RESULT_PATH_ALREADY_EXISTS:' + group)
    for group, _, _, _ in GROUPS:
        need(not (root / 'owned' / (group + '_SUPERVISOR.json')).exists() and
             not (root / 'jobs' / group).exists(), 'C4_VALIDATION_GROUP_ALREADY_USED:' + group)
    return matched


def main():
    started = time.monotonic();cpu = time.process_time();deadline = started + 60.
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--root-inventory', required=True)
    parser.add_argument('--root-inventory-sha256', required=True)
    parser.add_argument('--main-approval', required=True)
    parser.add_argument('--main-approval-sha256', required=True)
    args = parser.parse_args();root = Path(args.package).resolve()
    need(root == ROOT, 'UNIQUE_V8_PACKAGE')
    approval_path, approval_relative = input_path(root, args.main_approval)
    inventory_path, inventory_relative = input_path(root, args.root_inventory)
    need(sha(approval_path) == args.main_approval_sha256, 'EXACT_FUTURE_MAIN_METADATA_APPROVAL')
    approval = load(approval_path)
    need(approval.get('schema') == 'v8.C4.validation_metadata_build_approval.v1' and
         approval.get('status') == 'ROOT_APPROVED_METADATA_BUILD_ONLY_V1' and
         approval.get('source_manifest_sha256') == sha(root / SOURCE) and
         approval.get('contract_sha256') == sha(root / CONTRACT) and
         approval.get('root_inventory_path') == inventory_relative and
         approval.get('root_inventory_sha256') == args.root_inventory_sha256 and
         approval.get('root_inventory_completeness_review_pass') is True and
         approval.get('new_parameter_preoutcome_freeze_review_pass') is True and
         approval.get('physics_dispatch_authorized') is False,
         'SEPARATE_ROOT_METADATA_AUTHORITY_REQUIRED')
    contract = load(root / CONTRACT);source = load(root / SOURCE)
    need(approval.get('outputs') == contract['proposed_outputs'] and
         approval.get('budget') == contract['metadata_build_budget'], 'EXACT_METADATA_SCOPE_BUDGET')
    guard(deadline)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('METADATA_BUILD_ORIGINAL_CAP')))
    signal.setitimer(signal.ITIMER_REAL, min(deadline - time.monotonic(), STOP - time.time()))
    for relative, expected in source['files_sha256'].items():
        guard(deadline);need(sha(bounded(root, relative)) == expected, 'BUILDER_INPUT_SOURCE_CHANGED:' + relative)
    activation = load(root / 'ACTIVATION.json')
    need(activation['activation_id'] == 'deep_learning_method_exploration_v8_20261027T032540Z'
         and activation['hard_stop_unix'] == STOP, 'ORIGINAL_ACTIVATION_CLOCK')
    original_closed_metadata(root)
    need(sha(inventory_path) == args.root_inventory_sha256, 'EXACT_ROOT_ACTUAL_FULL_INVENTORY_SHA')
    inventory = load(inventory_path)
    need(inventory.get('status') == 'ROOT_APPROVED_ALL_ACTUAL_MODELS_PROGRAMS_STRONGCONTROLS_FROZEN_V1'
         and inventory.get('original_global_stop_unix') == STOP and
         inventory.get('all_models_programs_strongcontrols_complete') is True and
         inventory.get('new_parameter_validation_physics_started') is False and
         isinstance(inventory.get('frozen_unix'), (int, float)) and
         math.isfinite(inventory['frozen_unix']) and inventory['frozen_unix'] < time.time(),
         'ACTUAL_PREOPEN_COMPLETENESS_AUTHORITY_NOT_A_NONEMPTY_DICT')
    sections = {key: pin_map(inventory.get(key), key)
                for key in ('frozen_artifacts', 'models', 'strongcontrols')}
    permissions = approval.get('runtime_gate_permissions', {key: False for key in GATES})
    need(set(permissions) == set(GATES) and all(type(v) is bool for v in permissions.values()),
         'EXPLICIT_NEW_RUNTIME_GATES_REQUIRED')
    need(all(not v for v in permissions.values()) or all(permissions.values()),
         'DO_NOT_CHANGE_BO_PROCEDURE_BY_PARTIAL_PERMISSIONS')
    if any(permissions.values()):
        need(approval.get('new_C4_runtime_gate_capabilities_explicitly_reviewed') is True,
             'OLD_KNOWN_HEAVY_FLAGS_ARE_NOT_NEW_CASE_AUTHORITY')
    registered = load(root / REGISTRATION)
    for _, key, seed, digest in GROUPS:
        matches = [r for r in registered['cases'] if r['case_key'] == key]
        need(len(matches) == 1 and matches[0]['role'] == 'FROZEN_VALIDATION' and
             matches[0]['seed'] == seed and matches[0]['payload_sha256'] == digest,
             'ORIGINAL_TWO_VALIDATION_CASE_SEED_REGISTRATION')
    observed_configs = no_validation_launch_metadata(root, deadline)
    base = load(root / BASE_CONFIG);closed_source = load(root / BASE_SOURCE)
    need(closed_source['config_sha256'] == sha(root / BASE_CONFIG), 'ORIGINAL_CONFIG_SOURCE_CLOSURE')
    pins = {};merge(pins, pin_map(closed_source['files'], 'original_runtime_source_closure'))
    merge(pins, pin_map(base['frozen_artifacts'], 'original_config_pins'))
    merge(pins, source['files_sha256'])
    for section in sections.values():merge(pins, section)
    merge(pins, {inventory_relative: args.root_inventory_sha256,
                 approval_relative: args.main_approval_sha256,
                 SOURCE: sha(root / SOURCE)})
    for _, key, _, digest in GROUPS:merge(pins, {CASE_PREFIX + key + '.json': digest})
    for relative, expected in pins.items():
        guard(deadline);need(sha(bounded(root, relative)) == expected, 'FROZEN_ARTIFACT_CHANGED:' + relative)
    output_paths = [bounded(root, relative) for relative in contract['proposed_outputs']]
    need(all(not p.exists() for p in output_paths) and not (root / RECEIPTS).exists(),
         'ALL_OUTPUTS_NEW_ORIGINAL_PARTIALS_PRESERVED')
    receipts = root / RECEIPTS;receipts.mkdir(parents=True, exist_ok=False);written = []
    try:
        frozen_unix = time.time()
        protocol = dict(schema='v8.continuous_procedure_new_parameter_validation.v1',
            status='APPROVED_FROZEN_PROCEDURE_NEW_PARAMETER_VALIDATION_V1',
            original_global_stop_unix=STOP, all_original_task_guard_scorer_unchanged=True,
            frozen_unix=frozen_unix, authorized_groups={group: dict(case_path=CASE_PREFIX + key + '.json',
                case_sha256=digest) for group, key, _, digest in GROUPS},
            frozen_artifacts=pins, root_full_inventory_path=inventory_relative,
            root_full_inventory_sha256=args.root_inventory_sha256,
            root_inventory_all_models_frozen_unix=inventory['frozen_unix'],
            original_inventory_sections=copy.deepcopy(sections),
            runtime_gate_permissions=permissions, metadata_build_main_approval=approval_relative,
            physics_dispatch_authorization=False,
            validation_is_adaptive_frozen_procedure_not_frozen_weight_pure_inference=True,
            local_adaptation='own completed T1/T2/T3 only; fixed heterogeneous prior not value labels',
            registered_base_tasks=14, registered_inter_rep_boundaries=2, optional_legal_BO_child_max=1,
            preopen_config_metadata_checked=observed_configs)
        no_validation_launch_metadata(root, deadline)
        new(root / PROTOCOL, protocol);written.append(PROTOCOL)
        protocol_sha = sha(root / PROTOCOL);configs = []
        for group, key, seed, digest in GROUPS:
            config = copy.deepcopy(base)
            config.update(group=group, worker=Path(WRAPPER).name,
                case_path=CASE_PREFIX + key + '.json', case_sha256=digest,
                continuous_owner_version='CONTINUOUS_ILC_COMPONENT_BO_V4',
                continuous_validation_protocol=PROTOCOL,
                continuous_validation_protocol_sha256=protocol_sha,
                job_wall_cap_s=3600, nested_owner_timeout_s=3600,
                known_heavy_engineering=False,
                scientific_branch='FROZEN_CONTINUOUS_PROCEDURE_NEW_PARAMETER_VALIDATION',
                metadata_build_status='ROOT_PHYSICS_JOB_REVIEW_AND_DISPATCH_STILL_REQUIRED',
                c2b_component_bo_v2_fit_approval_id=approval_relative)
            config.update(permissions)
            config['condition'].update(name=group, seed=seed,
                split='FROZEN_NEW_PARAMETER_CONTINUOUS_PROCEDURE_VALIDATION',
                role='original preregistered parameter/seed; real coldT1 then own persistent T2/T3; no outcome based reassignment')
            config['frozen_artifacts'] = dict(pins, **{PROTOCOL: protocol_sha})
            need(config['B'] == base['B'] and config['H150'] == base['H150'] and
                 config['arms'] == base['arms'] and config['actions'] == base['actions'] and
                 config['condition']['prefix'] == base['condition']['prefix'] and
                 config['ilc_population_history_sha256'] == base['ilc_population_history_sha256'],
                 'PROCEDURE_ACTION_RECIPE_PRIOR_OR_PREFIX_CHANGED')
            relative = 'experiments/' + group + '.json'
            guard(deadline);new(root / relative, config);written.append(relative)
            configs.append(dict(group=group, path=relative, sha256=sha(root / relative)))
        guard(deadline)
        for relative, expected in pins.items():
            guard(deadline);need(sha(bounded(root, relative)) == expected, 'POST_BUILD_ARTIFACT_CHANGED')
        result = dict(status='METADATA_BUILT_NOT_PHYSICS_DISPATCH_APPROVAL',
            root_inventory_sha256=args.root_inventory_sha256, protocol_sha256=protocol_sha,
            configs=configs, frozen_artifacts_count=len(pins),
            copied_inventory_section_counts={k: len(v) for k, v in sections.items()},
            all_given_inventory_pins_included=True, runtime_gate_permissions=permissions,
            wall_seconds=time.monotonic() - started, CPU_seconds=time.process_time() - cpu,
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            model_imports=0, model_inference=0, fit=0, physics=0,
            output_files_sha256={p: sha(root / p) for p in written})
        new(receipts / 'BUILD_END.json', result)
        print(json.dumps(result, sort_keys=True))
    except BaseException as error:
        new(receipts / 'FAILED_PRESERVED.json', dict(status='FAILED_NO_RETRY_METADATA_ONLY',
            error=str(error), traceback=traceback.format_exc(), written=written,
            partial_metadata_never_execution_authority=True, model_imports=0, fit=0, physics=0))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)


if __name__ == '__main__':
    main()
