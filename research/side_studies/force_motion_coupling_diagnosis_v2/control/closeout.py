"""Write the scoped scientific report, verify preservation, export review copy."""
from analyze import *

REVIEW=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/force_motion_coupling_diagnosis_v2')

def loadj(n):return json.loads((P/n).read_text())
def write(n,s): (P/n).write_text(s.strip()+'\n')

def main():
    if Path(__file__).resolve()!=P/'control/closeout.py':shutil.copy2(__file__,P/'control/closeout.py')
    M=loadj('RAW_DERIVED_METRICS.json')['cases'];D={x['label']:x for x in M};W=loadj('FORCE_WINDOWS_AND_CONTRASTS.json');L=loadj('LAG_ANALYSIS.json')['cases'];A=loadj('ANOMALY_TIME_ALIGNMENT.json')
    B=D['B0'];E=D['18D'];gain=B['J_F_N_s']-E['J_F_N_s'];covered=W['18D']['gain_4to6_N_s']+W['18D']['gain_15to16_N_s']
    for rec in M:
        assert abs(rec['J_F_N_s']-sum(x['J_F_N_s'] for x in rec['phase_metrics'].values()))<1e-8
        assert rec['torque_component_closure_max_Nm']<1e-9
    raw=loadj('audit/RAW_NATIVE_RECEIPT_VERIFICATION.json');assert len(raw)==5 and all(x['native_q_max_error']==x['native_dq_max_error']==0 for x in raw)
    assert loadj('audit/DERIVED_ANOMALY_REPEAT_IDENTITY.json')['status']=='PASS'
    phase_table='\n'.join(f"| {ph} | {B['phase_metrics'][ph]['duration_s']:.3f} | {B['phase_metrics'][ph]['J_F_N_s']:.6f} | {E['phase_metrics'][ph]['J_F_N_s']:.6f} | {B['phase_metrics'][ph]['J_F_N_s']-E['phase_metrics'][ph]['J_F_N_s']:.6f} |" for ph in PHASES)
    return_top=sorted([r for r in W['B0']['half_second_windows'] if r['start_s']>=10.025],key=lambda r:r['J_F_N_s'],reverse=True)[:2]
    bseries=np.load(P/'series/B0.npz');peak_t=float(bseries['tf'][np.argmax(bseries['f'])])
    lag_rows=[]
    for label in ['B0','18D']:
        for ph in ['OUTBOUND','RETURN']:
            for trans in ['level','linear_detrend','first_difference']:
                z=L[label][f'0.05|SG0|{ph}|acceleration_variation_rate|{trans}']
                lag_rows.append(f"| {label} | {ph} | {trans} | {z['zero_lag_r']:+.3f} | {z['peak_abs_r']:+.3f} | {z['peak_lag_s']:+.2f} |")
    core_table='\n'.join(f"| {label} | {D[label]['J_F_N_s']:.9f} | {D[label]['force_peak_N']:.6f} | {D[label]['force_RMS_N']:.6f} | {D[label]['velocity_TV_ratio_vs_B']:.6f} | {D[label]['acceleration_variation_ratio_vs_B']:.6f} | {D[label]['jerk_combined_RMS_ratio_vs_B']:.6f} | {'FAIL' if D[label]['qualification']['motion'] is False else 'development PASS'} |" for label in ['B0','18D','legacy002','legacy005','legacy005_repeat'])
    report=f'''
# iHEAR Lab — Force–Motion Coupling Diagnosis + Bounded Continuous Coordination v2

**决定：情况 D，停止扩大 waypoint/speed 搜索；纯 temporal 接口另保留情况 E 限制。** 当前资料支持局部 force–motion 瞬态共现，未支持跨 phase、跨尺度稳定的“motion variation 提前上升 → force 上升 → 累计力增加”关系，也未证明“让运动更平滑能够降低累计 cuff force”。本轮新 physical START=0，没有新候选或新资格升级，正式 B 不变。报告日期：2026-10-17（Asia/Shanghai）。

## 直接回答八个问题

1. **力主要累积在哪里？** B 的 OUTBOUND/HOLD/RETURN 分别为 725.825779/54.394339/658.393380 N·s，约 50.45%/3.78%/45.76%。最高 0.5 s 窗是 task 1.5–2.0 s（absolute 11.55–12.05 s），56.127576 N·s，平均 112.255 N；1.0–2.5 s 都是高负荷。RETURN 的最高窗是 {return_top[0]['start_s']:.1f}–{return_top[0]['end_s']:.1f} s，{return_top[0]['J_F_N_s']:.6f} N·s。B 的瞬时峰值为 115.479119 N，在 task {peak_t:.3f} s。累计 25%/50%/75% 的时刻为 3.544/8.883/14.627 s；负荷分布在宽时间段，并非由一个导数尖峰主导。
2. **对应明显 motion variation 吗？** 部分区间对应，整体不稳定。50 ms 窗中，B 的最高四分位 velocity TV 仅承担 OUT/RETURN 的 26.27%/25.29% force 积分；18D 为 24.43%/23.93%。高 acceleration variation 的四分位窗口约承担 27–28%，存在温和富集，远非主要累计负荷的集中解释。HOLD 几乎静止仍累积 54.394 N·s。零滞后、最佳滞后及相关符号均依赖 phase、窗口和去趋势处理。
3. **+0.05° anomaly 与 force 有时间对应吗？** 有局部对应：task 5.870 s / absolute 15.920 s 的 hip acceleration=106.588°/s²，B 同时刻为 29.480°/s²；最大 force 差同在该 5 ms 采样点，为 +3.013366 N。jerk 峰在 5.8655 s，较 force 采样间隔还短的先后差不能支持可靠因果排序。5.82–5.92 s 净力差 +0.000895 N·s，但 5.8–6.0 s 为 −0.002985 N·s：局部增量与减量抵消。全程净差 −0.001446 N·s，正/负差面积为 +0.053962/−0.055408 N·s，force RMS 略升。它不是全任务主要高力窗口；motion FAIL 不能因净力稍低被接受。两次存档重复的 native-derived motion、force、reference、command 精确一致。
4. **旧18D收益来自哪里？** 总收益 {gain:.9f} N·s（2.635613%），OUT/RETURN 各 18.725259/19.191012，HOLD 几乎零。4–6 s 为 10.099746、15–16 s 为 9.996502 N·s；合计 {covered:.6f}，占净收益 {covered/gain*100:.2f}%。最大半秒窗 15.5–16.0 s 为 5.691310；前三个半秒窗占净收益 34.29%，前五个占 48.32%。收益有局部集中，也有分布式贡献。15.0–15.5 s 降力 4.305193 N·s，同时 velocity TV 增加 0.002816 rad/s、acceleration variation 增加 3.287643 rad/s²；5.5–6.0 s 也同时降力而两项 variation 上升。不能将全部收益归于平顺性。
5. **spatial 与 temporal 哪个值得继续？** 暂无证据支持继续二者的 force 搜索或确定胜者。已合法执行的 spatial shape 可作为后续 robustness 归因的受控微扰；优先问题是 tracking/allocator/replan。S_PROXY 仅保留 waypoint q 与总时长，点间 Hermite 路径会改变，不能当纯 speed 实验。旧 exact fixed-path timewarp 为 degree30，超出现有 2×6 quintic 证书表示；本轮仅复用该接口限制证据，没有绕过证书或新增 timewarp physics。
6. **已有“平滑能降低累计力”的证据吗？** 18D 同时较低 J_F 和 combined TV_v，是 **CONSISTENT-WITH-HYPOTHESIS** 的一个开发状态观察；combined TV_v 下降 10.597%、acceleration variation 下降 0.544%、combined jerk RMS 下降 0.475%，但 hip jerk RMS 上升 7.40%、hip jerk max 上升 20.69%、knee tracking RMS 变差，moment 积分上升 7.03%。历史 S_late、D1_hip_neg 的微小同向变化也保留，但不能从中推导稳定因果机制。当前“稳定、可操作的通用 force–smoothness 关系”标记 **NOT-SUPPORTED**；平滑干预的因果效果仍 **UNRESOLVED**。
7. **有没有新的完整 PASS 且优于 B 的候选？** 没有，本轮未启动新物理。已知 18D 开发 PASS 与历史合法小扰动没有重新命名为新发现。历史 D1_coupled_inverse/repeat=1438.613358554，比 B 低 0.000139914 N·s，但 velocity TV 上升；D1_hip_neg、S_late 的更小收益也不是本轮新重复或新 state 验证。旧18D的合法新 prefix motion 0/4、原 host plan_age FAIL 原样保留。
8. **下一步研究哪里？** 先对可重复异常做 tracking response、allocator wrench→robot torque 映射和 request/activation/splice 时序的归因；检查 18D 收益窗口的姿态、跟踪误差、moment 与 allocation 分配。存档 anomaly 附近 allocator/velocity/position/base 的最大差范数约 9.558/1.990/0.238/0.013 Nm，clipping=0；加和闭合，最大贡献不等于单独致因。最近 activation/splice 在峰前约 0.280/0.235 s，不是节点瞬间跳变。任何下一轮 physics 必须另立冻结配对合同，从合法完整父状态 fork，保留全部既有门；本包不自动执行。

## 时间、采样与指标合同

20 条完整存档：最新研究的19个 arm（含 B、+0.02、两次+0.05、D1/D2/D3、adaptive、S_PROXY、P+S_PROXY、selected repeat），加冻结18D。各自独立确认 TASK 起点 absolute=10.05 s，终点29.08 s。绝对时间与 task elapsed 的映射仅作坐标变换，不作 phase 归一化或峰值对齐。

| phase | duration s | B J_F N·s | 18D J_F N·s | B−18D N·s |
|---|---:|---:|---:|---:|
{phase_table}

| case | J_F N·s | peak N | RMS N | TV_v/B | TV_a/B | combined jerk RMS/B | motion |
|---|---:|---:|---:|---:|---:|---:|---|
{core_table}

force 有3807个5 ms boundary samples、3806个区间；原 J_F 为 F(t_i)·(t_(i+1)−t_i) 左积分，phase 使用真实转移时间裁剪。native motion 有76121个0.25 ms点，原始 dq 连续两次 `np.gradient(..., edge_order=2)` 得 a/jerk，未删端点。5个关键 case 全部116320 native rows、5817个正步 receipt 重新核对：Human q/dq 地址[0,1]、逐native值、唯一 receipt ownership、command torque 与步数全部一致。其余15个case复算已保存 native-derived series，并逐5 ms核对实际q/dq；没有冒称重新审核其全部native/receipt。

TV_v=Σ||Δdq||₂，acceleration variation=Σ||Δa||₂；同时保存逐关节 L1 TV，不能混作同一指标。jerk 保存逐关节和combined RMS/p95/max；不将数值导数峰称临床抖动。force RMS为按原区间加权 RMS，tracking为actual−issued reference。全部case有phase J_F、瞬时peak/RMS、trajectory deviation、tracking、torque-component差和原qualification；累计曲线在 `series/*.npz`。

## 滞后分析与科学分类

只相关 motion feature 与 instantaneous mean F、force变化，不相关单调 J_F 本身。分别在OUTBOUND/RETURN内聚合50/100/250/500/1000 ms等长窗，短尾只从相关分析中排除，完整J_F仍全部计入。motion保留raw并做21/101 native sample SG敏感性；线性去趋势、一阶差分和paired candidate−B对照分列。相关pair不跨phase。正lag表示motion领先force，范围±1 s；窗口≤1 s只允许至少8对样本，1 s结果样本很少且部分峰在范围边界，不能精确认定生理delay。

下面仅展示50 ms raw acceleration-variation rate；“peak r”取±1 s内最大绝对值，保留原正负号，未挑选最好看的正相关。

| case | phase | transform | zero-lag r | peak signed r | lag s |
|---|---|---|---:|---:|---:|
{chr(10).join(lag_rows)}

B/18D OUTBOUND 原水平在+0.25–0.30 s出现温和正峰，去趋势后最大峰转为负且lag变为−0.35 s；RETURN原水平峰在+1 s搜索边界，一阶差分则主要同步。velocity TV、jerk没有提供一致领先关系。部分within-phase circular-shift max-lag比较显示罕见相关，全部保留；它们有负向、force领先或同步的结果，不能选择性解释为motion领先降力机制。循环shift仅为保留序列自相关的描述性参照，短周期任务的非平稳趋势、不同指标/尺度和同一Human状态仍限制其统计含义，不提供因果p值或独立重复数。

**CORRELATIONAL：** 局部motion/force瞬态共现、宽窗acceleration variation与force的部分相关。**CONSISTENT-WITH-HYPOTHESIS：** 18D整体及部分合法微扰同时较低force与某些motion指标。**NOT-SUPPORTED：** 现有资料中的稳定同向、稳定领先、跨OUT/RETURN的通用motion→force规则；据此驱动持续waypoint/speed优化。**UNRESOLVED：** 纯temporal因果效应、allocator/tracking/replan的独立机制、跨状态可靠性。四者范围不同，不将未解决问题写成全局不可能。

## 分支与交付

Phase1不足以通过进入新物理敏感性实验的门，采用情况D。历史+0.05属于force稍低但motion明显变差的B类反例；adaptive_D2的TV_v/jerk微好而force升高，属于C类反例，acceleration variation也略升，不能称全指标motion改进。D1 inverse的微小降力伴velocity TV上升，不能作为本轮force+motion有效改进。历史D1_hip_neg/S_late的少量同向指标变化保留，force RMS及部分逐关节指标仍可能变差，也没有新的稳健Pareto区域证据。没有满足A的新候选，因此新repeat=0、新prefix验证=0。

情况E的最小缺口是：可绑定同一spatial path及独立单调clock、并对复合导数、连续geometry/offset、causal20ms约束、mechanics、stop/40ms bridge和current-state admission完整重验的reference/certificate合同。原100ms生命周期和native ownership仍须保持。已有multisegment quintic执行能力不等于已支持degree30纯timewarp；没有修改旧证书、阈值或plant。

核心图01为B/18D/+0.05，图02为B/+0.02/代表合法D1；每列相同task/absolute时间与phase边界，含actual/reference hip-knee、F、J_F、actual dq、TV_v、acceleration variation、jerk及request/activation/splice/waypoint/knot/terminal marker。planned waypoint与实际Human到达明确区分。图03为force及18D局部收益，04为anomaly，05–06为lag/trend敏感性，07为历史候选trade-off。PNG/SVG均保留。

入口：`REPRODUCTION.md`、`CANDIDATES.md`、`CANDIDATE_PARAMETERS_AND_QUALIFICATION.json`、`RAW_DERIVED_METRICS.json`、`LAG_ANALYSIS.json`、`FORCE_RISE_LAGS.json`、`PAIRED_DIFFERENCE_LAGS.json`、`ANOMALY_TIME_ALIGNMENT.json`、`SOURCE_MANIFEST.json`和`EXECUTION/ATTEMPT_ACCOUNTING.json`。原始完整trace/native/receipt保存在其原canonical包，本包以hash引用并保存关键完整receipt流和派生数组；这是显式存档依赖，Windows副本仅作审阅。

分析工程失败两次均保留：终末无command的NaN component误纳入断言；raw validator误假设Human坐标位于最后两轴。已分别按真实命令区间、存档[0,1]地址修正并逐样本验证，未改变科学参数、数值精度门或原始数据。没有训练RL/Q/MLP、Git修改命令、硬件动作或新physics。保护审核范围和结果见`audit/FINAL_PROTECTION.json`。**NEXT_RESEARCH_DECISION：研究tracking/allocator/replan interaction mechanism；不提出已获证据支持的bounded continuous coordination下一阶段。STOP。**
'''
    write('REPORT.md',report)
    candidates=['# 存档候选参数与资格','全部为历史物理结果的本轮只读重算；本轮没有新增candidate。原始完整门、参数、逐关节/phase指标见JSON。','| candidate | J_F N·s | B−J_F N·s | TV_v/B | TV_a/B | jerk RMS/B | motion |','|---|---:|---:|---:|---:|---:|---|']
    for x in M:candidates.append(f"| {x['label']} | {x['J_F_N_s']:.9f} | {x['gain_vs_B_N_s']:+.9f} | {x['velocity_TV_ratio_vs_B']:.6f} | {x['acceleration_variation_ratio_vs_B']:.6f} | {x['jerk_combined_RMS_ratio_vs_B']:.6f} | {'FAIL' if x['qualification']['motion'] is False else 'development PASS'} |")
    candidates.extend(['','最新19个arm：task/safety/receipt均为存档scientific-mode PASS；motion 17 PASS、2 FAIL。18D另为historical development PASS，旧合法prefix motion 0/4保持。Host plan_age失败不升级。','D1/D2/D3、adaptive及S_PROXY的精确fraction、每点hip/knee角度、时间fraction见CANDIDATE_PARAMETERS_AND_QUALIFICATION.json；18D18参数与冻结候选完整复制，未重新选择。','正负force差、force RMS和全部motion指标要联合审阅；低于B的极小数字不能单独当作新的有效改善。'])
    write('CANDIDATES.md','\n\n'.join(candidates[:3])+'\n'+'\n'.join(candidates[3:]))
    write('NEXT_RESEARCH_DECISION.md','''
# NEXT_RESEARCH_DECISION — STOP

分支D：现有同Human、同开发状态数据没有建立稳定motion→instantaneous force→cumulative burden的同向领先关系。局部共现保留为CORRELATIONAL；通用平滑降力规则NOT-SUPPORTED，因果机制UNRESOLVED。新physics/repeat/prefix validation均0。

不扩大waypoint/speed搜索，不启动smoothness optimizer或RL/Q/MLP，不将旧18D或微小历史force差重新命名为新候选。正式B不变。

下一研究优先tracking response、allocator wrench/robot torque映射和request→activation→splice timing：异常task5.87s/absolute15.92s以及旧18D4–6s、15–16s收益区间最有信息量。先做因果链和状态依赖分析，再另立有界、配对、合法父状态fork的验证合同。此处仅建议，不自动运行。

分支E保留：纯spatial-path-preserving speed需要完整time-map/reference/证书支持。现有S_PROXY有几何混杂，exact degree30 warp不能借旧2×6证书执行。没有证据要求当前立即扩该接口。

没有新完整qualification PASS且优于B的候选；未满足情况A，因此不提出已经得到实证支持的bounded continuous coordination研究推进。STOP。
''')
    write('REPRODUCTION.md',f'''
# Reproduction — archive-only, zero new physics

Canonical package: `{P}`. Windows review: `C:\\Users\\HankL\\Desktop\\Coding\\adaptive_traction_mpc\\force_motion_coupling_diagnosis_v2`.

Python `/home/hank/envs/adaptive-online-rl-v1/bin/python` and existing NumPy/SciPy/Matplotlib are reused. No dependency installation. `SOURCE_MANIFEST.json` lists every consumed archive path/size/SHA256, including complete 5ms trace, summary/config, 0.25ms native-derived arrays and full compressed native/receipt archive. These archives remain in original Side Study packages. `provenance/` holds copied original contracts/results, all candidate configs/measured qualification, frozen18D parameters and complete positive-step receipts for five core cases. `series/` stores all20 force/cumulative/native motion arrays. This is an explicit archive-dependent package; it does not claim all historical physical source/model closures were duplicated.

For a fresh, separately named output (never overwrite this stopped package):

```bash
PY=/home/hank/envs/adaptive-online-rl-v1/bin/python
SRC={P}
OUT=/home/hank/coding/adaptive-traction-mpc-side-studies/force_motion_coupling_diagnosis_v2_recompute_001
export IHEAR_DIAG_OUTPUT="$OUT"
"$PY" -B "$SRC/control/analyze.py"
"$PY" -B "$SRC/control/enrich.py"
"$PY" -B "$SRC/control/focus_and_plot.py"
```

OUT must not exist. These commands import no controller/plant and never step physics. They regenerate read-only analyses into OUT. No inherited campaign/owner script should be run. Full native checks may take roughly a minute depending on storage. The `--resume-engineering` and `--verify-only` flags are guarded recovery modes used for the two recorded analysis failures; default reproduction requires a fresh output and does not use them.

The finalized script uses explicit archived Human joint addresses [0,1], verifies every native task q/dq against archived series, and checks native command ownership/counts across all116320 native rows/5817positive-step receipts in each of B/18D/+0.02/+0.05/repeat. For other15cases it verifies every5ms q/dq node and derivatives of stored native series, retaining the earlier full evaluator evidence separately. Last TASK trace row has no future command and NaN torque-component decomposition; only that final row is excluded from component checks, while force/trajectory completion and all integration intervals stay present.

J_F is original5ms boundary-left quadrature, not trapezoidal and not a fabricated0.25ms force stream. Phase costs clip original intervals at actual transition times. Motion TV and numerical derivatives retain native rate. Correlation uses independently aggregated phase-local equal bins, positive lag=motion leadsforce, ±1s, >=8pairs. Full tails remain in cost accounting. Raw/SG21/SG101, level/detrend/first-difference, force-rise and matched-difference analyses are separate; cumulative J is never an independent correlated signal. All trends/lag maxima remain exploratory, without independent participant replication.

All qualification is inherited at its original PHYSICAL_LEVEL1/scientific-mode scope. No new qualification, new physical candidate, host qualification, cross-state validation or training. Main git state/metadata and hashes of consumed archives are compared before/after; this is not a new full-byte hash of every unrelated historical package. Exact scope is in FINAL_PROTECTION. Engineering failures and their repairs are preserved in EXECUTION. STOP.
''')
    (P/'EXECUTION').mkdir(exist_ok=True)
    eng=loadj('audit/ENGINEERING_ATTEMPTS.json');eng[-1]['status']='PASS';put('audit/ENGINEERING_ATTEMPTS.json',eng)
    put('EXECUTION/ATTEMPT_ACCOUNTING.json',{'analysis_attempts':[{'id':1,'status':'FAIL','stage':'terminal command-component boundary'},{'id':2,'status':'FAIL','stage':'native Human address mapping'},{'id':3,'status':'PASS','stage':'corrected raw verification and finalized archive diagnosis'}],'negative_results_preserved':True,'physics':{'START':0,'END':0,'native_steps':0,'simulated_time_s':0,'new_candidates':0,'repeats':0,'new_prefix_validation':0},'historical_denominator':{'latest_archived_candidate_arms':19,'additional_frozen18D':1,'latest_archived_motion_pass':17,'latest_archived_motion_fail':2,'raw_reaudited_cases':5},'branch':'D, with temporal interface limitation E','source_or_parameter_changes':'analysis implementation only; original B/plant/config/contracts/raw unchanged','claim':'No new experiment trace/receipt exists because no new experiment was launched; existing full provenance explicitly referenced.'})
    write('EXECUTION/FAILURES.md','''
# Preserved analysis failures

Attempt1 stopped at `load_case` torque-component closure. The final TASK boundary has NaN components because no subsequent command is issued; all3806 actual command intervals close at <3e-14Nm. The repair asserts every earlier row finite and only the terminal no-command row excluded, retaining the original1e-9 check. Initial source is audit/analyze_attempt1.py.

Attempt2 completed all20derived metrics and lag analyses, then stopped at raw-native coordinate verification: it had incorrectly assumed Human occupied the finaltwo generalized coordinates. Archived evaluator quality explicitly maps Human qpos/qvel to[0,1]. Repair uses that mapping and verifies every native sample/receipt. Source is audit/analyze_attempt2.py. This did not change the already-correct stored native-derived arrays or their5ms truth alignment.

Attempt3 completed all5raw native/receipt audits with exactly zero q/dq discrepancy. These are postprocessing implementation failures, no physical STARTs, no threshold change and no raw data edits. This file reconstructs the concise failure record from session tool outputs; it is not presented as an original captured subprocess log.
''')
    ex=loadj('EXECUTION.json');ex.update(status='STOP',client_closeout_date='2026-10-17',phase2='NOT_RUN_BRANCH_D',next_research_decision='tracking/allocator/replan mechanism; do not expand waypoint/speed search');put('EXECUTION.json',ex)
    put('PHYSICS_STOP.json',{'status':'STOP','allow_restart':False,'physics_starts':0,'reason':'Phase1 did not establish stable force-motion coupling; branchD; no new physical interface work justified'})
    print('REPORT_WRITTEN',str(P/'REPORT.md'),flush=True)
    # Protected scope: unchanged main metadata+git and every consumed archive SHA.
    before=loadj('audit/PROTECTION_BEFORE.json');aftergit={}
    for label,args in [('HEAD',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
        bb=subprocess.check_output(['git','-C',str(MAIN)]+args);aftergit[label]=hashlib.sha256(bb).hexdigest();assert aftergit[label]==before['git'][label]['sha256'],label
    index=sha(MAIN/'.git/index') if (MAIN/'.git/index').exists() else None;assert index==before['git']['index_sha256']
    meta={str(f.relative_to(MAIN)):[f.stat().st_size,f.stat().st_mtime_ns] for f in MAIN.rglob('*') if f.is_file() and '.git' not in f.relative_to(MAIN).parts}
    assert meta==before['main_file_metadata']
    sf=loadj('SOURCE_MANIFEST.json')['files'];changed=[f for f,v in sf.items() if sha(f)!=v['sha256']];assert not changed
    put('audit/FINAL_PROTECTION.json',{'status':'PASS','main_git_HEAD_branch_status_index_staged_unstaged_exact':True,'main_metadata_files':len(meta),'main_metadata_unchanged':True,'consumed_source_hashes':len(sf),'consumed_archives_bytes_unchanged':True,'unrelated_side_studies_scope':'not rehashed; analysis did not write outside its new package','formal_B_modified':False,'no_git_mutations':True,'no_physics_spawned':True,'new_physics_START_END':[0,0]})
    # This is validation, not a promise of causal scientific success.
    put('PACKAGE_VERIFICATION.json',{'status':'PASS','meaning':'declared data accounting, source preservation and archive diagnosis complete; stable coupling hypothesis NOT-SUPPORTED at tested scope','cases':20,'core_raw_audits':5,'phase_integrals_close':True,'no_native_force_fabrication':True,'motion_derivatives_reconstructed_exact':True,'all_negative_results_retained':True,'new_physics':0,'new_qualified_improvement':None,'visual_QA':'pending human-readable image inspection in session'})
    inventory={str(f.relative_to(P)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in P.rglob('*') if f.is_file() and f.name not in ['PACKAGE_MANIFEST.json','STORAGE.json']}
    put('PACKAGE_MANIFEST.json',{'files':inventory,'excluded':['PACKAGE_MANIFEST.json','STORAGE.json']})
    put('STORAGE.json',{'logical_bytes':sum(v['bytes'] for v in inventory.values()),'file_count':len(inventory),'raw_archives_shared_by_hash_reference':True})
    # Review export excludes the large raw git diff snapshots; source provenance
    # and exact metrics remain canonical and no old Windows folder is changed.
    for d in ['figures','derived','events','series','EXECUTION','provenance','audit']:
        for f in (P/d).rglob('*'):
            if not f.is_file() or f.name=='git_staged_before.txt':continue
            target=REVIEW/f.relative_to(P);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    for f in P.glob('*'):
        if f.is_file():shutil.copy2(f,REVIEW/f.name)
    print('CLOSEOUT_PROTECTION_PASS',len(meta),len(sf),'RETURN_TOP',return_top,flush=True)
    print('REVIEW_EXPORTED',REVIEW,flush=True)

if __name__=='__main__':main()
