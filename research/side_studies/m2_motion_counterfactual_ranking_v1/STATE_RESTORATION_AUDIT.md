# 状态恢复审计

新增合法 fork：**NOT_EVALUABLE**。阶段 C 停止，新增 branch attempts=0。

原完整 fork 与磁盘摘要必须区分。`native_data.py` 在 CPU 单线程静止状态调用 `os.fork()`，fork 前后校验完整 manifest digest，并等待每个 child；原 BRANCH_GATE 保存两条零残余 full trace 逐字段差为0、parent hash不变证据。该证据支持历史进程内合法反事实，不支持本轮从JSON恢复。

共审计 15 个 snapshot 文件。`fork_core.state_manifest` 将 ndarray、MuJoCo integration state、长历史列表变成 SHA256/shape/dtype；opaque locks和native cache handles仅标注fork_preserved。JSON包含q/dq相关状态、estimator/commissioning、reference/phase、planner、mask/carry/count、lifecycle/pending、RNG等摘要，但缺少完整数组内容、对象关系的可执行恢复及native handles。仅q/dq不能补齐这些状态。

未找到durable checkpoint；任务开始进程清单没有存活的历史父进程或重型物理实验。没有重建plant/Human、拼接snapshot或尝试近似replay。历史合法fork、当前不可恢复摘要、近似replay三个类别分别记录；第三类本轮0次。

历史执行模式为SCIENTIFIC_SIMULATION。其物理安全与simulation-version因果检查可用于有限committed标签；原raw scorer的wall plan_age FAIL仍保留，mode-aware realtime结果为N/A。本轮不将它改写为40ms bridge/100ms wall lifecycle的host合格执行。不能进入相同state下V_replan对照。

后续只读取已完成分支与dense native原始证据；所有source/hash、component字段与原BRANCH_GATE原文在JSON。
