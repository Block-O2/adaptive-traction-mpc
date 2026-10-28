# IL / DAgger / SAC：最终结果

最终口径：BC预登记OLD_NORM主法1/2合格，NEW_DEV_NORM变体0/2；SAC与Neural Q固定final主法各1/2，未立强简单基线增量。早期面板的主法误标已明确superseded，精确指针见文末更正。

模仿的状态覆盖修正、终末离散 SAC 的优化机制及 matched Neural Q 表示诊断已完成；尚未建立强传统基线之外的独立收益。旧连续 SAC、真正多步 DAgger/SAC 仍为 **NOT_FULLY_EXPLORED**，不能以本轮单步模型代替。

## 教师与 BC 覆盖

从完整原评价数据构造相同五动作权限的教师，只把合格完成轨迹作为正示范。实际训练 3 个 BC 模型，各 240 次 SGD，共 720 次；另有 1 次训练归一化与 6 个简单规则拟合。48 条观测来自 10 个 case，motion 失败轨迹作为资格信息保留，不以其 partial/低成本充当成功。

主法 AGGREGATE_5_OLD_NORM 在开发诊断为 10/10 合格，合计 ΔJF=−274.2721、ΔJM=+40.0913；旧数据单独训练为 9/10。深度 2 树和 nearest 同样 10/10，因而新增覆盖有效，但学习没有独有增量。少见 phase 动作没有合格教师正例。OUT0 输入对动作外生，当前数据聚合不是逐步访问策略诱发状态并查询教师的真正 DAgger。

实际 exposed live API 已运行 9 个 BC/规则 bundle，按完整动作 recipe hash 连接真实候选；具体任务资格以原 scorer 为准，不能把离线开发 10/10 当作新条件验证。

## 合法 off-policy 数据与 V6 训练

冻结 64 条实际完成轨迹：旧 48 + 首批真实 on-policy 16，12 个 case、52 个唯一 case/action cell、12 个重复，39 合格、25 完整 motion 失败。新 16 行仅覆盖两个 case/四个 cell，没有因此增加 16 个独立患者条件。数据不含后来的 G3 或当前新比较结果。

终末状态 done=True，目标 y=r，不作未来 Bellman bootstrap。相对 B 的 JF 资格奖励与 JM 独立报告；完整 motion 失败为 −1。没有将不同连续动作接口强行混合。实际 48 次初始化、1,650 次 SGD、84 次 SAC state API；完整主模型和所有开发 fold 均冻结，不挑最佳 checkpoint。

AGG64 vanilla actor 开发 LOCO 为 11 合格/1 失败，合格子集平均 ΔJF=−14.614545、ΔJM=+2.101544；该子集不能代表全体净收益。adaptive temperature 结果同选，α 仅 .01→.00999932；保守版本多次弃权。同 Q 的 greedy 与 soft-Q 在全部比较中同选，LOCO 为 6 合格/4 失败/2 UNKNOWN。原单独付费 B 控制实际 12/12 合格；policy cohort 缺失的 B 行保持 UNKNOWN。

## V7：精确解隔离优化不足

保持相同 64 行、25D、训练归一化、五动作线性终末 Q 目标，比较 empirical gain1、gain20 和 case/action 均衡。26 次正规方程求解、39 RHS、72 state API，0 actor/温度梯度或新物理。正规方程最大残差 1.67e−16。

full objective 从旧 Q1=.066779664 / Q2=.066598370 降至 .001218647，约下降 98.17%，**CONFIRMED：**旧有限 SGD 存在优化不足。但预登记主法 LOCO 仅 7 合格/3 失败/2 UNKNOWN，未达到旧 actor 的 11/1/0；失败 floor、线性表示、case 覆盖仍不能排除。合格 Q 的 LOCO RMSE 从旧 .065809 升至 .294789，失败 RMSE 从 .974948 降至 .689045，说明训练目标下降不自动改善合格区泛化。

gain20 只放大合格收益，失败仍 −1，改变了相对奖励权重；FULL 改选 4 个 case，LOCO 改选 0 个。均衡重复行权重使 Q 数值变化但未改选。两个 twin 使用同一唯一凸解，不是独立 ensemble。严格 JM 与任务资格分别评价，没有用合格子集降力掩盖失败。

## Neural Q 的表示机制

另立神经 Q 合同：相同 frozen64、whole-case LOCO，独立 RETURN/RISK/JF/JM 头，matched LINEAR/tanh16 与 ridge、训练内归一化、parent/25/200 固定 checkpoint、3 个预登记 seed。它针对表示与物理标签尺度机制，不冒称多步 SAC。

GateM V3 数学检查已一次 PASS，最大有限差分误差 2.64e−10，25 个实际计数全部吻合。GateR V3 在一次 120s 合同内实际用时 48.45s 完成固定设计：468 初始化、93,600 次 SGD/gradient、96,300 次 forward、2,700 次 predict、1,404 次 snapshot，另有 39 次 ridge/195 RHS。全部 13 个训练范围与 3 个预登记 seed 完整保留，没有挑最佳 epoch。

主法 tanh16 RETURN 的 200-step LOCO 为 6合格/4失败/2未知、8/2/2、8/2/2；matched LINEAR 三种子均 7/3/2，精确 ridge 为 8/2/2。固定风险门使 tanh 三种子均 8/2/2、linear/ridge 均 9/1/2，但仍误放失败 cell，不能授予真实资格。病例内成本中心化改善尺度问题：seed101 的 tanh LOCO JF MAE 从 505.820 降至 35.578、JM 从 38.134 降至 2.738；该分量诊断不是预登记 RETURN 主法的成功证据。

冻结只读 API 已完成 known12 一次数值/选择 parity：63 次 restore、756 次 forward、1,260 次 matmul，3,780 个数值及 816 项选择/回退一致；最大 RETURN/RISK 误差 6.66e−16，物理成本 6.82e−13。此检查为开发输入上的实现一致性，0 fit/physics，尚无新参数 OUT0 部署或控制增量证据。训练批准到期不自动授权 live 部署。

## 证据与范围

- [SAC V7 结果](families/il_dagger_sac/discrete_sac_v1/solver_floor_v7/REPORT.md)
- [Neural Q 数学门](families/il_dagger_sac/neural_q_v2/GATE_M_RESULT_REPORT_V3.md)
- [实际 live 选择与候选映射](analysis/V8COMPENG03_SELECTOR_EXECUTION_LINK.json)

LEVEL1 在所列实现范围通过；覆盖改进及精确优化学到数值信息，是否达到 LEVEL2 依目标/held-case 分开判断；LEVEL3 多个模型改变选择。LEVEL4 受失败与未知限制；LEVEL5 没有强简单控制之外的独有收益；LEVEL6 新参数冻结验证待运行；LEVEL7 真实物理省试未建立。不得据此否定所有 IL/DAgger/SAC。


## 原两新参数冻结评价（已闭合）

CONFIRMED：BC聚合主法0/2完整合格；SAC vanilla actor和V7精确gain1 greedy均1/2，轻载选择B、没有相对B的降力。NeuralQ tanh16的三个固定seed在200更新端点均为1/2：重载选EARLY_PHASE partial，轻载选B。0/25端点虽然均选B而2/2合格，也不能在看到结果后替换已登记200端点；所有seed/阶段均留表。全部85逻辑SAC/NQ变体在轻载可合格，不增加独立物理数。

因此改善训练求解、神经表达或风险头有信息的证据仍保留，跨参数强基线增量未建立。结果来自实际OUT0原推理和相同原menu，详情见[两条件固定面板](families/critic_value/analysis/val04_and_two_original_cases_brief_v1/REPORT.md)。真正多步SAC/TD与策略诱发状态的DAgger仍NOT_RUN/NOT_FULLY_EXPLORED。


## 主法身份与原两条件结果更正（精确原行，旧滚动面板保留）

**CONFIRMED，更正而非重训：** BC批准的预登记primary是 `AGGREGATE_5_OLD_NORM`，不是 `AGGREGATE_5_NEW_DEV_NORM`。批准fit manifest `families/il_dagger_sac/context_aggregation_v1/SOURCE_MANIFEST_FIT_V1.json`，SHA `84518257bc5c0713e2cf8c29a69245c46ec58059de3a1fdaff6ebb485961f76e`，JSON pointer `/primary`。原VAL03 helper `families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL03_MAIN_V1/RESULT.json` SHA `0f456b53387de27ed539463e6cd2e9126a411ec0a181471dc0b86caf8e7823cd` 的 `/decision_alignment/choice_table/24`：OLD_NORM选EARLY_H150、PARTIAL_NOT_RANKED；原VAL04 helper `families/critic_value/analysis/inference_receipt_audit_v1/outputs/VAL04_MAIN_V1/RESULT.json` SHA `a5bdb426efd6fcd95ad696f17035f24fad6db1439ad1468b7ffb0a6e8aaa9617` 的同一 `/decision_alignment/choice_table/24`：OLD_NORM选EARLY_H150、COMPLETE_ORIGINAL_QUALIFIED。因此**原BC主法为1/2完整合格**，light与强固定H同一recipe；没有学习独有增量。

NEW_DEV_NORM变体在两文件的 `/decision_alignment/choice_table/23` 分别选EARLY_H150 partial、EARLY_PHASE完整motion不合格，才是**0/2**。此前本文件或所链滚动面板中的“BC主法0/2”、将NEW_DEV_NORM列为primary的解释现已superseded；原模型、原输出和旧面板字节保留，不以改表掩盖更正。A1/A2/A3/A5 JF主法0/2、A4 margin两次B的2/2、SAC/NQ指定主端点1/2等其它原结果不受此身份更正影响。

另，12个categorical parent/first/last逻辑端点（两helper的 `/decision_alignment/choice_table/11` 至 `/decision_alignment/choice_table/22`）在VAL03均选EARLY_H150 partial、VAL04均选B完整合格：每个端点均1/2，light零B增量；不得把parent误述为light选H150。它们不是12个独立参数条件。

本更正仅逐项读取已闭合原metadata：0新helper/model/fit/raw/scorer/physics调用，未改冻结源、模型、阈值、原标签或主法。
