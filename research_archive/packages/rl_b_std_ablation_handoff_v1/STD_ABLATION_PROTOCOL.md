# STD 冻结评价预注册协议

冻结时间 UTC：2026-10-21T04:44:34.512749+00:00。模型身份见 audit/CHECKPOINT_IDENTITY.json；每份配置与噪声均在 pilot 前写入并校验 SHA。

A 为 checkpoint 实际 Gaussian STD；B 仅在采样算式中使用 0.2；C 取 mean。所有网络、critic、Adam、执行合同保持。raw Gaussian → [-1,1] clip → 原协调参数映射 → planner准入 → applied receipt 分别保存。

每父6条新流 202610213101–202610213106，24个正式配对attempt。pilot流202610213001的A/B两个attempt先运行且单列；两父C各一次做历史身份回归。预定28次，上限32。单环境，单Torch/BLAS线程；每attempt最多165000 native、128 decisions、300秒。最后15分钟不启动物理。

A/B共享同一已保存128×2标准正态数组，按决策索引配对；闭环状态分歧另报，不把相同noise当作相同轨迹。每条流交替A/B顺序。旧2191–2194仅作已见历史。

主要结果为逐父完整成功/几何拒绝及配对discordance；pilot排除。另报告时长、phase、JF/JM、实际Human q/dq/a/jerk、tracking、overshoot、source-age、receipt、clip。失败partial剂量单列；不对不同任务时长的JF差值宣称控制效率提升。样本量仅支持开发信号。

pilot要求恢复全状态身份、无梯度/权重/Adam变化、噪声映射正确、原native/receipt/force/motion审计通过；任务失败可作为科学结果继续。完整性/安全失控才全局阻断。不得因B失败追加STD网格。
