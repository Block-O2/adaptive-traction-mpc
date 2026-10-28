# 保存轨迹上的动作与执行诊断

只读原始和本轮冻结证据，零新增物理/Adam。完整准入结果、每phase的提议/执行向量与source SHA见同名JSON。协调动作不是torque；实际应用仍由既有native/receipt审计证明。

|branch|seed|续训端点|mode|split/RNG|任务完成|RL决策|planner决策|接受/拒绝|applied receipts|raw分量clip比例|RETURN结果|
|---|---|---|---|---|---|---|---|---|---|---|---|
|ORIGINAL_050|1495656323|0|deterministic|historical/—|True|19|19|18/1|5817|旧轨迹无raw Gaussian|{'ACTIVATED': 8, 'FAILED': 1}|
|ORIGINAL_050|1630784693|0|deterministic|historical/—|True|17|17|17/0|5817|旧轨迹无raw Gaussian|{'ACTIVATED': 8}|
|H1|1495656323|10|deterministic|development/2026102101|False|18|18|16/2|5176|0.0000|{'ACTIVATED': 6, 'FAILED': 2}|
|H1|1495656323|10|stochastic|development/2026102101|True|25|25|20/5|6000|0.4800|{'ACTIVATED': 9, 'FAILED': 5}|
|H1|1630784693|10|deterministic|development/2026102101|True|16|16|16/0|5817|0.0000|{'ACTIVATED': 7}|
|H1|1630784693|10|stochastic|development/2026102101|False|18|18|15/3|5017|0.4722|{'ACTIVATED': 5, 'FAILED': 3}|
|H1|1495656323|20|deterministic|development/2026102101|False|18|18|16/2|5215|0.0000|{'ACTIVATED': 6, 'FAILED': 2}|
|H1|1495656323|20|stochastic|development/2026102101|True|25|25|20/5|6006|0.4400|{'ACTIVATED': 9, 'FAILED': 5}|
|H1|1630784693|20|deterministic|development/2026102101|True|15|15|15/0|5817|0.0000|{'ACTIVATED': 7}|
|H1|1630784693|20|stochastic|development/2026102101|False|18|18|15/3|5046|0.5278|{'ACTIVATED': 5, 'FAILED': 3}|
|H1|1495656323|30|deterministic|development/2026102101|False|17|17|15/2|5244|0.0000|{'ACTIVATED': 6, 'FAILED': 2}|
|H1|1495656323|30|stochastic|development/2026102101|False|18|18|15/3|4947|0.5278|{'ACTIVATED': 5, 'FAILED': 3}|
|H1|1630784693|30|deterministic|development/2026102101|True|15|15|15/0|5817|0.0000|{'ACTIVATED': 7}|
|H1|1630784693|30|stochastic|development/2026102101|False|18|18|15/3|5052|0.5278|{'ACTIVATED': 5, 'FAILED': 3}|
|H2_AGG64|1495656323|30|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|H2_AGG64|1495656323|30|stochastic|development/2026102101|True|25|25|20/5|5992|0.4400|{'ACTIVATED': 10, 'FAILED': 5}|
|H2_AGG64|1630784693|30|deterministic|development/2026102101|True|16|16|16/0|5817|0.0000|{'ACTIVATED': 7}|
|H2_AGG64|1630784693|30|stochastic|development/2026102101|False|18|18|14/4|5011|0.4722|{'ACTIVATED': 5, 'FAILED': 3}|
|REWARD_R1|1495656323|10|deterministic|development/2026102101|True|18|18|17/1|5817|0.0000|{'ACTIVATED': 8, 'FAILED': 1}|
|REWARD_R1|1495656323|10|stochastic|development/2026102101|True|25|25|20/5|5996|0.4200|{'ACTIVATED': 9, 'FAILED': 5}|
|REWARD_R1|1630784693|10|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|REWARD_R1|1630784693|10|stochastic|development/2026102101|True|22|22|18/4|5888|0.4091|{'ACTIVATED': 9, 'FAILED': 3}|
|REWARD_R1|1495656323|30|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|REWARD_R1|1495656323|30|stochastic|development/2026102101|True|25|25|20/5|5994|0.4400|{'ACTIVATED': 10, 'FAILED': 5}|
|REWARD_R1|1630784693|30|deterministic|development/2026102101|True|16|16|16/0|5817|0.0312|{'ACTIVATED': 7}|
|REWARD_R1|1630784693|30|stochastic|development/2026102101|True|22|22|19/3|5993|0.4773|{'ACTIVATED': 10, 'FAILED': 2}|
|REWARD_R2|1495656323|10|deterministic|development/2026102101|True|18|18|17/1|5817|0.0000|{'ACTIVATED': 8, 'FAILED': 1}|
|REWARD_R2|1495656323|10|stochastic|development/2026102101|True|25|25|20/5|5997|0.4200|{'ACTIVATED': 9, 'FAILED': 5}|
|REWARD_R2|1630784693|10|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|REWARD_R2|1630784693|10|stochastic|development/2026102101|True|22|22|18/4|5887|0.4091|{'ACTIVATED': 9, 'FAILED': 3}|
|REWARD_R2|1495656323|30|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|REWARD_R2|1495656323|30|stochastic|development/2026102101|True|25|25|20/5|5992|0.4400|{'ACTIVATED': 10, 'FAILED': 5}|
|REWARD_R2|1630784693|30|deterministic|development/2026102101|True|16|16|16/0|5817|0.0312|{'ACTIVATED': 7}|
|REWARD_R2|1630784693|30|stochastic|development/2026102101|True|22|22|19/3|5989|0.4773|{'ACTIVATED': 10, 'FAILED': 2}|
|RETENTION_H2|1495656323|60|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|RETENTION_H2|1495656323|60|stochastic|development/2026102101|True|24|24|20/4|5937|0.4167|{'ACTIVATED': 10, 'FAILED': 4}|
|RETENTION_H2|1630784693|60|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|RETENTION_H2|1630784693|60|stochastic|development/2026102101|True|22|22|18/4|5904|0.4091|{'ACTIVATED': 9, 'FAILED': 3}|
|REWARD_R3|1495656323|10|deterministic|development/2026102101|True|18|18|17/1|5817|0.0000|{'ACTIVATED': 8, 'FAILED': 1}|
|REWARD_R3|1495656323|10|stochastic|development/2026102101|True|26|26|21/5|5998|0.4615|{'ACTIVATED': 10, 'FAILED': 5}|
|REWARD_R3|1630784693|10|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|REWARD_R3|1630784693|10|stochastic|development/2026102101|True|23|23|18/5|5950|0.4783|{'ACTIVATED': 9, 'FAILED': 4}|
|RETENTION_R1|1495656323|60|deterministic|development/2026102101|True|17|17|17/0|5817|0.0000|{'ACTIVATED': 8}|
|RETENTION_R1|1495656323|60|stochastic|development/2026102101|True|25|25|20/5|6000|0.4400|{'ACTIVATED': 10, 'FAILED': 5}|
|RETENTION_R1|1630784693|60|deterministic|development/2026102101|True|16|16|16/0|5817|0.1250|{'ACTIVATED': 7}|
|RETENTION_R1|1630784693|60|stochastic|development/2026102101|True|22|22|19/3|6012|0.4773|{'ACTIVATED': 10, 'FAILED': 2}|
|RETENTION_R1|1495656323|60|stochastic|heldout_action_stream/2026102191|True|18|18|17/1|5817|0.3889|{'ACTIVATED': 8, 'FAILED': 1}|
|RETENTION_R1|1495656323|60|stochastic|heldout_action_stream/2026102192|True|23|23|18/5|5876|0.4130|{'ACTIVATED': 7, 'FAILED': 3}|
|RETENTION_R1|1495656323|60|stochastic|heldout_action_stream/2026102193|False|20|20|14/6|5593|0.4000|{'ACTIVATED': 5, 'FAILED': 6}|
|RETENTION_R1|1495656323|60|stochastic|heldout_action_stream/2026102194|True|18|18|18/0|5817|0.3333|{'ACTIVATED': 9}|
|RETENTION_R1|1630784693|60|stochastic|heldout_action_stream/2026102191|True|18|18|17/1|5817|0.5278|{'ACTIVATED': 8, 'FAILED': 1}|
|RETENTION_R1|1630784693|60|stochastic|heldout_action_stream/2026102192|False|1|1|0/1|2012|0.5000|{}|
|RETENTION_R1|1630784693|60|stochastic|heldout_action_stream/2026102193|True|19|19|15/4|5826|0.4737|{'ACTIVATED': 6, 'FAILED': 4}|
|RETENTION_R1|1630784693|60|stochastic|heldout_action_stream/2026102194|True|17|17|17/0|5817|0.4412|{'ACTIVATED': 8}|

每条轨迹的访问状态及决策数不同，以上统计不等于相同状态下的策略参数效应。失败planner请求和activation-validator拒绝分别保留；ESCAPE_ADMITTED按原审计事件名保存，不把该标签直接判为安全失败。
