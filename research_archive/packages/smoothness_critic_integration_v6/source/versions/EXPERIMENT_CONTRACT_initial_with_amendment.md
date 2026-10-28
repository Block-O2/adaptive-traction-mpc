# v6 事前研究合同

唯一 ACTIVATION 与六小时截止见 ACTIVATION.json；新动力学任务截止前预留封包时间。旧包只读，原 motion、安全、任务、5ms JF/JM 左积分及权限不变。

先恢复 v5 真实 raw、源码、模型与 manifest。强固定 BEST、HANDOFF、PATTERN、COMPOSE、ANTICIPATORY 保留原身份。只新增一个在 PATTERN 与 COMPOSE 合法坐标间的 BLEND，假设其保留大部分平顺性而减少 COMPOSE 的 JF 代价。初始最多 6 个开发父状态、4 个冻结评价父状态，每菜单 B 资格参照及五个候选；不广域搜索、不新增 PPO。

A 固定 COMPOSE；B 0.5 秒实测 JF；C 1 秒实测 JF；D 0.5 秒 JF 加冻结 Critic；E 在实际完整合格续跑中取最低剩余 JF，仅为有限菜单离线参照。固定 HANDOFF、PATTERN 另外报告。所有方法菜单、初态、任务与执行语义相同：选择候选后，在每次后续决策都提交该候选的冻结动作，经原 admission、scheduler、governor、guard 和 fallback 执行。标签按候选策略条件化，不将旧 B rolling 单次干预标签混入成本回归。此续跑语义与“所有候选的下一次决策均恢复同一个 B”分别标记。

0.5/1 秒候选数据来自真实 MuJoCo 分支，不能称低成本在线预测或硬件尝试。累计历史只读取当下 observer、measured wrench、原 guard 返回值与已有 context rejection。observer 差分峰值与原 native 门不等价；最终资格仍由原 raw scorer 独立评价。不得使用未来 PASS/FAIL 作为选择 mask。完整任务失败绝不进入正式收益排名；若当前已知不可逆的原门失败，无论尾部预测如何均无资格。

模型须保留时间和阶段信息，按训练折拟合变换并设物理尺度下限；按整个父状态分割。常量/近常量字段有分布审计与 OOD 处理，ensemble 分歧不是校准置信度。成本回归和资格风险预测分开。新 test 输入、源、菜单、模型、规则在任何 test 动力学结果前冻结，揭示后不再训练并称其未见。

主线 D 的原消息在第2步截断，已请求补充。冻结验证前不开展物理尝试节省声明；全菜单短窗和尾部实际执行时 savings=0。继续推进不依赖截断内容的 A/B/C。

主比较的后续策略进一步固定为 COMMON_COMPOSE：菜单只更改当前一次决策，之后所有候选均恢复同一 COMPOSE（包括其 H150 timing/posture 语义）。A 当前也选 COMPOSE，B/C/D 菜单相同。原 B 分支仅为原资格参照，不在决策菜单。DEV_O1 的整策略承诺实验单独作为动作库诊断，绝不混入此成本标签。该约束在主比较第一个 START 之前冻结。
