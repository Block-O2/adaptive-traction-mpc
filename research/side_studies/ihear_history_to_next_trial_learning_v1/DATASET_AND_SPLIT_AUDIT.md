# 数据和划分审计

独立患者是统计与 split 单位。历史 P00–P11 的工作包 A 结果已全部暴露，P09–P11 不再称严格未见。历史 11 父状态/44 动作来自同一 Human；不能当作 11 患者。

本包开发患者预先选为 P00（参考）、P05（低刚度 motion 边界）、P08（高阻尼 motion 边界），覆盖已知失败而不只选 H150 成功者。P00 的 harness retry 使用新运行标签 P00R，但仍是同一患者，首次失败和重复不增加独立样本数。

新患者 V12/V13 为 validation；U14/U15/U16 为 held-out。参数在首次物理之前用 seed=202610192200 冻结，见 COHORT.json 和每患者 case hash。新配置只改变预注册的形态一致 length/mass 和 passive stiffness/damping；robot/cuff/contact/task 结构保持。范围是工程取样，不是临床分布。静态检查并不提供患者任务成功标签。

开发数据单位为该患者第一次完整 B 历史 H1，加第二次同完整 live parent 的实际 action outcome。首次同患者历史只能进入该患者本次在线更新，不能跨 split 回流。各动作共享父状态，有相关性；留一验证必须整患者留出。时间点、phase bins、重复、相反动作都不构成独立患者。

完整成本模型只使用实际 complete 结果；拒绝、中止、partial 记录进入执行资格标签，不以 partial J_F 当完整低成本。B_REPEAT_ZERO 仅用于技术等价门，ILC 与 grid 可能同动作的重复只作复现；这些不重复加权训练。冻结后验证及确认结果均不加入训练。

训练入口为 train_models.py；部署选择仅接受 history_features 的 allowlist。学习模型不读取当前患者 T2 对照或 native 文件。每患者所有 T2 决策在第一个 T2 START 前落盘哈希；即使先执行固定 B，也不能把其结果带回该患者其他 T2 决策。

最终独立患者、父状态、完整结果、连续重复、失败、拒绝与 partial 精确计数由 ATTEMPT_ACCOUNTING.json、LEARNING_RESULTS.json 和 PACKAGE_VERIFICATION.json 汇总；本文件不以计划数冒充完成数。
