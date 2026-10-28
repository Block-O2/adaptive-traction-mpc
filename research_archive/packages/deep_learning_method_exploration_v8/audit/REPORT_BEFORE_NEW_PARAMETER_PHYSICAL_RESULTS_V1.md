# iHEAR v8：Learning 方法家族系统探索

**研究仍在运行，本文为滚动报告，不是最终封包。** 唯一 T0 为 2026-10-27 03:25:40 UTC，硬截止 15:25:40 UTC；原全局时钟未重置。已结束的离散 PG 窗口为 04:47:55–06:47:55 UTC。新动作表示的 Beta 分支独立登记 07:57:15–09:57:15 UTC，仍在同一全局截止内。最终状态须以尚未生成的 `END.json` 和最终核验为准。

目前没有证据证明某种 Learning 方法普遍无效，也没有建立超过强简单基线的独立增量。已确认的进展是：合法因果输入及真实执行接口得到审计；状态覆盖和目标求解改变了部分决策；真实连续历史改变了 reference；多个针对明确失败机制的变体完成了训练。风险误放行、力/力矩交换以及强固定方案的竞争仍限制任务收益。两个新参数验证条件尚未产生物理轨迹或结果。

## 评价合同与可比性

JF/JM 分别使用原 measured wrench 范数的 5ms 左积分；native motion 保持原始 0.25ms、未滤波。原 OUTBOUND/HOLD/RETURN 为 9.005/1.020/9.005 秒，完整任务共 19.03 秒。原任务、安全、端点、ROM、torque、clearance、motion 与积分合同不变。JM 比值 ≤1.25 的资格门不等于 JM 不增加；降 JF 的同时增加 JM 必须单列。

原 77D 因缺少真实可用字段仍为 INVALID。审计后的 commissioned25、KIN33、WRENCH39 是其合法子集，不能补零伪造缺失 scheduler/governor 状态。OUT0 的完整未来成本和峰值不存在，不作当前输入；case hash、未来资格和 native 真值只用于分组/评价。

早期离线 RF/PPO/BC 及 C3B 的权限为 B/LATE_H150/EARLY_H150 三动作。A1–A4、真实离散 PG、BC 聚合及终末离散 SAC 为五动作。连续 Beta 是另一条冻结的 18D 参数缩放轴，λ∈[0,1]，λ0 也不是 B。不同权限不混合排名。相同菜单上的多个模型共用实际候选轨迹作决策评价，不把它们计成独立物理重复或真实省试。

“封存验证”指冻结程序前不产生或利用新参数条件的物理结果，并非参数文件字节盲测。四个新参数 payload 按预登记 α 构造；现有 case adapter 的统一 14-case 任务结构校验会解析两条 validation 文件。非选中 human 参数未作为 actor 输入，当前也没有 validation outcome 可用于训练。该设计不构成严格文件访问隔离或临床盲测。

四个 stock-case 的 frozen transfer 对原先已经冻结的方法构成测试；后来使用这些轨迹训练的 A2/A3/A4、BC 聚合、SAC、Neural Q 和 E 模型只能把相应结果视为开发数据。新参数条件须在全部模型和程序冻结后重新评价。

## 1. 哪些方法得到实质探索

| 家族 | 已实际完成的机制探索 | 当前最高证据与限制 |
|---|---|---|
| A Value / Cost-to-go | 完整剩余 JF/JM、相对收益、ranking、资格风险；25/33/39D；新增 case 覆盖；45 原资格 margin；三 λ 分量 ensemble | 学到数值信息并改变选择；开发改善不稳定，新参数泛化待测 |
| B PG / PPO | 离线诊断与真正新 rollout 分开；REINFORCE/PPO × gain1/gain20；真实两轮提交、parent/early/last；连续 Beta 轴数学及物理能力门 | 离散 32 fresh policy rollout、16 次更新；Beta 首批 16 个完整失败导致 8 次零梯度更新调用；没有独立策略优势 |
| C History / ILC / BO | action-only/历史加性/交互/disabled；两增益真实连续 ILC；强固定 ±.25；JF/JM/45 margin 分开的线性/二次/核 BO | 连续 14 个完整任务全合格；历史改变动作，未超过固定 −.25；BO 弃权 |
| D IL / SAC / Neural Q | BC 数据覆盖/归一化/树/nearest；合法 frozen64 off-policy；actor/Q/soft-Q/保守/温度；精确 critic；matched linear/tanh/ridge、独立物理和风险目标 | 覆盖与优化不足得到区分；风险和资格泛化仍有限，强简单方法可竞争 |
| E 学习辅助优化 | 因果短时轨迹、共同 OUT0、action-blind/action-only/context/paired；直接窗口与时间曲线；matched D4/DFull 完整 TASK 训练 | 时间域修正改善部分预测，DFull paired 主模型十例同选固定 EARLY_H150，尚无个体化控制证据 |

所有家族仍为 **NOT_FULLY_EXPLORED**。已完成变体可形成限定范围负证，不能扩大成家族结论。

## 2–4. 合理变体、修正和已证实机制

**A：**A1/A2/A3 逐步区分价值目标、资格覆盖和合法状态表示。A3 的 WRENCH39 开发 LOCO 达 10/10，风险关闭仅 6/10；但假可行仍为 6/48。A4 直接预测原 45 项 margin，把假可行降至 2/48，同时假失败由 3 增至 17，主策略反而为 9/10。CTX03 的 jerk margin 被错误预测为正，合格 H150 又被额外余量要求排除；降低假可行数量不足以保证最终选择更好。**CONFIRMED** 为该实际预测/排序机制，不能声称风险已校准。

**B：**真正 categorical PG 使用同一初始权重和分开记录的 RNG、相同五动作、两个开发 context 的平衡新采样。完整资格失败奖励 −1，JM 不并入 JF 单分数。gain20 只放大合格收益并 clip，不是整体线性缩放。两轮提交分别保持 parent、first-completed、last-completed，未选最佳 checkpoint。首批轻载 8 个动作均完整 motion 失败；第二批 16/16 合格但 15 个 B。RNG JSON 表示、fork generator 共享写和准备器自 hash 等工程错误分别修正，原付费失败、取消和 RNG 消耗均保留，未冒称梯度成果。

连续 Beta 改变动作表示和分布测度：两个正 shape 头产生标量 λ 的 Beta 密度，不把它当 18D 联合密度，不 clip/resample。Gate1 的 λ1 与原 H150 完整 raw 一致，λ=.5 合格，λ0 完整 motion 失败仍保留；没有据结果缩窄 λ 域。首批 16 个 fresh policy sample 均完整 excursion 失败、奖励全为 −1，减批均值后 advantage 为零；8 次实际更新调用、32 次 score、48 次训练 forward 均已计账，但梯度和权重变化全为零。第二批从同一 G1 继续真实采样；不能把零梯度调用称作学到信息。

**C：**真实同进程 T1→T2→T3、自身完整历史和参考激活证据通过独审。gain=.25 相对同起点 H150 降 JF .261417、增 JM .032363；disabled 降 .222978/增 .027649；固定 −.25 降 .535213/增 .066306。历史有效改变动作，但本例尚不如强固定降力。BO 的六类分量模型看到局部成本交换，按原规则弃权，没有额外候选。此结果不等于 BO 不会个体化。

**D：**BC 新增 case 覆盖由 9/10 改善至 10/10，树/nearest 同为 10/10。离散 SAC 的旧 critic 存在有限优化不足：相同凸目标精确解使 full objective 降约 98.17%，但开发 LOCO 仅 7合格/3失败/2未知，低于 actor 的 11/1/0。Neural Q 一次完整固定设计为 468 初始化、93,600 更新；tanh16 三种子主法分别 6/4/2、8/2/2、8/2/2，matched LINEAR 均 7/3/2。风险门改善部分选择但仍误放真实失败。**CONFIRMED**：更好训练拟合、更多表达能力或独立风险头并不自动建立任务优势；原因仍需按目标和覆盖继续区分。

**E：**共同 OUT0 的动作变化标签和原成本闭合已审计。paired 短时 ΔJF/ΔJM 有预测信息，但 4s 完整任务选择只有 5/10 合格，未超过强 action-only。4s 时间曲线外推到 16s 的严重误差混有训练时间域不足；新变体实际使用 48 条完整 3807 节点数据、保持原前缀，以相同八训练点和初始化比较 D4/DFull。实际 704 次 ridge solve/11,264 RHS、66 初始化/13,200 次 Adam 更新已完成。context ridge 的全任务角度 MAE 从 D4 的 hip/knee 123.768/75.911° 降至 DFull 4.589/4.136°；paired MLP 的 ΔJF MAE 从 27.988 降至 19.458，ranking 75/93→89/93，但 DFull 十例全选同一 EARLY_H150、仅 6/10 合格。时间域机制得到支持，个体化和控制增量仍未证明。paired wrench 差的范数不是成本差；未来真实 B 轨迹不能用作推理重构。

新增风险支持 A5 只把两条原 partial 加入操作资格标签，成本权重/归一化不改。实际 11 个风险拟合完成；整 case 留出与原 A3 十项主选择完全一致，已见 heavy 局部修补被其它 case 退化抵消，FULL 仍 8/10。不能把新增数据或局部修补自动升级为泛化。

连续 Beta 第二批遇到轻载 λ≈.193 的原膝参考断言 partial，整批不更新；24 个完整 policy child 的运动失败与 1 个 partial 均保留。新的可行性余量反事实比较从相同 4 个 unique 闭合动作恢复非零梯度；global-batchmean 与按条件留一 baseline 的首梯度 cosine=−.356，两个条件的 mean 移动方向相反。它们共新增 8 次私有参数步，明确是离线反事实，0 新物理，未改真实四臂或原奖励。资格、强基线与泛化仍需真实评价。

## 5. 学到信息但未改变决策

**CONFIRMED：**SAC gain/样本权重修正、多个 soft-Q/greedy 变体及部分 history 模型改变预测数值却保持同选。四 frozen stock-case 中，三动作 history-enabled、commissioned25、RF/PPO/BC 同为 B/H/B/B。BC 聚合的树/nearest 与神经策略同样可覆盖合格教师，未建立神经表示独有信息价值。具体逐 case 表保留在各家族报告，不能把相同动作重复算作多份控制成功。

## 6. 改变决策但未改善完整任务

**CONFIRMED：**A1 在四 stock-case 为 3/4 合格；A4 margin 策略错误挑中 CTX03 phase；Neural Q、精确 SAC 仍选择失败或 UNKNOWN 动作。`V8COMPENG03` 实际 55 个 pre-B 决策中，5 个选择两种 phase，两个 recipe 均在原 `KNEE_REFERENCE_MUST_BE_CONSTANT` 断言处提前停止。11 项原硬条件全通过，任务仍不完整，部分 JF 不排名。该已曝光条件只验证接口，不构成新的泛化成功。新固定适用性探针将使用不同 recipe 身份，旧失败和模型标签不改变。

新适用性探针 `V8PHAPP01` 使用不同 recipe，只在原公开参考条件允许时请求可选 terminal timing；原膝参考断言与原阈值均保留。四个 child 均完整，B/H 合格，两种新 phase 仍 excursion 失败；五个 START 的原 scorer 独立重算均通过。接口适用性得到限定修复，运动资格并未恢复，旧失败标签不修改。

## 7–9. 强基线、独立收益与效率

**目前未建立独立 baseline increment。** 原 B 在四 stock-case 全合格，强固定 H/phase 是否可用随条件变化；比较必须同时报告完整资格和成本分量。C 的固定 −.25 比历史更新更降力，BC 的树/nearest 可匹配覆盖，SAC 同 Q 改温度不改 argmax，E 的 action-only 短窗排序强于复杂 paired。合格子集 ΔJF 不代表所有条件净收益。

四 stock-case 的原 frozen 三动作方法相对 B 合计 ΔJF=−42.412107、ΔJM=+6.122961，4/4 合格；相同简单选择也能做到，不能据此声称 PG 或 history 独有泛化。两个新参数条件的物理结果仍未产生，A3 之后的方法尚无该层证据。

真实省试 **未证明**。截至 Beta 启动前，107 个 START/107 个 END 全闭合，实际新增 8,392,340 native steps（包括工程失败与连续边界，排除继承前缀）；该数为中间快照，最终将加入后续物理。模型共用菜单轨迹只是评价去重，不是已部署的净试验节约。训练、推理、数据提取、scorer 重算和封包成本分别计账。

## 10–11. 限定负证与未完成范围

**SUPPORTED：**在本轮明确覆盖的实现、数据、任务合同与状态范围内，多种 value/PG/history/IL/SAC/surrogate 变体尚未发现强简单基线之外的独立增量。该表述不扩展到机器人领域或整个算法家族。

未充分探索的机制包括多阶段 Bellman/TD、真正逐步 DAgger、其他连续动作方向、校准不确定性、更多独立患者条件、history 增益与高维更新、可合法推理的长时模型及模型辅助控制。尚未实施的合理方向标记 NOT_RUN/NOT_TESTED，而不是失败。新分支依局部超时及全局硬截止推进，不设全家族固定仿真/梯度额度。

## 12. Reward、状态、动作和训练语义

改变限于隔离研究版本：绝对/相对/排序价值、资格分量、gain1/gain20、合法25/33/39D、三/五离散模式与连续 Beta 轴、BC 覆盖、终末 actor/Q/精确求解和直接轨迹 surrogate。原物理和评价合同不变。offline replay、真实 on-policy、冷启动 history 和真实连续 Trial 各自有账；单步 done=True 的终末模型不称多步 SAC，数据聚合不称真正 DAgger，条件轨迹预测不称 Markov World Model/PETS。

## 13–14. 文献与下一步

[RELATED_WORK.md](RELATED_WORK.md) 收录原论文/官方来源及可迁移假设；读过文献不等于复现。可迁移部分包括 PPO 的同一采样分布与有限多轮更新、Beta 有界密度、DAgger 的访问状态覆盖要求、SAC/CQL 的 off-policy/支持约束、分量成本和不确定性建模。没有把人形动作跟踪或 SuperMimic 的结果直接套用到本系统。

当前优先事项是完成连续 Beta 的原回执更新与 mean 部署对照；审查 E2 时间域/容量诊断；冻结全部实际模型、简单控制和程序后打开两个新参数条件；再验证 C 的冻结连续更新程序。相位适用性探针用于解释接口失败，采用新 recipe 身份，不追改旧结论。具体动态决策将在 [NEXT_RESEARCH_DECISION.md](NEXT_RESEARCH_DECISION.md) 更新。

## 15–16. 数据保护、日志与进程

初始保护扫描 219,908 个历史文件、105,969,234,540 bytes，原包、checkpoint、raw、正式控制器和 scorer 不覆盖。长期日志仅追加，初始前缀 SHA 保留；详细失败与修正留在新包。最终保护扫描、日志结束记录、全 owned 进程闭合、模型身份聚合、最终资源账和 PACKAGE_VERIFICATION/END **待完成**。当前无运行中的物理 owner，正在完成 Beta 取消安全范围和新参数程序冻结；未启动 Stage2、正式 Campaign、硬件或自动 Git 写操作。

## 详细结果

- [研究合同](EXPERIMENT_CONTRACT.md) 与 [方法覆盖矩阵](METHOD_EXPLORATION_MATRIX.md)
- [Critic/Value](CRITIC_VALUE_RESULTS.md)、[PPO/Reward](PPO_REWARD_RESULTS.md)
- [History/ILC/BO](HISTORY_CONDITIONED_RESULTS.md)、[IL/DAgger/SAC/Neural Q](IL_DAGGER_SAC_RESULTS.md)
- [学习辅助优化](LEARNING_ASSISTED_OPTIMIZATION.md)
- [基线比较](BASELINE_COMPARISON.md) 与 [motion/force/moment 交换](MOTION_FORCE_MOMENT_TRADEOFF.md)


10:05 UTC 主审补充：Beta 第二批父前缀实际 40,200 native 步已闭合；原数据在 commissioning 人加速度、commissioning session clearance、active recovery sleeve gap 三个 scope 缺观测，最终保留 UNKNOWN。未执行 all-arm cancel、未发布第二批更新；原 CURRENT 仍为 G1，第二批九个实际 draw/receipt/RNG 留在 external pending。此未完成分支不能标为安全通过或成功训练。第一批已提交 G0→G1 与此隔离，后续只读端点清单必须明确披露这一范围。

phase applicability 新探针的五个原 scorer 重算全部通过一致性检查；B 与 H150 对 V8COMPENG03 相同 case/seed/prefix 的全部 trace、116,320 native 记录和 5,817 command receipts 分别完全一致。两个新 phase recipe 都在 RETURN slot5 根据当前 reference 与公开目标拒绝了不适用的 optional timing 请求，原阈值 1e-10、原断言均未改变；两者完整结束但 excursion 不合格。确认接口适用性修正能避开这次中止，尚未确认完整运动资格或相对强基线增量。核验见 audit/PHASE_APPLICABILITY_CLOSED_REVIEW_V1.json；额外物理/模型调用均0。


10:35 UTC 实际冷OUT0整合 V8FROZENENG01 在B前停止：E2外层MLP记录实际只有 model/normalizer，旧适配器重复要求外层kind/paired；内层网络字段和权重原本正确。已付2个ridge API/10query，随后KeyError；父前缀40,200 native步、0候选child，原partial不排名，supervisor exit1且无survivor。此前synthetic parity验证的是数学路径，未覆盖真实外层序列化schema，不能称为实际部署接口通过。保留所有原失败/成本；新V2只修外层字段检查，先做真实冻结权重canary，再用新唯一作业组，不改原模型或任务。


10:59 UTC 主审补充：真实 E2 权重 schema canary 实际通过，candidate 7 API/35 query、原参考 18 API/50 query，共25 API/85 query；320个标量比较误差为0，九个选择一致，0 A3、0 fit、0新物理。该结果确认最小外层 schema 修正与原数学路径相容，不替代实际冷 OUT0 来源证明。新 ENG02 已以同一已曝光 heavy case、seed2690启动，逐次保存已成功返回的推理回执；ENG01原失败不覆盖。

GateK 对同一旧四行行为数据的实际数值分解确认共享特征的跨条件干扰：Gram(H,H)=12.7249783、Gram(H,L)=−16.3313512、Gram(L,L)=38.6695169。LOO Light 自身对 mean 的一阶贡献为+0.0000314110，Heavy 跨项为−0.0002882602，合计−0.0002568492，与已存 RF1 mean 位移一致。故按条件 baseline 本身尚未修复共享参数的更新方向；正在准备同尺度的上下文核去耦合变体，训练数据、奖励、原物理和评价门不变。这个旧批次代数结论不证明总体方差、真实任务收益或泛化。诊断19次26D dot、16次2D dot、4次2×2分解、16个方向导数，0 learner forward/score/fit/physics。


11:04 UTC GateG 实际一次完成：保留同一G0、四个已闭合行为draw、余量奖励、LOO优势、lr .15、RF1/PPO3和原clip，仅以冻结训练context核去耦合更新，并共同缩放回当前原梯度范数。首梯度与旧LOO逐值一致，K_eff、span重建、范数和实际step上界全部通过。24 forward/16 score/4私有步；0采样/真实actor更新/新物理；核心wall .04605s、CPU .045185s、RSS 27772KiB。RF Heavy/Light mean=.500136641/.500019109，PPO=.500410048/.500057325，旧Light的负方向由几何修正转正；这只支持旧批次的干扰解释，不证明可行性、JF/JM增量或泛化。两个固定最终端点全部保留，正在与原四个端点共同冻结独立六mean程序，之后才打开新参数物理结果。
