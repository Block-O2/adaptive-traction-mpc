# Force–motion diagnostic

本轮区分三层：reference变化、实际Human变化、完整force结果。新非零多段对象具有独立reference identity及worker/current certificate；逐receipt的q/dq由对象系数独立重建，实际native步唯一归属，command torque匹配。每例support之前与匹配base完全一致的negative control另存。

原allocator代数分解见derived/NEW_DEMAND_DECOMPOSITION.json：gravity、elastic、velocity terms、remainder与allocation geometry投影差精确闭合。remainder包含惯性、tracking、soft-limit、residual及安全修正，不是单独测得的acceleration项。模型beta差另存。模型需求与实测接触力差不同，后者仍受robot/contact及窗口边界响应影响。

实际tracking、command torque的base/position/velocity/allocator/clipping分量和request/activation/splice时序均保存；trace里的allocated_wrench_world是总command wrench，不能称纯allocator输出。原纯allocator输出只来自明确标注的代数重算。局部正负force差面积与完整净差分列，避免把局部低力或小净差误当全程改善。

所有完整候选的逐窗数值在ALL_ANALYZED_RESULTS.json，包含全程、OUTBOUND/HOLD/RETURN、4–6s、15–16s和各注册support。新组合的微小改善、恶化、证书拒绝和motion失败同等保留。无独立smoothness中介操纵，因此因果归因仍有限。

## 本轮关键反例、重复与组合

18D回程平滑support内ΔJ_F=-0.051323951 N·s，support外=+0.067754591，完整=+0.016430641。已存档的request时刻/执行标签变化数量=0；没有据此把抵消归为重规划时序改变。原纯allocator重算完整差=+0.007598878 N·s，实测差=+0.016430641；模型姿态需求、tracking、robot/contact响应仍共同参与，独立smoothness中介未识别。

两个batch的B/18D及18D去/回程smooth重复均比较了全部trace、116320 native行和5817 receipts，结果PASS。两批来自不同冷父进程，完整fork hash的跨批相等情况逐例保存；只声明同开发条件的确定性物理重复，不称相同父进程或新prefix验证。

|base|O+R完整ΔJ_F N·s|单独O/R差值之和|组合交互差|完整TV_v变化%|
|---|---:|---:|---:|---:|
|B|-0.109443162|-0.109443138|-0.000000024|-0.2291|
|E|+0.000017610|+0.000017610|+0.000000000|-0.4602|

交互差为ΔJ_OR−ΔJ_O−ΔJ_R，负值表示额外降力。它只描述本base的O/R组合；B与18D使用各自设计的S，不能将两者差异解释为相同处理的纯因果synergy。

![四组共同时间轴](figures/four_group_comparison.png)

![局部与下游累计变化](figures/downstream_cumulative_effects.png)
