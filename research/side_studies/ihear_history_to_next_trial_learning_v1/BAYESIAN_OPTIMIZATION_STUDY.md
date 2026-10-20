# Constrained Bayesian optimization

实际训练样本 15，来自三个开发患者、三个同父状态动作网格。输入是四个 phase-local force/tracking 特征以及两个有界动作坐标；成本 GP 和 motion-margin GP 分开，实际 execution 结果用 Beta(1,1) 平滑。核、尺度、噪声和阈值见冻结源码与 NPZ；未知/拒绝动作不获得虚构回报。

history-enabled 加入当前患者实际 Trial1 B 的带噪成本观察，history-disabled 不读取该历史，仅用训练平均 context。重复初态漂移由开发 B 的实际漂移设噪声下限，仍是局部平稳性假设。资格概率未经充分校准，保守 EI 每患者只有一个探索提案，原物理证书和所有安全/task/motion 门仍最终裁决。**DATA_LIMITED；不是形式安全控制器。**

| 患者 | 方法 | 选择 | 适用域 | 预测 JF | 标准差/保守误差 | 实际 JF | 选择依据 |
|---|---|---|---|---|---|---|---|
| V12 | BO | B | True | 1668.484 | 0.481 | 1668.845 | 候选预测资格不足，A0 |
| V12 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1668.845 | 候选预测资格不足，A0 |
| U14 | BO | B | True | 1578.587 | 0.436 | 1578.804 | 候选预测资格不足，A0 |
| U14 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1578.804 | 候选预测资格不足，A0 |
| U15 | BO | B | True | 1558.589 | 0.436 | 1559.504 | 候选预测资格不足，A0 |
| U15 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1559.504 | 候选预测资格不足，A0 |
| U16 | BO | OUTBOUND[1] 膝 +0.300000° | True | 1208.466 | 0.449 | 1209.359 | 通过保守选择；仍须原物理门 |
| U16 | BO_DISABLED | B | True | 1338.092 | 0.429 | 1209.028 | 候选预测资格不足，A0 |

| 患者 | split | 相对 B 降力 / N·s | 相对 disabled 降力 / N·s | 完整资格 | 严格历史消融 |
|---|---|---|---|---|---|
| V12 | validation | 0.000000 | 0.000000 | True | False |
| U14 | heldout | 0.000000 | 0.000000 | True | False |
| U15 | heldout | 0.000000 | 0.000000 | True | False |
| U16 | heldout | -0.330361 | -0.330361 | True | False |

BO 在四个新患者上均完整合格，但只有 U16 实际改变动作；该次完整力积分增加 0.330361 N·s，未取得力收益。其 cuff moment 降低 0.096051 N·m·s、膝 tracking RMS 降低 0.001390°，是付出更高累计力的局部运动代价交换，不能升级为降力学习成功。其余三位患者与 disabled 同选 B，记 NO_ACTION_CHANGE。候选预测资格不足不等于候选已被真实物理判定非法。

是否实际改变和产生合格历史收益，以 REPORT 的分离标志与实际结果为准。随机搜索 NOT_RUN；四个预注册固定网格、固定 B/H150、简单 ILC 和 disabled 提供对照，不能仅凭 surrogate prediction 选胜者。

方法背景：[Gelbart、Snoek、Adams，Bayesian Optimization with Unknown Constraints](https://arxiv.org/abs/1403.5607)。这里只采用分离成本/资格预测和受约束采集的思路，不宣称复现完整算法或其性能。
