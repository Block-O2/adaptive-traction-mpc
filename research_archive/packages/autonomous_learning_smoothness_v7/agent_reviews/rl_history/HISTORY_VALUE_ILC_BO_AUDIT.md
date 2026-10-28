# 历史 History Value、ILC 与 BO 的决策证据

登记 `HISTORICAL_RL_HISTORY_DECISION_AUDIT_V1`；只读，无新增仿真、训练、模型推理或物理尝试。完整选定证据路径/hash 与缺失清单见 `SELECTED_EVIDENCE_AND_AVAILABILITY.json`。

## 范围纠正与可复核程度

**CONFIRMED：** 之前对 learning_guided_v1、v2、v3、v4、v5、v6 连续研究包的审计不能替代整个项目的历史检索。那些包中“患者 history 未实施/未验证”的结论仅限该系列。另有 `ihear_history_to_next_trial_learning_v1` 明确保留了实际 History Value、ILC、BO 和冻结下一次决策的源码/报告，不能写成全项目历史 NOT_RUN。

下文 `H`=`/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_history_to_next_trial_learning_v1/`；`O` 为同一 `side_studies/` 下的 `ihear_overnight_control_learning_transition_v1/`。

**CONFIRMED：** H 的 `models/METHOD_FREEZE.json` 固定 train=P00/P05/P08，validation=V12/V13，heldout=U14/U15/U16。当前归档中 `learning_models.py` 与 `history_features.py` 的实际 hash 与 freeze 完全一致，分别为 `1599427a2b5c33b4cb0889f51c2ae0d7741dcf4d1962175dfcadaf4b043920cb`、`9ccd56b8197b2e2a37f40da98518562162eb79e8715705d450e06637879a5630`；U14/U15/U16 的 `learning/*_T2_DECISIONS_FROZEN.json` 也存在。

但 H 的 `models/history_models.npz`、`TRAINING_DATA.json`、`POPULATION_HISTORY.json`、`LEAVE_PATIENT_OUT.json`、`source/results/` 与完整 attempt ledger **当前本地归档缺失**。models 目录只有 METHOD_FREEZE；output 目录只有共享动作合同。预期权重 hash 为 `a2596c0d445923b898e6f1492a5f1495286c1dcfaf0adb42aeac676bca636d8b`，预期 training data hash 为 `886468bfd1442bd6b254baa3cfcaff4a646ac6ddf67aa40a29510a2bce62e1f2`，本次无法核验实际 bytes。故下面算法机制与冻结声明标 **CONFIRMED**；历史性能、79 START/END 和独立测试结果只能标 **SUPPORTED（原报告支持）**，原 raw 独立复核标 **NOT_TESTED / PAYLOAD_NOT_AVAILABLE_IN_THIS_ARCHIVE**。缺档不是历史没运行，也不能以报告摘要补造模型或 raw。

## H 的状态、动作与真实信息能力

**CONFIRMED（源码和合同）：** 原任务和 Human/robot/cuff 保持，动作仅在 native B 的 OUTBOUND 零基 slot1 或 RETURN slot3 修改中间膝 reference，幅度 ±.3°。原 hip、duration、pass velocity、endpoint、HOLD 和原 admission 不改；可选 frozen H150 完整策略。它与当前 v7 modal8 retiming 不是同一搜索权限，因此其 JF 不能直接拼到当前排名。

历史摘要来自完整 5 ms causal observer/reference/force/moment，保留 phase-local 信息与 source age；12 维候选特征中，模型只使用 OUT/RETURN 中段平均 force 和膝 tracking error 四维。历史 JF 用作已发生 trial 的成本基准，native truth 不在 `history_features.py` 的 policy 数值输入。估计速度的 gradient 所得 derivative 是历史描述，不能替代 native motion gate。源码排除未来结果并不替代缺失 raw 的运行时 truth-firewall 核验。

报告规模 **SUPPORTED**：79 START/79 END、5,500,360 native、68 完整任务、7 个已运行模拟 Human 身份、9 个 live parent。三开发 Human×五动作=15 labels，独立患者信息量只有 3，不能称 15 独立患者。V13 计划但未运行；U14–U16 已暴露，改方法后不能重新当新 heldout。

## History Value 真正学了什么

**CONFIRMED（`learning_models.py`、`train_models.py`）：** 17 维 ridge feature 为 intercept、4 context、2 action、2 action²、8 history×action；λ=1 的 full fit+3 leave-one-patient-out fit。输出是 J2−J1、一个 motion margin、execution/task 指标。没有 TD、Bellman backup 或长期神经 value；在线仅换 context，没有更新权重。disabled 分支函数明确断言 history 必须为 None，使用 z=0 开发均值，动作权限与规则相同。适用域和预测门只是保守候选选择，仍须原物理门。

LOO 的标准化参数由全部三个开发 Human 共享，因此不是严格独立 uncertainty calibration；外部 heldout 没被用于这个标准化。ensemble spread 和误差下限未经过足够独立校准，不能称安全保证。缺失 weights/labels 使本审查不能重建实际预测误差、标签值、独立 replay selection 或数据泄漏全链。

**SUPPORTED（`HISTORY_VALUE_STUDY.md` 和冻结决策）：** V12、U14、U15 相对 B/同规则 disabled 的完整合格 JF 收益分别 .636836、.580099、.639314 N·s；U16 回退 B，无动作改变/收益。前三次都选择同一个 RETURN[3] −.3°。说明历史可能学到了“是否启用小修正”，尚未证明患者特定的非零动作排序。必须与开发数据预选的固定 RETURN−.3°、最强合格 H150 比较；已有报告明确未超 H150，不能把 history-disabled=B 的收益当独立增量已完成。

## ILC 的正负结果与界限

**CONFIRMED：** `history_features.py.ilc` 在 OUT/RETURN 参考进度 .2–.6 中选平均 force 更高的窗口，以 `delta_next=clip(previous_delta+.25*(estimated_actual-reference knee error),±.3°)` 修改中间参考。无已识别 force 梯度，无学习参数训练，无收敛证明。它是具体的历史误差驱动传统修正，不应包装成神经 policy。

**SUPPORTED（`ILC_STUDY.md`）：** V12 的完整合格收益为 .239097 vs B、.133849 vs disabled；U14 为 .179960/.080135。U15、U16 分别比 disabled **差** .005210/.066505；开发 P05 也比 B 差 .012753。第二次更新 T3，P08 比 matched KEEP 好 .151137，但 P05 差 .011518，均完整合格。必须保留负结果：一例继续改善不是普遍单调收敛。跨 repetition 的直接 JF 降低还含真实起始状态漂移，不能代替同父 KEEP/B 对照。

## BO 的更新与失败机制

**CONFIRMED：** H constrained BO 以四历史特征+两动作坐标构建独立 cost GP、motion-margin GP 和 action execution Beta-smoothed 估计。history-enabled 在当前 context 加入前一次 B 的带噪 `J1−J1=0` 观察，不是已经观察本次 B 的真实回报。acquisition 为 EI×Pmotion×Ptask，保留硬适用域与概率/余量阈值；unknown/refused 动作没有虚构回报。模型假定局部 trial 漂移可由开发噪声覆盖；这不是个体动力学已识别。报告的 cost noise 约1.607 N·s，大于许多约.5 N·s 的目标差，保守 gate 与 sparse data 是有方向的限制，尚非因果证明。

**SUPPORTED（`BAYESIAN_OPTIMIZATION_STUDY.md`）：** V12/U14/U15 都与 disabled 同选 B；U16 唯一改变为 OUTBOUND+.3°，完整合格 JF 却增加 .330361 N·s，JM 减 .096051 N·m·s、tracking RMS 减 .001390°。它改变动作但无降力收益，局部取舍不应升级为成功。预测资格不足也不能说候选已被真实物理证伪。

## O 的状态 Q 与实际反馈记忆

**CONFIRMED（`learning/value_model.py`、`control/feedback_selector_retry.py`）：** 更早 O 在单 nominal Human 的六开发 parent×四动作上训练七 causal features 的 ridge Q/value，只有 rank5、两个 val、三个 U 状态。不是多患者训练。Q/value 带显式 action interaction，不是深度 RL。Q 选择器与 early-value 是不同决策头。

**SUPPORTED（`Q_VALUE_EXPERIMENTS.md`、`EARLY_VALUE_STUDY.md`）：** Q test 三状态全部选择 H150，未超过固定 H150；early-value 受保守资格 buffer 限制三状态退回 B，约34 N·s regret。报告指出 buffer 排除已知能通过的非 B 候选。这是有限 head/置信规则的问题，不是“state value 从未训练”，也不能在测试后放松门再声称原 heldout 通过。

**SUPPORTED（`FEW_REPETITION_EVALUATION.md`）：** 连续 plant 第一次 H150、原 settle/HOLD、第二次同父 B/H150/MEMORY，读取第一次 measured JF 后更新一项 kernel coefficient −1.553142 N·s；仍选 H150，实际动作改变 False，相对同父固定 H150 收益0。原 REP serializer failure 与零物理日志失败被保留，修复后 REPR 是已暴露 pilot，不能算新独立状态。

**CONFIRMED（反馈源码/协议的结构）：** kernel=exp(−.5×平均标准化状态差平方)；记忆 residual 被原 absolute LOO error 裁剪；force confidence buffer 又包含这个误差。仅一次反馈、其他动作原先预测更差时，这种有界修正不能凭空产生有置信度的优势翻转。把测到的全任务成本 residual 广播到非 B action delta，还可能混入决策前共同 prefix，无法从一条 H150 结果识别其他动作的反事实梯度。该接口 pilot 支持数据闭环可执行，不支持有用少重复个体化。

O 保留部分 Q/early-value/repetition_base NPZ，但 `REPETITION_RETRY_MEMORY_V1.json` 和主要 U/repetition raw 当前不可得；只看到部分 D01R fixture。报告规模83 START、6,038,480 native 是 SUPPORTED，未独立重验全部账。O 的 P2 RL NOT_RUN 只适用于 O，不能覆盖其他 PPO/SAC 历史。

## 与当前局部 BO/响应面的联系

**CONFIRMED（现有原源码）：** `learning_guided_motion_improvement_v1/source/optimizers.py` 和 `autonomous_coordination_learning_v2/source/acl2_search.py` 已真实实现 residual GP/BO；后者使用自己的历史、完整候选成本和独立 completion/motion 模型，在 8D 固定 context 候选中选择。它改变过候选；不能说所有 GP 只做 prediction 未改变选择。

**SUPPORTED（原始包报告和前次独立原 raw 审计）：** learning_guided_v1 的20次配对 GP 未超过强传统方案；v2 同32次预算，GP best JF1399.188323、pattern1398.549121，C 改变过14/16选择。v5 同4D、12次，pattern12/12 eligible，BO11/12；以其冻结 S 合同 pattern best .953545 优于 BO .964078（BO 最佳为共享 handoff）。这些是特定动作空间、预算和 scorer 的结论，不是 BO 理论上无效，也不应混用不同 JF/JM 目标。

因此主Agent正在做的 GP vs 二次响应面与不同 Human 筛查可直接回答剩余问题；本审查没有重复该分支。若低维局部响应可被二次式或 phase 成本组合解释，模型复杂度不构成独立研究价值。phase 分解已有真实标签/尝试成本，不是零物理数据。

## 建议与停止边界

**SUPPORTED，优先级高：** 先问“完整历史能否预测同父 action−强基线的差值和完整资格，而且改变有用选择”。对照固定 RETURN−.3°/H150/当前最强 phase rule、同权限 history-disabled、ILC、局部二次/GP；训练与选择必须分开，使用真正预先保留的合法 state/Human。只有至少两个合格动作的优势随 causal context 发生可复验变化，才有清楚的 history learning 需求。三个非零动作都相同的旧 Value 结果尚未做到这一点。

**HYPOTHESIS，需新登记：** 以已发生 prefix 成本为条件预测剩余 cost-to-go 或 action advantage，分离全任务 common offset；用重复数据估计患者内 action 差值不确定性。不能仅把 full JF label 改名 value，不能用一次已执行动作补出所有 counterfactual labels。若 current-state 已充分包含历史信息或固定 rule 等效，则停止复杂 history 分支。

**NOT_TESTED：** 旧 Value/ILC 是否超过固定 RETURN−.3°、新 reward 优化瓶颈的因果诊断、真实物理尝试节省、包含训练/恢复开销的 amortized compute 优势、真实硬件/临床舒适度/患者安全。不得从仿真小幅改善升级结论。

目前有理由继续有辨别力的状态/动作响应检验，没有理由为了把 Learning 清单填满而新开 PPO/DAgger。若未来出现适应性反馈能力缺口，再另行规定动作、on-policy 数据、完整任务/motion 门、停止条件与预算。当前报告仅提建议，没有授权或启动这些实验。
