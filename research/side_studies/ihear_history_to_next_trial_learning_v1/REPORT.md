# iHEAR：完整历史到下一次康复运动学习 v1

## 核心回答

**YES，但仅限列明的患者、动作和工程资格：V12/ILC, V12/VALUE, U14/ILC, U14/VALUE, U15/VALUE 的 history-enabled 优于同起点固定 B 与相同规则的 history-disabled。 不能由此推导优于冻结 H150、开发数据中的最佳固定小扰动、广泛患者泛化或临床有效。**

未见患者上的独立合格消融收益出现在 U14/ILC, U14/VALUE, U15/VALUE；这是有限工程证据。 本轮研究层级为 MuJoCo `SCIENTIFIC_SIMULATION`；原 B-relative motion/fairness 是工程可比资格，不是临床安全阈值。

| 方法 | 运行患者 | 动作改变 | 完整资格 | 优于匹配 B 且合格 | 严格 history 消融通过 | 未见患者消融通过 |
|---|---|---|---|---|---|---|
| ILC | 7 | 7 | 7 | 5 | 2 | 1 |
| BO | 4 | 1 | 4 | 0 | 0 | 0 |
| VALUE | 4 | 3 | 4 | 3 | 3 | 2 |

## 证据和预算

共 79 个 START / 79 个 END，预算上限 80。包含首次父轨迹、准备边界、失败、同起点 fork 和第三次重复；完整任务 68 个，独立复算 68 个。实际新增 native steps 为 5,500,360，它们不是独立训练样本。实际运行 7 个独立患者，P00R 是 P00 的重试身份。成功执行比较的完整 live 父状态共有 9 个，其中同患者不同 repetition 仍不具有患者级统计独立性。

训练只有 3 个独立患者、3 个 Trial2 父状态、15 个完整网格动作结果。所有学习器冻结后才运行 V12 与 U14–U16。V13 在查看验证/测试结果之前因预算分配明确保留为 NOT_RUN。P05/P08 的第三次重复由自己的第二次 ILC 分支继续；不拼接其他方法状态。纯 PPO/SAC、神经网络以及 Bellman 多步学习均 NOT_RUN。

原始证据见 `source/results/`（trace、native、receipt）、`learning/`（完整因果历史及冻结决策）、`reports/`、`motion_series/`、`models/`、`audit/`。执行时间、代码/患者/动作哈希、returncode、partial 原因和 native 成本见 `ATTEMPT_ACCOUNTING.json` 与不可覆盖的 `ATTEMPTS.jsonl`。

## 十三个研究问题

### 1–2. 第一次运动提供了什么？哪些特征因果可用？

保存整次 OUTBOUND/HOLD/RETURN 的合法状态估计、reference、测量 force/moment、source age、commissioning belief、执行提案与 applied receipts；按真实 phase 和参考进度对齐。紧凑表示含完整/分 phase 积分、负担窗口、tracking、估计速度/加速度/jerk。没有将 JF 单标量冒充全部历史。原始历史始终保留，选择器仅使用明确允许的输入。

| 患者 | split | 5ms样本 | Trial1 JF | OUT mid force | RET mid force | OUT膝误差/° | RET膝误差/° |
|---|---|---|---|---|---|---|---|
| P00 | development | 3807 | 1436.456 | 99.524 | 71.630 | -0.384378 | 0.420115 |
| P05 | development | 3807 | 1138.932 | 85.029 | 53.434 | 0.053373 | 0.893850 |
| P08 | development | 3807 | 1437.277 | 102.282 | 69.265 | -0.491312 | 0.467467 |
| V12 | validation | 3807 | 1668.355 | 111.170 | 86.165 | -0.634392 | 0.088398 |
| U14 | heldout | 3807 | 1578.290 | 106.319 | 80.745 | -0.500465 | 0.287889 |
| U15 | heldout | 3807 | 1558.285 | 105.722 | 79.817 | -0.260653 | 0.299396 |
| U16 | heldout | 3807 | 1207.994 | 85.217 | 59.663 | -0.028178 | 0.740619 |

力窗口和误差随患者变化，但负担最高窗口不等于动作收益最大的窗口。native Human qpos/qvel、真实模型系数、native motion 门与下一次结果只用于离线标签/评估，没有进入在线历史或策略。估计 5ms 导数不是 0.25ms native 资格指标。

### 3. 实际学到了什么？

ILC 使用事前固定的增益 0.25，将高负担窗口的中间膝参考向上一轮 estimated actual-reference 偏差方向移动，累计限幅 ±0.3°；它没有学习未知力梯度。BO 用实际开发动作数据训练独立成本和 motion-margin GP，再用当前患者已完成 B 的真实历史做一次有噪条件更新。Value 用显式 history×action 特征的正则化回归 ensemble，训练预测下一次完整成本、执行资格和 motion margin；在线只更新输入 context，权重不再变化。二者均标记 **DATA_LIMITED**，不是成功的 Bellman Q-learning。

### 4–7. 提出了什么动作，谁改变、谁获益，是否优于固定及 disabled？

| 患者 / split | 方法 | 实际动作 | JF / N·s | 相对 B 降力 / N·s | 相对 disabled 降力 / N·s | 完整资格 | 历史因果增益 |
|---|---|---|---|---|---|---|---|
| P00 / development | ILC | OUTBOUND[1] 膝 -0.096095° | 1437.284 | 0.119799 | 0.119799 | PASS | 未证明 |
| P05 / development | ILC | OUTBOUND[1] 膝 +0.013343° | 1140.552 | -0.012753 | -0.012753 | PASS | 未证明 |
| P08 / development | ILC | OUTBOUND[1] 膝 -0.122828° | 1437.979 | 0.147562 | 0.147562 | PASS | 未证明 |
| V12 / validation | ILC | OUTBOUND[1] 膝 -0.158598° | 1668.606 | 0.239097 | 0.133849 | PASS | YES |
| V12 / validation | BO | B | 1668.845 | 0.000000 | 0.000000 | PASS | 未证明 |
| V12 / validation | VALUE | RETURN[3] 膝 -0.300000° | 1668.208 | 0.636836 | 0.636836 | PASS | YES |
| U14 / heldout | ILC | OUTBOUND[1] 膝 -0.125116° | 1578.624 | 0.179960 | 0.080135 | PASS | YES |
| U14 / heldout | BO | B | 1578.804 | 0.000000 | 0.000000 | PASS | 未证明 |
| U14 / heldout | VALUE | RETURN[3] 膝 -0.300000° | 1578.224 | 0.580099 | 0.580099 | PASS | YES |
| U15 / heldout | ILC | OUTBOUND[1] 膝 -0.065163° | 1559.403 | 0.101012 | -0.005210 | PASS | 未证明 |
| U15 / heldout | BO | B | 1559.504 | 0.000000 | 0.000000 | PASS | 未证明 |
| U15 / heldout | VALUE | RETURN[3] 膝 -0.300000° | 1558.865 | 0.639314 | 0.639314 | PASS | YES |
| U16 / heldout | ILC | OUTBOUND[1] 膝 -0.007044° | 1209.021 | 0.007628 | -0.066505 | PASS | 未证明 |
| U16 / heldout | BO | OUTBOUND[1] 膝 +0.300000° | 1209.359 | -0.330361 | -0.330361 | PASS | 未证明 |
| U16 / heldout | VALUE | B | 1209.028 | 0.000000 | 0.000000 | PASS | 未证明 |

动作绑定零基 slot：OUTBOUND[1] 或 RETURN[3]，只改中间膝姿态；原 hip 目标、段时长、pass velocity、终点和 HOLD 保持原合同。certificate/admission/activation 和 native command 所有权必须通过。开发网格四方向是预注册固定对照，不是事后学习收益。严格消融在验证/测试使用相同规则、冻结群体平均历史填补或模型平均 context，当前患者历史不传入。开发 ILC 对 B 的零更新消融较弱，不能代替此检验。

冻结 H150 是另一完整低力对照，其资格逐患者单列，不能以它降力掩盖 motion 失败，也不能把运动门失败记作绝对安全失败。所有候选、正负结果、拒绝和 partial 均保留。所有增益是同一个完整 live parent 的配对比较；跨 repetition 的原始 JF 差异不解释为学习收益。

| 开发动作 | 患者数 | 完整资格 | 平均相对匹配 B 降力 / N·s |
|---|---|---|---|
| ILC | 3 | 3 | 0.084870 |
| O_MINUS | 3 | 3 | 0.342192 |
| O_PLUS | 3 | 3 | -0.356421 |
| R_MINUS | 3 | 3 | 0.456185 |
| R_PLUS | 3 | 3 | -0.547839 |

这张表只描述已经执行的开发网格，不是新增确认试验。相同模型/规则的 disabled 消融可识别当前历史对选择的贡献，但它不等价于“开发数据选出的最佳统一固定策略”。特别是 Value 选择 RETURN −0.3° 时，执行的参数本身也是一个固定网格动作。尚未证明历史个体化必要地优于这种强固定小扰动；不把该未检验结论附加到历史消融的正结果上。

Value 的 3 个实际干预采用同一个固定参数动作 RETURN[3] 膝 -0.300000°；这些消融中历史改变的是是否启用该修正，尚未证明丰富的患者特异动作排序。

### 8. 第三次真实重复是否进一步改善？

| 患者 | T3 B JF | T3 KEEP JF | T3 更新 JF | 更新相对 KEEP 降力 | 三个分支均完整合格 | 重复获益 |
|---|---|---|---|---|---|---|
| P05 | 1140.566809 | 1140.579562 | 1140.591080 | -0.011518 | True | False |
| P08 | 1438.149056 | 1438.001493 | 1437.850356 | 0.151137 | True | True |

T3 的 KEEP 保留该分支 T2 动作，更新臂只能读该分支 T2 历史。`FEW_REPETITION_BENEFIT` 要求 T2 相对匹配 B 合格获益，且 T3 相对 KEEP 再次合格获益；一次正向 T3 数值不足以通过此标志。

### 9–10. 哪些仅属开发结果，未见患者如何？

P00/P05/P08 均是已公开的开发身份。旧 P09–P11 不再充当未见患者。新 V12、U14–U16 在实验前冻结物理生成种子及参数；模型/方法冻结早于其 Trial1，所有 Trial2 动作又冻结早于该患者任何 Trial2 结果。未见患者上的独立合格消融收益出现在 U14/ILC, U14/VALUE, U15/VALUE；这是有限工程证据。 三个 heldout 不足以建立广泛跨患者可靠性。

本轮结束后这些已执行患者的结果已经公开；后续若据此修改算法，不能继续把 U14–U16 称作新算法的严格未见测试。V13 仍为本包 NOT_RUN，未生成任何物理结果。

### 11. 数据不足或模型不可靠的表现是什么？

| 患者 | 方法 | 选择 | 适用域 | 预测 JF | 标准差/保守误差 | 实际 JF | 选择依据 |
|---|---|---|---|---|---|---|---|
| V12 | BO | B | True | 1668.484 | 0.481 | 1668.845 | 候选预测资格不足，A0 |
| V12 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1668.845 | 候选预测资格不足，A0 |
| V12 | VALUE | RETURN[3] 膝 -0.300000° | True | 1668.162 | 0.481 | 1668.208 | 通过保守选择；仍须原物理门 |
| V12 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1668.845 | 保守采集/效益不足，A0 |
| U14 | BO | B | True | 1578.587 | 0.436 | 1578.804 | 候选预测资格不足，A0 |
| U14 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1578.804 | 候选预测资格不足，A0 |
| U14 | VALUE | RETURN[3] 膝 -0.300000° | True | 1578.415 | 0.481 | 1578.224 | 通过保守选择；仍须原物理门 |
| U14 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1578.804 | 保守采集/效益不足，A0 |
| U15 | BO | B | True | 1558.589 | 0.436 | 1559.504 | 候选预测资格不足，A0 |
| U15 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1559.504 | 候选预测资格不足，A0 |
| U15 | VALUE | RETURN[3] 膝 -0.300000° | True | 1558.569 | 0.481 | 1558.865 | 通过保守选择；仍须原物理门 |
| U15 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1559.504 | 保守采集/效益不足，A0 |
| U16 | BO | OUTBOUND[1] 膝 +0.300000° | True | 1208.466 | 0.449 | 1209.359 | 通过保守选择；仍须原物理门 |
| U16 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1209.028 | 候选预测资格不足，A0 |
| U16 | VALUE | B | True | 1209.296 | 0.481 | 1209.028 | 保守采集/效益不足，A0 |
| U16 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1209.028 | 保守采集/效益不足，A0 |

只有三个训练患者；17 维显式特征经 ridge 正则化，leave-one-patient-out 误差仍不能成为可靠概率校准。GP 采用原始任务重复间存在漂移的噪声下限，把上一轮 B 作为带噪同局部观察是经验假设，不是第二次回报标签。预测 motion margin 只覆盖选定工程余量，不能替代任何原门。域外/不确定时选择 A0 应记录 NO_ACTION_CHANGE；较保守的预测器没有带来动作变化时，不能宣传为学习增益。

冻结模型诊断：设计矩阵秩为 11/17；成本头交互系数 L2 范数为 0.097329，不是旧模型那种会在动作排序中完全抵消的纯状态项。开发上下文下，未加保守项的 full-fit 排序在 P05 更偏向 OUTBOUND 负向，在 P00/P08 更偏向 RETURN 负向；这只是模型诊断。Value 的成本误差下限为 0.480664 N·s，GP 观察噪声为 1.607214 N·s，均与小幅动作收益同量级或更大。真实策略选择和物理收益仍须单独检验。

内部留一开发患者诊断还有一项限制：被留出的患者行不参与对应 ridge fit，但标准化均值/尺度仍来自全部三个开发患者。因此它不是严格独立的留一校准，误差下限只能作启发式风险控制。正式 validation/heldout 患者的特征与标签从未进入训练或标准化；两者须区分。发现后保持已冻结模型和所有真实结果，不作测试后重训。详见 `INTERNAL_VALIDATION_CAVEAT.json`；下一研究应在每个训练折内独立拟合预处理并另留校准患者。

完整成本预测以已知首轮 JF 为基线；绝对误差小不等于动作优势预测准确。history-disabled 没有当前患者的该基线，采用开发平均值。图5因此同时展示完整成本与同 context 的 action−B 配对优势，后者更接近本研究真正要识别的增益。

### 12–13. 哪个动作方向值得扩大？下一步是什么？

先扩大跨患者、同父状态的局部膝姿态正负扰动数据，尤其对比 OUTBOUND 高力窗口和 RETURN[3]，辨识动作条件下的力梯度与 motion 代价。P00 的固定 RETURN 负向网格收益高于其高负担窗口 ILC，已经证伪“最高力窗口自然就是最好修改位置”的强假设。保留低维有界参考优化，优先直接预测同父状态 action−B 优势并校准其不确定性，避免跨 repetition 状态漂移压过小控制收益；现阶段没有证据支持直接升级复杂 Neural Value/Q-learning 或大规模纯 RL。

## 分离验收标志

| 标志 | 结果 |
|---|---|
| HISTORY_DATA_READY | True |
| LEARNING_MODEL_TRAINED | True |
| ACTION_ADAPTED | True |
| TRIAL_2_QUALIFIED | True |
| HISTORY_CAUSAL_BENEFIT | True |
| FEW_REPETITION_BENEFIT | True |
| CROSS_PATIENT_GENERALIZATION | LIMITED_ENGINEERED_HELDOUT_EVIDENCE |

`HISTORY_DATA_READY`、模型训练、动作改变、完整资格与历史因果收益是独立证据层级。0.01 N·s 是本包保守的收益报告门槛，不是原资格门、临床重要性标准或统计显著性阈值。更小的正向力差保留为 `QUALIFIED_SMALL_FORCE_SIGNAL_BELOW_0_01_N_s`，不抹去其原始数值，也不把它自动升格为历史因果收益。

## 完整资格与运动代价

| 患者 | 方法 | safety | task | execution | 原 motion | 完整资格 | JF / N·s | moment / N·m·s | knee RMS / ° | 失败项 |
|---|---|---|---|---|---|---|---|---|---|---|
| P00 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1437.404 | 101.632 | 0.473 | — |
| P00 | B_REPEAT_ZERO | PASS | PASS | PASS | PASS | PASS | 1437.404 | 101.632 | 0.473 | — |
| P00 | ILC | PASS | PASS | PASS | PASS | PASS | 1437.284 | 101.662 | 0.474 | — |
| P00 | O_MINUS | PASS | PASS | PASS | PASS | PASS | 1437.031 | 101.725 | 0.474 | — |
| P00 | O_PLUS | PASS | PASS | PASS | PASS | PASS | 1437.810 | 101.525 | 0.471 | — |
| P00 | R_MINUS | PASS | PASS | PASS | PASS | PASS | 1436.815 | 101.741 | 0.474 | — |
| P00 | R_PLUS | PASS | PASS | PASS | PASS | PASS | 1437.910 | 101.534 | 0.474 | — |
| P00 | H150 | PASS | PASS | PASS | PASS | PASS | 1403.797 | 107.427 | 0.530 | — |
| P05 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1140.540 | 85.652 | 0.605 | — |
| P05 | ILC | PASS | PASS | PASS | PASS | PASS | 1140.552 | 85.647 | 0.605 | — |
| P05 | O_MINUS | PASS | PASS | PASS | PASS | PASS | 1140.249 | 85.748 | 0.606 | — |
| P05 | O_PLUS | PASS | PASS | PASS | PASS | PASS | 1140.833 | 85.558 | 0.604 | — |
| P05 | R_MINUS | PASS | PASS | PASS | PASS | PASS | 1140.258 | 85.761 | 0.605 | — |
| P05 | R_PLUS | PASS | PASS | PASS | PASS | PASS | 1140.818 | 85.543 | 0.605 | — |
| P05 | H150 | PASS | PASS | PASS | FAIL | FAIL | 1109.378 | 91.106 | 0.678 | excursion |
| P08 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1438.127 | 101.908 | 0.517 | — |
| P08 | ILC | PASS | PASS | PASS | PASS | PASS | 1437.979 | 101.947 | 0.517 | — |
| P08 | O_MINUS | PASS | PASS | PASS | PASS | PASS | 1437.765 | 102.005 | 0.518 | — |
| P08 | O_PLUS | PASS | PASS | PASS | PASS | PASS | 1438.497 | 101.812 | 0.517 | — |
| P08 | R_MINUS | PASS | PASS | PASS | PASS | PASS | 1437.629 | 102.000 | 0.517 | — |
| P08 | R_PLUS | PASS | PASS | PASS | PASS | PASS | 1438.986 | 101.842 | 0.518 | — |
| P08 | H150 | PASS | PASS | PASS | FAIL | FAIL | 1404.332 | 107.441 | 0.561 | excursion |
| V12 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1668.845 | 115.941 | 0.540 | — |
| V12 | ILC | PASS | PASS | PASS | PASS | PASS | 1668.606 | 115.999 | 0.541 | — |
| V12 | ILC_DISABLED | PASS | PASS | PASS | PASS | PASS | 1668.739 | 115.965 | 0.540 | — |
| V12 | BO | PASS | PASS | PASS | PASS | PASS | 1668.845 | 115.941 | 0.540 | — |
| V12 | BO_DISABLED | PASS | PASS | PASS | PASS | PASS | 1668.845 | 115.941 | 0.540 | — |
| V12 | VALUE | PASS | PASS | PASS | PASS | PASS | 1668.208 | 116.027 | 0.542 | — |
| V12 | VALUE_DISABLED | PASS | PASS | PASS | PASS | PASS | 1668.845 | 115.941 | 0.540 | — |
| V12 | H150 | PASS | PASS | PASS | PASS | PASS | 1632.524 | 121.813 | 0.576 | — |
| U14 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1578.804 | 110.667 | 0.472 | — |
| U14 | ILC | PASS | PASS | PASS | PASS | PASS | 1578.624 | 110.710 | 0.472 | — |
| U14 | ILC_DISABLED | PASS | PASS | PASS | PASS | PASS | 1578.704 | 110.690 | 0.472 | — |
| U14 | BO | PASS | PASS | PASS | PASS | PASS | 1578.804 | 110.667 | 0.472 | — |
| U14 | BO_DISABLED | PASS | PASS | PASS | PASS | PASS | 1578.804 | 110.667 | 0.472 | — |
| U14 | VALUE | PASS | PASS | PASS | PASS | PASS | 1578.224 | 110.753 | 0.473 | — |
| U14 | VALUE_DISABLED | PASS | PASS | PASS | PASS | PASS | 1578.804 | 110.667 | 0.472 | — |
| U14 | H150 | PASS | PASS | PASS | PASS | PASS | 1543.447 | 116.274 | 0.523 | — |
| U15 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1559.504 | 111.033 | 0.440 | — |
| U15 | ILC | PASS | PASS | PASS | PASS | PASS | 1559.403 | 111.058 | 0.441 | — |
| U15 | ILC_DISABLED | PASS | PASS | PASS | PASS | PASS | 1559.398 | 111.059 | 0.441 | — |
| U15 | BO | PASS | PASS | PASS | PASS | PASS | 1559.504 | 111.033 | 0.440 | — |
| U15 | BO_DISABLED | PASS | PASS | PASS | PASS | PASS | 1559.504 | 111.033 | 0.440 | — |
| U15 | VALUE | PASS | PASS | PASS | PASS | PASS | 1558.865 | 111.156 | 0.441 | — |
| U15 | VALUE_DISABLED | PASS | PASS | PASS | PASS | PASS | 1559.504 | 111.033 | 0.440 | — |
| U15 | H150 | PASS | PASS | PASS | PASS | PASS | 1522.740 | 117.426 | 0.504 | — |
| U16 | B | PASS | PASS | PASS | SELF_REFERENCE | PASS | 1209.028 | 87.852 | 0.513 | — |
| U16 | ILC | PASS | PASS | PASS | PASS | PASS | 1209.021 | 87.854 | 0.513 | — |
| U16 | ILC_DISABLED | PASS | PASS | PASS | PASS | PASS | 1208.954 | 87.875 | 0.513 | — |
| U16 | BO | PASS | PASS | PASS | PASS | PASS | 1209.359 | 87.756 | 0.511 | — |
| U16 | BO_DISABLED | PASS | PASS | PASS | PASS | PASS | 1209.028 | 87.852 | 0.513 | — |
| U16 | VALUE | PASS | PASS | PASS | PASS | PASS | 1209.028 | 87.852 | 0.513 | — |
| U16 | VALUE_DISABLED | PASS | PASS | PASS | PASS | PASS | 1209.028 | 87.852 | 0.513 | — |
| U16 | H150 | PASS | PASS | PASS | FAIL | FAIL | 1178.410 | 93.561 | 0.592 | excursion |

完整 phase 积分和 native velocity/acceleration/jerk 在每个 `*_MEASURED.json`、`*_INDEPENDENT.json`；RETURN extrema 和终点另见 `derived/TERMINAL_RECHECK.json`。不以更低 partial JF 与完整任务排名。

下表均相对同起点 B，负数表示该诊断量降低。某项平顺性改善与累计力改善分开解释，不能用一项降低抵消其他资格失败。

| 患者 | 方法 | Δmoment / N·m·s | Δknee tracking / ° | knee velocity RMS Δ% | knee acceleration RMS Δ% | knee jerk RMS Δ% | ΔRETURN膝下冲 / ° |
|---|---|---|---|---|---|---|---|
| P00 | ILC | 0.029803 | 0.000284 | -0.0079 | 0.1423 | 0.0094 | 0.000000 |
| P00 | H150 | 5.795388 | 0.057131 | 2.5327 | -18.9162 | -2.8266 | 0.623118 |
| P05 | ILC | -0.004483 | -0.000065 | 0.0016 | -0.0845 | -0.0169 | -0.000000 |
| P05 | H150 | 5.453976 | 0.073237 | 3.2274 | -13.6149 | -2.8331 | 0.812439 |
| P08 | ILC | 0.039187 | 0.000328 | -0.0066 | 0.0851 | -12.1411 | 0.000000 |
| P08 | H150 | 5.533873 | 0.044182 | 2.4988 | -20.7124 | -15.3199 | 0.677176 |
| V12 | ILC | 0.058118 | 0.000555 | 0.0007 | 0.5415 | 0.0656 | 0.000000 |
| V12 | BO | 0.000000 | 0.000000 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |
| V12 | VALUE | 0.086172 | 0.002181 | 0.1507 | 0.2859 | 0.0309 | 0.044862 |
| V12 | H150 | 5.871683 | 0.035304 | 1.9051 | -21.5269 | -2.9470 | 0.565832 |
| U14 | ILC | 0.042476 | 0.000291 | -0.0061 | 0.3347 | 0.0383 | 0.000000 |
| U14 | BO | 0.000000 | 0.000000 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |
| U14 | VALUE | 0.085549 | 0.001853 | 0.1146 | 0.1108 | -0.0560 | 0.033180 |
| U14 | H150 | 5.606655 | 0.051929 | 2.2860 | -18.8344 | -2.8721 | 0.505281 |
| U15 | ILC | 0.024510 | 0.000661 | 0.0125 | 0.3837 | 0.0586 | 0.000000 |
| U15 | BO | 0.000000 | 0.000000 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |
| U15 | VALUE | 0.123153 | 0.001069 | 0.1389 | -0.0145 | -0.0970 | 0.034290 |
| U15 | H150 | 6.392976 | 0.064584 | 2.5237 | -17.6669 | -1.7902 | 0.497998 |
| U16 | ILC | 0.002426 | 0.000042 | -0.0003 | 0.0441 | 0.0080 | 0.000000 |
| U16 | BO | -0.096051 | -0.001390 | 0.0393 | -0.9457 | -0.1745 | -0.000000 |
| U16 | VALUE | 0.000000 | 0.000000 | 0.0000 | 0.0000 | 0.0000 | 0.000000 |
| U16 | H150 | 5.709383 | 0.078979 | 3.1096 | -15.2580 | -2.6134 | 0.697801 |

## 连续性、修复及限制

原合法 inter-repetition boundary 每次运行真实 native 步进；所有边界时间、保持命令及其 receipt 单独记录。后续任务通过原 fresh TRACK bootstrap（额外 10ms）进入 TASK，plant、measurement、observer、allocator、updater 等持久对象保留；原框架规定的临时 lifecycle/session/reference 状态重建。每个比较来自完整 Linux live address-space fork，父进程等待子进程，前后完整状态哈希一致。Python `os.fork` 自动 reseed 导致最初 P00 零步子进程校验失败；只修复隔离 fork RNG 恢复并保留失败，P00R 再执行零改动 raw/native/receipt 精确复现。没有写入 Human qpos/qvel。

实验编排器在首轮之后进行离线原资格审查，以确定是否能够形成合格配对；这个实验资格步骤会读 evaluation-only truth，但它不是学习器输入，也不改变其动作规则。部署层面的真实 wall-clock 时限与 `HOST_EXECUTION_CAUSAL_VALID` 在本科学仿真中为 NOT_EVALUABLE；这里的 execution PASS 指原科学模式的证书、causal receipt 和 native 命令所有权。

P00R v2 的准备 bootstrap 成本未独立导出，但实际额外时间、native、receipt 和命令保留；v3 后各 repetition 的准备元数据单独保存。所有主要 JF 都是完整 TASK，准备成本不并入目标。确定性单种子、狭窄虚拟参数范围、三个训练患者和三个 heldout、少量重复及微小力差，限制了结论范围。原安全门不改变；本包不晋升正式控制器。

BO/Value 只验证了固定 B 首轮到第二轮的条件优化；第三轮只运行 ILC。不能把这些结果解释为 BO/Value 在任意先前动作下的多轮收敛或长期价值学习。

## 图与核验

![完整历史到动作](figures/01_history_to_action.png)
![方法对照](figures/02_methods_force_moment_tracking.png)
![连续重复](figures/03_continuous_trials.png)
![真实运动与力](figures/04_actual_motion_force.png)
![预测与实际](figures/05_prediction_vs_observation.png)
![资格矩阵](figures/06_qualification_matrix.png)

最终保护、所有权退出、独立复算、split、历史隔离、交付 manifest 结果以 `PACKAGE_VERIFICATION.json` 为准。研究结束后 STOP，不自动继续研究。
