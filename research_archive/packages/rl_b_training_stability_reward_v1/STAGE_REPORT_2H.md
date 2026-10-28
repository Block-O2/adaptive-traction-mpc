# ACTIVATION + 2h 阶段报告

UTC：2026-10-21T08:07:13.305831+00:00；实际elapsed 2.0000h。

训练完成 80 集；Adam 340 steps；native 9,594,580。

|分支|父seed|模式|完整/已完成|Adam steps|
|---|---|---|---|---|
|CHECKPOINT_STD|1495656323|stochastic_training|7/10|52|
|CHECKPOINT_STD|1630784693|stochastic_training|3/10|28|
|CHECKPOINT_STD|1495656323|deterministic|1/1|0|
|CHECKPOINT_STD|1495656323|stochastic|1/1|0|
|CHECKPOINT_STD|1630784693|deterministic|1/1|0|
|CHECKPOINT_STD|1630784693|stochastic|1/1|0|
|STD_INIT_0p2|1495656323|stochastic_training|22/30|140|
|STD_INIT_0p2|1630784693|stochastic_training|29/30|120|
|STD_INIT_0p2|1495656323|deterministic|1/1|0|
|STD_INIT_0p2|1495656323|stochastic|1/1|0|
|STD_INIT_0p2|1630784693|deterministic|1/1|0|
|STD_INIT_0p2|1630784693|stochastic|1/1|0|

当前任务：['STD_INIT_0p2_seed1495656323_ep030_deterministic_2026102201']。剩余预算：{'training': 80, 'evaluation': 27, 'native': 23405420, 'wall_s': 21599.83152627945}。

失败 partial 原样保留，单分支失败继续其他有界假设；正式 G4/live matched/Stage2/Campaign 均未获资格。本报告不是STOP信号；继续已授权有限队列，最终候选先锁SHA再打开预留流。
