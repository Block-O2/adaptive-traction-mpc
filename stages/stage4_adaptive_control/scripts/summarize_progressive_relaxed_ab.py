#!/usr/bin/env python3
"""Read saved exploratory evidence; no simulator calls or qualification promotion."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
REPO=Path(__file__).resolve().parents[3]
STAGE=REPO/'stages/stage4_adaptive_control'
ROOT=STAGE/'results/engineering_validation/progressive_relaxed_ab_20260905_v1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def norm(x):return np.linalg.norm(x,axis=1) if x.ndim>1 else abs(x)
def rms(x,t):return float(np.sqrt(np.trapezoid(norm(x)**2,t)/(t[-1]-t[0]))) if len(t)>1 else float(norm(x)[0])
def fmt(x):return '—' if x is None else f'{x:.6g}' if isinstance(x,(float,int)) else str(x)
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows])
s=read(ROOT/'PROGRESSIVE_RELAXED_AB_SPEC.json');reg=read(ROOT/'registration.json')
assert sha(ROOT/'PROGRESSIVE_RELAXED_AB_SPEC.json')==sha(STAGE/'docs/PROGRESSIVE_RELAXED_AB_SPEC.json')==reg['spec_sha']
assert sha(ROOT/'PROGRESSIVE_RELAXED_AB_SPEC.md')==sha(STAGE/'docs/PROGRESSIVE_RELAXED_AB_SPEC.md')==reg['md_sha']
for p,h in {**s['frozen_hashes'],**reg['implementation_hashes']}.items():assert sha(REPO/p)==h,p
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==s['head']
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True).strip()
results={};data={};flat=[];pids=[];arraycount=0
for run in s['runs']:
    out=ROOT/run['id']
    if not out.exists():
        flat.append(dict(id=run['id'],trajectory='/'.join(map(str,run['point']['endpoint_deg'])),arm=run['arm'],task='NOT_RUN',reason='CAMPAIGN_STOP'))
        continue
    r=read(out/'result.json');results[r['id']]=r;data[r['id']]=load(out/'mechanics.npz');x=data[r['id']]
    pids.append(read(out/'started.json')['pid'])
    for file in out.glob('*.npz'):
        for k,a in load(file).items():
            if a.dtype.kind in 'fci':assert np.isfinite(a).all(),(file,k)
            arraycount+=1
    assert np.allclose(np.diff(x['time_s']),.00025,rtol=0,atol=1e-10)
    assert read(out/'model_lock.json')['all_cycle_assertions_passed']
    flat.append(dict(id=run['id'],trajectory='/'.join(map(str,run['point']['endpoint_deg'])),arm=run['arm'],task=r['task'],reason=r['termination_reason'],duration_s=r['simulated_duration_s'],phase_s=r['reference_phase_s'],rmse_deg=r['tracking_rmse_deg'],endpoint_deg=r['endpoint_error_deg'],return_or_final_offset_deg=r['return_error_deg'],return_reached=r['return_reached'],command_rms_n=r['command_force_n']['rms'],command_peak_n=r['command_force_n']['peak'],physical_rms_n=r['physical_force_n']['rms'],physical_peak_n=r['physical_force_n']['peak'],force_rate_peak_n_s=r['rates']['physical_force_n_s']['peak'],moment_peak_nm=r['physical_moment_R_nm']['peak'],translation_mm=r['deformation_peak_mm'],rotation_deg=r['rotation_peak_deg'],force_classification=r['force_contract']['classification'],brake_entries=r['brake'].get('transition_count'),brake_cycles=r['brake'].get('brake_cycle_count'),no_safe_action=r['no_safe_action_count'],wall_s=r['runtime']['total_run_wall_s']))
assert len(pids)==len(set(pids))
stop=read(ROOT/'campaign_status.json');assert stop['stop']
assert len(results)<=6
energy_trends={}
for rid,r in results.items():
    if r['arm']!='P1':continue
    x=data[rid];t=x['time_s'];R=x['energy_residual'];S=x['energy_scale'];windows=read(ROOT/rid/'growth_windows.json')
    tail=t>=max(0.,t[-1]-.2);tail_slope=float(np.polyfit(t[tail],R[tail],1)[0]) if np.count_nonzero(tail)>1 else None
    maximum_ratio=float(np.max(np.abs(x['normalized_energy_residual'])))
    energy_trends[rid]=dict(duration_s=float(t[-1]),initial_residual_j=float(R[0]),final_signed_residual_j=float(R[-1]),maximum_absolute_residual_j=float(max(abs(R))),maximum_positive_residual_j=float(max(0.,max(R))),maximum_abs_running_normalized_residual=maximum_ratio,final_normalized_residual=float(x['normalized_energy_residual'][-1]),tail_200ms_slope_j_s=tail_slope,complete_50ms_windows=len(windows),watchdog_triggers=[w['stop_reason'] for w in windows if w['stop_reason']],spring_energy_peak_j=float(max(x['stored_energy'])),damping_loss_j=float(x['cumulative_damping_loss'][-1]),minimum_damping_power_w=float(min(x['damping_power'])))
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    axes[0,0].plot(t,R);axes[0,0].set_ylabel('Signed port energy residual (J)')
    axes[0,1].plot(t,100*x['normalized_energy_residual']);axes[0,1].set_ylabel('Running normalized residual (%)')
    axes[1,0].plot(t,x['stored_energy'],label='Spring U');axes[1,0].plot(t,x['cumulative_damping_loss'],label='Damping loss');axes[1,0].set_ylabel('Energy (J)');axes[1,0].legend()
    axes[1,1].plot([w['end_s'] for w in windows],[w['residual_slope_w'] for w in windows],label='50 ms window slope');axes[1,1].set_ylabel('Residual growth rate (J/s)');axes[1,1].legend()
    for ax in axes.flat:ax.set_xlabel('Physical time (s)');ax.grid(alpha=.2)
    fig.suptitle(rid+' — diagnostic only; no numerical qualification')
    fig.savefig(ROOT/(rid+'_energy.png'),dpi=150);plt.close(fig)
write(ROOT/'energy_trends.json',energy_trends)

rate_segments={}
for rid,r in results.items():
    z=data[rid];t=z['time_s'];rate=np.diff(z['force_R_world'],axis=0)/np.diff(t)[:,None];rn=norm(rate);times=.5*(t[1:]+t[:-1]);mask=t[:-1]>=1.
    rate_segments[rid]=dict(overall_peak_time_s=float(t[1:][np.argmax(rn)]),initial_hold_end_s=1.,post_initial_hold_peak_n_s=float(max(rn[mask])) if np.any(mask) else None,post_initial_hold_rms_n_s=rms(rate[mask],times[mask]) if np.any(mask) else None,note='Post-hold diagnostic segmentation uses the registered 1 s initial hold; not a new acceptance threshold.')
write(ROOT/'force_rate_segments.json',rate_segments)
pairdata=[];initialchecks=[]
for j in [0,2,4]:
    ar,br=s['runs'][j:j+2];aid,bid=ar['id'],br['id']
    if aid not in results or bid not in results:continue
    a,b=results[aid],results[bid];xa,xb=data[aid],data[bid]
    ia=load(ROOT/aid/'initial_state.npz');ib=load(ROOT/bid/'initial_state.npz')
    for key in ia:np.testing.assert_array_equal(ia[key],ib[key])
    ca=read(ROOT/aid/'run_config.json');cb=read(ROOT/bid/'run_config.json')
    assert {k:v for k,v in ca.items() if k!='candidate'}=={k:v for k,v in cb.items() if k!='candidate'}
    la=read(ROOT/aid/'model_lock.json');lb=read(ROOT/bid/'model_lock.json')
    assert la['expected_fingerprints']==lb['expected_fingerprints']
    initialchecks.append(dict(trajectory=ar['point']['endpoint_deg'],initial_state_exact=True,config_equal_except_interface=True,model_fingerprints_equal=True))
    end=min(a['simulated_duration_s'],b['simulated_duration_s']);pair=dict(trajectory=ar['point']['endpoint_deg'],matched_wall_time_end_s=end,full_pair_complete=a['task']=='COMPLETE' and b['task']=='COMPLETE',rigid=a['task'],compliant=b['task'],rescued=a['task']!='COMPLETE' and b['task']=='COMPLETE',arms={})
    for rid,x in [(aid,xa),(bid,xb)]:
        mask=x['time_s']<=end+1e-12;t=x['time_s'][mask];f=x['force_R_world'][mask];df=np.diff(f,axis=0)/np.diff(t)[:,None]
        tr=load(ROOT/rid/'trace.npz') if (ROOT/rid/'trace.npz').exists() else None
        if tr is not None:
            tm=tr['time_s']<=end+1e-12;e=tr['human_q_deg_god_view'][tm]-tr['human_q_ref_deg'][tm]
        else:e=np.degrees(x['q_true_rad'][mask]-x['manager_reference_q_rad'][mask])
        pair['arms'][results[rid]['arm']]=dict(physical_force_peak_n=float(max(norm(f))),physical_force_rms_n=rms(f,t),physical_force_rate_peak_n_s=float(max(norm(df))) if len(df) else None,tracking_rmse_deg=float(np.sqrt(np.mean(e**2))),translation_peak_mm=float(1000*max(norm(x['deformation_H'][mask]))),rotation_peak_deg=float(np.degrees(max(norm(x['rotation_vector_H'][mask])))))
    aa=pair['arms']['rigid'];bb=pair['arms']['P1'];pair['delta_P1_minus_rigid']={k:bb[k]-aa[k] for k in aa};pairdata.append(pair)
    fig,axes=plt.subplots(3,2,figsize=(11,9),layout='constrained')
    for rid,x in [(aid,xa),(bid,xb)]:
        # Both traces explicitly cropped to common wall-time coverage.
        mask=x['time_s']<=end+1e-12;t=x['time_s'][mask];label=results[rid]['arm']
        ys=[norm(x['force_R_world'][mask]),norm(x['moment_R_world'][mask]),1000*norm(x['deformation_H'][mask]),np.degrees(norm(x['rotation_vector_H'][mask])),np.degrees(x['q_true_rad'][mask,0]),np.degrees(x['q_true_rad'][mask,1])]
        for ax,y in zip(axes.flat,ys):ax.plot(t,y,label=label,lw=1.2)
    for ax,label in zip(axes.flat,['Physical force (N)','Physical moment at robot cuff (Nm)','Global translation (mm)','Global rotation (deg)','True hip angle (deg)','True knee angle (deg)']):ax.set_xlabel('Physical time (s)');ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend()
    fig.suptitle(f"Exploratory {'/'.join(map(str,ar['point']['endpoint_deg']))}: common time interval, end={end:.6g} s")
    fig.savefig(ROOT/f"{ar['point']['id']}_matched_prefix.png",dpi=160);plt.close(fig)
keys=list(dict.fromkeys(k for r in flat for k in r))
with (ROOT/'six_run_table.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(flat)
write(ROOT/'matched_pair_comparisons.json',pairdata)
validation=dict(spec_sha=reg['spec_sha'],md_sha=reg['md_sha'],frozen_hashes_verified=len(s['frozen_hashes']),implementation_hashes_verified=len(reg['implementation_hashes']),npz_arrays_verified=arraycount,executed_runs=len(results),unique_process_ids=pids,matched_pairs=initialchecks,tracked_diff_empty=True,head=s['head'],postprocessor_sha=sha(Path(__file__)),command=[sys.executable,*sys.argv],no_additional_simulation=True)
write(ROOT/'postprocess_validation.json',validation)
allthree=len(pairdata)==3
consistent=allthree and all(p['delta_P1_minus_rigid']['physical_force_peak_n']<0 and p['delta_P1_minus_rigid']['physical_force_rate_peak_n_s']<0 for p in pairdata)
interpretation=dict(consistent_positive_force_peak_and_rate_trend=consistent if allthree else 'NOT_ESTABLISHED_INCOMPLETE_THREE_POINT_COVERAGE',rescued_points=[p['trajectory'] for p in pairdata if p['rescued']],unexecuted_points=[r['trajectory'] for r in flat if r['task']=='NOT_RUN'],stop_reasons=stop['stop_reasons'],authoritative_capability_or_safety_claim=False,numerical_qualification=False)
write(ROOT/'interpretation.json',interpretation)
params=s['candidate']['parameters']
lines=['# Exploratory progressive-interface A/B at 0.25 ms','',
 f"**Executed {len(results)}/6 scheduled runs. Campaign stopped: {', '.join(stop['stop_reasons']) or 'six-run budget exhausted'}.**",
'Exploratory diagnostic evidence only. The previous failed bench qualification, including the 0.25 ms energy residual, remains unchanged. No clinical safety, validated compliance physics or authoritative capability claim is supported.',
'## Frozen setup',f"Spec JSON SHA256: `{reg['spec_sha']}`",f"Spec MD SHA256: `{reg['md_sha']}`",f"Branch codex/interface-phase3a-de23ea3; HEAD `{s['head']}`. Controller baseline `{s['baseline']}`.",
'Candidate P1 only: F=−(K1+K3||x||²)x−Dv; M=−(Kr1+Kr3||theta||²)theta−Dr*omega, with the registered two-port frame/moment transport. Fixed coincident rest frames; no preload capture. P1 was selected before these task results as the lower small-motion stiffness registered candidate. No P2 trial.',
 table(['Parameter','Value'],list(params.items())),
'Both arms have 0.25 ms physics, 20 substeps per unchanged 5 ms control tick. Same de23ea3 controller stack, suspended_high_rom, nominal High-ROM Human, frozen population prior/model/geometry, 140 mm adapter, seed 44104, trajectory law/timing, force contracts, Reference Manager, Safety Filter and BRAKE. Every executed run used a fresh process/state.',
'Controller bytecode is unchanged; local CONTROL_SUBSTEPS=20 preserves control cadence. The compliant arm uses its registered robot-port sensor adapter with unchanged noise/filter/sampling. Rigid mechanics and sensor reconstruction retain the baseline implementation.',
'## Six scheduled runs',table(['Trajectory','Arm','Task','Reason','Sim time s','RMSE deg','Endpoint deg','Return/final offset deg','Force class'],[[r.get(k) for k in ['trajectory','arm','task','reason','duration_s','rmse_deg','endpoint_deg','return_or_final_offset_deg','force_classification']] for r in flat]),
'Return/final offset is error from initial [5,10] deg at the last sample. When return_reached=false, this is NOT a completed return error. Missing endpoint means the target hold was not reached. All incomplete-run RMS/peak values cover only that executed prefix.',
 table(['Trajectory','Arm','Command RMS/peak N','Physical RMS/peak N','Force-rate peak N/s','Moment peak Nm','Translation mm','Rotation deg','Wall s'],[[r['trajectory'],r['arm'],f"{fmt(r.get('command_rms_n'))} / {fmt(r.get('command_peak_n'))}",f"{fmt(r.get('physical_rms_n'))} / {fmt(r.get('physical_peak_n'))}",r.get('force_rate_peak_n_s'),r.get('moment_peak_nm'),r.get('translation_mm'),r.get('rotation_deg'),r.get('wall_s')] for r in flat]),
'RMS force values are time-weighted trapezoidal norms. Command RMS uses issued-command timestamps; physical RMS uses physics timestamps. Force/moment rates are world-vector finite differences using actual dt. The baseline raw summary assumes 1 ms for some derivatives; those uncorrected fields are preserved but not used here.',
'## Matched-time force/tracking/deformation trade-off',
'The 40/40 pair has identical full physical-time coverage (14.10625 s); both reached the end of the reference. P1 remains SAFE_INCOMPLETE because endpoint/return tracking tolerance was not met. The common-interval comparison therefore uses the entire executed reference, not the previous 0.5 ms truncated evidence. No time shifting or smoothing is applied.',
 table(['Trajectory','Common end s','Arm','Force peak N','Force RMS N','Rate peak N/s','Tracking RMSE deg','Translation mm','Rotation deg'],[[str(p['trajectory']),p['matched_wall_time_end_s'],arm]+[d[k] for k in ['physical_force_peak_n','physical_force_rms_n','physical_force_rate_peak_n_s','tracking_rmse_deg','translation_peak_mm','rotation_peak_deg']] for p in pairdata for arm,d in p['arms'].items()]),
]
for p in pairdata:lines.append(f"![Matched prefix](hip{p['trajectory'][0]}_knee{p['trajectory'][1]}_matched_prefix.png)")
lines+=['## Energy residual policy and trend',
'Energy residual is diagnostic, not an instantaneous hard stop. This campaign uses frozen four-window (50 ms each) persistence and material-amplitude guards. The prior strict numerical qualification FAIL and old 0.5 ms exploratory stop remain unchanged. Engineering bounds 3 mm/1 deg are harder-pair admission criteria; gross emergency bounds are 10 mm/10 deg. See frozen Spec for exact growth thresholds.',
'## Per-run diagnostics']
for rid,r in results.items():
    if rid in energy_trends:
        lines.extend([f"Energy trend: {json.dumps(energy_trends[rid],sort_keys=True)}",f"![Energy trend]({rid}_energy.png)"])
    lines.extend([f'### {rid}',f"Termination: {r['termination_reason']}; raw termination: {r['raw_termination_reason']}. Diagnostic guard uses the caller's existing break path; its generic raw physical-policy label must not be interpreted as an actual hard-force violation when the precise reason is deformation/energy.",
    f"Human ROM event: {r['human_rom_event']}; observed min/max deg: {r['human_min_deg']} / {r['human_max_deg']}. BRAKE transitions: {r['brake'].get('transition_count')}; BRAKE cycles: {r['brake'].get('brake_cycle_count')}; final mode: {r['brake'].get('active_mode')}; NO_SAFE_ACTION/MPC failure count: {r['no_safe_action_count']}. MuJoCo warnings: {r['warning_count']}.",
    f"Physical moment RMS/peak at R: {r['physical_moment_R_nm']}; at H: {r['physical_moment_H_nm']}. Rigid moments retain baseline weld-wrench semantics; progressive R/H moments are separately referenced.",
    table(['Motion channel','Acceleration RMS','Acceleration peak','Jerk RMS','Jerk peak'],[[channel,m['acceleration']['rms'],m['acceleration']['peak'],m['jerk']['rms'],m['jerk']['peak']] for channel,m in r['motion'].items()]),
    'Human-joint units rad/s² and rad/s³; cuff translation units m/s² and m/s³. Differentiated unsmoothed saved velocities; early transients are retained.',
    f"Energy/damping: {json.dumps(r['energy'],sort_keys=True)}" if r['energy'] else 'Rigid spring/damping energy: not applicable; no compliant storage law is assigned to the weld.',
    f"Transient force report: {json.dumps(r['force_contract'],sort_keys=True)}",f"Runtime: {json.dumps(r['runtime'],sort_keys=True)}"])
lines+=['## Interpretation',
'The new relaxed-energy policy allowed P1 to execute the full reference. The campaign closes at the P1 40/40 COMPLETE gate, not an energy/pathology guard. Endpoint error 0.37037595 deg and return error 0.82769438 deg exceed the unchanged 0.06896926724 deg tolerance.',
'Observed full-40/40 trade-off: physical force peak increases from 117.44772 to 118.68231 N and RMS from 98.99135 to 99.28240 N; tracking RMSE increases from 0.157621 to 0.556420 deg. Global P1 translation/rotation remain within 1.039794 mm / 0.509747 deg. Peak moment increases from 17.69069 to 19.11903 Nm. Both force contracts classify STRICT_PASS; no ROM event, warning, BRAKE or NO_SAFE_ACTION occurs.',
'The maximum full-run force derivative occurs at startup (t=0.00025 s) in both arms. It decreases from 251692 to 8711.51 N/s with P1. Excluding only the registered first 1 s initial hold, peak derivative decreases from 8712.73 to 707.129 N/s: the smoothing effect is also present during later reference execution. This derivative benefit does not reduce the overall peak/RMS force or preserve the original completion accuracy.',
 table(['Run','Overall rate peak time s','After initial hold rate peak N/s','After initial hold rate RMS N/s'],[[rid,v['overall_peak_time_s'],v['post_initial_hold_peak_n_s'],v['post_initial_hold_rms_n_s']] for rid,v in rate_segments.items()]),
'P1 energy remains finite. Maximum absolute residual 0.002140517 J; final signed residual -0.001749246 J; maximum absolute running-normalized residual 1.05234%, final ratio -0.817596%. Final-200ms slope -9.88925e-5 J/s. Peak stored energy 0.1162406 J; cumulative damping loss 0.1165622 J. All 282 completed 50 ms windows show no registered persistent-growth trigger. Residuals are not zero and prior strict numerical qualification remains failed.',
f"Consistent positive trend across all three points: {interpretation['consistent_positive_force_peak_and_rate_trend']}. Rescued tested points: {interpretation['rescued_points']}.",
'If the 40/40 guard stops the campaign, 40/80 improvement and 90/120 failure-mode/completion trend remain untested. A prefix force decrease alone cannot establish a useful interaction improvement when tracking, deformation or energy invalidates the comparison.',
'Interpret stopped or incomplete comparisons only over the recorded coverage. A reduced force peak without preserved task completion is a trade-off, not a rescued task. The force-rate benefit is offset by higher peak/RMS force and worse tracking at 40/40. No consistent three-point trend can be established when harder points are unexecuted. Further compliant-interface research may investigate the observed trade-off, but this evidence does not qualify the physics or justify tuning in this campaign.',
'## Reproducibility and scope',
 f"Twelve preflight tests passed before freeze; these checked reset/model equality, original runtime bytecode bindings, synthetic stop rules and actual-dt derivatives without time integration. Postprocessing verified {arraycount} NPZ arrays, exact paired initial states, paired config/model fingerprints and {len(s['frozen_hashes'])} frozen file hashes. git diff --check passed; tracked diff is empty.",
'Added this task: PROGRESSIVE_RELAXED_AB_SPEC.md/.json; run_progressive_relaxed_ab.py; test_progressive_relaxed_ab.py; summarize_progressive_relaxed_ab.py; this new result directory. Existing files, failed bench evidence and old soft-interface negative evidence are unchanged. Everything remains uncommitted.',
'Only the paired interface and the explicitly requested common 0.25 ms physics experiment differ from historical rigid 1 ms evidence. No controller gains/costs/constraints, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, seed, adapter, trajectory law, integrator or solver were modified. No extra run, replay, capability scan or retuning.',
'Commands:', '```text',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_relaxed_ab.py',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_relaxed_ab.py --freeze',
 f'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_relaxed_ab.py --run-next  # {len(results)} separate process invocations; see started.json per run',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/summarize_progressive_relaxed_ab.py',
'git diff --check', 'git status --short', '```',
'Formal command reserved for user: none; these outputs are exploratory, and the stop rule admits no further execution under this campaign.']
(ROOT/'REPORT.md').write_text('\n\n'.join(lines)+'\n')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
print(json.dumps(validation,indent=2));print(json.dumps(interpretation,indent=2))
