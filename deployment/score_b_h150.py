"""Run the frozen original B/H150 offline scorer in a new isolated directory.

No runner/physics/training imports. Scientific gates are invoked unchanged.
"""
import argparse
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
CANONICAL = REPO / 'research/side_studies/ihear_overnight_control_learning_transition_v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


class OfflineOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in {'mujoco', 'torch', 'study_common', 'sac_env', 'campaign', 'campaign_r2'}:
            raise RuntimeError('OFFLINE_SCORER_FORBIDS_IMPORT:' + fullname)
        return None


def compare_values(actual, expected, path=''):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), 'KEYS:' + path
        for key in expected:
            if path == '' and key in {'sources', 'execution_lineage_path'}:
                continue  # Original metadata records the new scratch location.
            compare_values(actual[key], expected[key], path + '/' + key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), 'LENGTH:' + path
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare_values(a, b, path + '/' + str(i))
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and math.isfinite(actual) and abs(actual - expected) <= 1e-8, 'VALUE:' + path
    else:
        assert actual == expected, 'VALUE:' + path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True, help='Must not exist; originals are never overwritten')
    args = parser.parse_args()
    if not __debug__:
        parser.error('Do not use Python -O: original frozen assertions are qualification gates')
    sys.dont_write_bytecode = True
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    manifest = json.loads((REPO / 'deployment/b_h150_fixture_manifest.json').read_text())
    inputs = args.fixture_dir.resolve()
    for row in manifest['files']:
        p = inputs / row['path']
        assert p.is_file() and p.stat().st_size == row['bytes'] and digest(p) == row['sha256'], 'FIXTURE_IDENTITY:' + row['path']
    expected_code = json.loads((REPO / 'deployment/b_h150_code_identity.json').read_text())
    for rel, value in expected_code.items():
        assert digest(CANONICAL / rel) == value, 'FROZEN_SOURCE_IDENTITY:' + rel
    root = args.work_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ('code', 'control', 'reports', 'motion_series', 'derived', 'audit'):
        (root / name).mkdir()
    for rel in expected_code:
        if rel.startswith(('code/', 'control/')) or rel == 'MOTION_ACCEPTANCE_PROTOCOL.json':
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CANONICAL / rel, p)
    for row in manifest['files']:
        dest = root / row['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inputs / row['path'], dest)
    sys.meta_path.insert(0, OfflineOnly())
    sys.path[:0] = [str(root / 'code'), str(root / 'control')]
    # Load the exact frozen dependency closure by file, in dependency order.
    # Historical modules insert canonical absolute paths during import. Clear
    # those paths after each import, before importing the next original module.
    legacy = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
    def original_module(name, folder='code'):
        spec = importlib.util.spec_from_file_location(name, root / folder / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        sys.path[:] = [p for p in sys.path if not Path(p).is_relative_to(legacy)]
        return module
    bootstrap = original_module('task_bootstrap')
    stream = original_module('stream_runtime_evidence')
    attribution = original_module('attribution')
    ec = original_module('explore_common')
    am = original_module('analyze_matched')
    independent = original_module('independent_recompute', 'control')
    modules = (bootstrap, stream, am, ec, attribution, independent)
    for module in modules:
        assert Path(module.__file__).resolve().is_relative_to(root), 'NONPORTABLE_IMPORT:' + module.__name__
    am.S = ec.S = root
    independent.P = root
    measurements = {}
    checks = []
    for ident in ('D01R_parent', 'D01R_B', 'D01R_H150'):
        historical = json.loads((inputs / 'reports' / (ident + '_MEASURED.json')).read_text())
        result = am.measure(ident)  # Original promotion assertion remains enabled.
        compare_values(result, historical)
        measurements[ident] = result
        verified = independent.measure(ident)
        checks.append(verified)
        print('ORIGINAL_MEASURE_AND_INDEPENDENT_PASS ' + ident, flush=True)
    comparison = am.compare(measurements['D01R_H150'], measurements['D01R_B'])
    assert comparison['acceptance_pass'], 'ORIGINAL_MOTION_ACCEPTANCE_FAILED'
    assert comparison['gain_percent'] > 0, 'HISTORICAL_GAIN_FAILED'
    for row in manifest['files']:
        assert digest(inputs / row['path']) == row['sha256'], 'ORIGINAL_INPUT_MODIFIED'
    report = dict(status='PASS', scope='OFFLINE_SCORER_REPRODUCIBLE',
                  original_scientific_gates='UNCHANGED_AND_ENABLED',
                  imported_physics_or_training=False, new_physics_starts=0,
                  full_fork_replay='NOT_RUN_NO_PORTABLE_PARENT_CHECKPOINT',
                  metadata_path_binding={'analyze_matched.S': str(root), 'explore_common.S': str(root), 'independent_recompute.P': str(root)},
                  original_code_sha256=expected_code, inputs_verified=len(manifest['files']),
                  original_module_bindings={m.__name__: m.__file__ for m in modules},
                  historical_numeric_tolerance=1e-8, independent_checks=checks, comparison=comparison)
    (root / 'OFFLINE_SCORER_RESULT.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(status=report['status'], result=str(root / 'OFFLINE_SCORER_RESULT.json'),
                          B_J_F=measurements['D01R_B']['J_F_N_s'], H150_J_F=measurements['D01R_H150']['J_F_N_s'],
                          gain_percent=comparison['gain_percent'])), flush=True)


if __name__ == '__main__':
    main()
