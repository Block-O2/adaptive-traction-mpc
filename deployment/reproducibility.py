"""Portable identity checks shared by deployment entry points (no physics)."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / 'deployment/configs/b_h150_original_v1.json'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def repository_path(relative):
    path = (REPO / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(REPO):
        raise ValueError('REPOSITORY_PATH_REQUIRED:' + relative)
    return path


def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text())
    if config['schema'] != 'ihear.original_offline_scoring.v1':
        raise ValueError('UNSUPPORTED_CONFIG_SCHEMA')
    # Configuration selects the unchanged historical experiment, never thresholds.
    if config['ids'] != ['D01R_parent', 'D01R_B', 'D01R_H150']:
        raise ValueError('ORIGINAL_D01R_IDENTITIES_REQUIRED')
    for key in ('fixture_root', 'fixture_manifest', 'code_identity', 'model_manifest', 'plan', 'dependency_lock'):
        repository_path(config[key])
    return config


def check_rows(root, rows, label):
    errors = []
    for row in rows:
        path = (root / row['path']).resolve()
        if (not path.is_relative_to(root.resolve()) or not path.is_file()
                or (root / row['path']).is_symlink()
                or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']):
            errors.append(label + ':' + row['path'])
    return errors


def verify_inputs(config, fixture_dir=None):
    canonical = repository_path(config['fixture_root'])
    fixture = Path(fixture_dir).resolve() if fixture_dir else canonical
    manifest = json.loads(repository_path(config['fixture_manifest']).read_text())
    errors = check_rows(fixture, manifest['files'], 'FIXTURE_IDENTITY')
    identities = json.loads(repository_path(config['code_identity']).read_text())
    for relative, expected in identities.items():
        p = canonical / relative
        if not p.is_file() or digest(p) != expected:
            errors.append('FROZEN_SOURCE_IDENTITY:' + relative)
    model_manifest = json.loads(repository_path(config['model_manifest']).read_text())
    errors += check_rows(REPO, model_manifest['files'], 'MODEL_IDENTITY')
    frozen = json.loads((REPO / 'research/side_studies/ihear_cross_patient_b_h150_v1/audit_execution/FROZEN_SOURCE_CHAIN_HASHES.json').read_text())['files']
    for relative, expected in frozen.items():
        p = canonical / relative
        if not p.is_file() or digest(p) != expected:
            errors.append('ORIGINAL_SOURCE_ANCHOR:' + relative)
    v6 = json.loads((canonical / 'EXECUTION_CODE_MANIFEST_v6.json').read_text())['files']
    for relative, expected in v6.items():
        p = canonical / relative
        if not p.is_file() or digest(p) != expected:
            errors.append('ORIGINAL_V6_IDENTITY:' + relative)
    for relative, expected in config['frozen_contracts'].items():
        p = canonical / relative
        if not p.is_file() or digest(p) != expected:
            errors.append('FROZEN_CONTRACT_IDENTITY:' + relative)
    plan = json.loads(repository_path(config['plan']).read_text())
    if plan['condition']['seed'] != config['seed']:
        errors.append('ORIGINAL_SEED_MISMATCH')
    actual_candidates = {r['id']: r['candidate_hash'] for r in plan['arms'] if r['id'] in ('B', 'H150')}
    if actual_candidates != config['candidate_hashes']:
        errors.append('ORIGINAL_CANDIDATE_MISMATCH')
    return dict(status='FAIL' if errors else 'PASS', fixture_files=len(manifest['files']),
                fixture_bytes=sum(r['bytes'] for r in manifest['files']), frozen_scorer_files=len(identities),
                frozen_contracts=len(config['frozen_contracts']), original_source_anchors=len(frozen),
                original_v6_files=len(v6), model_files=len(model_manifest['files']), errors=errors,
                physics='NOT_RUN', full_fork_replay='NOT_RUN_NO_COMPLETE_PARENT_CHECKPOINT')


def provenance(config_path, config):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(REPO), *args], text=True).strip()
    manifest = json.loads(repository_path(config['fixture_manifest']).read_text())
    return dict(schema='ihear.run_provenance.v1', source_commit=git('rev-parse', 'HEAD'),
                source_dirty=bool(git('status', '--porcelain', '--untracked-files=all')),
                source_diff_sha256=hashlib.sha256(subprocess.check_output(['git', '-C', str(REPO), 'diff', 'HEAD', '--binary'])).hexdigest(),
                published_source_payload_commit=config['published_source_payload_commit'],
                historical_generation_source_commit='UNKNOWN_USE_ORIGINAL_HASH_MANIFESTS',
                config_sha256=digest(config_path), input_data_id=config['input_data_id'],
                inputs={r['path']: r['sha256'] for r in manifest['files']},
                model_manifest_sha256=digest(repository_path(config['model_manifest'])),
                code_identity_sha256=digest(repository_path(config['code_identity'])),
                maintenance_entry_hashes={n: digest(REPO / 'deployment' / n) for n in ('score_b_h150.py', 'reproducibility.py')},
                frozen_contracts=config['frozen_contracts'], candidate_hashes=config['candidate_hashes'],
                seed=config['seed'], seed_role='historical_generation_seed_no_random_rollout_this_run',
                dependency_lock_sha256=digest(repository_path(config['dependency_lock'])),
                runtime=dict(python=platform.python_version(), platform=platform.platform(),
                             packages={p: importlib.metadata.version(p) for p in ('numpy', 'scipy')}),
                command=[sys.executable, *sys.argv], physics_steps=0, training='NOT_RUN')
