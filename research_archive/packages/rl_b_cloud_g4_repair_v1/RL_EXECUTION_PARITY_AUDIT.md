# 原执行链独立回归

PARITY_PASS=PASS（已观察输入）；EXECUTION_PASS=FAIL（完整冻结时长回归未通过）。科学仿真执行不代表host实时资格，host realtime为NOT_EVALUABLE。

`parity_audit.py`逐项读取历史与本轮完整raw。slow79480、maximal116320、random120860个native状态，共316660行；时间、native Human q/dq、实际command torque、contact均最大差0。trace的reference q/dq/ddq、estimated/true state、cuff force/moment和applied torque也最大差0；完整command_receipts的apply/native count、physics边界、source timestamp与torque完全一致。三个输出见audit/PARITY_*.json，容差1e-12，实测差0。

全部9个episode还独立核对唯一native所有权、receipt扭矩、source age、100ms同epoch/model admission、40ms bridge、current-state certificate、executor退出及真实Human运动。原ROM0–125°，dq45/75°/s，ddq300/600°/s²（native、5ms、20ms），force200N、moment60Nm、torque、clearance、contact均通过已观察case；无MuJoCo warning。TEST_ONLY安全事件来自合成monitor字段，真实plant并未违反这些物理限值。

414个封存source载荷中412个逐字节不变，只改runtime统计和reference-safe deadline优先级两个文件。Human/robot/cuff资产、模型参数、native0.25ms、controller5ms、Planner/certificate、current-state admission、receipt governor、40ms bridge、100ms lifecycle、source age、causal receipt/native ownership及安全阈值均未修改。各code hash与diff见CODE_CHANGE_MANIFEST.json和audit/ALL_CODE_CHANGES.patch。

新隔离版本rl_b_native_event_g4_repair_v1已登记，旧资格没有自动沿用；RL action仍是每次native planner event的两个最大progress fraction。没有变成50ms动作接口，没有B/H150模仿权重。deadline过期结果收紧，正常合法输入物理含义保持。物理重复回归用于修复验证，不能冒充独立held-out稳健性研究。

完整任务maximal两次19.030s；random复现20.165s，仍不满足19.030±0.050s封存标准，因此不给EXECUTION_PASS。核心raw审计通过不覆盖这项失败。
