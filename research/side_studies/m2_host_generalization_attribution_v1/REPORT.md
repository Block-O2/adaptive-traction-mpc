# iHEAR Lab — Frozen M2 泛化与协调机制归因 v1

终态：**PARTIAL**。阶段 A 排序结构审计 PASS（真正 state-conditioned preference FAIL），阶段 B 独立注册扰动配对 PASS（4/4），阶段 C 解析等价 PASS / 物理 comparator NOT_RUN，阶段 D 描述性 RETURN 归因 PASS，阶段 E 多指标测量 PASS，FAST 根因诊断 PARTIAL。PACKAGE_VERIFICATION 是证据完整性校验，不是科学、实时或硬件资格。

冻结 M2 在两个上一 host 工作包未运行的注册合法 prefix × 两个 seed 上均降低 J_F，合并 **-6.828%**。平均力项解释合并下降的 **99.962%**，RETURN 贡献 **85.578%**。同时四组 moment integral 增加 **13.28%–25.64%**，knee TASK RMS 增加 **0.341°–0.424°**；3/4 true/measured clearance 下降，一组 force peak 增加4.229703 N。原始物理/安全合同8/8 PASS，但 force 收益没有构成多指标 Pareto dominance。

## 范围、协议和实际分母

上一包 REPORT 及 ledger/START-END/完整 axes 交叉核验 PASS：17次尝试、6次有效M2、25个非零计划、143645关联 native steps。旧失败与旧 R2 结论不变。本轮新目录 `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1`；权重 SHA256 `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9`；没有训练、微调、G/P、online adaptation 或新异步 planner。冻结120D/K3、candidate generation、排序定义、B native controller、scheduler/governor、commissioning科学语义、admission、40ms physical bridge、100ms expiry、causal ownership、carry/fallback和安全合同。仅迁移包路径。

Prefix P1={OUTBOUND:[[0.30,-0.10,0.05]]}；P2={OUTBOUND:[[-0.15,0.25,-0.20]]}，来自旧 `LEGAL_PREFIX_STABILITY_PROTOCOL.json` 的第1/2项。相对上一个 host 包独立，早期 SCI 已暴露，不能称完全未见扰动或新Human。Seeds=2026100801/2026100802；顺序P1s1 B→M2、P1s2 M2→B、P2s1 M2→B、P2s2 B→M2。输入物理模型、initial physical state、waypoints、prefix、instrumentation在每对内一致；真实 commissioning fit 允许并记录差异。B/M2都使用同一既有 worker envelope；B在公共prefix后为zero residual。Pair有效需完整导出、物理与causal PASS、配置一致、Q identity可核验及M2实际非零执行；不要求 FAST/R2 PASS 来纳入研究pair。协议先冻结，没有按结果改阈值或排除失败。

19ms strict55-derived研究性preguard的关闭仅适用于本轮已注册host配置（strict55_guard=false）：host_adapter以40ms检查worker年龄；原生100ms生命周期、source timestamp、current-state admission、native safety、causal ownership仍完整保留。没有解除其他检查。真实strict55结果单独失败。

新增 attempted dispatch **9/12**：8次完整host配对＋1次隔离诊断启动失败。隔离诊断在commissioning setup后、study_common.run/物理epoch前因INVALID_COMPILED_CAPTURE_BINDING退出，实际物理步0、没有完整RESULT，不计入有效运行；原始log/diagnostic JSON/ledger保留，未重试。成功物理8次，累计真实物理native steps **936370**；M2实际Q-selected非零计划 **19**，关联native steps **107891**。公共prefix非零介入单独记录，不能当作Q收益执行证据。

## 配对力与多指标

单位J_F=N·s；Δ=M2−B，负值改善。主指标4/4改善；均值ΔJ_F=-100.001462，median=-94.194436，sample SD=21.019590。相对差值范围-9.008%至-5.664%。n=4只有两个prefix且seed复用，描述性分布不能支持人口泛化或显著性结论。

| Pair | B J_F | M2 J_F | ΔJ_F (M2−B) | 相对差值 | Moment Δ | Knee RMS Δ° | True clearance Δmm |
|---|---:|---:|---:|---:|---:|---:|---:|
| deviation_P1_seed1 | 1440.100759 | 1358.534427 | -81.566332 | -5.664% | +25.643% | +0.368753 | +1.803774 |
| deviation_P1_seed2 | 1443.779913 | 1313.729271 | -130.050643 | -9.008% | +13.281% | +0.423791 | -5.396904 |
| deviation_P2_seed1 | 1496.267407 | 1404.831512 | -91.435895 | -6.111% | +23.536% | +0.371913 | -1.227049 |
| deviation_P2_seed2 | 1477.838429 | 1380.885452 | -96.952976 | -6.560% | +25.192% | +0.341038 | -4.776410 |

| Pair / arm | force peak N | moment integral / peak Nm·s / Nm | hip / knee TASK true RMS° | true / measured min clearance mm | force / moment headroom N / Nm |
|---|---:|---:|---:|---:|---:|
| deviation_P1_seed1 / B | 113.289683 | 97.183124 / 15.320035 | 0.456545 / 0.507692 | 12.122547 / 5.119720 | 86.71031693126216 / 44.67996501981532 |
| deviation_P1_seed1 / M2 | 107.214259 | 122.103388 / 15.305298 | 0.428687 / 0.876446 | 13.926321 / 5.942875 | 92.78574081362744 / 44.69470218695469 |
| deviation_P1_seed2 / B | 107.347648 | 103.532656 / 15.303667 | 0.455996 / 0.502683 | 17.253565 / 9.356765 | 92.65235242916454 / 44.69633332375139 |
| deviation_P1_seed2 / M2 | 111.577351 | 117.282678 / 15.460071 | 0.414689 / 0.926475 | 11.856661 / 4.145995 | 88.42264932420674 / 44.539929306443554 |
| deviation_P2_seed1 / B | 110.815591 | 91.844764 / 15.812049 | 0.468590 / 0.474107 | 16.000728 / 8.049746 | 89.1844088715133 / 44.18795127894213 |
| deviation_P2_seed1 / M2 | 110.838493 | 113.460981 / 15.816825 | 0.447803 / 0.846020 | 14.773679 / 6.761354 | 89.16150671180422 / 44.1831754432217 |
| deviation_P2_seed2 / B | 110.828691 | 90.661221 / 15.810631 | 0.464531 / 0.465840 | 15.951091 / 8.006176 | 89.17130935186107 / 44.18936914453623 |
| deviation_P2_seed2 / M2 | 110.593933 | 113.500931 / 15.808150 | 0.416592 / 0.806878 | 11.174680 / 3.643330 | 89.40606745767545 / 44.191849513801856 |

完整moment积分/peak、力mean/peak、hip/knee true-reference TASK RMS及max、true/measured/session clearance、安全conditions/headroom和阶段tracking在MULTIOBJECTIVE_TRADEOFFS.json与PAIRED_HOST_RESULTS.json。最低measured sleeve gap为3.643330mm。原始速度、加速度、ROM、torque、contact、clearance门限保持原条件审计；没有猜造缺失阈值。真实RMS基于TASK评估trace，native安全peak和clearance来自原native scorer，口径不混用。

## 排序能力与RETURN机制

selected_Q=linear，归一化反归一化折叠为Q=offset+w·x。固定集合、mask、carry和counts后，ΔQ_ij=w_U·[masked(p_i)−masked(p_j)]；state/history/carry/count公共项相消，state×plan交叉导数0。审计131个真实旧/新决策（OUTBOUND 58、RETURN 73）。固定集合探针的解析排序数1、raw native mixed-precision排序数1，top-choice变化0；native pairwise数值误差最大3.41483963e-06 N·s。不宣称native bitwise等价；close-rank safeguard原样保留。Mask可以改变固定排序，carry可以改变候选身份，native feasibility和late-carry可以改变实际执行；都不是learned conditional preference。HOLD没有实际Q决策，经验排序审计NOT_EVALUABLE。解析等价足以回答固定排序comparator问题，无额外物理比较。

RETURN执行非零计划 **12**，OUTBOUND **7**。RETURN实际native Δd均为负（range -0.070034至-0.013622，mean -0.049657），OUTBOUND多为正；固定计划偏好经过native实现产生方向一致但不完全相同的Δd，不能宣称反复精确同一个residual。实际RETURN同phase-elapsed window 12/12 J_F更低，OUTBOUND 6/7更低；窗口不足以独立识别因果效应，也不覆盖任务全部区间。

合并ΔJ_F=-400.005846126：时长项=-0.151673419，平均力项=-399.854172707 N·s。每阶段用对称乘积分解，阶段积分之和与完整任务闭合；同时保留真实phase-clock与integrated-trace duration，未裁剪HOLD或改R2。

| Pair / phase | B / M2 J_F N·s | integrated T B / M2 s | phase-clock T B / M2 s | mean F B / M2 N | duration contribution | mean-force contribution |
|---|---:|---:|---:|---:|---:|---:|
| deviation_P1_seed1 / OUTBOUND | 727.671006 / 734.017995 | 9.010000 / 9.010000 | 9.010000 / 9.010000 | 80.762598 / 81.467036 | +0.000000 | +6.346989 |
| deviation_P1_seed1 / HOLD | 54.922251 / 54.663029 | 1.030000 / 1.025000 | 1.030000 / 1.025000 | 53.322573 / 53.329784 | -0.266631 | +0.007409 |
| deviation_P1_seed1 / RETURN | 657.507503 / 569.853403 | 9.010000 / 9.010000 | 9.011500 / 9.011750 | 72.975306 / 63.246771 | +0.000000 | -87.654100 |
| deviation_P1_seed2 / OUTBOUND | 739.810546 / 687.614689 | 9.005000 / 9.010000 | 9.005000 / 9.010000 | 82.155530 / 76.316836 | +0.396181 | -52.592038 |
| deviation_P1_seed2 / HOLD | 54.916953 / 54.799844 | 1.030000 / 1.025000 | 1.030000 / 1.025000 | 53.317430 / 53.463262 | -0.266952 | +0.149843 |
| deviation_P1_seed2 / RETURN | 649.052415 / 571.314738 | 9.010000 / 9.010000 | 9.011500 / 9.011250 | 72.036894 / 63.408961 | +0.000000 | -77.737676 |
| deviation_P2_seed1 / OUTBOUND | 786.274145 / 787.417544 | 9.010000 / 9.005000 | 9.010000 / 9.005000 | 87.266831 / 87.442259 | -0.436773 | +1.580172 |
| deviation_P2_seed1 / HOLD | 54.908877 / 55.186780 | 1.030000 / 1.035000 | 1.030000 / 1.035000 | 53.309589 / 53.320560 | +0.266575 | +0.011327 |
| deviation_P2_seed1 / RETURN | 655.084385 / 562.227188 | 9.005000 / 9.005000 | 9.006500 / 9.006750 | 72.746739 / 62.435001 | +0.000000 | -92.857196 |
| deviation_P2_seed2 / OUTBOUND | 767.131926 / 754.571376 | 9.005000 / 9.010000 | 9.005000 / 9.010000 | 85.189553 / 83.748210 | +0.422344 | -12.982895 |
| deviation_P2_seed2 / HOLD | 55.177702 / 54.853389 | 1.035000 / 1.030000 | 1.035000 / 1.030000 | 53.311789 / 53.255718 | -0.266419 | -0.057894 |
| deviation_P2_seed2 / RETURN | 655.528801 / 571.460687 | 9.010000 / 9.010000 | 9.011750 / 9.011500 | 72.755694 / 63.425159 | +0.000000 | -84.068114 |

Q source time→raw ranking→selected K3/Δd→native admission/lifecycle→receipt→实际steps的逐请求链及状态/force/moment/tracking/clearance窗口见EXECUTION_LINEAGE.json及RETURN_ATTRIBUTION.md。进入RETURN的true q/dq差与commissioning beta/residual/geometry差已导出。OUTBOUND可能通过状态历史影响RETURN；没有单独阻断OUTBOUND或匹配commissioning，因此不能分离这些效应。Native timing改变carry与激活机会，也可解释部分pair差异；平均力下降仅支持协调改善，不是严格因果识别。

## FAST与独立资格轴

| run | physical | causal host | observed FAST | formal runtime | legacy R2 | strict55 | hardware | gap p50/p95/p99 ms | rolling1s max ms |
|---|---|---|---|---|---|---|---|---:|---:|
| 001_deviation_P1_seed1_B | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.003499/5.846045/7.114809 | 5.414834 |
| 002_deviation_P1_seed1_M2 | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.003579/5.677970/6.736267 | 5.465980 |
| 003_deviation_P1_seed2_M2 | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.003664/5.592490/6.270773 | 5.391945 |
| 004_deviation_P1_seed2_B | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 4.999373/5.605358/6.503397 | 5.331625 |
| 005_deviation_P2_seed1_M2 | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.002389/5.608919/6.421281 | 5.446927 |
| 006_deviation_P2_seed1_B | PASS | PASS | FAIL | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.001057/5.784032/8.186251 | 6.648456 |
| 007_deviation_P2_seed2_B | PASS | PASS | FAIL | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.029395/6.536357/9.273388 | 6.303055 |
| 008_deviation_P2_seed2_M2 | PASS | PASS | PASS | NOT_RUN | FAIL | FAIL | NOT_RUN | 5.003656/5.575691/6.553020 | 5.362764 |
| 009 isolated diagnostic | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE | NOT_RUN | NOT_EVALUABLE | NOT_EVALUABLE |

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

t0=2026-10-08 20:59:12 Asia/Shanghai；停止启动新实验时间22:59:12；硬截止23:29:12。本报告生成累计wall约31.48min；未耗尽预算。没有重型实验并行；没有改Windows/WSL RAM、swap、电源或调度、没有终止无关进程。资源记录WSL available最低5.773GiB，Windows available最低1.655GiB，commit headroom最低8.122GiB，swap in/out delta=0/0，OOM delta=0。

Git branch/HEAD/status/index/staged-diff与startup快照完全相同。没有branch切换、stage、commit、push、reset、stash或删除历史文件。上一包所有字节及file set、其他历史保护清单、冻结Q与复制实现（仅路径迁移）校验PASS。所有8个TASK worker JOIN exitcode0，诊断dispatcher已退出；无task-owned process遗留。原完整gzip EOF/CRC验证、TASK力/矩积分独立重算、phase分解与receipt非重复PASS。

要求的10个文件：REPORT.md、EXPERIMENT_MANIFEST.json、Q_RANKING_ATTRIBUTION.md/.json、PAIRED_HOST_RESULTS.json、RETURN_ATTRIBUTION.md、MULTIOBJECTIVE_TRADEOFFS.json、EXECUTION_LINEAGE.json、FAST_RUNTIME_OBSERVATIONS.json、PACKAGE_VERIFICATION.json。完整source/results包含8次trace.npz/summary/config/runtime_artifacts.json.gz；logs、queue、output、reports、weights、frozen code/binary与preservation保留。历史数据只读取。新派生JSON的raw NaN/Infinity明确导出为null并记录字段路径/NOT_EVALUABLE，原artifact不改。

命令：prepare_package.py；audit_ranking.py；冻结run_registered_batch.py pairs；analyze_package.py；additional_attribution.py；fast_compare.py；注册并单次fast_dispatch.py隔离diagnostic；close_package.py。均使用用户指定`/home/hank/envs/adaptive-online-rl-v1/bin/python -B`。新研究Python/report导出代码在本包code；paired运行实现与原包仅path relocation。报告Windows副本`C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_host_generalization_attribution_v1/REPORT.md`，canonical Linux源路径保持可追溯。

STOP。不自动开始下一工作包，不训练Q，不宣称online personalization或hardware qualification。

数值精度核验：实际feature/normalization=float32，linear_W/Q_output/y_mean/y_scale=float64；原close-rank的float32保守误差bound保持不变。固定候选探针candidate0绝对Q从357.786644730到1324.292717211 N·s，但相对排序始终不变。共同状态项的明显绝对变化不能证明state-conditioned preference。
