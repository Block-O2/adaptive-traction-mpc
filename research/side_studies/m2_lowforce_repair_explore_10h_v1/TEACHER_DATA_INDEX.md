# Teacher 数据索引

本轮不训练。紧凑表 TEACHER_COMPACT.jsonl 有 229 条完整策略／fork 后续价值记录；局部执行以独立原生 receipt 引用。失败标签在 SEARCH_AND_VALIDATION 与 ATTEMPTS，短程积分不作正常回归目标。

当前输入来源：决策当时 causal55D observation、phase/public progress、model_hash、K3历史与 issued index；55D含估计人体状态及模型参数。动作从 graph/registered_spec 或真实 K3 表读取；raw_v2全零 action是占位，不是执行动作。完整策略不转换为旧120D单步Q动作。carry、issued history/count/mask 和估计 beta/residual 在对应 SNAPSHOT 的 interface_scientific_state／native manifest；需保持与当前决策时间对齐，未来receipt仅用于标签审计。当前输入与真实状态审计通道分开。

固定 PWL/table 续跑由 B 原生规划 segments、carry/fallback；Frozen_M2 是旧冻结 Q 滚动重选，分账。完整 TASK left quadrature 与 fork 时已发生 prefix 积分分别定义 full 与 remaining 标签。相同完整父状态重建 gate 与原生 fork实现保留；父进程退出后哈希／JSON不恢复活对象，不能称可独立checkpoint。唯一重建代码、协议、seed与合法prefix保存在 code、SEARCH_PROTOCOL 与 queue。训练／验证未来必须按 parent、condition、source分组隔离；V1–V3不能转为开发样本后仍声称未见测试。

LOCAL_EXECUTED_DECISIONS.jsonl 有 2636 条实际执行局部决策。剩余力积分按原 TASK trace 在实际 proposal time 剪裁所有 left-quadrature 区间；不复用导数去重索引。这是已观察的固定后续规则价值，不是单步 Q^B，不能当作已做独立局部反事实。未来接受值／receipt 和实际 native steps 全在 label_only；当前 action_input 保留真实 graph/spec／K3 编码。

TEACHER_CURRENT_INPUTS.jsonl 提供新增探索决策的逐时刻估计 observation、beta／residual、issued count／mask、已 issued graph 历史、前次合法 graph／coordination carry。读取发生在本次动作选择之前；未把未来 receipt 和 realized delta 放入当前输入。full_capture_available=false 的初期复现／Frozen_M2 记录仍保留，但不能当作完整部署输入训练样本。snapshot 里的 ndarray 哈希只审计身份，不能替代数值输入。


保留验证范围补充：V1–V3的合法OUTBOUND前缀使fork父q/dq不同，但在最佳方案首次RETURN实际执行时，真实q相对开发条件最大差仅3.94e−9 rad，dq差约1.03e−10 rad/s；相对C4额外降力均约6.140119 N·s。由此推断，HOLD／端点续跑使RETURN状态高度收敛，三个完整TASK收益百分比差异主要来自此前前缀影响与同条件B分母。3/3仍是按预注册条件完成的配对通过，但不构成三个显著不同RETURN决策状态下的稳健性证据；不得称跨状态或跨Human成功。已见条件数、重复数与动作数不能当独立状态样本数。来源及真实状态属于事后审计通道，见RETURN_STATE_VALIDATION_SCOPE.json。
