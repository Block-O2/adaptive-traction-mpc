# 冻结 Q 排序机制归因

状态：解析审计 PASS；真正 state×plan 排序能力 FAIL；物理固定排序 comparator NOT_RUN。

冻结权重 SHA256：3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9。selected_Q=linear；120D 输入依次为 causal normalized55、previous K3 residual3、masked candidate30、masked carry30、issued counts2。实际归一化与输出反归一化折叠后 Q(x)=offset+coef·x。同一候选集合、mask、carry、issued counts 下，ΔQ_ij=coef[58:88]·(masked(p_i)−masked(p_j))；状态、history、carry、counts 的公共项完全相消，交叉导数为零。因此绝对分数随状态变化不能证明条件化排序。

从真实旧/本轮 worker 记录审计 131 个决策，阶段计数 {'OUTBOUND': 58, 'RETURN': 73}。固定候选、mask、carry 后使用 131 个真实上下文：解析排序数 1，native mixed-precision 排序数 1，top-choice变化 0；native mixed-precision 分数差漂移最大 4.54747351e-13 N·s。真实记录中 raw-top 被 native eligibility 改选 3 次，carry 被选 40 次，worker late-carry 77 次。候选变化、随机噪声、mask 与 native feasibility 仍可改变实际选择，但不等于 learned conditional preference。

Q-first 只验证直至首个有效候选；未访问候选 eligibility 是 unknown。原 close-rank float32 safeguard 完整保留。实数排序等价不宣称 bitwise 等价，最大 pairwise 数值误差 3.41483963e-06 N·s。未运行 HOLD Q 决策，标为 NOT_EVALUABLE；解析结论覆盖所有120D输入。

Issued slots 在发出时推进，包括后来被拒的提案，不能视为物理完成数。carry 特征是公共项，carry 候选身份可改变排序；late guard 恢复 carry 属执行机制。完整 raw scores、margins、固定计划、coefficients、记录路径及哈希在同名 JSON。无训练、无物理新增尝试。

固定计划的36个 issued-mask 组合产生 14 个排序与 5 个 top-choice，属于 mask-induced selection 的离线解析证据。Absolute recorded q_all 重建最大误差 0 N·s。

数值精度核验：实际feature/normalization=float32，linear_W/Q_output/y_mean/y_scale=float64；原close-rank的float32保守误差bound保持不变。固定候选探针candidate0绝对Q从357.786644730到1324.292717211 N·s，但相对排序始终不变。共同状态项的明显绝对变化不能证明state-conditioned preference。
