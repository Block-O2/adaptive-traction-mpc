# B/H150执行与评价审计

审计对象为只读历史包 `ihear_overnight_control_learning_transition_v1`，并追溯 `ihear_model_terminal_compensation_v1` 的 H150 冻结选择。以下行号对应前者副本；新包仅重定位路径。未启动任何物理实验。

## 可复用执行链

`code/study_common.py:51–70` 是完整执行入口：`SACExpertEnv`、`runtime_coordination_residual_v2.run_executed_case`、`qualification_arm='commissioning_only'`、`SCIENTIFIC_SIMULATION`、`scientific_host_delay_s=0`、独立空 session context、30 s task timeout、既有 recovery/rigid table reference 配置。`control/campaign_v2.py:38` 的 `Campaign.control` 保留 B 与 H150 两臂逻辑；新 `cross_runner.py` 继承该控制方法，而只重写患者队列、失败保留、配对与日志。

`source/.../scripts/single_human_sac_expert_v1/sac_env.py:147–150` 原案例入口是 `configs/high_rom_v1/high_rom_nominal_sync_120_v1.json`。**当前冻结案例并非低 ROM 示例**：名义起点 [5°,10°]，目标 [120°,120°]，Human hard ROM [0°,125°]。原 B/H150 的在线终末目标可落在原任务允许的终末盒中；不得将实际发出参考强制改成名义起点。D02 的实际最终参考是 [5.5°,9.5°]，具体患者仍从 trace 读取。

## 冻结动作

`provenance/H150__NEW_FROZEN_SELECTION.json` 中 H150 candidate hash 为 `255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931`。`FROZEN_18D.json` 保存全部 18 个参数及 RETURN 历史 plateau，不能只复制 18 个数而丢掉 residual graph。

| 层 | 冻结定义 | 实现证据 |
| --- | --- | --- |
| B | 原 planner、在线测量/模型、反馈、allocator、证书、admission、fallback | `control/base_campaign.py:50–69`；B 不进入 richer planner |
| 18D | `quality_NATIVE_SCALAR_18_063`，原 18D 数值；RETURN 既有 plateau −0.020、−0.022 | `FROZEN_18D.json`；`base_campaign.py:50–63` |
| T | 最终 OUTBOUND suffix duration ×1.5；目标与 pass velocity 不改 | `code/terminal_repair.py:11–37` |
| D | RETURN slot 2、3 的目标增量均为 hip +0.3°、knee −0.3°；duration、外端速度不改 | `control/round_planner.py:18–37` |
| ER | RETURN slot 1 ×1.10；slot 4 ×1.20 | `control/early_return_planner.py:7–31` |
| H150 | RETURN slot 5 hip duration ×1.5；要求 knee reference 已恒定、终点保留 | `control/terminal_planner.py:8–31` |

slot 使用原 `count` 序列，不能自行换成一基索引。所有 duration 使用 `ceil(duration*factor/.005 - 1e-10)*.005`；T 从原 scheduler 的 5 ms reference period 量化。所有变更都重新调用原 `_evaluate` 和 fixed-duration certificate，若不可行可保留原动作；这意味着“候选配置 H150”并不保证“完整 H150 已执行”。新分析逐条核验 T/D/ER/H150 的 ACCEPTED、selected_plan_activated、冻结倍率/偏移和正 native receipt steps。

## P0 的模型语义与冷启动

`runtime_coordination_residual_v2.py:240–336` 接受分离的 `physical_human/physical_geometry` 和 `control_human`。`fresh_qualification_v1/scenario.py:hidden_plant` 是现有 generation-side truth 构造入口，不进入控制器 action selection。

原 cold initialization 明确包含 `plant.reset` 与 t=0 qpos/qvel 初始装配（`runtime...:258–280`）。这不是复用后续 native state，也不是伪造 task 入口：每患者必须重新从这一步、原支持载荷/机器人 IK、完整物理 commissioning 和合法 prefix 出发。原初始化将同一名义 cuff-relative support preload 放在患者实际 cuff pose，机器人跟随 IK 匹配；这是装配初始化，不改变 robot dynamics、接触机制或控制权限。

**P0 冻结的是原控制算法/先验/参数和获知机制，不是每位患者完全相同的已估计数值。** 原 `commissioning_only` 在 `runtime...:2344` 从该患者真实获得的合法传感记录拟合 geometry、beta、residual；随后 B/H150 同父状态共享相同 commissioned belief。这是原 B 的一部分，必须保留且明示。若将 qualification_arm 改成 fixed_population，便更换了原 B 方法。P1 应是另行显式提供合法已知患者模型参数的次级协议，本轮 P0 不把物理 truth 注入 model。

## 配对、归属和失败保留

`deps/fork_core.py:state_manifest` 对 MuJoCo `mjSTATE_INTEGRATION`、MjModel 数组、runtime、估计器、planner、任务、传感历史、RNG、证书与不透明原生句柄作完整审计；`quiesce` 要求 scientific session 且只剩单线程。`code/matched_harness.py:53–104` 实施 `os.fork`、串行 wait、子进程恢复 hash、父进程不变性检查。不同患者必须独立冷进程，不能共用 fork 父状态。

新配对除 full_hash 外还检查 patient_id、case SHA256、XML SHA256；同患者 B/H150 对应同一 commissioning 和 prefix。force gain 只在两臂完整 TASK、积分闭合、身份相同下给出。若 B 本身 task/safety/causal 不合格，保留完整描述性 gain，但不得将其作为合格 motion 参照。

旧 orchestration 的 stop-on-first-failure 不适合本任务：`matched_harness.py:103–104` 在子进程失败或物理不合格后抛出；`campaign_v2.py:94` 在 B 安全/任务/归属失败后停止剩余臂；`analyze_matched.py:73` 在已保存测量结果后以 promotion assert 停止。新 runner 只允许捕获已 join 且父状态未变的 CHILD_FAILED / NATIVE_PHYSICAL_FAILURE；不关闭任何物理安全门。新分析仅在内存中移除 `measure` 最后一个 promotion assert，完整记录删除文本和前后函数 SHA256。所有算术、原安全条件和 motion 阈值保留。部分运行保存已观察积分但 `J_F_N_s=null`，不冒充完整任务收益。

## 四条资格轴

旧 `campaign_r2.metric:24` 将 `task_valid` 赋为 `physical_audit.pass_`，这是 task/safety/execution 混合结论。因此新分析从原 evaluator 的条件分拆，仍原样保存总门：

1. task：summary COMPLETE、phase transition order、timeouts、真实 goal dwell 与 return。
2. absolute safety：force、moment、Human velocity/acceleration、robot velocity/torque、Human ROM、shank contact、true/session/sleeve clearance、native/trace finite。
3. causal/execution：原 scientific request version/source age 门、online 与 activation certificate、reference C2、case hash、每 native step 的 receipt/torque/数量归属，及 H150 实际 intervention。
4. motion relative：只给相同患者的 H150 与合格 B 比较；B 自身输出 `NOT_APPLICABLE_SELF_REFERENCE`。B 的完整合格性来自前三条及完整积分，绝不由 B/B 运动比值决定。

原科学时间门 `scripts/high_rom_v1/evaluate_execution_mode.py:74–115` 验证 request source/receipt/activation 的 episode、phase、model、physics-step 版本以及科学 source age <100 ms；host catchup 不得推进物理。SCIENTIFIC_SIMULATION 不证明 host realtime 合格；原 host 年龄和 realtime fail 作为独立 profiling 保留。

## 算术与阈值

`code/analyze_matched.py:11–18` 使用原 5 ms TASK 左积分，并在真实 phase 边界裁切每个 interval；三个 phase 积分与 full J_F/moment 必须闭合 <1e−8。`analyze_matched.py:55–72` 从 0.25 ms native qvel 求 gradient acceleration/jerk，保留端点；SG5/21 仅敏感性。

`MOTION_ACCEPTANCE_PROTOCOL.json` 与 `code/explore_common.py:57–79`：velocity/acceleration max、p95、RMS ≤1.10×B；jerk p95/RMS ≤1.10×B；excursion 差 ≤0.5°；travel 比 [0.95,1.05]；endpoint/phase boundary 差 ≤0.5°；full/phase duration 差 ≤0.1 s；moment integral ≤1.25×B；force/moment peak ≤1.05×B；tracking RMS ≤B+0.5°。phase shape 仅诊断，不新增资格门。新分析增加真实 velocity TV、acceleration variation、force/moment RMS、实际发出终末参考定义的 overshoot/undershoot，但不把新增诊断变成 post-hoc 门。

## 已执行的无物理复核

`audit_execution/test_offline_adapter.py` 在独立临时 fixture 内只读 D02 历史原始 trace/native/receipt，运行新 adapter 及旧 `control/independent_recompute.measure`：B J_F=1431.1757302086514 N·s，H150=1397.7276753090318 N·s，gain=2.33710327765%；原数值、运动、ownership/source hash 闭合。还验证 unsafe B 不产生合格相对 motion、patient hash 不匹配不产生 gain、partial 不产生 full J_F、scientific version/age FAIL 不被 native ownership PASS 掩盖。详细审计见 `OFFLINE_ADAPTER_CHECK.json`。这些是历史算术复核，不是新患者物理证据。
