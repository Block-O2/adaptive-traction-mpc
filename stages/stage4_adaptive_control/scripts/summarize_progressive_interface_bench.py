#!/usr/bin/env python3
"""Postprocess saved bench evidence only. Does not simulate or change gates."""
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

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / 'stages/stage4_adaptive_control'
ROOT = STAGE / 'results/engineering_validation/progressive_interface_bench_20260904_v1'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj): p.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)+'\n')
def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def trace(cid, case, us):
    with np.load(ROOT/f'{cid}_{case}_dt{us:04d}us_repeat1/trace.npz', allow_pickle=False) as z:
        return {k:z[k] for k in z.files}
def result(cid, case, us): return read(ROOT/f'{cid}_{case}_dt{us:04d}us_repeat1/result.json')

s=read(ROOT/'PROGRESSIVE_INTERFACE_BENCH_SPEC.json'); reg=read(ROOT/'registration.json')
checks={}
for p,h in {**s['original_frozen_sha256'], **s['old_evidence_sha256'], **reg['implementation_hashes']}.items():
    assert sha(REPO/p)==h,p
old=read(REPO/'stages/stage4_adaptive_control/results/engineering_validation/phase3a_soft_1ms_qualification_20260904_v1/implementation_registration.json')
for p,h in old['hashes'].items(): assert sha(REPO/p)==h,p
for suffix,key in [('json','spec_hash'),('md','doc_hash')]:
    name=f'PROGRESSIVE_INTERFACE_BENCH_SPEC.{suffix}'
    assert sha(ROOT/name)==reg[key] and sha(STAGE/'docs'/name)==reg[key],name
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==s['head']
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=REPO,text=True).strip()
rows=read(ROOT/'all_ringdown_results.json'); verdict=read(ROOT/'bench_verdict.json')
assert len(rows)==s['bench']['run_budget']==36
assert verdict['selected_candidate'] is None and not verdict['gate_40_40_authorized']
max_repeat_difference=0.; checked_arrays=0
for c in s['candidates']:
    for case in s['bench']['cases']:
        for dt in s['bench']['timesteps_s']:
            us=round(dt*1e6); cid=c['id']; caseid=case['id']
            a=trace(cid,caseid,us)
            with np.load(ROOT/f'{cid}_{caseid}_dt{us:04d}us_repeat2/trace.npz',allow_pickle=False) as z:
                assert set(a)==set(z.files)
                for k,v in a.items():
                    assert np.isfinite(v).all() and np.isfinite(z[k]).all()
                    assert v.shape==z[k].shape
                    delta=float(np.max(np.abs(v-z[k])))
                    max_repeat_difference=max(max_repeat_difference,delta);checked_arrays+=1
                    assert delta<=1e-12
            assert len(a['time_s'])==round(.2/dt)+1
            assert np.allclose(np.diff(a['time_s']),dt,rtol=0,atol=1e-12)
            for repeat in (1,2):
                r=read(ROOT/f'{cid}_{caseid}_dt{us:04d}us_repeat{repeat}/result.json')
                assert r['termination']=='completed_ringdown' and r['error'] is None and r['warning_count']==0
checks.update(spec_hash=reg['spec_hash'],md_hash=reg['doc_hash'],original_frozen_files_verified=len(s['original_frozen_sha256']),old_evidence_files_verified=len(s['old_evidence_sha256']),old_implementation_files_verified=len(old['hashes']),new_implementation_files_verified=len(reg['implementation_hashes']),ringdowns_complete=36,repeat_pairs=18,repeat_arrays_checked=checked_arrays,max_repeat_absolute_difference=max_repeat_difference,tracked_diff_empty=True,closed_loop_runs=0,postprocessor_sha=sha(Path(__file__)),command=[sys.executable,*sys.argv])
write(ROOT/'postprocess_validation.json',checks)

with (ROOT/'static_curves.csv').open() as f: curves=list(csv.DictReader(f))
with (ROOT/'static_load_deflection.csv').open() as f: static=list(csv.DictReader(f))
plt.rcParams.update({'font.size':10, 'axes.spines.top':False,'axes.spines.right':False})
fig, axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for ax,kind,factor,ylabel in zip(axes,['force','moment'],[1000,180/np.pi],['Global translation (mm)','Global rotation (deg)']):
    for cid in ['P1','P2']:
        q=[r for r in curves if r['candidate']==cid and r['kind']==kind]
        ax.plot([float(r['load']) for r in q],[float(r['deflection_si'])*factor for r in q],label=cid)
        q=[r for r in static if r['candidate']==cid and r['kind']==kind]
        ax.scatter([float(r['load']) for r in q],[float(r['deflection_si'])*factor for r in q],s=14)
    if kind=='force':
        ax.scatter([100,200,300],[1,2,3],marker='x',color='black',label='Registered target ceilings')
        ax.set_xlabel('Static force (N)')
    else:
        ax.axhline(1,color='black',linestyle=':',label='1 deg target ceiling');ax.set_xlabel('Static moment (Nm)')
    ax.set_ylabel(ylabel);ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Static load-deflection: engineering interface models, not tissue limits')
fig.savefig(ROOT/'load_deflection_curves.png',dpi=180);plt.close(fig)

fig,axes=plt.subplots(5,2,figsize=(11,13),sharex=True,layout='constrained')
adir=np.array([1.,2,3])/np.sqrt(14);rdir=np.array([2.,-1,1])/np.sqrt(6)
for col,cid in enumerate(['P1','P2']):
    for us,label in [(1000,'1.0 ms'),(500,'0.5 ms'),(250,'0.25 ms (finite ref.)')]:
        a=trace(cid,'translation_release_200n',us);b=trace(cid,'rotation_release_50nm',us)
        vals=[a['force']@adir,1000*a['x']@adir,b['moment']@rdir,(180/np.pi)*b['theta']@rdir,100*a['interface_R']/result(cid,'translation_release_200n',us)['energy_scale_j']]
        for row,y in enumerate(vals): axes[row,col].plot(a['time_s']*1000,y,label=label,lw=1.3)
    axes[0,col].set_title(cid);axes[0,col].legend(fontsize=8)
    for row,label in enumerate(['Force projection (N)','Translation projection (mm)','Moment projection (Nm)','Rotation projection (deg)','Translation energy residual (%)']):
        axes[row,col].set_ylabel(label);axes[row,col].grid(alpha=.2);axes[row,col].set_xlim(0,45)
    axes[4,col].axhline(-1,color='black',ls=':',label='-1% residual bound')
    axes[4,col].set_xlabel('Time since preload release (ms)')
fig.suptitle('Saved ringdowns: timestep sensitivity despite bounded motion\nTranslation and rotation shown from separate release cases; first 45 ms of 200 ms')
fig.savefig(ROOT/'ringdown_convergence.png',dpi=150);plt.close(fig)

numerical=[]; energy=[]; params=[]; motion=[]; failures=[]
for c in s['candidates']:
    cid=c['id']; p=c['parameters']
    params.append([cid,f"{p['k1_n_m']:.0f}",f"{p['k3_n_m3']:.3g}",f"{p['damping_ns_m']:.9f}",f"{p['kr1_nm_rad']:.0f}",f"{p['kr3_nm_rad3']:.3g}",f"{p['rotational_damping_nms_rad']:.9f}"])
    relevant=[r for r in rows if r['candidate']==cid]
    motion.append([cid,f"{1000*max(r['max_x_m'] for r in relevant):.6f}",f"{np.degrees(max(r['max_theta_rad'] for r in relevant)):.6f}",f"{max(r['final_energy_fraction'] for r in relevant):.3e}"])
    for case in s['bench']['cases']:
        conv=read(ROOT/f"{cid}_{case['id']}_convergence.json")
        for dtkey,dtlabel in [('dt1ms','1.0'),('dt05ms','0.5')]:
            for key,m in conv[dtkey]['metrics'].items():
                numerical.append(dict(candidate=cid,release=case['id'],dt_ms=dtlabel,metric=key,**m))
                if not m['passed']: failures.append(dict(candidate=cid,release=case['id'],dt_ms=dtlabel,gate='waveform_or_peak',metric=key,**m))
        for us in [1000,500,250]:
            r=result(cid,case['id'],us)
            energy.append([cid,case['id'],us/1000,f"{100*r['abs_R_ratio']:.6f}",f"{r['max_energy_increase_j']:.6g}",f"{r['energy_increase_limit_j']:.6g}",str(r['energy'])])
            if not r['energy']:
                failures.append(dict(candidate=cid,release=case['id'],dt_ms=us/1000,gate='discrete_energy',abs_residual_ratio=r['abs_R_ratio'],max_step_energy_increase_j=r['max_energy_increase_j'],step_increase_limit_j=r['energy_increase_limit_j']))
with (ROOT/'numerical_comparison.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(numerical[0]));w.writeheader();w.writerows(numerical)
final=dict(overall='FAIL',selected_candidate=None,bench_static='PASS',MECHANICS_CONSISTENCY='PASS_WITHIN_STANDALONE_BENCH',DETERMINISM='PASS',DISCRETE_ENERGY='FAIL',BENCH_TIMESTEP_AGREEMENT='FAIL',CLOSED_LOOP_TIMESTEP_AGREEMENT='NOT_RUN',TASK_RESULT='NOT_RUN_GATE_CLOSED',FORCE_CONTRACT='NOT_EVALUATED_NO_CLOSED_LOOP',motion_bounds='PASS_WITHIN_STANDALONE_BENCH',gate_40_40_authorized=False,phase3a_ab_authorized=False,exact_stop_reason=verdict['stop_reason'],failures=failures)
write(ROOT/'final_verdicts.json',final)

out=['# Progressive global cuff interface engineering bench','',
'**Overall numerical qualification: FAIL. Neither candidate selected. The 40/40 gate is closed; no new closed-loop trajectory was executed.**',
'User-authorized engineering evidence only, not formal/authoritative evidence and not a clinical or measured-tissue model. All failed results are retained. No tuning followed the results.','',
'## Frozen contract',f"JSON SHA256: `{reg['spec_hash']}`",f"MD SHA256: `{reg['doc_hash']}`",f"Branch: `codex/interface-phase3a-de23ea3`; HEAD: `{s['head']}`; baseline: `{s['baseline']}`.",
'Two candidates; three release cases; dt = 1, 0.5, 0.25 ms; two repeats each: exactly 36 standalone ringdowns of 0.2 s. No MPC/Reference Manager/High-ROM trajectory is called by the bench. The 0.25 ms data are a finite reference, not independently qualified exact mechanics evidence.','',
'## Model and candidates',
'In cuff H coordinates: x = R_H^T(p_R-p_H), u = R_H^T(v_R-v_H-omega_H cross (p_R-p_H)); theta = Log(R_H^T R_R), w = R_H^T(omega_R-omega_H).',
'F_R = -R_H[(K1 + K3 ||x||^2)x + D u]; M_R = -R_H[(Kr1 + Kr3 ||theta||^2)theta + Dr w].',
'F_H = -F_R; M_H = -M_R + (p_R-p_H) cross F_H. Moments are about their respective attachment origins; the transport moment is required for angular action-reaction and port power.',
'U = K1 ||x||^2/2 + K3 ||x||^4/4 + Kr1 ||theta||^2/2 + Kr3 ||theta||^4/4; dissipation = D ||u||^2 + Dr ||w||^2 >= 0. Fixed zero rest displacement/rotation; explicit opt-in only.',
'Positive tangent eigenvalues K1+K3 r^2 and K1+3 K3 r^2 guarantee smooth monotone radial stiffening. The radial law preserves force direction; its mixed-axis magnitude dependence is intentional. Static axis/diagonal checks do not certify full-plant coupling.',
 table(['Candidate','K1 N/m','K3 N/m^3','D Ns/m','Kr1 Nm/rad','Kr3 Nm/rad^3','Dr Nms/rad'],params),
'Damping uses the frozen analytic rule zeta=0.5, D=2*zeta*sqrt(m*K_tangent) at 100 N, and the rotational analog at 20 Nm. Coefficients were selected from deformation targets without inspecting a new High-ROM trajectory.',
'Bench: one free rigid body against a fixed cuff frame, no gravity/contact/controller. Mass 1.23114691647 kg, isotropic inertia 0.0545369149438 kg m^2, from smallest principal directional inertia at the frozen nominal 5/10 deg reset. This omits full coupling and configuration dependence; it is a local test fixture, not a globally conservative plant surrogate. MuJoCo 3.10.0, implicitfast, Newton, 100 iterations, tolerance 1e-8; interface load applied explicitly each step.','',
'## Static load-deflection',table(['Candidate','Load type','Load N or Nm','Deflection','Unit'],[[r['candidate'],r['kind'],r['load'],f"{float(r['deflection_display']):.6f}",r['display_unit']] for r in static]),
'Both candidates pass the registered static targets, positive-stiffness and axis-alignment checks. The additional 300 N point is a static extreme-load point, not a trajectory or capability scan.',
'![Static curves](load_deflection_curves.png)','',
'## Determinism, deformation and mechanics',
 f"18/18 repeat pairs passed rtol=0, atol=1e-12; {checked_arrays} array pairs were rechecked during postprocessing, maximum absolute difference {max_repeat_difference:g}. All 36/36 runs have complete 0.2 s coverage, finite values, zero MuJoCo warnings and no runtime errors.",
 table(['Candidate','Maximum translation mm','Maximum rotation deg','Largest final/initial total energy'],motion),
 f"Across all cases: max force balance residual {max(r['max_force_balance_n'] for r in rows):.6g} N; moment balance {max(r['max_moment_balance_nm'] for r in rows):.6g} Nm; instantaneous power identity residual {max(r['max_power_identity_w'] for r in rows):.6g} W. Damping power never negative. Motion remains bounded, but successful decay alone does not satisfy the discrete passivity gate.",'',
'## Timestep comparison and discrete energy',
'Waveform thresholds are Linf <=5%, L2 <=2%, native peak relative difference <=5%, plus independent physical-force peak difference <=2 N. Frozen absolute budgets are force 0.1 N, moment 0.01 Nm, translation 0.01 mm, rotation 1e-4 rad, energy 1e-5 J; each norm uses max(absolute budget, relative budget). Comparisons use coarse linear interpolation on the fine time grid, with no shifting or smoothing. Full per-case values are in numerical_comparison.csv.',
 table(['Candidate','dt vs .25 ms','Force Linf %','Force L2 %','Moment Linf %','Moment L2 %','x Linf %','theta Linf %','Force peak delta N'],[[cid,dtlabel]+[f'{v:.4f}' for v in values] for cid in ['P1','P2'] for dtkey,dtlabel in [('dt1ms','1 ms'),('dt05ms','.5 ms')] for tr in [read(ROOT/f'{cid}_translation_release_200n_convergence.json')[dtkey]['metrics']] for ro in [read(ROOT/f'{cid}_rotation_release_50nm_convergence.json')[dtkey]['metrics']] for values in [[100*tr['force']['linf_relative'],100*tr['force']['l2_relative'],100*ro['moment']['linf_relative'],100*ro['moment']['l2_relative'],100*tr['x']['linf_relative'],100*ro['theta']['linf_relative'],tr['force']['peak_absolute_difference']]]]),
'Native force peaks agree because the prescribed 200 N initial preload sets the maximum in these releases. This passes the 2 N peak gate but does not establish waveform convergence. Half-step errors decrease, yet force and moment waveform gates still fail.',
'Interface residual R=U-U0+integral(P+D)dt; scale S=max(max U, final dissipated energy, max absolute net port work). Required max|R|/S <=1%, positive R/S <=0.5%. Total kinetic+spring energy may increase per step by at most max(1e-10 J, 1e-5 E0).',
 table(['Candidate','Release','dt ms','max abs R/S %','max total-E step rise J','allowed rise J','Energy gate'],energy),
'Translation energy residuals are negative (excess discrete loss relative to the registered port-work identity), not evidence of net energy creation. Rotation-only ringdowns at 1 and 0.5 ms additionally exceed the per-step total-energy-rise budget. All final energies decay, but these discrete-energy failures remain. At 0.25 ms the translation residual is still 4.873973% / 5.082267% (P1/P2), so that reference is not fully energy-qualified either.',
'These failures occur in a controller-free mechanics bench under explicit load stepping. They establish failure of this implemented model/numerical contract combination. They cannot be attributed to CEM, actions or Reference Manager divergence, and do not establish failure of the continuous conservative spring law.',
'![Saved ringdowns](ringdown_convergence.png)','',
'## Verdict and closed-loop gate',table(['Check','Verdict'],[[k,v] for k,v in final.items() if k in ['bench_static','MECHANICS_CONSISTENCY','DETERMINISM','DISCRETE_ENERGY','BENCH_TIMESTEP_AGREEMENT','CLOSED_LOOP_TIMESTEP_AGREEMENT','TASK_RESULT','FORCE_CONTRACT','motion_bounds']]),
'No candidate satisfies all required numerical gates; no compliant 40/40 or rigid-vs-compliant A/B is authorized by these gates. No controller/task failure or physical force-contract classification is inferred from this standalone bench.',
'Preserved rigid 40/40 context: COMPLETE / STRICT_PASS, tracking RMSE 0.1624167776 deg, physical force peak 117.4563479259 N. New compliant task tracking, Human ROM, BRAKE/NO_SAFE_ACTION, force-contract result and degradation versus rigid are unavailable because no closed-loop gate run was executed. Bench preload peaks are not comparable to these full-task peaks.',
'The old linear candidate (Kt=500 N/m, Dt=35.6390267653 Ns/m, Kr=20 Nm/rad, Dr=1 Nms/rad) is retired in the new registration and retained as negative evidence: 49.7481 mm separation during the early 40/40 hold, stopped at 0.118 s. All historical evidence hashes remain unchanged.','',
'## Files, commands and checks',
'Added: progressive_interface.py; PROGRESSIVE_INTERFACE_BENCH_SPEC.md/.json; run_progressive_interface_bench.py; test_progressive_interface.py; summarize_progressive_interface_bench.py; this new result directory. Existing untracked interface/qualification work was preserved. No tracked file changed.',
'Commands (Python = /opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python):',
'```text',
'PYTHONDONTWRITEBYTECODE=1 <Python> -m pytest -q -p no:cacheprovider stages/stage4_adaptive_control/tests/test_progressive_interface.py',
'<Python> stages/stage4_adaptive_control/scripts/run_progressive_interface_bench.py --freeze',
'<Python> stages/stage4_adaptive_control/scripts/run_progressive_interface_bench.py --run',
'<Python> stages/stage4_adaptive_control/scripts/summarize_progressive_interface_bench.py',
'git status --short', 'git diff --check', '```',
'Nine targeted tests passed before freezing/execution. Bench command exited successfully with 36 mechanically complete runs, but numerical qualification failed. Postprocessing verifies frozen hashes, original sources/configs, old evidence, both repeats and full coverage; it performs no simulation.',
 f"Verified {checks['original_frozen_files_verified']} original frozen source/config files, {checks['old_evidence_files_verified']} old evidence files, {checks['old_implementation_files_verified']} old implementation files and {checks['new_implementation_files_verified']} registered new implementation files.",
'Only the opt-in interface law/coefficients and isolated bench were introduced. No MPC, Reference Manager, Safety Filter, BRAKE, force limits, Human/robot model, trajectory law, seed or closed-loop numerical settings changed. Bench timestep variation was preregistered. No 40/80, 90/120, 120/120, capability scan, new 40/40 or other A/B rollout was run. No post-result parameter or threshold changes. Everything remains uncommitted; no push or merge.',
'Formal command reserved for user: none at present; the numerical gate is closed. Do not run the conditional 40/40.','']
(ROOT/'REPORT.md').write_text('\n\n'.join(out))
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
(ROOT/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in files))
print(json.dumps(checks,indent=2))
print('REPORT_SAVED; NO_SIMULATION_PERFORMED')
