# 短期与完整剩余任务

CONFIRMED：候选完整真实续跑提供E离线参照；E不是可部署方法或全局最优oracle。原5ms左积分逐条闭合short+tail=remaining，原门失败不按低积分成功排序。

| 状态 | 0.5s选择 | 1s选择 | 完整合格选择 | 0.5s regret N·s |
| --- | --- | --- | --- | --- |
| DEV_O1 | COMPOSE | COMPOSE | HANDOFF | 4.351741 |
| TRAIN_O1 | COMPOSE | COMPOSE | HANDOFF | 1.311227 |
| TRAIN_O2 | COMPOSE | COMPOSE | HANDOFF | 1.313615 |
| TRAIN_O3 | COMPOSE | COMPOSE | HANDOFF | 1.307838 |
| TRAIN_R1 | HANDOFF | HANDOFF | None | — |
| TRAIN_R2 | HANDOFF | HANDOFF | None | — |
| TRAIN_R3 | HANDOFF | HANDOFF | None | — |
| COORD_R1 | HANDOFF | HANDOFF | COMPOSE | 0.451689 |
| COORD_R2 | HANDOFF | HANDOFF | COMPOSE | 0.451224 |
| COORD_R3 | HANDOFF | HANDOFF | COMPOSE | 0.456480 |

SUPPORTED：出程HANDOFF/PATTERN的当前有效坐标相同，未来又恢复共同COMPOSE，实际轨迹相同；标签变化不等于真实动作或收益变化。当前菜单的短视不自动证明Learning必要，必须比较训练时冻结的透明固定动作/阶段规则。

CONFIRMED：开发表中的DEV_O1为整策略承诺，其余TRAIN/COORD为当前一次后接共同COMPOSE，不能把两种尾部标签混合训练。原B上游RETURN没有合格主菜单时E为空。

| 冻结状态 | 0.5s | 1s | Critic | 完整合格参照 | Critic相对1s少JF |
| --- | --- | --- | --- | --- | --- |
| TEST_O1 | COMPOSE | COMPOSE | PATTERN | HANDOFF | 1.312819 |
| TEST_O2 | COMPOSE | COMPOSE | HANDOFF | HANDOFF | 1.307640 |
| TEST_R1 | HANDOFF | HANDOFF | COMPOSE | COMPOSE | 0.450490 |
| TEST_R2 | HANDOFF | HANDOFF | COMPOSE | COMPOSE | 0.449027 |
