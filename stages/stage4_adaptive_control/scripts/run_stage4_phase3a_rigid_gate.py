#!/usr/bin/env python3
"""One unchanged de23ea3 rigid 40/40 reproduction; never runs a soft arm."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / 'stages/stage4_adaptive_control'
for stage in ('stage3_full3d', 'stage4_adaptive_control'):
    sys.path.insert(0, str(REPO / 'stages' / stage / 'src'))
import mujoco
import numpy as np
import run_stage4_coarse_rom_capability as base
import run_stage4_model_locked_commissioning as commissioning

BASELINE = 'de23ea3cdf9f0fb078496ba5ba4abb6a205ad955'
CANONICAL = commissioning.OUTPUT
RUN_NAME = 'rigid_hip40_knee40'
ATOL = commissioning.DETERMINISTIC_ATOL
HOST_TIMERS = {'model_lock_assertion_compute_ms', 'safety_filter_compute_ms',
               'safety_layer_compute_ms', 'high_level_fast_path_compute_ms'}


def write(path, value):
    path.write_text(json.dumps(base.clean(value), indent=2, sort_keys=True, allow_nan=False) + '\n')


def load_trace(path):
    with np.load(path, allow_pickle=False) as saved:
        return {key: saved[key] for key in saved.files}


def compare_arrays(old, new):
    checks = {}
    for key in sorted(set(old) | set(new)):
        if key in HOST_TIMERS:
            continue
        if key not in old or key not in new:
            checks[key] = dict(passed=False, reason='missing_array')
            continue
        a, b = old[key], new[key]
        if a.shape != b.shape or a.dtype != b.dtype:
            checks[key] = dict(passed=False, reason='shape_or_dtype_mismatch',
                               historical_shape=list(a.shape), new_shape=list(b.shape))
        elif a.dtype.kind in 'fciu':
            finite = bool(np.all(np.isfinite(a)) and np.all(np.isfinite(b)))
            delta = float(np.max(np.abs(a.astype(float) - b.astype(float)))) if a.size else 0.
            checks[key] = dict(passed=finite and delta <= ATOL, finite=finite,
                               maximum_absolute_difference=delta if finite else None)
        else:
            checks[key] = dict(passed=bool(np.array_equal(a, b)), comparison='exact')
    return checks


def analyze(output):
    run = output / RUN_NAME
    spec = json.loads((output / commissioning.SPEC_NAME).read_text())
    if not (run / 'manifest.json').exists():
        # Reuse historical postprocessing recovery, redirecting only its output.
        commissioning.OUTPUT = output
        commissioning.recover_saved_repeat(spec['endpoint'], spec, RUN_NAME)
    row = json.loads((run / 'manifest.json').read_text())['metrics']
    trace = load_trace(run / 'trace.npz')
    comparisons = {}
    for name in ('hip40_knee40_repeat1', 'hip40_knee40_repeat2'):
        old = CANONICAL / name
        old_row = json.loads((old / 'manifest.json').read_text())['metrics']
        old_trace = load_trace(old / 'trace.npz')
        primary = commissioning.compare_repeats([old_row, row], [old_trace, trace])
        arrays = compare_arrays(old_trace, trace)
        comparisons[name] = dict(primary_comparison=primary, all_non_host_timer_arrays=arrays,
                                 passed=primary['passed'] and all(c['passed'] for c in arrays.values()))
    summary = json.loads((run / 'raw_summary.json').read_text())
    events = summary['events']
    passed = bool(commissioning.acceptance(row) and all(c['passed'] for c in comparisons.values())
                  and not events['mujoco_warning_counts'] and not events['unintended_contact_pairs']
                  and not events['rom_event_samples'])
    result = dict(schema='phase3a_rigid_reproduction_gate_v1',
                  evidence_category='user_authorized_engineering_reproduction_not_formal',
                  baseline_commit=BASELINE, rtol=0., atol=ATOL,
                  rigid_reproduction_gate_passed=passed, comparisons=comparisons,
                  excluded_host_timers=sorted(HOST_TIMERS),
                  exclusion_reason='Host compute duration is not a physical or control trajectory.',
                  observed_metrics=row, events=events, soft_arm_executed=False,
                  other_endpoints_executed=False,
                  next_action='STOP_REGISTERED_SOFT_TIMESTEP_CONFLICT' if passed else 'STOP_RIGID_REPRODUCTION_MISMATCH',
                  timestep_contract=dict(frozen_de23ea3_rigid_dt_s=.001,
                      phase2_qualified_soft_dt_s=.00025, non_interface_numeric_changes_authorized=False,
                      soft_at_1ms_qualified=False, does_not_establish_that_soft_at_1ms_is_unstable=True))
    write(output / 'gate_result.json', result)
    print(json.dumps({k: result[k] for k in ('rigid_reproduction_gate_passed', 'soft_arm_executed', 'next_action')}), flush=True)
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.analyze_only:
        return 0 if analyze(output) else 2
    spec_path = CANONICAL / commissioning.SPEC_NAME
    spec = json.loads(spec_path.read_text())
    assert base.sha(spec_path) == 'dabea8f7a493a41d898dcefeb9b6ac89b88aac5517b7af9ac901c6c7ba635c60'
    assert base.sha(REPO / spec['additive_to_base_scan_spec']) == spec['base_scan_spec_sha256']
    for path, expected in spec['wiring_source_hashes'].items():
        assert base.sha(REPO / path) == expected, path
    frozen_paths = [f'stages/{stage}/{directory}' for stage in ('stage3_full3d', 'stage4_adaptive_control')
                    for directory in ('src', 'configs', 'models')]
    subprocess.run(['git', 'diff', '--exit-code', BASELINE, '--', *frozen_paths], cwd=REPO, check=True)
    source_files = subprocess.check_output(['git', 'ls-files', '--', *frozen_paths], cwd=REPO, text=True).splitlines()
    source_hashes = {path: base.sha(REPO / path) for path in source_files}
    plant = base.CapturePlant(base.HIGH_ROM_HUMAN)
    assert plant.model.opt.timestep == .001
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(spec_path, output / commissioning.SPEC_NAME)
    shutil.copyfile(REPO / spec['additive_to_base_scan_spec'], output / 'base_scan_spec.json')
    write(output / 'registration.json', dict(
        baseline_commit=BASELINE,
        source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        command_argv=[sys.executable, *sys.argv], cwd=str(REPO), script_sha256=base.sha(Path(__file__)),
        source_config_model_sha256=source_hashes,
        historical_artifacts={str(p.relative_to(REPO)): base.sha(p)
            for repeat in ('hip40_knee40_repeat1', 'hip40_knee40_repeat2')
            for p in sorted((CANONICAL / repeat).iterdir()) if p.is_file()},
        environment=dict(python=sys.version, numpy=np.__version__, mujoco=mujoco.__version__, platform=platform.platform()),
        physics=dict(dt_s=plant.model.opt.timestep, integrator=int(plant.model.opt.integrator),
                     solver=int(plant.model.opt.solver), iterations=int(plant.model.opt.iterations),
                     tolerance=float(plant.model.opt.tolerance)),
        allowed_runs=[RUN_NAME], soft_execution_allowed_by_this_script=False, rtol=0., atol=ATOL,
        scientific_changes=[]))
    print('RUN_ONE_RIGID_40_40_AT_HISTORICAL_1MS', flush=True)
    try:
        base.run_point(spec['endpoint'], spec, output, run_name=RUN_NAME,
                       freeze_control_geometry=True, spec_filename=commissioning.SPEC_NAME)
    except Exception:
        (output / 'run_exception.txt').write_text(traceback.format_exc())
        raise
    assert all(base.sha(REPO / path) == value for path, value in source_hashes.items())
    return 0 if analyze(output) else 2


if __name__ == '__main__':
    raise SystemExit(main())
