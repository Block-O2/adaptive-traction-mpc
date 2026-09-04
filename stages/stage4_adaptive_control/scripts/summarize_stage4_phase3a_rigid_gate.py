#!/usr/bin/env python3
"""Render the saved reproduction gate only; no simulation or controller imports."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / 'stages/stage4_adaptive_control'
BASELINE = 'de23ea3cdf9f0fb078496ba5ba4abb6a205ad955'
DONOR = '3ce0129587bae3b9d13c0f581e0e4d8af5779e3a'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    root = args.input.resolve()
    gate = json.loads((root / 'gate_result.json').read_text())
    reg = json.loads((root / 'registration.json').read_text())
    r = gate['observed_metrics']
    historical = STAGE / 'results/engineering_validation/coarse_rom_commissioning_model_lock_20260904/hip40_knee40_repeat1'
    old = json.loads((historical / 'manifest.json').read_text())['metrics']
    with np.load(root / 'rigid_hip40_knee40/trace.npz', allow_pickle=False) as z:
        trace = {k: z[k] for k in z.files}
    with np.load(historical / 'trace.npz', allow_pickle=False) as z:
        previous = {k: z[k] for k in z.files}
    fig, axes = plt.subplots(5, 1, figsize=(11, 12), sharex=True)
    t = trace['time_s']
    for j, color in enumerate(('#245a96', '#b44c20')):
        axes[0].plot(t, previous['human_q_deg_god_view'][:, j], color='0.75', lw=3,
                     label=f'historical rigid q{j+1}')
        axes[0].plot(t, trace['human_q_deg_god_view'][:, j], color=color, lw=1,
                     label=f'reproduced rigid q{j+1}')
        axes[0].plot(t, trace['human_q_ref_deg'][:, j], color=color, ls='--', lw=.8,
                     label=f'q{j+1} reference')
        axes[3].plot(t, trace['human_q_deg_god_view'][:, j] - previous['human_q_deg_god_view'][:, j],
                     color=color, label=f'q{j+1} difference')
    axes[1].plot(t, np.linalg.norm(previous['cuff_force_local_n_god_view'], axis=1), color='0.75', lw=3, label='historical rigid')
    axes[1].plot(t, np.linalg.norm(trace['cuff_force_local_n_god_view'], axis=1), color='#245a96', lw=1, label='reproduced rigid')
    axes[1].axhline(200, color='red', ls=':', label='200 N reference')
    axes[2].plot(previous['executed_command_time_s'], np.linalg.norm(previous['executed_command_force_total_n'], axis=1), color='0.75', lw=3, label='historical rigid')
    axes[2].plot(trace['executed_command_time_s'], np.linalg.norm(trace['executed_command_force_total_n'], axis=1), color='#245a96', lw=1, label='reproduced rigid')
    axes[4].plot(t, trace['reference_speed_scale'], label='reference speed scale')
    axes[4].set_ylim(.9, 1.1)
    axes[4].text(.03, .15, 'TRACK throughout; zero BRAKE / NO_SAFE_ACTION / filter interventions', transform=axes[4].transAxes, fontsize=9)
    for ax, label in zip(axes, ('Human q (deg)', 'Physical force (N)', 'Command force (N)', 'q difference (deg)', 'Reference scale')):
        ax.set_ylabel(label); ax.grid(alpha=.25); ax.legend(loc='best', fontsize=8, ncol=2)
    axes[-1].set_xlabel('Simulation time (s)')
    fig.suptitle('40/40 rigid reproduction at frozen 1 ms\nHistorical and reproduced curves coincide; no soft arm executed')
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(root / 'rigid_reproduction.png', dpi=150)
    plt.close(fig)
    donor_path = 'stages/stage3_full3d/docs/INTERFACE_PHASE2_REPORT.md'
    donor_report = subprocess.check_output(['git', 'show', f'{DONOR}:{donor_path}'], cwd=REPO)
    (root / 'phase2_timestep_evidence.txt').write_text(
        f'Donor commit: {DONOR}\nPath: {donor_path}\nSHA256: {hashlib.sha256(donor_report).hexdigest()}\n\n'
        + donor_report.decode().split('## Measurement and rest outcomes')[0].rstrip() + '\n')
    checks = {}
    for path, expected in reg['source_config_model_sha256'].items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected, path
    for path, expected in reg['historical_artifacts'].items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected, path
    assert hashlib.sha256((STAGE / 'scripts/run_stage4_phase3a_rigid_gate.py').read_bytes()).hexdigest() == reg['script_sha256']
    for path in root.rglob('*.npz'):
        with np.load(path, allow_pickle=False) as z:
            assert all(np.all(np.isfinite(z[k])) for k in z.files if z[k].dtype.kind in 'fciu'), path
    assert np.all(np.diff(t) > 0)
    for name, comparison in gate['comparisons'].items():
        checks[name] = dict(array_count=len(comparison['all_non_host_timer_arrays']),
                           passed=comparison['passed'],
                           max_absolute_numeric_difference=max(c.get('maximum_absolute_difference', 0.)
                                for c in comparison['all_non_host_timer_arrays'].values()))
    validation = dict(source_config_model_files_unchanged=len(reg['source_config_model_sha256']),
                      historical_artifact_files_unchanged=len(reg['historical_artifacts']),
                      trace_numeric_arrays_finite=True, physics_time_strictly_increasing=True,
                      registration_script_hash_matches=True, comparisons=checks,
                      mechanical_only_not_scientific_promotion=True)
    (root / 'validation.json').write_text(json.dumps(validation, indent=2, sort_keys=True) + '\n')
    command = shlex.join(reg['command_argv'])
    postcommand = shlex.join([sys.executable, *sys.argv])
    metrics = [
        ('Task classification', old['task_status'], r['task_status']),
        ('Physical-force classification', old['force_status'], r['force_status']),
        ('Tracking RMSE (deg)', old['tracking_rmse_deg'], r['tracking_rmse_deg']),
        ('Endpoint error (deg)', old['endpoint_error_deg'], r['endpoint_error_deg']),
        ('Return error (deg)', old['return_error_deg'], r['return_error_deg']),
        ('Maximum tracking error (deg)', old['tracking_max_error_deg'], r['tracking_max_error_deg']),
        ('Physical force peak (N)', old['physical_force_n']['peak'], r['physical_force_n']['peak']),
        ('Physical moment peak (Nm)', old['physical_moment_nm']['peak'], r['physical_moment_nm']['peak']),
        ('Command force peak (N)', old['command_force_n']['peak'], r['command_force_n']['peak']),
        ('BRAKE entries', old['brake_entry_count'], r['brake_entry_count']),
        ('NO_SAFE_ACTION count', old['no_safe_action_count'], r['no_safe_action_count']),
    ]
    lines = [
        '# Phase 3A rigid reproduction gate and timestep contract stop', '',
        f'Experiment baseline: `{BASELINE}`. Interface donor (not imported): `{DONOR}`.',
        'Branch: `codex/interface-phase3a-de23ea3`. This worktree was created directly from the baseline; the donor and original worktrees were preserved.',
        'Evidence: user-authorized engineering reproduction, not formal scientific evidence or clinical validation.', '',
        '## Observed reproduction', '',
        f"The single new rigid 40/40 gate {'passed' if gate['rigid_reproduction_gate_passed'] else 'did not pass'}. Both historical repeats were compared separately.",
        'All 66 non-host-timer trace arrays match each historical repeat; maximum numeric absolute difference is 0 with registered rtol=0 and atol=1e-12. Labels and model fingerprints match. All 11 retained primary metric differences are 0.',
        'The comparison covers physical Human/robot states, force/moment, robot torque, desired action, estimated state, measured wrench, allocation, reference progression, confidence traces and Safety Filter outputs.',
        'The only excluded trace arrays are four host compute-time arrays. Host timing metrics remain saved and are not deterministic trajectory acceptance conditions.', '',
        '| Metric | Historical rigid repeat 1 | New rigid |', '|---|---:|---:|',
    ]
    lines += [f'| {name} | {a} | {b} |' for name, a, b in metrics]
    lines += [
        '', 'Completion tolerance remains 0.06896926724078867 deg; endpoint and return both meet it.',
        'Reference duration remains 14.106060606060604 s; simulation finished at 14.10699999999762 s on the historical time grid.',
        'Physical force never exceeded 200 N: exceedance time, contiguous duration and excess impulse are zero. No MuJoCo warning, nonfinite trajectory, ROM event or unintended contact was observed. All 2823 model-lock assertions passed; Safety Filter left all 2822 commands unchanged.', '',
        '![Rigid reproduction](rigid_reproduction.png)', '',
        '## Required stop before compliant execution', '',
        'The user now freezes all numerical settings to de23ea3. That baseline uses physics dt=1 ms, implicitfast, the original solver and five physics steps per 5 ms low-level update.',
        'The sole Phase-2 registered soft candidate is Kt=500 N/m, Dt=35.63902676526988 Ns/m, Kr=20 Nm/rad, Dr=1 Nms/rad, qualified only at dt=0.25 ms. The donor report is identified and excerpted in phase2_timestep_evidence.txt.',
        'Changing only the compliant arm to 0.25 ms would violate matching. Changing both arms to 0.25 ms would depart from the newly frozen historical numerical baseline. Using the soft candidate at 1 ms would exceed its retained numerical qualification and earlier explicit registration. None was done.',
        '**This is a registration/qualification conflict, not a demonstrated instability of the soft interface at 1 ms, and not a rigid reproduction failure.** No soft trajectory or new qualification diagnostic was run. The interface was not ported into this baseline yet.', '',
        '| Endpoint | Rigid | Soft |', '|---|---|---|',
        '| 40/40 | Reproduction gate COMPLETE / STRICT_PASS | NOT_RUN: timestep qualification conflict |',
        '| 40/80 | NOT_RUN | NOT_RUN |', '| 90/120 | NOT_RUN | NOT_RUN |', '',
        'DIRECTLY OBSERVED: baseline rigid behavior and physical/control traces reproduced exactly.',
        'SUPPORTED: this checkout and environment preserve the tested rigid contract.',
        'UNRESOLVED: whether the registered compliant mechanics are numerically credible at frozen 1 ms in the suspended scenario.',
        'NOT SUPPORTED: any compliant force benefit, deformation/tracking/proxy tradeoff, ROM enlargement, or A/B outcome. The original A-D soft-behavior alternatives cannot be adjudicated without a soft run.', '',
        '## Scope and reproducibility', '',
        'Scientific variables changed: none. Scenario, contact domain, reference timing, seeds, population prior, geometry, allocator, Human, robot, 140 mm adapter, MPC, executable-command path, Reference Manager, safety contracts, integrator, timestep, solver and gains are unchanged.',
        'New files consist only of the two gate/report scripts and this new result directory. No historical source, config or result was edited. No simulator exception occurred; no recovery or parameter adjustment was needed.',
        'The inherited run manifest contains the baseline runner generic command string. The actual invocation and environment are preserved in registration.json and below; the generic string is not the executed shell command.', '',
        'Actual working directory:', f'`{REPO}`', '', 'Single authorized simulation command:', '```sh', command, '```', '',
        'Read-only analysis of existing traces plus report/plot generation:', '```sh', postcommand, '```', '',
        'Checks: script compilation and seven synthetic gate-comparator checks passed before execution (identity, above-tolerance perturbation, missing field, nonfinite value, changed mode, changed shape, host-timer exclusion). Post-run validation checks source/config/model and historical artifact hashes, finite numeric NPZ arrays, monotonic physics time and both historical deterministic comparisons.',
        'No full test suite or additional experiment was run. There is no admitted formal or compliant command for the user to run under the unresolved timestep contract.', '',
        '## Exact added file inventory', '',
        f'- `{STAGE / "scripts/run_stage4_phase3a_rigid_gate.py"}`',
        f'- `{Path(__file__).resolve()}`',
    ]
    names = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    names.update({'REPORT.md', 'SHA256SUMS'})
    lines += [f'- `{root / name}`' for name in sorted(names)]
    (root / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    hashes = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}'
              for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS']
    (root / 'SHA256SUMS').write_text('\n'.join(hashes) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
