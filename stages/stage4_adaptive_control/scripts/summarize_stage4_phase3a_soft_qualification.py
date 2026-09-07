#!/usr/bin/env python3
"""Saved-evidence report only. No plant/controller imports and no trajectory execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
ROOT=STAGE/'results/engineering_validation/phase3a_soft_1ms_qualification_20260904_v1'
SPEC='PHASE3A_1MS_QUALIFICATION_SPEC_APPROVED'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load_npz(p):
    with np.load(p,allow_pickle=False) as z: return {k:z[k] for k in z.files}
def norm(x): return np.linalg.norm(x,axis=1)
def write(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')


def main():
    s=json.loads((ROOT/(SPEC+'.json')).read_text()); impl=json.loads((ROOT/'implementation_registration.json').read_text())
    status=json.loads((ROOT/'campaign_status.json').read_text())
    for suffix,h in impl['spec_sha256'].items():
        assert sha(ROOT/(SPEC+suffix))==h and sha(STAGE/'docs'/(SPEC+suffix))==h
    for p,h in impl['hashes'].items(): assert sha(REPO/p)==h,p
    for p,h in impl['original_source_config_model_sha256'].items(): assert sha(REPO/p)==h,p
    existing=[r for r in s['runs'] if (ROOT/r['id']/'result.json').exists()]
    # This report focuses on the observed early-stop campaign. Do not manufacture
    # a repeat or a fine-reference comparison when those trajectories did not run.
    assert len(existing)==1 and status['stop'] and status['overall']=='FAIL'
    run=existing[0]; d=ROOT/run['id']; r=json.loads((d/'result.json').read_text())
    summary=json.loads((d/'raw_summary.json').read_text()); p=load_npz(d/'mechanics.npz'); c=load_npz(d/'trace.npz'); m=load_npz(d/'modes.npz')
    t=p['time_s']; ct=c['control_time_s']; local=r['local_checks']
    assert len(t)==len(c['time_s']) and np.array_equal(t,c['time_s'])
    eq=np.degrees(c['control_estimated_state'][:,:2]-c['control_true_q_rad_god_view'])
    edq=np.degrees(c['control_estimated_state'][:,2:]-c['control_true_dq_rad_s_god_view'])
    proxy={}
    for name,e in [('q',eq),('dq',edq)]:
        proxy[name]=dict(rmse_per_joint=np.sqrt(np.mean(e**2,axis=0)).tolist(),
            peak_abs_per_joint=np.max(np.abs(e),axis=0).tolist(),
            peak_time_s_per_joint=ct[np.argmax(np.abs(e),axis=0)].tolist(),
            final_control_sample_error=e[-1].tolist(),final_control_sample_time_s=float(ct[-1]))
    rom_min=0.; bad=np.flatnonzero(np.any(np.degrees(p['q_true_rad'])<rom_min-np.degrees(1e-9),axis=1))
    assert len(bad) and summary['events']['rom_event_samples']==1
    first=int(bad[0]); command_peak=float(np.max(norm(c['executed_command_force_total_n'])))
    deformation=norm(p['deformation_H']); rotation=norm(p['rotation_vector_H'])
    rms=lambda x: float(np.sqrt(np.trapezoid(x*x,t)/(t[-1]-t[0])))
    diagnostics=dict(
        interval_s=[float(t[0]),float(t[-1])],physics_samples=len(t),control_samples=len(ct),
        first_human_rom_violation_time_s=float(t[first]),
        true_q_deg_at_stop=np.degrees(p['q_true_rad'][-1]).tolist(),
        true_dq_deg_s_at_stop=np.degrees(p['dq_true_rad_s'][-1]).tolist(),
        previous_sample_time_s=float(t[first-1]),previous_sample_q_deg=np.degrees(p['q_true_rad'][first-1]).tolist(),
        command_force_peak_n=command_peak,physical_force_peak_n=r['diagnostics']['force_peak_n'],
        translation_peak_mm=1000*float(np.max(deformation)),translation_rms_mm=1000*rms(deformation),
        final_translation_H_mm=(1000*p['deformation_H'][-1]).tolist(),
        rotation_peak_deg=float(np.degrees(np.max(rotation))),rotation_rms_deg=float(np.degrees(rms(rotation))),
        final_rotation_H_deg=np.degrees(p['rotation_vector_H'][-1]).tolist(),
        relative_velocity_peak_m_s=float(np.max(norm(p['relative_velocity_H']))),
        relative_angular_velocity_peak_rad_s=float(np.max(norm(p['relative_angular_velocity_H']))),
        robot_port_work_j=float(p['work_R'][-1]),human_port_work_j=float(p['work_H'][-1]),
        stored_energy_peak_j=float(np.max(p['stored_energy'])),damping_energy_final_j=float(p['cumulative_damping_loss'][-1]),
        time_above_200_n_s=0.,excess_impulse_above_200_n_ns=0.,
        target_endpoint_error_deg=None,return_endpoint_error_deg=None,
        note='Endpoint and return were not reached. Inherited result.json return_error_deg is only early-stop distance from start, not a completed return error.',
        proxy_diagnostics_offline_only=proxy)
    assert np.max(norm(p['force_R_world']))<200 # validates the explicit zero exceedance metrics
    verdicts={
      'MECHANICS_CONSISTENCY':dict(verdict=r['MECHANICS_CONSISTENCY'],scope='Recorded 0-0.118 s prefix only; not the full registered trajectory',evidence=local),
      'DISCRETE_ENERGY':dict(verdict=r['DISCRETE_ENERGY'],scope='Recorded 0-0.118 s prefix only',max_abs_residual_ratio=local['normalized_max_abs_energy_residual'],max_positive_residual_ratio=local['normalized_max_positive_energy_residual']),
      'CLOSED_LOOP_TIMESTEP_AGREEMENT':dict(verdict='NOT_EVALUATED',reason='Repeat 2 and matched 0.25 ms reference not run after mandatory coverage stop'),
      'TASK_RESULT':dict(verdict=r['TASK_RESULT'],termination_reason=r['termination_reason'],specific_trigger='Human hip below frozen 0 degree ROM bound during initial hold',time_s=float(t[-1])),
      'FORCE_CONTRACT':dict(verdict=r['FORCE_CONTRACT'],scope='Recorded prefix only; no force violation',physical_force_peak_n=r['diagnostics']['force_peak_n'],command_force_peak_n=command_peak)}
    report=dict(approved_spec_sha256=impl['spec_sha256'],overall_numerical_qualification='FAIL',
        exact_cause='FAIL_EVIDENCE_INCOMPLETE: existing Human ROM guard terminated first 1 ms run at 0.118 s before reference motion began',
        verdicts=verdicts,deterministic_repeat='NOT_EVALUATED',timestep_comparison='NOT_EVALUATED',independent_2n_force_peak_gate='NOT_EVALUATED',
        rigid_vs_compliant_ab_authorized_next=False,executed_runs=[run['id']],not_run=[x['id'] for x in s['runs'][1:]],
        additional_trajectories=0,threshold_changes_after_execution=False,diagnostics=diagnostics,
        unsupported_claims=['interface integration is unstable','CEM or reference manager is timestep-sensitive','fine timestep would fix the ROM event','global or clinical safety','full 40/40 mechanics or energy qualification'])
    write(ROOT/'final_verdicts.json',report)
    # Synchronized physical/proxy/command diagnostics from the one preserved run.
    fig,axes=plt.subplots(7,1,figsize=(11,17),sharex=True)
    colors=['#215b96','#c65a24']
    for j,col in enumerate(colors):
        axes[0].plot(t,np.degrees(p['q_true_rad'][:,j]),color=col,label=f'q{j+1} true')
        axes[0].plot(ct,np.degrees(c['control_estimated_state'][:,j]),color=col,ls='--',label=f'q{j+1} proxy')
        axes[0].plot(t,c['human_q_ref_deg'][:,j],color=col,ls=':',label=f'q{j+1} reference')
        axes[4].plot(ct,eq[:,j],color=col,label=f'q{j+1} proxy error')
    axes[0].axhline(0,color='red',lw=.8,label='Human ROM lower bound')
    axes[1].plot(t,norm(p['force_R_world']),label='Physical transmitted force')
    axes[1].plot(c['executed_command_time_s'],norm(c['executed_command_force_total_n']),label='Executable command force')
    axes[1].axhline(200,color='red',ls=':',label='Existing 200 N reference')
    for j,col in enumerate(['#215b96','#c65a24','#527e49']):
        axes[2].plot(t,1000*p['deformation_H'][:,j],color=col,label=f'H-frame {"xyz"[j]}')
        axes[3].plot(t,np.degrees(p['rotation_vector_H'][:,j]),color=col,label=f'H-frame {"xyz"[j]}')
    axes[2].plot(t,1000*deformation,color='black',ls='--',label='norm')
    axes[3].plot(t,np.degrees(rotation),color='black',ls='--',label='norm')
    axes[5].plot(t,100*p['energy_residual']/local['energy_scale_j'],label='Energy balance residual / S (%)')
    axes[5].axhline(1,color='red',ls=':',label='Abs residual limit 1%')
    axes[5].axhline(-1,color='red',ls=':')
    axes[5].axhline(.5,color='orange',ls=':',label='Positive residual limit 0.5%')
    axes[6].plot(t,c['reference_speed_scale'],label='Reference speed scale')
    axes[6].text(.03,.12,'TRACK; no BRAKE, NO_SAFE_ACTION or filter intervention\nStop: hip ROM violation during initial hold',transform=axes[6].transAxes,fontsize=9)
    axes[6].set_ylim(.8,1.2)
    labels=['q (deg)','Force (N)','Translation (mm)','Rotation (deg)','Proxy error (deg)','Energy residual (%)','Reference scale']
    for ax,label in zip(axes,labels):
        ax.set_ylabel(label);ax.grid(alpha=.25);ax.legend(fontsize=8,ncol=2,loc='best');ax.axvline(t[-1],color='red',alpha=.5)
    axes[-1].set_xlabel('Physical time (s)')
    fig.suptitle('Compliant 40/40, 1 ms repeat 1: mandatory stop at 0.118 s\nNo repeat 2 or fine-reference trajectory executed')
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(ROOT/'early_stop_diagnostics.png',dpi=150);plt.close(fig)
    rows=[('Physical force peak (N)',r['diagnostics']['force_peak_n']),('Command force peak (N)',command_peak),
          ('R-referenced moment peak (Nm)',r['diagnostics']['moment_R_peak_nm']),('H-referenced moment peak (Nm)',r['diagnostics']['moment_H_peak_nm']),
          ('Translation peak (mm)',diagnostics['translation_peak_mm']),('Rotation peak (deg)',diagnostics['rotation_peak_deg']),
          ('Stored energy peak (J)',diagnostics['stored_energy_peak_j']),('Damping loss (J)',diagnostics['damping_energy_final_j']),
          ('Max abs energy residual (%)',100*local['normalized_max_abs_energy_residual']),('Max positive energy residual (%)',100*local['normalized_max_positive_energy_residual'])]
    lines=['# Phase 3A compliant 40/40 numerical qualification: stopped on coverage', '',
      '**Overall: FAIL_EVIDENCE_INCOMPLETE.** Only 1 ms repeat 1 ran. The frozen Human ROM guard terminated it at 0.118 s when hip q1=-0.0249297231631465 deg crossed the existing 0 deg lower bound. Initial hold lasts 1 s, so outbound motion had not begun.',
      'This is neither a demonstrated interface/mechanics numerical failure nor a measured closed-loop timestep disagreement. Repeat 2 and the 0.25 ms matched reference were not admitted after the first run stopped.', '',
      '## Approved Spec SHA256', '',
      f"- MD: `{impl['spec_sha256']['.md']}`",f"- JSON: `{impl['spec_sha256']['.json']}`", '',
      'The original 5% Linf, 2% L2, energy budgets and independent 2 N physical-force peak difference gate remain frozen. The 2 N gate was not evaluated because the fine-reference run was not executed. The 200 N/transient contract was not changed.', '',
      '## Five separate verdicts', '', '| Category | Verdict | Scope |', '|---|---|---|',
      '| MECHANICS_CONSISTENCY | PASS on recorded prefix | finite; no warnings; port/action-reaction and instantaneous power checks |',
      '| DISCRETE_ENERGY | PASS on recorded prefix | max absolute residual 0.0396451%; max positive residual 0.00794321% |',
      '| CLOSED_LOOP_TIMESTEP_AGREEMENT | NOT_EVALUATED | no repeat 2 or matched fine reference; coverage gate failed |',
      '| TASK_RESULT | UNSAFE_TERMINATION | Human ROM event, not force or robot limit; initial hold only |',
      '| FORCE_CONTRACT | STRICT_PASS on recorded prefix | physical peak below 200 N; command also below 200 N |', '',
      'PASS on a recorded prefix does not qualify the full 40/40 trajectory. Overall numerical qualification therefore fails and rigid-vs-compliant Phase 3A A/B is **not authorized next** by this gate.', '',
      '## Run inventory and requested timestep comparison', '',
      '| Run | Execution | Repeat/coverage result |', '|---|---|---|',
      '| 1 ms repeat 1 | EXECUTED; 119 physics samples, 24 control samples | stopped at 0.118 s |',
      '| 1 ms repeat 2 | NOT_RUN | mandatory incomplete-coverage stop |',
      '| 0.25 ms matched reference | NOT_RUN | mandatory incomplete-coverage stop |', '',
      '1 ms deterministic repeatability is NOT_EVALUATED. Cross-dt waveform/force-peak/deformation/energy differences are N/A. The old 0.3 s mechanics fixture is not substituted as a matched reference.', '',
      '| Metric | 1 ms recorded prefix | 0.25 ms matched reference |', '|---|---:|---|']
    lines += [f'| {name} | {value:.10g} | NOT_RUN |' for name,value in rows]
    lines += ['',f"Final true hip/knee: {diagnostics['true_q_deg_at_stop']} deg; preceding sample at {diagnostics['previous_sample_time_s']:.3f} s: {diagnostics['previous_sample_q_deg']} deg.",
      'One ROM event, zero robot-limit events, zero unintended contacts, zero MuJoCo warnings, zero BRAKE, zero NO_SAFE_ACTION, and 24 SAFE_UNCHANGED filter decisions. Physical >200 N duration and excess impulse are zero. These are simulation observations, not a clinical safety claim.',
      'No endpoint or return was reached. The inherited raw result field return_error_deg is early-stop deviation from the start state, not a completed return error; actual endpoint/return metrics are null in final_verdicts.json.', '',
      '## Proxy and physical diagnostics', '',
      f"Offline hip/knee proxy q RMSE: {proxy['q']['rmse_per_joint']} deg; peak absolute errors: {proxy['q']['peak_abs_per_joint']} deg.",
      f"Offline proxy dq RMSE: {proxy['dq']['rmse_per_joint']} deg/s; peak absolute errors: {proxy['dq']['peak_abs_per_joint']} deg/s.",
      f"Translation RMS {diagnostics['translation_rms_mm']:.6f} mm; rotation RMS {diagnostics['rotation_rms_deg']:.6f} deg; relative velocity peak {diagnostics['relative_velocity_peak_m_s']:.6f} m/s.",
      'Robot-facing proxy and Human truth move apart while deformation grows in the initial hold. This supports reporting an observation/model mismatch in the compliant closed loop. No matched fine trace is available to distinguish physical behavior from timestep sensitivity, and correlation does not establish a unique controller-failure cause.', '',
      '![Saved prefix diagnostics](early_stop_diagnostics.png)', '',
      '## Evidence interpretation', '',
      'DIRECTLY OBSERVED: unchanged ROM guard triggered; low physical force; finite prefix with checked mechanical identities and small discrete energy residual; missing full-trajectory coverage.',
      'SUPPORTED: the interface allowed robot/Human relative motion and a substantial robot-proxy error during the initial hold.',
      'UNRESOLVED: full-trajectory numerical stability, 1 ms repeatability, timestep agreement, whether a finer timestep would change this event, and the unique causal contribution of CEM/action/reference dynamics.',
      'NOT SUPPORTED: interface integration is unstable; the candidate is fully qualified; timestep refinement would fix the task; low force implies overall safety; ROM is structurally infeasible.', '',
      '## Implementation, checks, commands, and git status', '',
      'The two donor interface modules were added; only the spring-damper constructor signature was adapted to the de23ea3 API. The original 61 source/config/model files retain their hashes. A new plant/measurement adapter feeds only the restricted robot-port sample to the unchanged sensor processing. The unchanged runner code object uses private bindings for that adapter and the registered 5/20 substeps. There was no original controller/solver/physics/gain/Reference Manager/source edit.',
      'Raw inherited diagnostic conventions are retained and explicitly annotated in raw_report_semantics.json. H-referenced physical moment must not be mistaken for R-referenced sensor moment. Separate R/H diagnostics and actual-timestamp derivative reports are preserved. The controller always receives the R-referenced transmitted wrench.',
      'Pre-execution targeted pytest: 8 passed in 1.34 s. Tests covered frozen options/reset, measurement boundary, port mechanics, energy and waveform gates, independent 2 N gate, deterministic data and event transitions. No test integrated another trajectory.',
      'Post-run checks: approved Spec and all registered implementation/source/config/model hashes unchanged; finite numeric NPZ arrays and time alignment checked; no new trajectory was executed during analysis.', '',f'Working directory: `{REPO}`', '', 'Executed commands:', '```sh',
      'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_phase3a_soft_qualification.py',
      '/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_stage4_phase3a_soft_qualification.py --freeze-implementation',
      '/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_stage4_phase3a_soft_qualification.py --run-next',
      shlex.join([sys.executable,*sys.argv]), '```', '',
      'The single --run-next invocation returned exit code 2 to report the preregistered qualification stop; there was no runtime exception. No fourth run, tuning, other endpoint, A/B rollout, commit or push occurred. No further scientific command is admitted under this stopped Spec.', '',
      '## Files added in this request', '',
      '- stages/stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py',
      '- stages/stage3_full3d/src/traction_mpc_stage3/interface_measurement_contract.py',
      '- stages/stage4_adaptive_control/scripts/run_stage4_phase3a_soft_qualification.py',
      '- stages/stage4_adaptive_control/scripts/summarize_stage4_phase3a_soft_qualification.py',
      '- stages/stage4_adaptive_control/tests/test_phase3a_soft_qualification.py',
      '- stages/stage4_adaptive_control/docs/PHASE3A_1MS_QUALIFICATION_SPEC_APPROVED.md',
      '- stages/stage4_adaptive_control/docs/PHASE3A_1MS_QUALIFICATION_SPEC_APPROVED.json',
      '- stages/stage4_adaptive_control/docs/PHASE3A_1MS_QUALIFICATION_SPEC_APPROVED.sha256',
      f'- All new evidence under {ROOT.relative_to(REPO)}; exact result inventory is in SHA256SUMS.',
      'The preflight and two DRAFT documents were already untracked at task start and remain preserved. Everything is uncommitted; HEAD remains 99169491ea1336d6af74e3b63318afba18c1e881.']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    files=list(ROOT.rglob('*.npz'))
    for path in files:
        z=load_npz(path)
        assert all(np.all(np.isfinite(a)) for a in z.values() if a.dtype.kind in 'fciu')
    write(ROOT/'postprocess_validation.json',dict(spec_hashes_unchanged=True,
        original_frozen_file_count=len(impl['original_source_config_model_sha256']),implementation_files_unchanged=True,
        numeric_npz_files_finite=len(files),monotonic_time=bool(np.all(np.diff(t)>0)),
        only_one_trajectory_directory=True,additional_simulation_count=0,
        postprocessor_sha256=sha(Path(__file__)),tests_passed=8,tests_failed=0))
    (ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
    print(json.dumps(dict(overall=report['overall_numerical_qualification'],cause=report['exact_cause'],diagnostics=diagnostics),indent=2))


if __name__=='__main__': main()
