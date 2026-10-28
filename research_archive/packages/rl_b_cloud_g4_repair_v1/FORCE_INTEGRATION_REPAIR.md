# 累计力与reward归属

| slow episode量 | 修复前 | 独立raw / 修复后 |
|---|---:|---:|
| TASK左积分 N·s | summary928.0810851870452 | 927.5259761342978 |
| 错误单行 N·s | 0.5551090533471514 | 0（dt=0） |
| wrapper累计 N·s | 927.5259761342987 | 927.5259761342987 |
| reward force项 | -0.1855051952268596 | -0.1855051952268596 |
| reward总和 | -10.187928954054334 | -10.187928954054334 |
| moment summary N·m·s | 114.71605487166386 | 114.75606389076545 |

修复后slow summary force927.5259761342987与独立trace积分差9.094947017729282e-13N·s。不是按固定0.555109抵扣；每个拟执行事件只拥有实际推进的物理区间。

完整TASK与分phase复算：maximal OUTBOUND725.825779277981、HOLD54.39433879320881、RETURN669.61994288184，合计1449.840060953029N·s；random依次848.6989146009525、54.58529223632176、713.4114302774352，合计1616.69563711471N·s；slow仅OUTBOUND927.5259761342978。结束边界成本0。

`force_audit.py`完全不调用runtime积分或reward函数，从完整raw逐边界重算force/moment，再与独立online tick、summary和reward比较。所有9个episode均PASS，完整结果位于每个episode的 `FORCE_INDEPENDENT_AUDIT.json`。`audit_reward_physical.py`另从保存的transitions与public contract验证各reward项、吸收终态和无timeout bootstrap。

历史PPO reward未受这项重复积分影响：wrapper使用tick时间差乘前一传感器力，并非读取summary或interval cost。历史没有PPO训练，gradient update为0。若错误summary被用于后续监督标签/跨策略力成本比较，会污染标签与资格评价。对slow的13条现有native Learning记录逐字段比较，force、duration、completion及state均相同；仅candidate/selected_plan中的host reference_apply_ns不同，见 `audit/LEARNING_DIFFERING_FIELDS.json`。未证明所有未提供的外部Learning消费者都安全。

terminal observation为41维零向量；真实终端力仅保留在评价证据。reset前后force/moment/reward/动作队列/计数器清零，第二episode不继承状态。原始拒绝、失败与partial均保留。trace_node_count包含失败尝试，旧boundary_interval_relation_holds在含额外拒绝行时可为false；独立receipt ownership验证真实区间数，而不是将每一trace行当成已执行5ms。

物理回归：slow/maximal/random共316660个native状态与历史逐样本一致（q/dq、torque、contact、reference与force最大差0）；force修复没有改变Human真实运动、控制或cuff物理。
