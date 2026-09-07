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
ROOT=STAGE/'results/engineering_validation/progressive_exploratory_ab_20260905_v1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
def load(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def norm(x):return np.linalg.norm(x,axis=1) if x.ndim>1 else abs(x)
def rms(x,t):return float(np.sqrt(np.trapezoid(norm(x)**2,t)/(t[-1]-t[0]))) if len(t)>1 else float(norm(x)[0])
def fmt(x):return '—' if x is None else f'{x:.6g}' if isinstance(x,(float,int)) else str(x)
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows])
s=read(ROOT/'PROGRESSIVE_EXPLORATORY_AB_SPEC.json');reg=read(ROOT/'registration.json')
assert sha(ROOT/'PROGRESSIVE_EXPLORATORY_AB_SPEC.json')==sha(STAGE/'docs/PROGRESSIVE_EXPLORATORY_AB_SPEC.json')==reg['spec_sha']
assert sha(ROOT/'PROGRESSIVE_EXPLORATORY_AB_SPEC.md')==sha(STAGE/'docs/PROGRESSIVE_EXPLORATORY_AB_SPEC.md')==reg['md_sha']
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
    fig.suptitle(f"Exploratory {'/'.join(map(str,ar['point']['endpoint_deg']))}: common prefix only, end={end:.6g} s")
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
'## Matched-prefix force/tracking/deformation trade-off',
'Full rigid and truncated compliant peaks are not a matched whole-task comparison. The following comparisons crop both arms to the same physical-time interval without shifting/smoothing; reference phases may still diverge because the unchanged manager responds to different observations.',
 table(['Trajectory','Common end s','Arm','Force peak N','Force RMS N','Rate peak N/s','Tracking RMSE deg','Translation mm','Rotation deg'],[[str(p['trajectory']),p['matched_wall_time_end_s'],arm]+[d[k] for k in ['physical_force_peak_n','physical_force_rms_n','physical_force_rate_peak_n_s','tracking_rmse_deg','translation_peak_mm','rotation_peak_deg']] for p in pairdata for arm,d in p['arms'].items()]),
]
for p in pairdata:lines.append(f"![Matched prefix](hip{p['trajectory'][0]}_knee{p['trajectory'][1]}_matched_prefix.png)")
lines+=['## Per-run diagnostics']
for rid,r in results.items():
    lines.extend([f'### {rid}',f"Termination: {r['termination_reason']}; raw termination: {r['raw_termination_reason']}. Diagnostic guard uses the caller's existing break path; its generic raw physical-policy label must not be interpreted as an actual hard-force violation when the precise reason is deformation/energy.",
    f"Human ROM event: {r['human_rom_event']}; observed min/max deg: {r['human_min_deg']} / {r['human_max_deg']}. BRAKE transitions: {r['brake'].get('transition_count')}; BRAKE cycles: {r['brake'].get('brake_cycle_count')}; final mode: {r['brake'].get('active_mode')}; NO_SAFE_ACTION/MPC failure count: {r['no_safe_action_count']}. MuJoCo warnings: {r['warning_count']}.",
    f"Physical moment RMS/peak at R: {r['physical_moment_R_nm']}; at H: {r['physical_moment_H_nm']}. Rigid moments retain baseline weld-wrench semantics; progressive R/H moments are separately referenced.",
    table(['Motion channel','Acceleration RMS','Acceleration peak','Jerk RMS','Jerk peak'],[[channel,m['acceleration']['rms'],m['acceleration']['peak'],m['jerk']['rms'],m['jerk']['peak']] for channel,m in r['motion'].items()]),
    'Human-joint units rad/s² and rad/s³; cuff translation units m/s² and m/s³. Differentiated unsmoothed saved velocities; early transients are retained.',
    f"Energy/damping: {json.dumps(r['energy'],sort_keys=True)}" if r['energy'] else 'Rigid spring/damping energy: not applicable; no compliant storage law is assigned to the weld.',
    f"Transient force report: {json.dumps(r['force_contract'],sort_keys=True)}",f"Runtime: {json.dumps(r['runtime'],sort_keys=True)}"])
lines+=['## Interpretation',
'The observed stop occurred at 0.0005 s, after only two physics steps and before a second 5 ms control cycle. The positive residual is 9.53069109e-8 J, versus an 8.92491927e-8 J budget (0.533937% versus 0.5%). This is a frozen diagnostic-budget exceedance at a very small energy scale, not demonstrated macroscopic instability or validated nonpassivity. The instantaneous constitutive power identity still holds. No ROM event, warning, or engineering-motion violation occurred before this stop. The derivative/jerk values use only three states and one jerk sample for P1.',
'The secondary machine reason compliant_40_40_loses_rigid_completion follows from this diagnostic truncation. It is not independent evidence that P1 would fail to finish the trajectory absent that guard. No guard threshold was relaxed and no run was resumed.',
f"Consistent positive trend across all three points: {interpretation['consistent_positive_force_peak_and_rate_trend']}. Rescued tested points: {interpretation['rescued_points']}.",
'If the 40/40 guard stops the campaign, 40/80 improvement and 90/120 failure-mode/completion trend remain untested. A prefix force decrease alone cannot establish a useful interaction improvement when tracking, deformation or energy invalidates the comparison.',
'This run supports further investigation of the discrete-energy diagnostic at startup and interface integration, not a demonstrated benefit from compliant High-ROM mechanics. The 0.5 ms prefix cannot establish whether additional compliant modeling will improve task behavior. It does not justify promoting the candidate or claiming capability gains. No automatic tuning, threshold change or additional run is authorized.',
'## Reproducibility and scope',
 f"Ten preflight tests passed before freeze; these checked reset/model equality, original runtime bytecode bindings, synthetic stop rules and actual-dt derivatives without time integration. Postprocessing verified {arraycount} NPZ arrays, exact paired initial states, paired config/model fingerprints and {len(s['frozen_hashes'])} frozen file hashes. git diff --check passed; tracked diff is empty.",
'Added this task: PROGRESSIVE_EXPLORATORY_AB_SPEC.md/.json; run_progressive_exploratory_ab.py; test_progressive_exploratory_ab.py; summarize_progressive_exploratory_ab.py; this new result directory. Existing files, failed bench evidence and old soft-interface negative evidence are unchanged. Everything remains uncommitted.',
'Only the paired interface and the explicitly requested common 0.25 ms physics experiment differ from historical rigid 1 ms evidence. No controller gains/costs/constraints, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, seed, adapter, trajectory law, integrator or solver were modified. No extra run, replay, capability scan or retuning.',
'Commands:', '```text',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_exploratory_ab.py',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_exploratory_ab.py --freeze',
 f'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/run_progressive_exploratory_ab.py --run-next  # {len(results)} separate process invocations; see started.json per run',
'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage4_adaptive_control/scripts/summarize_progressive_exploratory_ab.py',
'git diff --check', 'git status --short', '```',
'Formal command reserved for user: none; these outputs are exploratory, and the stop rule admits no further execution under this campaign.']
(ROOT/'REPORT.md').write_text('\n\n'.join(lines)+'\n')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
print(json.dumps(validation,indent=2));print(json.dumps(interpretation,indent=2))
