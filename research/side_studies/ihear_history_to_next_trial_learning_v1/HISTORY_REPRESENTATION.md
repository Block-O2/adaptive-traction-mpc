# 因果历史表示 v1

History 是已完成的上一轮真实运动的数据，不是下一次候选 rollout 的结果缓存。保存 `learning/*_RAW_HISTORY.json` 与 `*_HISTORY.json` 两层；每个 decision 绑定 raw、compact 和方法身份哈希。只有 complete history 可训练完整成本模型，失败历史保留但不假装拥有完整标签。

在线 allowlist：commissioning 的 belief/value-state record，观察器估计 q/dq，签发 reference q/dq/ddq，测得 cuff force/moment，phase、phase elapsed、reference progress，request/sample/source age，完整执行结束标志，已发生的 proposed action 与 applied receipt。完整原 trace/native/summary 仍独立保留；其中 Human native qpos/qvel、真实模型参数与真实导数仅用于离线资格、标签与诊断。

完整序列按实际 5 ms 时间戳左积分；最后 boundary 无后续区间。phase 用实际事件，不按统一墙钟对齐。OUTBOUND/RETURN 分别计算归一化 reference progress，再切 5 个 progress bins。compact 保留逐 phase force/moment 积分、峰值、p90、tracking RMS 和估计运动导数；两个候选修正窗口使用 progress 0.2–0.6 的力加权时间均值与实际-minus-reference knee lag。

估计速度的 acceleration/jerk 由 5 ms 合法历史求导，仅表征观察器输出；原 motion 资格仍由独立 0.25 ms native 真值按冻结公式计算，不能互换。关节 reference/estimated 端点、局部峰值、force 高负担持续时间和每个 applied command 仍可从 raw 复算。

value 模型输入是显式命名的 12 维向量：完整 J_F、moment、去/回程中段平均力、去/回程 knee/hip 平均 lag、hip/knee tracking RMS、去/回程 knee 速度 p95。训练时明确存在状态×动作交互。第一次结果不是未来标签：只有该次实际执行的 A0/B 成本可作为本患者在线更新样本，不能给未执行的相反动作伪造回报。

最初仅能确认负担位置和跟踪滞后。完整 J_F 与其跨患者变化不能单独确定修改方向的因果效果。开发叉分支可以提供动作标签；它们是同父不同动作的昂贵实验，全部归在同一患者 split，不能按 native 步或窗口计作独立样本。

History-disabled 使用相同模型、动作网格和选择规则，history 向量改为训练患者均值，禁止纳入当前患者第一次样本。ILC 的无历史条件为零更新。禁用条件仍可使用原 B 的当前测量与 admission；这里禁用的是上一轮学习信息，不是关闭安全控制器的反馈。
