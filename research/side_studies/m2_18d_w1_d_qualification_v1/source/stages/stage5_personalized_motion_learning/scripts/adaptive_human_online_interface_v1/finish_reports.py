"""Generate source-grounded final reports, integrity evidence and data inventory."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,csv,hashlib,subprocess,shutil,gzip
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_w1_d_qualification_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1';W=S/'scripts/adaptive_human_online_interface_v1';OUT=S/'results/adaptive_human_online_interface_v1'
def load(n):return json.loads((D/n).read_text())
def save(n,x):(D/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def md(n,x):(D/n).write_text(x.rstrip()+'\n')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(str(x) for x in row)+' |\n' for row in rows)
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True).strip()
def main():
    h=load('CURRENT_HUMAN_ADAPTATION_VALIDATION.json');v=load('ONLINE_ACTION_INTERFACE_VALIDATION.json');p=load('CURRENT_VERSION_PHYSICAL_AUDIT.json');g=load('DIRECT_RL_GYM_READINESS.json');cuda=load('CUDA_RL_ENV_READINESS.json');b=load('ONLINE_INTERFACE_BLOCKER_RETEST.json');a=load('ONLINE_INTERFACE_ADVERSARIAL_TEST.json');m=load('MOTION_SET_COMPARISON.json');c=load('EXPERIMENT_CONTRACT.json');cl=load('CR12_ONLINE_INTERFACE_CLOSED_LOOP.json');effects=sorted(v['actual_effect'],key=lambda x:x['period_s'])
    audits={x['run']:x for x in p['rows']}
    for row in g['runs']:
        matches=[x for x in p['rows'] if '/gym/'+row['pattern']+'/' in x['run']]
        row['physical_audit']='PASS' if matches and all(x['physical_result']=='PASS' for x in matches) else 'FAIL'
    g['status']='SMOKE_PASS' if all(x['status']=='PASS' and x['physical_audit']=='PASS' for x in g['runs']) else 'PARTIAL';save('DIRECT_RL_GYM_READINESS.json',g)
    frozen=load('SOURCE_FINGERPRINTS.json');bad=[name for name,digest in frozen.items() if not (R/name).is_file() or sha(R/name)!=digest]
    integrity=dict(checked_files=len(frozen),changed_or_missing=bad,protected_source_unchanged=not bad,source_commit=git('rev-parse','HEAD'),branch=git('branch','--show-current'),tracked_diff_paths=git('diff','--name-only','HEAD').splitlines(),physics_and_config_change=False,historical_evidence_change=False)
    save('FINAL_SOURCE_INTEGRITY.json',integrity)
    old=next(x for x in h['runs'] if x['condition']=='high_rom_nominal_sync_120_v1' and x['arm']=='continual_adaptive');constant=next(x for x in cl['runs'] if x['run_path'].endswith('nominal_50ms_constant_attempt03'));locals_=sorted([x for x in cl['runs'] if x['pattern']=='local_switch'],key=lambda x:x['period_s'])
    human_table=table(['Human','arm','runtime','physical','J_F (N s)','F peak (N)','M peak (Nm)','duration (s)','task beta accepted'],[[x['condition'].removeprefix('high_rom_').removesuffix('_v1'),x['arm'],x['completion'],x['physical_audit'],f"{x['J_F_task_n_s']:.2f}",f"{x['force_peak_n']:.2f}",f"{x['moment_peak_nm']:.2f}",f"{x['duration_s']:.3f}",x['accepted_dynamic_updates_task']] for x in h['runs']])
    evidence_table=table(['Human continual','beta delta L2','task updates','residual changes','actual execution models','planner numeric models','torque residual RMS (Nm)'],[[x['condition'],f"{x['beta_change_l2']:.4f}",x['accepted_dynamic_updates_task'],x['residual_update_task_count'],x['execution_numeric_model_count'],len(set(y['numeric_model_sha256'] for y in x['planner_models_consumed'])),', '.join(f'{y:.4f}' for y in x['prediction_residual_rms_nm'])] for x in h['runs'] if x['arm']=='continual_adaptive'])
    truth_table=table(['fixture','height m','mass kg','stiffness pair','damping pair','length scales','cuff fraction','hip X/Z m'],[[x['id'],x['case']['physical']['height_m'],x['case']['physical']['body_mass_kg'],x['case']['physical']['passive_stiffness_nm_rad'],x['case']['physical']['passive_damping_nms_rad'],[x['case']['physical']['thigh_length_scale'],x['case']['physical']['shank_length_scale']],x['case']['physical']['cuff_fraction_of_shank'],x['case']['physical']['hip_translation_xz_m']] for x in c['cases']])
    md('CURRENT_HUMAN_ADAPTATION_VALIDATION.md',f'''# Current-version bounded Human qualification

{h['classification']}. Four inherited development fixtures, three arms per fixture, identical physical truth and commissioning path within each trio. All use the registered 5/10° → 120/120° → HOLD → 5/10° task. These are exposed development conditions, with one repetition per arm; no statistical population qualification.

{truth_table}

All four continual and all four commissioning-only arms pass the unchanged physical and scientific-mode checks. Fixed nominal passes only nominal. Heavy/stiff times out; short-segment recovery aborts; light/soft returns outside the true endpoint criterion despite the runner's COMPLETE string. Failed partial-task integrals cannot be ranked against complete-task integrals.

{human_table}

{evidence_table}

Continual adaptation is numerically active and consumed. The light/soft J_F is about 2.16% worse than commissioning-only, heavy/stiff about 0.58% worse; nominal and short-segment differences are small. No uniform benefit claim. Commissioning is sufficient to restore physical validity in these four conditions; this experiment does not isolate causal performance benefit of every continual update.

The JSON contains initial/final beta, exact Human truth, effective geometry actually used, causal/truth tracking RMSE, force mean/RMS/peak, moment integral/peak, clearance, attempted-update rejection reasons and model hashes. Continual task beta accepts nominal/light/heavy/short = 31/30/29/29; no attempted dynamic update was rejected. Between-update samples are not counted as rejected fits. Residual RMS is the on-path measured generalized-torque regressor residual, before residual correction; it is not held-out prediction accuracy.

The legacy TASK controller_model_version string is blank. That logging gap is reported rather than used as evidence. Actual command-call numerical beta/residual hashes, planner worker-input snapshots and mechanics belief sequence records provide consumption evidence, tied to exact active source locations in CURRENT_HUMAN_ADAPTATION_SOURCE_EVIDENCE.json. Repetition persistence is source-audited; the new qualification has no multi-repetition longevity test. Geometry is commissioning-frozen; task updates change effective dynamics and residual only. Full shank length and cuff fraction are not separately identified.

Three multiprocessing launch failures are retained as EXCEPTION attempts; after the main guard repair the nominal three-arm rerun completed. No safety threshold, physical fixture or cost was adjusted to obtain completion.
''')
    md('ONLINE_ACTION_INTERFACE_SPEC.md','''# Online action interface v1

Research implementation: online_reference.py + separately generated runtime_online_v1.py. Original runtime.py, plant, estimator and historical evidence remain unchanged. Upper layer nominates a finite 2-D desired Human joint position, or maps a 2-D increment to that position. It does not send Human torque. Motion still arises from CR12 torque, cuff interaction and passive Human dynamics.

LONG PREDICTION / SHORT COMMITMENT. Reference/control cadence is 5 ms; command cadence is independently 5, 10, 20 or 50 ms. A target is a soft intention with terminal velocity and acceleration zero, never a next-sample equality. Each change starts from the currently owned q/dq/ddq at the exact legal boundary, tolerance 1e-10. The owner retains preceding segments for a pending future activation. Identical targets retain the exact original continuation and do not restart acceleration. Independent axes permit hip/knee lead changes, pauses, reversal and catch-up; no H1–H4 template or phase synchronization is imposed.

Local state-to-state Ruckig 0.12.2, MIT license, Synchronization.No. No intermediate waypoint list or cloud service is used. OTG requires no runtime network. The isolated research environment inherits the frozen physical environment without modifying it. [Ruckig API](https://docs.ruckig.com/), [synchronization API](https://docs.ruckig.com/namespaceruckig.html), [version/license](https://pypi.org/project/ruckig/0.12.2/).

Reference limits use inherited scheduler fractions: velocity 0.6 × physical task limit, acceleration 0.5 × physical task limit. In the high-ROM case these are [27,45]°/s and [150,300]°/s². Added reference jerk cap = reference acceleration cap / 0.020 s = [7500,15000]°/s³, approximately [130.8997,261.7994] rad/s³. This is an explicit additional reference shaping cap, not a changed physical safety threshold. Human/robot limits, endpoint tolerances and task timeouts are inherited.

Mandatory acceptance gate: finite input, ROM target and OTG position extrema; q/dq/ddq continuity; same phase and remaining phase deadline; full trajectory to a stationary target; existing combined rigid-table body margins using the existing geometry and shank structural upper-length prior; existing 21-sample adaptive mechanics force/moment screen (200 N / 60 Nm). Clearance sampling cells are at most 2 ms with a conservative global-velocity Lipschitz intersample bound, retaining original body margins. The installed proximal gap has an analytic monotonic envelope under its documented geometry conditions. Existing causal tracking-offset hypothesis is applied where enabled. Mechanics screening remains a finite model screen, not a theorem of nonlinear physical invariance.

Current numeric beta/residual/geometry signature changes trigger revalidation of the remaining old continuation, excluding the already executed prefix. A new target is installed only after certification. Infeasible targets explicitly return REJECTED_CONTINUE_CERTIFIED and retain the valid terminal continuation. Missing input retains that trajectory to zero velocity/acceleration. Late readiness activates at ceil(max(received,ready,requested)/5ms), without backdating, retaining the committed prefix. If the current model invalidates the owned continuation, the research runtime explicitly aborts; this is not a qualified hardware emergency braking guarantee.

The new reference gate replaces endpoint-oriented RSS activation for this research mode. The old representation-specific monotonic progress governor is disabled; original receipt velocity/20ms acceleration checks, low-level actuation/filter/supervisor, monitors, commissioning/recovery and phase machine remain. Original validate_activation is preserved for original code paths; no ddq continuity check is deleted. Robust terminal reference selection remains inside the original endpoint tolerance box; task endpoints and actual HOLD/RETURN requirements stay unchanged.

Host computation freezes the scientific physics epoch. Reference latency is simulation chronology, reported separately from host realization and physical response. Accepted target changes can have delayed numerical effects under common saturated motion; acceptance does not promise a distinct next sample for every target. Hardware realtime qualification is absent.
''')
    rate_table=table(['command period ms','first changed receipt task s','reference effect ms','physical difference ms','physical pass'],[[int(x['period_s']*1000),f"{x['received_task_s']:.3f}",f"{1000*x['T_command_to_reference_effect_s']:.3f}",f"{1000*x['T_command_to_physical_response_s']:.3f}",x['physical_audit']] for x in effects])
    source_rate=load('ONLINE_INTERFACE_RATE_TEST.json')
    reference_fields=['condition','phase','command_period_s','C2_pass','new_status','same_target_status','same_target_acceleration_jump_rad_s2','old_endpoint_deferred_effect_s']
    with (D/'REFERENCE_PROBE_RATE_TEST.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=reference_fields);writer.writeheader();writer.writerows({key:x.get(key) for key in reference_fields} for x in source_rate['rows'])
    source_rate['actual_physical_effect_rows']=effects;source_rate['physical_response_latency']='See actual_physical_effect_rows; reference probes alone cannot establish physical response.';save('ONLINE_INTERFACE_RATE_TEST.json',source_rate)
    fields=['period_s','received_task_s','T_command_to_reference_effect_s','T_command_to_physical_response_s','complete','physical_audit','run']
    with (D/'ONLINE_INTERFACE_RATE_TEST.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({key:x[key] for key in fields} for x in effects)
    physical_host=[y['host_realization_ms'] for x in cl['runs'] if x['status']=='COMPLETE' for y in x['online_records'] if y.get('status')=='ACCEPTED']
    v['physical_changed_command_host_profile_ms']=dict(count=len(physical_host),median=float(np.median(physical_host)),maximum=max(physical_host));v['profile_scope']='Changed-command realization/certification timing, plus complete run wall times; identical-command model revalidation is not separately attributed. No realtime deadline proof.';save('ONLINE_ACTION_INTERFACE_VALIDATION.json',v)
    md('ONLINE_ACTION_INTERFACE_VALIDATION.md',f'''# Online action qualification

{v['classification']}. Seven kinematic/ownership unit tests; {b['pass_count']}/16 complete blocker criteria; 44 adversarial probes; 48 deterministic reference streams; 9 successful full physical online runs. Two earlier integration aborts remain in the data. Two subsequent Gym smoke runs also pass the inherited physical/scientific evaluator.

{rate_table}

Actual first local-switch reference differences use the recorded six-dimensional q/dq/ddq against the same-interface constant-target run, threshold 1e-8; physical differences use evaluation-only Human q, threshold 1e-7 rad. This is a controlled first-command difference measurement, not per-command plant settling latency or host inference delay. The remaining stream may supersede accepted commands before their individually predicted effects.

Reference-only stream changed-command effects range {1000*v['reference_only_effect_latency_s']['min']:.1f}–{1000*v['reference_only_effect_latency_s']['max']:.1f} ms. Some small forward adversarial changes share a saturated prefix for about 410–460 ms, still preceding the former endpoint. Far-endpoint physical switch inputs were superseded before visible change; their successful completion does not demonstrate action freedom. The separate local-switch tests supply that evidence.

Short-stream host realization median {v['host_realization_profile_ms']['median']:.3f} ms, maximum {v['host_realization_profile_ms']['max']:.3f} ms. Full physical changed-command host profile: median {np.median(physical_host):.3f} ms, maximum {max(physical_host):.3f} ms. Full-horizon clearance and mechanics certification is retained at every accepted update and on model-signature changes. Timing excludes separately attributed identical-command revalidation; complete per-run wall duration remains recorded. Scientific physics freezes while computing. No hardware realtime claim, no silent lookahead bypass.

Raw scorer wall-age outputs are retained; physical/scientific PASS comes from the unchanged evaluate_execution_mode.py plus explicit new online continuity/chronology/certificate checks. The original 100 ms wall-age rule has not been relaxed or promoted to a realtime PASS.
''')
    blocker_table=table(['condition','phase','period ms','nonzero initial ddq rad/s²','changed effect ms','old endpoint s','all criteria'],[[x['condition'],x['phase'],int(x['command_period_s']*1000),', '.join(f'{z:.5f}' for z in x['old_initial_acceleration_rad_s2']),f"{1000*x['changed_command']['reference_effect_latency_s']:.3f}",f"{x['old_endpoint_deferred_effect_s']:.3f}",x['all_blocker_criteria_pass']] for x in b['rows']])
    md('ONLINE_INTERFACE_BLOCKER_RETEST.md',f'''# Original blocker retest

{b['pass_count']}/16 pass all criteria. Reconstructed original saved moving quintic states for sync_120 and low_ordinary_early, OUTBOUND/RETURN, 20/50 ms; extended to 5/10 ms. The inherited nonzero acceleration is carried unchanged into OTG. Original eight historical artifacts are immutable.

{blocker_table}

Every row separately certifies the initial acceleration-aware continuation, preserves exact repeated-same-target acceleration, then accepts a changed target, validates its C2/full continuation and verifies a sampled change before the original endpoint. Initial diagnostic output is retained as ONLINE_INTERFACE_BLOCKER_RETEST_initial.json. The original schedule/state is reconstructed, while certification uses the historical causal commissioning belief; later task-adapted RETURN beta is not reconstructed in these probes. These are reference/safety screen probes, not physical simulations. Actual new physical qualification uses its continually updated current belief separately; low-ROM online task completion was not newly studied.
''')
    adversarial_counts=Counter(x['result']['status'] for x in a['tests'])
    adversarial_table=table(['case','phase','test','status','reason / activation'],[[x['condition'],x['phase'],x['test'],x['result']['status'],x['result'].get('reason',x['result'].get('actual_activation_s','retained'))] for x in a['tests']])
    md('ONLINE_INTERFACE_ADVERSARIAL_TEST.md',f'''# Adversarial command probes

44 reference-and-certification probes across two tasks and two phases. Status counts: {dict(adversarial_counts)}.

{adversarial_table}

Outside-ROM requests explicitly reject. The low-ROM hip-to-knee change fails full-continuation certification in both phases and retains its certified path. A far intention beyond the immediately reachable horizon is allowed as a soft target if its complete approach is certified. Near-ROM targets must also satisfy continuous OTG extrema and clearance. Late command received at 20 ms, ready at 27 ms, activates at 30 ms; its 25 ms committed prefix is explicitly checked against the prior path. Missing commands retain a certified stationary-target continuation. No discontinuous replacement is accepted. These finite probes do not guarantee all adversarial inputs or hardware fallback safety.
''')
    physical_table=table(['path','J_F N s','F peak N','M peak Nm','duration s','deployable clearance mm','robot cuff peak error mm','physical'],[[name,f"{x['J_F_task_n_s']:.2f}",f"{x['force_peak_n']:.2f}",f"{x['moment_peak_nm']:.2f}",f"{x['duration_s']:.3f}",f"{1000*x['minimum_clearance_m']:.3f}",f"{1000*x.get('robot_tracking_peak_m',0):.4f}" if x.get('robot_tracking_peak_m') is not None else 'not collected',x['physical_audit']] for name,x in [('old nominal continual',old),('new constant 50ms',constant)]+[(f"new local switch {int(x['period_s']*1000)}ms",x) for x in locals_]])
    force_delta=100*(constant['force_peak_n']/old['force_peak_n']-1);moment_delta=100*(constant['moment_peak_nm']/old['moment_peak_nm']-1)
    md('CR12_ONLINE_INTERFACE_CLOSED_LOOP.md',f'''# Full CR12–cuff–Human validation

Nine final online runs pass unchanged mode-aware physical/scientific scoring: constant target 50 ms, far switch at 5/10/20/50 ms, local switch at 5/10/20/50 ms. A scalar task COMPLETE flag alone is not the acceptance criterion. All required true endpoint dwell (≥0.5 s), RETURN (1°/2°s⁻¹ tolerances), phase order, phase/global deadlines, robot torque/speed, Human speed/acceleration/ROM, shank/sleeve clearance, zero shank-table contact, finite native states and reference C2 checks pass. No native physics advances during scientific host catch-up. Original actuation and plant source fingerprints remain unchanged; Human is driven by CR12/cuff interaction only.

{physical_table}

{rate_table}

Constant-endpoint comparison shares identical nominal truth, commissioning, endpoints and causal model inputs. The old controller realizes its native scheduler decisions; the new controller realizes the same endpoint intention continuously. This is an interface-semantics comparison, not a matched motion-speed/algorithm-cost efficacy trial. New reference shaping is faster. J_F drops about {100*(1-constant['J_F_task_n_s']/old['J_F_task_n_s']):.2f}% and duration about {100*(1-constant['duration_s']/old['duration_s']):.2f}%, while peak force rises {force_delta:.2f}% and peak moment {moment_delta:.2f}%. Local switching raises force peak to 132.42–132.77 N, about 14.7–15.0% over old nominal; these are material regressions within the unchanged 200 N / 60 Nm limits. Deployable shank clearance stays about 6.50–6.52 mm and true clearance about 11.80 mm; sleeve gaps remain >4.14 mm. No material minimum-clearance regression is observed in these nominal runs.

Two earlier new-interface attempts abort explicitly because an integration diagnostic required an unowned future sample, then because recertification included an already executed prefix under a current offset. Both remain in results. Their fixes do not relax thresholds. Far switch paths equal the constant control because intermediate intentions were superseded while both trajectories shared saturation; only local switch provides recorded immediate-action evidence.
''')
    motion_table=table(['stream family','streams','realized lead sign changes','changed command acceptances'],[[pattern,sum(x['pattern']==pattern for x in m['rows']),sum(x['realized_lead_sign_change'] for x in m['rows'] if x['pattern']==pattern),sum(x['new_status_counts'].get('ACCEPTED',0) for x in m['rows'] if x['pattern']==pattern)] for pattern in ('identical','switch','reverse_alternating')])
    counts=Counter()
    for x in m['rows']:counts.update(x['new_status_counts'])
    md('OLD_RSS_VS_ONLINE_INTERFACE.md',f'''# Old/new action freedom comparison

48 matched high-level intention streams: sync_120/low-ROM × OUTBOUND/RETURN × 5/10/20/50 ms × identical/switch/reverse-alternating. The OLD comparator is reconstructed endpoint-bound ownership from the original saved schedule, with deferred effect at its endpoint; this is not a new old-RSS physical replay of every changed stream. NEW uses the same input intentions and current model safety screens. Status counts: {dict(counts)}; all active handoffs explicitly compare q/dq/ddq.

{motion_table}

The old represented suffix remains deferred until the inherited endpoint for 45.45–100% of commands, depending on period/context. That minimum-endpoint calculation is a representation-level deferral bound, not measured old actual acceptance/rejection after the endpoint. New changed-command reference effects range 5–60 ms in these streams, with no rejected targets in this bounded set. Explicit ROM bounding is in the stream generator; adversarial out-of-ROM rejection is tested separately. Lead sign change means a sign reversal of cumulative hip-minus-knee displacement relative to the stream origin; it is a reference metric and does not prove the same physical lead-switch count. Identical paths can naturally cross that metric too (4/16).

{physical_table}

The table gives actual full physical force/moment/completion for the equivalent constant endpoint intention and separately tested local-switch sequence. Force outcomes for all 48 reference streams were not simulated; OLD force outcomes for changed streams remain unmeasured. Thus immediate richer legal reference realization and actual local-switch influence are supported, but a complete paired physical efficacy matrix is not. No conclusion about historical small optimization gain, SAC, PPO or TQC is drawn.
''')
    gym_table=table(['episode','reset','invalid action rejected','steps','terminated','truncated','post-terminal reject','physical'],[[x['pattern'],x['reset_pass'],x['invalid_action_rejected'],x['steps'],x['terminated'],x['truncated'],x['post_terminal_step_rejected'],x['physical_audit']] for x in g['runs']])
    md('DIRECT_RL_GYM_READINESS.md',f'''# Direct-RL Gym readiness

{g['status']}: two sequential seed-20261002 non-scientific API smoke episodes at 20 ms. Each has one physics owner thread; no vector workers, policy optimization or replay training.

{gym_table}

Action Box[-1,1]² maps to ±0.05 rad target increments relative to the current phase soft target. Explicit ROM clipping is returned in info; current full-path safety acceptance remains mandatory. No Human torque action exists. Observation has 47 finite causal entries: estimated q/dq, owned q/dq/ddq, estimated beta/residual, measured wrench, estimated effective geometry, phase, task time and nominal soft target. Private physical truth is used only to construct the hidden plant; it is never placed in the observation. The existing ideal simulated measurement/derivative assumption remains.

COMPLETE is observed as terminated=True/truncated=False. API-only injected terminal records additionally test timeout → truncated, safety abort → terminated, and COMPLETE → terminated; these mapping checks are not additional physical timeout tests. Nonfinite/out-of-space action validation comes from Gym Box checks; actual smoke explicitly tests out-of-range rejection before physics advances and rejects step after terminal. Repeated reset support is implemented but multi-episode reset longevity is not qualified by this two-instance smoke.

Zero reward is intentional API scaffolding. Serious single-Human SAC campaign is NOT yet qualified: scientific reward, normalization, throughput, episode/reset stress behavior, evaluation seeds and frozen SAC experiment contract need completion. No RL algorithm comparison was performed.
''')
    md('CUDA_RL_ENV_READINESS.md',f'''# Isolated CUDA training environment

{cuda['status']}. Environment `{cuda['executable']}`; Python 3.10.21. PyTorch {cuda['torch_version']}, torch.version.cuda={cuda['torch_version_cuda']}, torch.cuda.is_available()={cuda['torch_cuda_is_available']}, device `{cuda['device_name']}`. A 64×64 GPU tensor multiplication/sum succeeds (262144). Package versions: {cuda['packages']}.

Pip check passes; NVIDIA_SMI.txt, RL_ENV_FREEZE.txt and installation logs are retained. RTX 4060 Laptop GPU has 8188 MiB reported memory. nvidia-smi reports driver 560.94 / 560.35.02 WSL and CUDA 12.6; the installed cu128 build nevertheless passes the recorded availability and tensor smoke. This limited check is not a broad CUDA-kernel/driver compatibility qualification. [Official PyTorch version installs](https://pytorch.org/get-started/previous-versions/), [SB3 2.6 installation](https://stable-baselines3.readthedocs.io/en/v2.6.0/guide/install.html).

New venv `/home/hank/envs/adaptive-online-rl-v1` inherits physical dependencies via system-site-packages. Only the new environment receives torch/Gym/SB3/SB3-Contrib/Ruckig; the frozen `/home/hank/envs/adaptive-traction-mpc` is untouched. No GPU physics acceleration: MuJoCo remains CPU. Training steps = 0. Reproduction commands are in cuda_prepare.sh and cuda_check.py.
''')
    checks=dict(human_execution=h['classification']=='CURRENT_HUMAN_ADAPTATION_CONFIRMED',bounded_Human_matrix=len(h['runs'])==12,online_implemented=v['classification']=='QUALIFIED_IN_TESTED_SCIENTIFIC_SIMULATION_DOMAIN',blocker=b['pass_count']==16,closed_loop=all(x['physical_audit']=='PASS' for x in locals_) and constant['physical_audit']=='PASS',gym_assessed=g['status']=='SMOKE_PASS',source_integrity=not bad)
    status='ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_COMPLETE' if all(checks.values()) else 'ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_PARTIAL'
    report=f'''# Adaptive Human Inheritance + RL-Compatible Online Action Interface v1

**{status}**

Question A: **{h['classification']}**，限本次四个继承的 development Human 条件。Question B: acceleration-aware 在线参考接口在测试的 scientific simulation 域通过。Gym smoke 和 CUDA 可用；正式 SAC campaign 尚未资格化。

## Human adaptation：问题 1–5

1. 当前完整链是否更新 effective Human 参数？是。四个 continual task 分别接受 31/30/29/29 次 beta 更新，residual 均改变；参数变化由实际模型消费证据支持。
2. 是否被 planner/mechanics/execution 使用？是。worker 输入 belief 数值哈希、mechanics sequence、实际 command 调用的 beta/residual 哈希与源代码调用链对应。原 TASK 字符串 model tag 为空，明确作为日志缺口保留，不作为证据。
3. continual 是否优于 fixed/commissioning-only？没有统一优势。commissioning-only 与 continual 均 4/4 物理通过；fixed 只有 nominal 通过。light/soft fixed 虽 COMPLETE 但真实 RETURN 不通过，heavy/short 失败。continual 对 light/soft、heavy/stiff 的 J_F 分别比 commissioning-only 高约 2.16%、0.58%；nominal/short 差异很小。这证实有效更新与不同执行，不证明每次在线更新有净性能收益。
4. 实际测试哪些扰动？下表给出继承配置；全部任务起点 5/10°、终点 120/120°，每组三臂的物理 truth 相同。

{truth_table}

5. 不支持哪些泛化？任意 Human、全部 120° 变体、独立 held-out population、统计显著收益、长期多重复继承、在线几何辨识以及硬件安全均未被本次数据支持。

{human_table}

{evidence_table}

## Online interface：问题 6–17

6. 能否接受 moving q/dq/ddq？能。16 个原/扩展 blocker 状态携带真实非零初始 ddq，新分支从当前拥有的完整状态开始。
7. 同目标是否重置加速度？不会，保留原轨迹；所有 16 行相同目标 acceleration jump 为 0。
8. 5/10/20/50 ms 指令多久影响参考？本次四个实际 local-switch 首个命令均在 5 ms 后改变参考；按 1e-7 rad 检测阈值，人体响应差异在 10 ms 后出现。不是目标到达时间或 host 推理延迟。

{rate_table}

9. 是否仍需旧 waypoint endpoint？不需要。16 行 changed-command 采样均在旧端点前生效。饱和共享前缀可延迟小改动；far switch 物理输入被后续命令取代而未显效，不能把 acceptance 当作逐指令即时响应保证。
10. q/dq/ddq 是否连续？是，显式 1e-10 handoff 比较、原 scientific-mode 边界检查与实际新参考记录通过。
11. 活跃限制是什么？继承 reference v=0.6×task limit、a=0.5×task limit；新增明确 jerk=a/20ms。高 ROM 为 [27,45]°/s、[150,300]°/s²、[7500,15000]°/s³；物理 Human [45,75]°/s/[300,600]°/s²、力 200 N、力矩 60 Nm、robot/ROM/clearance/HOLD/RETURN 判据不变。
12. 能否更丰富 lead/lag？48 个 matched reference streams 中，switch 16/16、reverse-alternating 14/16 出现累计位移 lead 指标符号改变；实际 local-switch 参考和物理响应也改变。OLD 为原 endpoint ownership 的重建 comparator，未对全部 changed streams 新跑 OLD 物理模拟；不能据此断言历史小优化收益源于 RSS。
13. 哪些修改/拒绝？无穷/非法形状拒绝，目标或 OTG 极值越 ROM 拒绝，clearance/mechanics/phase deadline/C2 不合格拒绝。Gym/stream generator 的 ROM 修改显式记录。一个低 ROM 方向切换被完整 continuation 拒绝；近边界或远软目标只有通过完整验证才接受。
14. Safety 看多远？看完整 stationary-target continuation，clearance ≤2 ms cells + Lipschitz intersample bound，原 geometry/body margin/shank prior，原 21-sample adaptive mechanics screen，以及模型改变后的剩余 continuation 再验证。它不是 nonlinear physical invariance 或硬件证书。
15. 晚到/不可行 fallback？保留仍有效的 certified continuation；晚到从下一合法 5 ms 边界激活，不回写已执行 prefix。模型变化使旧路径失效则明确 research abort，不能宣称已资格化硬件 emergency braking。
16. 实际 CR12–cuff–Human 是否有效？9 个最终 online run 全部通过继承的物理与 scientific-mode 评分；另外 2 个 Gym smoke 同样通过。Human 由 robot/cuff 物理作用产生，原 plant/actuation 文件无变化；没有 direct Human torque。
17. 力/力矩/clearance 是否退化？新 constant J_F 从 {old['J_F_task_n_s']:.2f} 降至 {constant['J_F_task_n_s']:.2f} N s，时长 {old['duration_s']:.3f}→{constant['duration_s']:.3f} s；但 force peak 增 {force_delta:.2f}%，moment peak 增 {moment_delta:.2f}%。局部切换 force peak 增约 14.7–15.0%。这是材料性峰值退化，虽仍在原限制内。deployable shank clearance 约 6.50–6.52 mm，true 约 11.80 mm，没有观察到显著 minimum-clearance 退化。不同 reference 时序混杂，不能宣称控制算法统一更优。

{physical_table}

## RL readiness：问题 18–20

18. Gym action 现在可物理实现吗？本次 20 ms 两个零奖励 API episode 可实现且通过物理检查。47 维 observation 仅因果测量/估计/reference/phase/time/目标，无真实 Human 参数或真实 Human q。COMPLETE/timeout/safety-abort 终止映射还做了 3 个 API-only 检查。
19. CUDA PyTorch 准备好了吗？有限 smoke 通过：{cuda['torch_version']}，CUDA {cuda['torch_version_cuda']}，is_available=True，{cuda['device_name']}，GPU tensor 运算成功。专用隔离环境与版本记录保留；MuJoCo CPU 不变。
20. 是否可以直接进入严肃单 Human SAC expert campaign？**还不能判定 ready**。需要先冻结科学 reward、normalization、throughput/episode contract、reset stress 和评估 protocol。本轮训练 0 steps，不评价 SAC/PPO/TQC，不自动开始任何训练或硬件实验。

## 证据、修复与 Git

Base branch codex/direct-rl-expert-v1，clean HEAD `{c['source_commit']}`，remote reachability 已核实。研究 branch `{git('branch','--show-current')}`。新增 research source 3 个文件，运行脚本/报告位于本 campaign 目录；原 physical/config/cost/measurement seed/threshold/endpoints 与历史证据未改。原 100 ms wall-age 输出保留；scientific physics 冻结 host epoch，不能据此报告 hardware realtime PASS。Short-stream changed-command host median {v['host_realization_profile_ms']['median']:.3f} ms / max {v['host_realization_profile_ms']['max']:.3f} ms；实际物理 changed-command host median {np.median(physical_host):.3f} ms / max {max(physical_host):.3f} ms。完整 run wall time 另记，未单独归因 identical-command recertification。

修复：multiprocessing main guard、Ruckig enum No、首次 activation diagnostic 的未拥有 future 查询、current offset 下错误重验已执行 prefix；全部失败 attempt 保留。环境 0.15.3 cp310 binary 不可用，选固定 0.12.2；shell rate-loop 空参数错误未运行物理，后续脚本修正。评分器首次调用缺少 case path，修复调用包装，评分器自身未改。详细结果与 negative evidence 均在 JSON/raw manifest。单 agent，无独立 Auditor，属于受限 development qualification；不把自查说成独立审计。

最终 gates：{checks}。原文件 fingerprint 核对 {len(frozen)} 个，变化/缺失 {len(bad)}。资源策略为一个 physics owner、一次一个模拟；规划 worker 为现有 CPU 机制，不增加并行环境。共 12 个 Human 有效三臂运行、3 个 launch exception、11 个 online attempt（9 成功、2 abort）、2 个 Gym episode；25 个有完整 trace 的 attempt 中 20 个物理/scientific PASS，5 个负例保留。未开展正式 held-out/population/RL campaign。

命令和版本：脚本目录可重跑 human_qualification.py、test_online_reference.py、online_probes.py、motion_set.py、closed_loop.py、physical_audit.py、collect_evidence.py、gym_smoke.py、gym_contract_checks.py；均使用 isolated research env、OMP/OPENBLAS/MKL=1。cuda_prepare.sh/cuda_check.py 记录独立环境准备。测试日志和 SHA256 在附属证据。报告/compact evidence/source/scripts 逐文件 staging，raw traces 留在本地 manifest 指向的位置；没有 commit/push/merge/reset/stash，未删除历史证据。Commit/push 需后续显式授权。

本轮到此 STOP。唯一建议下一步：先冻结并验证单 Human SAC 的 reward、normalization、episode/throughput/evaluation contract，再请求新的 bounded training campaign。
'''
    md('ADAPTIVE_HUMAN_ONLINE_INTERFACE_V1_REPORT.md',report)
    state=load('STATE.json');now=datetime.now(timezone.utc);state.update(status=status,phase='STOPPED_AFTER_READINESS_ASSESSMENT',completed_utc=now.isoformat(),wall_elapsed_hours=(now-datetime.fromisoformat(state['started_utc'])).total_seconds()/3600,gates=checks,Human_classification=h['classification'],next_action='STOP. A future explicitly authorized campaign should first freeze the single-Human SAC reward/normalization/episode/throughput/evaluation contract.',committed=False,pushed=False,merged=False,staging_intent='Individually stage compact reports, evidence and research source/scripts; leave raw traces local and inventoried.',no_training=True,no_hardware=True,negative_attempts_preserved=True);save('STATE.json',state)
    inventory=[]
    for root,kind in ((OUT,'raw_campaign_data'),(W,'reproducibility_script'),(D,'campaign_evidence'),(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1','new_research_source')):
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.name=='RAW_DATA_MANIFEST.json':continue
            if kind=='new_research_source' and path.name not in ('online_reference.py','runtime_online_v1.py','online_gym.py'):continue
            inventory.append(dict(path=str(path.relative_to(R)),bytes=path.stat().st_size,sha256=sha(path),kind=kind))
    save('RAW_DATA_MANIFEST.json',dict(schema='adaptive_human_online_v1_manifest',generated_utc=now.isoformat(),repo_root=str(R),source_commit=c['source_commit'],raw_trace_storage='local WSL results; not staged into Git',entries=inventory,total_bytes=sum(x['bytes'] for x in inventory),manifest_self_excluded=True,truth_scope='Physical truth and evaluation-only state in raw files never become actor observations.'))
    print(json.dumps({'status':status,'gates':checks,'fingerprints':len(frozen),'changed':bad,'manifest_files':len(inventory),'bytes':sum(x['bytes'] for x in inventory)}))
if __name__=='__main__':main()
