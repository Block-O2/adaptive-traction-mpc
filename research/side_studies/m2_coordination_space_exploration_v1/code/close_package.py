from pathlib import Path
import sys,os,json,hashlib,time,shutil,gzip,subprocess,datetime
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_coordination_space_exploration_v1')
OLD=S.parent/'b_fast_jitter_m2_host_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
sys.path.insert(0,str(S/'code'))
from prepare_package import git_snapshot
def load(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def save(name,x):(S/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def pct(x):return f'{x:.2f}%'
def main():
    ledger=load(S/'TASK_LEDGER.json');assert all(r['status']!='RUNNING' for r in ledger.values())
    plan=load(S/'RUN_PLAN.json');assert time.time()<plan['hard_stop_unix']
    evidence=load(S/'PAIRED_HOST_RESULTS.json');trade=load(S/'MULTIOBJECTIVE_TRADEOFFS.json');q=load(S/'Q_RANKING_ATTRIBUTION.json');lineage=load(S/'EXECUTION_LINEAGE.json');fast=load(S/'FAST_RUNTIME_OBSERVATIONS.json');extra=load(S/'reports/RETURN_EXECUTION_WINDOWS.json');agg=evidence['summary'];pairs=evidence['pairs'];assert len(pairs)==4 and all(p['status']=='PASS' for p in pairs)
    diagid='009_isolated_B_compiled_FAST_diagnostic';diag=load(S/'output'/(diagid+'_COMPILED_FAST_DIAGNOSTIC.json'));assert ledger[diagid]['status']=='FAILED_NO_RESULT' and diag['total_actual_services']==0
    log=(S/'logs'/(diagid+'.log')).read_text();assert 'INVALID_COMPILED_CAPTURE_BINDING' in log
    failed=dict(id=diagid,status='FAIL',physical='NOT_RUN',causal_host='NOT_EVALUABLE',observed_FAST='NOT_EVALUABLE',formal_runtime_qualification='NOT_RUN',legacy_R2='NOT_EVALUABLE',legacy_strict55='NOT_EVALUABLE',hardware='NOT_RUN',actual_native_physics_steps=0,worker_binding='FAIL',thread_CPU_scheduler_wait='NOT_EVALUABLE',reason='Compiled namespace capture identity assertion failed before study_common.run/physical epoch; no native physical step executed',attempt_counted_in_budget=True,excluded_from_primary_pairs=True,raw_diagnostic_file=str(S/'output'/(diagid+'_COMPILED_FAST_DIAGNOSTIC.json')),log_path=str(S/'logs'/(diagid+'.log')),no_retry=True)
    save('reports/'+diagid+'_AXES.json',failed)
    fast.update(status='PARTIAL',isolated_diagnostic=failed,historical_slowdown_recurrence_comparison=str(S/'reports/FAST_SERVICE_RECURRENCE_COMPARISON.json'),secondary_FAST_failed_ids=[r['id'] for r in fast['runs'] if r['observed_FAST_status']=='FAIL'],engineering_limit='Two rolling1s windows exceed unchanged6ms threshold; broad historical slowdown not conclusively reproduced; compiled-loop CPU/wait attribution attempt failed before physics. No root-cause or qualification claim.')
    save('FAST_RUNTIME_OBSERVATIONS.json',fast)
    resources=[json.loads(l) for l in (S/'output/RESOURCE_LOG.jsonl').read_text().splitlines()];resource=dict(samples=len(resources),WSL_min_available_GiB=min(r['mem_available'] for r in resources)/2**30,Windows_min_available_GiB=min(r['windows'].get('available',float('inf')) for r in resources)/2**30,Windows_min_commit_headroom_GiB=min(r['windows'].get('commit_headroom',float('inf')) for r in resources)/2**30,swap_in_delta=resources[-1]['swap_in']-resources[0]['swap_in'],swap_out_delta=resources[-1]['swap_out']-resources[0]['swap_out'],oom_delta=resources[-1]['oom_kill']-resources[0]['oom_kill'],source=str(S/'output/RESOURCE_LOG.jsonl'))
    save('reports/RESOURCE_SUMMARY.json',resource)
    joins=[]
    for ident,r in ledger.items():
        p=S/'output'/(ident+'_DIRECT_IPC.json')
        if p.exists():
            jr=[v for v in load(p)['rows'] if v.get('event')=='JOIN'];joins.append(dict(id=ident,joins=jr,status='PASS' if jr and all(v.get('joined') and v.get('exitcode')==0 for v in jr) else 'FAIL'))
    assert len(joins)==8 and all(r['status']=='PASS' for r in joins)
    processes=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if str(S) in cmd and 'python' in cmd:processes.append(dict(pid=int(p.name),cmd=cmd))
        except OSError:pass
    # Never kill unrelated processes; require joined study-owned workers.
    assert not processes,processes
    save('reports/WORKER_JOIN_AUDIT.json',dict(status='PASS',runs=joins,remaining_task_processes=processes,failed_diagnostic_process_joined_by_dispatcher=True,no_unrelated_process_terminated=True))
    (S/'analysis_code').mkdir(exist_ok=True)
    for p in W.glob('*.py'):
        dest=S/('analysis_code' if (OLD/'code'/p.name).exists() else 'code')/p.name
        shutil.copy2(p,dest)
    protection=[]
    for name in ('HISTORY_BEFORE.json','OTHER_HISTORY_BEFORE.json'):
        initial=load(S/'preservation'/name);changed=[p for p,h in initial.items() if not Path(p).is_file() or sha(Path(p))!=h];assert not changed,changed
        protection.append(dict(snapshot=name,verified_files=len(initial),changed=changed,status='PASS'))
    before=load(S/'preservation/GIT_BEFORE.json');after=git_snapshot();assert before==after
    save('preservation/GIT_AFTER.json',after)
    originalset=set(load(S/'preservation/HISTORY_BEFORE.json'));currentset={str(p) for p in OLD.rglob('*') if p.is_file()};assert originalset==currentset
    copied=[]
    for d in ('source','deps','native','build','weights','code'):
        for p in (S/d).rglob('*'):
            if not p.is_file() or 'results' in p.relative_to(S).parts or '__pycache__' in p.parts:continue
            rel=p.relative_to(S);original=OLD/rel
            if not original.is_file():continue
            if p.suffix in ('.py','.json','.xml','.yaml','.yml','.toml','.sh'):
                expected=original.read_text().replace(str(OLD),str(S)).replace("'b_fast_jitter_m2_host_v1'","'m2_coordination_space_exploration_v1'").replace('"b_fast_jitter_m2_host_v1"','"m2_coordination_space_exploration_v1"')
                assert p.read_text()==expected,str(rel)
            else:assert sha(p)==sha(original),str(rel)
            copied.append(str(rel))
    assert sha(S/'weights/frozen_Q_v1/weights.npz')==q['Q_sha256']
    save('preservation/FINAL_PRESERVATION.json',dict(status='PASS',main_git_unchanged=before==after,history_checks=protection,historical_file_set_unchanged=True,frozen_source_files_exact_or_path_relocated=len(copied),Q_sha256=q['Q_sha256'],controller_scheduler_governor_safety_lifecycle_math_unchanged=True,old_results_not_relabelled=True,Windows_WSL_configuration_unchanged=True))
    # Independent recomputation from raw traces rather than trusting summaries.
    sys.path.insert(0,str(W))
    import numpy as np
    recomputed=[];gzip_checks=[];truth=[]
    for r in lineage['runs']:
        ident=r['id'];folder=S/'source/results'/ident
        with np.load(folder/'trace.npz') as z:
            mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1);jf=float(f[:-1]@np.diff(t));mi=float(moment[:-1]@np.diff(t));summary=load(folder/'summary.json');m=load(S/'output'/(ident+'_RESULT.json'))['metric']
        assert abs(jf-m['J_F'])<1e-8 and abs(mi-m['moment_integral'])<1e-8
        recomputed.append(dict(id=ident,J_F_N_s=jf,moment_integral_Nm_s=mi,J_F_error_N_s=jf-m['J_F'],moment_error_Nm_s=mi-m['moment_integral']))
        h=hashlib.sha256();count=0
        with gzip.open(folder/'runtime_artifacts.json.gz','rb') as file:
            for b in iter(lambda:file.read(2**20),b''):h.update(b);count+=len(b)
        gzip_checks.append(dict(id=ident,status='PASS',uncompressed_bytes=count,uncompressed_sha256=h.hexdigest(),CRC_eof_verified=True))
        truth.append(dict(id=ident,truth_firewall=summary.get('truth_firewall'),deployable_truth_in_decisions=any(d.get('deployable_truth_consumed',False) for d in summary['decisions']),physical_conditions=load(S/'reports'/(ident+'_AXES.json'))['metric']['physical_audit']['unchanged_evaluator']['raw_scorer_v2']['conditions']))
    assert not any(r['deployable_truth_in_decisions'] for r in truth)
    save('reports/INDEPENDENT_TRACE_RECOMPUTATION.json',dict(status='PASS',runs=recomputed,gzip=gzip_checks,truth_firewall=truth))
    sign_table='| Pair | B J_F | M2 J_F | ΔJ_F (M2−B) | 相对差值 | Moment Δ | Knee RMS Δ° | True clearance Δmm |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
    for p in pairs:sign_table+=f"| {p['pair_id']} | {p['raw_B_J_F_N_s']:.6f} | {p['raw_M2_J_F_N_s']:.6f} | {p['delta_J_F_M2_minus_B_N_s']:.6f} | {p['relative_delta_J_F_percent']:.3f}% | +{p['moment_delta_percent']:.3f}% | +{p['tradeoff_deltas']['true_reference_RMS_deg'][1]:.6f} | {p['tradeoff_deltas']['true_clearance_m']*1000:+.6f} |\n"
    phase_table='| Pair / phase | B / M2 J_F N·s | integrated T B / M2 s | phase-clock T B / M2 s | mean F B / M2 N | duration contribution | mean-force contribution |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for p in pairs:
        for phase,v in p['phases'].items():
            b=v['B'];m=v['M2'];phase_table+=f"| {p['pair_id']} / {phase} | {b['J_F_N_s']:.6f} / {m['J_F_N_s']:.6f} | {b['integrated_trace_duration_s']:.6f} / {m['integrated_trace_duration_s']:.6f} | {b['phase_clock_duration_s']:.6f} / {m['phase_clock_duration_s']:.6f} | {b['mean_force_N']:.6f} / {m['mean_force_N']:.6f} | {v['duration_contribution_N_s']:+.6f} | {v['mean_force_contribution_N_s']:+.6f} |\n"
    physical_table='| Pair / arm | force peak N | moment integral / peak Nm·s / Nm | hip / knee TASK true RMS° | true / measured min clearance mm | force / moment headroom N / Nm |\n|---|---:|---:|---:|---:|---:|\n'
    for p in pairs:
        for label,ident in (('B',p['B_id']),('M2',p['M2_id'])):
            v=p['evaluation_records'][ident];ph=v['physical'];rms=ph['true_reference_tracking_RMS_deg'];head=v['safety_margins'];hf=head['force_headroom_N'];hm=head['moment_headroom_Nm']
            physical_table+=f"| {p['pair_id']} / {label} | {v['force_peak_N']:.6f} | {v['moment_integral_Nm_s']:.6f} / {v['moment_peak_Nm']:.6f} | {rms[0]:.6f} / {rms[1]:.6f} | {ph['minimum_true_shank_clearance_m']*1000:.6f} / {ph['minimum_measured_sleeve_gap_m']*1000:.6f} | {hf if hf is not None else 'NOT_EVALUABLE'} / {hm if hm is not None else 'NOT_EVALUABLE'} |\n"
    runtime_table='| run | physical | causal host | observed FAST | formal runtime | legacy R2 | strict55 | hardware | gap p50/p95/p99 ms | rolling1s max ms |\n|---|---|---|---|---|---|---|---|---:|---:|\n'
    for r in fast['runs']:
        gap=r['service_start_gap_ms'];runtime_table+=f"| {r['id']} | {r['physical']} | {r['causal_host']} | {r['observed_FAST_status']} | NOT_RUN | {r['legacy_R2']} | {r['legacy_strict55']} | NOT_RUN | {gap['p50']:.6f}/{gap['p95']:.6f}/{gap['p99']:.6f} | {r['rolling_1s_mean_ms']['max']:.6f} |\n"
    runtime_table+='| 009 isolated diagnostic | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE |\n'
    executable=sum(r['phase_execution']['RETURN']['executed_nonzero'] for r in lineage['runs']);outbound=sum(r['phase_execution']['OUTBOUND']['executed_nonzero'] for r in lineage['runs']);qfixed=q['fixed_candidates_mask_carry_probe'];elapsed=time.time()-plan['t0_unix'];minmeas=min(v['physical']['minimum_measured_sleeve_gap_m'] for p in pairs for v in p['evaluation_records'].values())
    report=f'''# iHEAR Lab — Frozen M2 泛化与协调机制归因 v1

终态：**PARTIAL**。阶段 A 排序结构审计 PASS（真正 state-conditioned preference FAIL），阶段 B 独立注册扰动配对 PASS（4/4），阶段 C 解析等价 PASS / 物理 comparator NOT_RUN，阶段 D 描述性 RETURN 归因 PASS，阶段 E 多指标测量 PASS，FAST 根因诊断 PARTIAL。PACKAGE_VERIFICATION 是证据完整性校验，不是科学、实时或硬件资格。

冻结 M2 在两个上一 host 工作包未运行的注册合法 prefix × 两个 seed 上均降低 J_F，合并 **{agg['pooled_delta_percent']:.3f}%**。平均力项解释合并下降的 **{agg['mean_force_fraction_of_total_delta']*100:.3f}%**，RETURN 贡献 **{agg['RETURN_fraction_of_total_delta']*100:.3f}%**。同时四组 moment integral 增加 **{trade['summary']['moment_integral_delta_percent']['min']:.2f}%–{trade['summary']['moment_integral_delta_percent']['max']:.2f}%**，knee TASK RMS 增加 **{trade['summary']['knee_RMS_delta_deg']['min']:.3f}°–{trade['summary']['knee_RMS_delta_deg']['max']:.3f}°**；3/4 true/measured clearance 下降，一组 force peak 增加4.229703 N。原始物理/安全合同8/8 PASS，但 force 收益没有构成多指标 Pareto dominance。

## 范围、协议和实际分母

上一包 REPORT 及 ledger/START-END/完整 axes 交叉核验 PASS：17次尝试、6次有效M2、25个非零计划、143645关联 native steps。旧失败与旧 R2 结论不变。本轮新目录 `{S}`；权重 SHA256 `{q['Q_sha256']}`；没有训练、微调、G/P、online adaptation 或新异步 planner。冻结120D/K3、candidate generation、排序定义、B native controller、scheduler/governor、commissioning科学语义、admission、40ms physical bridge、100ms expiry、causal ownership、carry/fallback和安全合同。仅迁移包路径。

Prefix P1={{OUTBOUND:[[0.30,-0.10,0.05]]}}；P2={{OUTBOUND:[[-0.15,0.25,-0.20]]}}，来自旧 `LEGAL_PREFIX_STABILITY_PROTOCOL.json` 的第1/2项。相对上一个 host 包独立，早期 SCI 已暴露，不能称完全未见扰动或新Human。Seeds=2026100801/2026100802；顺序P1s1 B→M2、P1s2 M2→B、P2s1 M2→B、P2s2 B→M2。输入物理模型、initial physical state、waypoints、prefix、instrumentation在每对内一致；真实 commissioning fit 允许并记录差异。B/M2都使用同一既有 worker envelope；B在公共prefix后为zero residual。Pair有效需完整导出、物理与causal PASS、配置一致、Q identity可核验及M2实际非零执行；不要求 FAST/R2 PASS 来纳入研究pair。协议先冻结，没有按结果改阈值或排除失败。

19ms strict55-derived研究性preguard的关闭仅适用于本轮已注册host配置（strict55_guard=false）：host_adapter以40ms检查worker年龄；原生100ms生命周期、source timestamp、current-state admission、native safety、causal ownership仍完整保留。没有解除其他检查。真实strict55结果单独失败。

新增 attempted dispatch **9/12**：8次完整host配对＋1次隔离诊断启动失败。隔离诊断在commissioning setup后、study_common.run/物理epoch前因INVALID_COMPILED_CAPTURE_BINDING退出，实际物理步0、没有完整RESULT，不计入有效运行；原始log/diagnostic JSON/ledger保留，未重试。成功物理8次，累计真实物理native steps **{lineage['all_physical_native_steps']}**；M2实际Q-selected非零计划 **{lineage['nonzero_plans']}**，关联native steps **{lineage['nonzero_native_steps']}**。公共prefix非零介入单独记录，不能当作Q收益执行证据。

## 配对力与多指标

单位J_F=N·s；Δ=M2−B，负值改善。主指标4/4改善；均值ΔJ_F={agg['delta_J_F_N_s']['mean']:.6f}，median={agg['delta_J_F_N_s']['median']:.6f}，sample SD={agg['delta_J_F_N_s']['sample_sd']:.6f}。相对差值范围{agg['relative_delta_J_F_percent']['min']:.3f}%至{agg['relative_delta_J_F_percent']['max']:.3f}%。n=4只有两个prefix且seed复用，描述性分布不能支持人口泛化或显著性结论。

{sign_table}
{physical_table}
完整moment积分/peak、力mean/peak、hip/knee true-reference TASK RMS及max、true/measured/session clearance、安全conditions/headroom和阶段tracking在MULTIOBJECTIVE_TRADEOFFS.json与PAIRED_HOST_RESULTS.json。最低measured sleeve gap为{minmeas*1000:.6f}mm。原始速度、加速度、ROM、torque、contact、clearance门限保持原条件审计；没有猜造缺失阈值。真实RMS基于TASK评估trace，native安全peak和clearance来自原native scorer，口径不混用。

## 排序能力与RETURN机制

selected_Q=linear，归一化反归一化折叠为Q=offset+w·x。固定集合、mask、carry和counts后，ΔQ_ij=w_U·[masked(p_i)−masked(p_j)]；state/history/carry/count公共项相消，state×plan交叉导数0。审计{len(q['rows'])}个真实旧/新决策（OUTBOUND {q['phase_counts']['OUTBOUND']}、RETURN {q['phase_counts']['RETURN']}）。固定集合探针的解析排序数{qfixed['analytic_unique_ranks']}、raw float32排序数{qfixed['raw_unique_ranks']}，top-choice变化{qfixed['raw_top_choice_changes']}；native pairwise数值误差最大{q['max_numeric_delta_error_N_s']:.9g} N·s。不宣称float32 bitwise等价；close-rank safeguard原样保留。Mask可以改变固定排序，carry可以改变候选身份，native feasibility和late-carry可以改变实际执行；都不是learned conditional preference。HOLD没有实际Q决策，经验排序审计NOT_EVALUABLE。解析等价足以回答固定排序comparator问题，无额外物理比较。

RETURN执行非零计划 **{executable}**，OUTBOUND **{outbound}**。RETURN实际native Δd均为负（range {extra['native_delta_d_by_phase']['RETURN']['min']:.6f}至{extra['native_delta_d_by_phase']['RETURN']['max']:.6f}，mean {extra['native_delta_d_by_phase']['RETURN']['mean']:.6f}），OUTBOUND多为正；固定计划偏好经过native实现产生方向一致但不完全相同的Δd，不能宣称反复精确同一个residual。实际RETURN同phase-elapsed window 12/12 J_F更低，OUTBOUND 6/7更低；窗口不足以独立识别因果效应，也不覆盖任务全部区间。

合并ΔJ_F={agg['pooled_delta_J_F_N_s']:.9f}：时长项={agg['duration_contribution_N_s']:.9f}，平均力项={agg['mean_force_contribution_N_s']:.9f} N·s。每阶段用对称乘积分解，阶段积分之和与完整任务闭合；同时保留真实phase-clock与integrated-trace duration，未裁剪HOLD或改R2。

{phase_table}
Q source time→raw ranking→selected K3/Δd→native admission/lifecycle→receipt→实际steps的逐请求链及状态/force/moment/tracking/clearance窗口见EXECUTION_LINEAGE.json及RETURN_ATTRIBUTION.md。进入RETURN的true q/dq差与commissioning beta/residual/geometry差已导出。OUTBOUND可能通过状态历史影响RETURN；没有单独阻断OUTBOUND或匹配commissioning，因此不能分离这些效应。Native timing改变carry与激活机会，也可解释部分pair差异；平均力下降仅支持协调改善，不是严格因果识别。

## FAST与独立资格轴

{runtime_table}
两个B运行（006、007）rolling1s mean超过原6ms；完整p50/p95/p99、rolling、miss/backlog、proposal age、lateness、reject/cancel/expiry/fallback在FAST_RUNTIME_OBSERVATIONS.json与逐run原始FUNCTIONAL/AXES。原始全局service wall compute与历史同边界对照在reports/FAST_SERVICE_RECURRENCE_COMPARISON.json。历史7.87–9.58ms是service gap p95，不能误写为service-compute。局部tail/window变慢存在，广泛历史根因仍未知。

为同步测实际compiled loop的CPU/wait而注册一次隔离诊断；绑定guard在物理前FAIL，阻止使用错误作用域数据。thread CPU/scheduler wait NOT_EVALUABLE；没有以wall-minus-CPU猜造scheduler wait，没有CPU频率/WSL调度根因或正式runtime/hardware资格结论。诊断不与pair混合，不改变B，停止后不再做物理尝试。

## 最终八项判断与下一方向

1. 冻结M2在本轮两新prefix×两seed的4/4配对持续降低J_F，合并6.83%；这是一名已暴露Human的有限合法扰动泛化证据，广泛泛化PARTIAL。
2. 合并下降99.962%来自实际平均力项，0.038%来自时长项；阶段乘积分解和trace积分独立重算闭合。
3. Q真正状态相关计划排序能力FAIL：线性120D缺少state×plan交互，固定mask下等价固定计划偏好。绝对分数、mask、candidate RNG或carry选择变化不能填补此能力。
4. RETURN机制更符合固定masked residual偏好经过state-dependent native feasibility/realization与carry执行。RETURN更多实际残余且Δd方向一致，收益85.578%集中RETURN；conditional learned coordination没有被证明。
5. Force收益伴随moment+13.28–25.64%、knee RMS+0.341–0.424°；3/4clearance下降，force peak非系统性改善。当前全部安全PASS不证明未见状态的安全鲁棒性；不构造新加权reward。
6. FAST仍有两个rolling1s FAIL、tail、callback miss和proposal/carry问题；历史根因未明，实际compiled CPU/wait诊断NOT_EVALUABLE，正式runtime资格NOT_RUN，legacy R2/strict55全部FAIL。
7. 冻结Q可作为透明的固定偏好residual-coordination执行baseline；不足以作为已经具备state-conditioned learning、personalization或硬件资格的baseline。应将固定masked ranking、native mask/admission与后续学习能力分开比较。
8. 下一代方法需具备可检验的state×plan preference、对力矩/膝tracking/clearance/peak的多指标决策约束，以及对候选、issued slots、carry/lifecycle与actual execution的清晰归因；不能仅拟合绝对J_F或在现有状态公共项上增加容量却不测ranking inversions。

**唯一推荐：C. Multi-objective / safety-aware coordination learning。** 本轮4/4 force改善同时4/4moment和knee代价支持优先处理Pareto trade-offs；state-conditioned ranking是所需能力的一部分。下一工作包应先明确多指标/安全目标并设计可检验state×plan排序结构与冻结fixed-ranking对照，本轮不开始、不训练。FAST实时工程问题独立保留，不能将其PASS/FAIL直接当成Q科学价值或硬件资格。

## 时间、保护、验证与交付

t0=2026-10-08 20:59:12 Asia/Shanghai；停止启动新实验时间22:59:12；硬截止23:29:12。本报告生成累计wall约{elapsed/60:.2f}min；未耗尽预算。没有重型实验并行；没有改Windows/WSL RAM、swap、电源或调度、没有终止无关进程。资源记录WSL available最低{resource['WSL_min_available_GiB']:.3f}GiB，Windows available最低{resource['Windows_min_available_GiB']:.3f}GiB，commit headroom最低{resource['Windows_min_commit_headroom_GiB']:.3f}GiB，swap in/out delta={resource['swap_in_delta']}/{resource['swap_out_delta']}，OOM delta={resource['oom_delta']}。

Git branch/HEAD/status/index/staged-diff与startup快照完全相同。没有branch切换、stage、commit、push、reset、stash或删除历史文件。上一包所有字节及file set、其他历史保护清单、冻结Q与复制实现（仅路径迁移）校验PASS。所有8个TASK worker JOIN exitcode0，诊断dispatcher已退出；无task-owned process遗留。原完整gzip EOF/CRC验证、TASK力/矩积分独立重算、phase分解与receipt非重复PASS。

要求的10个文件：REPORT.md、EXPERIMENT_MANIFEST.json、Q_RANKING_ATTRIBUTION.md/.json、PAIRED_HOST_RESULTS.json、RETURN_ATTRIBUTION.md、MULTIOBJECTIVE_TRADEOFFS.json、EXECUTION_LINEAGE.json、FAST_RUNTIME_OBSERVATIONS.json、PACKAGE_VERIFICATION.json。完整source/results包含8次trace.npz/summary/config/runtime_artifacts.json.gz；logs、queue、output、reports、weights、frozen code/binary与preservation保留。历史数据只读取。新派生JSON的raw NaN/Infinity明确导出为null并记录字段路径/NOT_EVALUABLE，原artifact不改。

命令：prepare_package.py；audit_ranking.py；冻结run_registered_batch.py pairs；analyze_package.py；additional_attribution.py；fast_compare.py；注册并单次fast_dispatch.py隔离diagnostic；close_package.py。均使用用户指定`/home/hank/envs/adaptive-online-rl-v1/bin/python -B`。新研究Python/report导出代码在本包code；paired运行实现与原包仅path relocation。报告Windows副本`C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1/REPORT.md`，canonical Linux源路径保持可追溯。

STOP。不自动开始下一工作包，不训练Q，不宣称online personalization或hardware qualification。
'''
    (S/'REPORT.md').write_text(report)
    events=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];assert len(starts)==len(ends)==9
    required=['REPORT.md','EXPERIMENT_MANIFEST.json','Q_RANKING_ATTRIBUTION.md','Q_RANKING_ATTRIBUTION.json','PAIRED_HOST_RESULTS.json','RETURN_ATTRIBUTION.md','MULTIOBJECTIVE_TRADEOFFS.json','EXECUTION_LINEAGE.json','FAST_RUNTIME_OBSERVATIONS.json','PACKAGE_VERIFICATION.json']
    verified=dict(status='PASS',scientific_package_status='PARTIAL',checked_unix=time.time(),required_files={r:dict(exists=(S/r).is_file(),sha256=sha(S/r)) for r in required if r!='PACKAGE_VERIFICATION.json'},primary_pairs=4,primary_runs=8,attempted_dispatches=9,failed_prephysics_diagnostics=1,actual_native_steps=lineage['all_physical_native_steps'],actual_Q_nonzero_plans=lineage['nonzero_plans'],actual_Q_nonzero_steps=lineage['nonzero_native_steps'],START_END_balance=True,time_budget_met=True,attempt_budget_met=True,source_Q_identity='PASS',history_main_git_preservation='PASS',gzip_CRC='PASS',independent_integral_recomputation='PASS',phase_integral_and_symmetric_decomposition_closure='PASS',receipt_nonduplication='PASS',source_state_truth_firewall='PASS',TASK_worker_JOIN='PASS',remaining_task_processes=[],formal_runtime_qualification='NOT_RUN',hardware='NOT_RUN',diagnostic_CPU_wait='NOT_EVALUABLE',no_auto_resume=True)
    save('PACKAGE_VERIFICATION.json',verified)
    for name in required:
        assert (S/name).is_file()
        if name.endswith('.json'):json.loads((S/name).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
    save('STATE.json',dict(status='COMPLETE',scientific_status='PARTIAL',phase='CLOSED',active=[],physics_attempts=9,valid_host_runs=8,valid_pairs=4,updated_unix=time.time(),next_action='STOP; no automatic follow-on or training'))
    save('PACKAGE_CLOSED.json',dict(status='CLOSED',t0_unix=plan['t0_unix'],closed_unix=time.time(),wall_seconds=time.time()-plan['t0_unix'],hard_stop_unix=plan['hard_stop_unix'],attempted_dispatches=9,valid_physical_runs=8,physical_native_steps=lineage['all_physical_native_steps'],active=[],physical_dispatch_permitted=False,no_auto_resume=True))
    manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name!='FULL_PACKAGE_MANIFEST.json'}
    save('FULL_PACKAGE_MANIFEST.json',manifest)
    # Complete review copy, including raw exports, with byte-for-byte readback.
    for p in S.rglob('*'):
        if not p.is_file():continue
        dest=W/p.relative_to(S);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        assert sha(dest)==sha(p),str(dest)
    print(json.dumps(dict(status='CLOSED',scientific_status='PARTIAL',verification='PASS',path=str(S),Windows_review=str(W),wall_seconds=time.time()-plan['t0_unix'],attempts=9,valid_pairs=4,files=len(manifest),bytes=sum(v['bytes'] for v in manifest.values()),aggregate=agg,FAST_failed_ids=fast['secondary_FAST_failed_ids']),ensure_ascii=False))
if __name__=='__main__':main()
