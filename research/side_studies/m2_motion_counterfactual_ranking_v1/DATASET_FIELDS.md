# 历史dense审计数据字段与复用边界

HISTORICAL_DENSE_COMMITTED_AUDIT.npz是80条原cohort的只读可复用导出，非新增独立状态、非v2就绪训练集。x为原causal120D float32，不注入真值；remaining_J_F_N_s为terminal native scorer−fork prefix，source_id/snapshot/parent/split保留原来源隔离，dense_trace是完整TASK高分辨率索引。无新模型/权重。

dense_branch_series/*：time_s、真实q/dq、梯度加速度/jerk、phase、fork_physical_s。所有true物理字段只作evaluation标签。branch_audits/*：完整来源/sha、candidate表、eligible mask、issued counts、carry、context、全部raw/5/21节点运动统计、full/remaining dose、启停/反转窗口、tracking、peak force/moment、remaining/full moment、clearance、原物理/SCI资格及host NOT_EVALUABLE、积分闭合及执行证据。

receipt_series/*：实际command receipt起止物理时间、native_steps、receipt_index、reference_effective_physics_s、q/dq reference。candidate action proposal不单独视作执行；branch_audits execution.requests/decisions与原runtime artifact索引保留认证、拒绝和科学版本因果链。未把这些SCI收据当作host40ms/100ms资格。

COUNTERFACTUAL_BRANCH_RESULTS包含80历史结果、3历史失败、8原cohort排除及空new_attempts。MANIFEST保存原91个DATA来源、所有raw/derived trace索引与hash。严格按父来源分组，dense节点和candidate pair不是独立样本。原失败/排除不重新筛选成有利样本。

候选池范围：74条ordinary、6条原offline G-head诊断标签。candidate_pool_class标明来源；当前ordinary池损失0，联合池最大3.241335来自G-head覆盖，不等同于state preference学习机会。所有model_hash/beta各1种，不能称跨estimate覆盖。
