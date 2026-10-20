# History-conditioned value regression

模型是 17 维 ridge ensemble：截距、四个标准化历史特征、两个动作、两个动作平方、八个显式 history×action 交互。三个输出是 `J2-J1` 完整成本差、选定 motion margin、execution/task 资格。训练一次 full fit 和三次 leave-one-patient-out fit，λ=1；没有神经网络、TD 或 Bellman backup。

内部留一拟合共享全开发集的标准化参数，不能称为严格独立的不确定性校准；外部验证/测试不参与该标准化。见 `INTERNAL_VALIDATION_CAVEAT.json`。本包保留原冻结模型，不以测试后重训掩盖这一限制。

15 个完整动作结果不等于同样多独立患者；只有三个患者/父状态，因此 **DATA_LIMITED**。持久权重见 `models/history_models.npz`，真实标签见 `models/TRAINING_DATA.json`，留患者误差见 `models/LEAVE_PATIENT_OUT.json`。预测误差下限和 ensemble spread 用于保守选择，不是可靠校准置信界。

| 患者 | 方法 | 选择 | 适用域 | 预测 JF | 标准差/保守误差 | 实际 JF | 选择依据 |
|---|---|---|---|---|---|---|---|
| V12 | VALUE | RETURN[3] 膝 -0.300000° | True | 1668.162 | 0.481 | 1668.208 | 通过保守选择；仍须原物理门 |
| V12 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1668.845 | 保守采集/效益不足，A0 |
| U14 | VALUE | RETURN[3] 膝 -0.300000° | True | 1578.415 | 0.481 | 1578.224 | 通过保守选择；仍须原物理门 |
| U14 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1578.804 | 保守采集/效益不足，A0 |
| U15 | VALUE | RETURN[3] 膝 -0.300000° | True | 1558.569 | 0.481 | 1558.865 | 通过保守选择；仍须原物理门 |
| U15 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1559.504 | 保守采集/效益不足，A0 |
| U16 | VALUE | B | True | 1209.296 | 0.481 | 1209.028 | 保守采集/效益不足，A0 |
| U16 | VALUE_DISABLED | B | True | 1338.641 | 0.481 | 1209.028 | 保守采集/效益不足，A0 |

| 患者 | split | 相对 B 降力 / N·s | 相对 disabled 降力 / N·s | 完整资格 | 严格历史消融 |
|---|---|---|---|---|---|
| V12 | validation | 0.636836 | 0.636836 | True | True |
| U14 | heldout | 0.580099 | 0.580099 | True | True |
| U15 | heldout | 0.639314 | 0.639314 | True | True |
| U16 | heldout | 0.000000 | 0.000000 | True | False |

V12、U14、U15 通过完整资格且优于同规则 disabled 与匹配 B；U16 回退 B，未获历史收益。三次干预都为 RETURN[3] 膝 −0.3°，当前证据说明历史改变了是否启用修正，尚未证明优于开发数据选出的统一固定 RETURN 负向动作，也没有超过合格 H150 的降力水平。微小降力伴随 moment、tracking 或局部下冲增加，详见主报告的逐项运动代价表。

在线 context 来自允许的完整历史；disabled 用训练平均 context 且函数断言其 history 参数必须为 None。若选择 B，则 NO_ACTION_CHANGE；若选择与 disabled 相同动作，不能声称历史反馈有额外贡献。完整结果和失败单列，不能用训练拟合宣传泛化。
