# 冻结 B/H150 跨患者执行合同

本合同只适用于工作包 A 的 P0：**W1 合法 prefix 条件下的跨患者冻结算法迁移**。证据类别为 `PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION`；这里不新增名为 SCIENTIFIC_LEVEL1 的证据等级，不声称 host realtime、硬件或临床合格。

## 原始来源与身份

历史规范源：`/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1`。逐文件原始 SHA256 见同目录 `FROZEN_SOURCE_CHAIN_HASHES.json`，由 canonical WSL 文件只读计算；新隔离副本因路径重定位而变化的 SHA256 由包级 `EXECUTION_CODE_MANIFEST.json` 和 `audit/PATH_REBASE.json` 记录。

| 冻结对象 | SHA256 / candidate hash |
| --- | --- |
| B candidate | `5908d9453a12b2aae83c88d46d4926979b223ff4732a3984eda43ec3ca9af60b` |
| H150 candidate | `255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931` |
| D01R_PLAN.json | `aba229fec433f1900dc6a419a0f3e52edb1f9a019368fac082754b50b0bcdbb5` |
| FROZEN_18D.json | `1d04594ff2ff088b83c94e424c6bd2cd02afa6f94330ffae2beb5727e545fc67` |
| ACTION_SET.json | `6f17b17e37160316323e8627638d5ed2e704a72addae794abcbb5ffcd80811be` |
| MOTION_ACCEPTANCE_PROTOCOL.json | `0f41463cab96b71ea39cc06f9fe86f432de07efe307bd486bc1c4df6cc196ece` |
| control/campaign_v2.py | `d240993a5137c00d2336a80765165fda705553847282493b6b55a917b33c5d72` |
| control/base_campaign.py | `98cfe2df845a41dac272aaa71cc0d7ffffd84c0ec9b59ed97c1ae24270b64ad6` |
| code/study_common.py | `1f7c761cfda788778c18d0ee2d24e3d41ea4f43b4ca888b1334f52edcd67daa0` |
| 原 runtime_coordination_residual_v2.py | `74d0f6b97b35671111bdd86bb4dfff845c90f2a12ee1cd9518de9445de99de79` |
| 原 high_rom_nominal_sync_120_v1.json | `d9f4d636b98db5792cf4b50915f4509bf2274c1c80764d6d8629bf22e3ae9b96` |

执行链为 `cross_runner.PatientPair → campaign_v2.Campaign.control → base_campaign.Qualification / matched_harness.MatchedInterface → study_common.run → runtime_coordination_residual_v2.run_executed_case`。新 runner 只改变隔离患者供给、attempt accounting、失败保留和日志。正式控制器、代价、目标、ROM、allocator、torque/force/moment 限制、证书、admission、fallback 均不得更改。

## B 与 H150 的实际定义

B 不接收 18D/T/D/ER/H150 intent。H150 = B 执行体系 + 完整 FROZEN_18D（包含历史 RETURN plateau，非单纯 18 数字向量）+ T + D + ER + RETURN5 hip timing。

| 部件 | 冻结操作 | 原实现 |
| --- | --- | --- |
| T | 最终 OUTBOUND suffix duration ×1.5；目标、端速度不变 | `code/terminal_repair.py:11–37` |
| D | RETURN slots 2/3 各 `[+0.3°,−0.3°]`；duration/外端速度不变 | `control/round_planner.py:18–37` |
| ER | RETURN slot1 duration ×1.10、slot4 ×1.20 | `control/early_return_planner.py:7–31` |
| H150 | RETURN slot5 hip duration ×1.5；knee reference 必须已恒定且终点不变 | `control/terminal_planner.py:8–31` |

slot 采用原内部 count 语义。量化为 `ceil(d/.005 − 1e−10)*.005`；原 fresh fixed-duration certificate 及 `_evaluate` 必须通过。仅配置了候选不足以声明执行了 H150：必须核实每条 intent ACCEPTED、activated、实际正 native receipt steps、原参数身份。拒绝后原策略的回退必须如实计为相应 execution 未完成，不能改名为完整 H150 PASS。

## W1 prefix、任务与 P00

所有患者预注册使用 D01R/W1 seed `2026102001`，相同 `prefix={OUTBOUND:[[0.08,0.04,0.03]], RETURN:[[0.04,0.02,0.03]]}`，fork_after_prefix=1。每患者独立冷启动、完整物理 commissioning，再由第一 OUTBOUND prefix 后同一 live 父状态串行 fork B/H150。完整 J_F 包含各臂共享的早期 TASK prefix，不能只积分 suffix。

这里的 B 是“原 B 控制体系在冻结 W1 prefix 合同下执行”的匹配对照，**不是零 prefix 的原始开发条件 B**。非零 RETURN prefix 会在两臂后续各自状态执行相同 intent；两臂此时的物理状态已可不同，不得称 RETURN 入口 matched-state 因果消融。跨患者结论条件于这个冻结 prefix，不能外推所有合法初态/prefix。

P00 使用原 physical/task case 的原值（反序列化内容完全一致）、seed/prefix/算法，以新的冷进程执行。应与历史 `D01R_B`、`D01R_H150` 的逐 trace、native、receipt 科学字段复现比较，而不是要求等于原始开发无该 prefix 的 J_F。历史 W1 参考 B=1436.456498145 N·s、H150=1402.643211486 N·s。当前结果必须由新运行产生；历史值仅是复现参照。

原任务名义起点 `[5°,10°]`，OUTBOUND 目标 `[120°,120°]`，完整 OUTBOUND/HOLD/RETURN。原 high-ROM hard bounds `[0°,125°]` 与所有任务限值保留。原允许终末盒内的真实发出参考可能不同于名义起点；overshoot/undershoot同时报告“相对实际终末参考”和“相对名义目标”，并从 trace 读取最终 reference，不能假定固定 [4.5°,9.5°] 或 [5.5°,9.5°]。

## P0 模型合同与 truth firewall

P0 保持固定 algorithm/prior/config 和原 `qualification_arm='commissioning_only'`。原体系在各患者 commissioning 的合法 sensor 数据上估计 geometry/beta/residual，B/H150 在 fork 时共享这份 belief。它是“未直接获知新患者真实参数的原算法迁移”，并非每个患者的已估计模型数值都相同。若改成 fixed_population 就改变了原 B 方法，不属于本轮冻结基线。

每个患者只通过原 generation-side `hidden_plant(qualification_case)` 供给物理 Human。`control_human` 必须等于原 high-ROM deployable_prior，不能以 patient truth 替代。新的 `audited_initialize` 仅在 generation/evaluation 侧验证实际 physical_human dataclass 等于 static case、control prior 完全不变；审计字段不传给策略。

原 t=0 `plant.reset` 与机械装配 qpos/qvel 赋值是合法 cold initialization。之后任何 Human state 必须经原 native physics 形成；禁止从别患者复制 native state、跨 patient fork 或写入 task 初态。原 cuff-relative support preload 与 robot IK 装配允许跟随患者几何，但不得改变机器人动力学/权限、接口刚度或接触机制。

P1 本轮仅协议，不可把 P0 原 commissioning estimator 重新命名成 oracle patient matching。

## 资格与失败处理

所有患者均保留：静态模型失败、commissioning/初始条件失败、B/H150 task、absolute safety、causal/execution、relative motion 失败。B 失败不会抑制同一已合法父状态下 H150 的独立执行。仅当父状态不合法或身份被破坏才不得继续使用该父状态。

原 `task_valid` 曾混合 task、safety 与 execution（`campaign_r2.py:24`），故必须展示原逐项门后分别归类。绝对安全含真实 ROM、force/moment、robot torque/speed、Human speed/acceleration、clearance/contact、finite 等；causal 含原 scientific version/age、current-state/activation certificates、reference C2、case identity 和每 native step 的 receipt/torque/step count。原科学 age <100 ms 与 host wall-age 不是同一指标。

B 自身 relative motion 标记 `NOT_APPLICABLE_SELF_REFERENCE`。B/B excursion差=0或所有比值=1不证明 B 绝对安全。仅合格 B 可作为 H150 的合格 motion 参照；否则保留诊断性原始差值但 motion qualification `NOT_EVALUABLE_INVALID_B`。

H150 complete-qualified 要求：匹配 patient/case/XML/full-state 身份、完整任务与积分、两臂合格基准前提、H150 absolute task/execution、安全及原 motion 门、所有冻结 intent 实际执行。所有原运动阈值原封不动：burden1.10、excursion0.5°、travel±5%、endpoint/phase boundary0.5°、full/phase duration0.1 s、moment integral1.25、force/moment peak1.05、tracking+B0.5°。

只有两臂完整任务、积分有效且同患者身份成立时计算 `(J_B−J_H)/J_B`。安全不合格但完整的 B 允许描述性 gain；必须单独标注该 gain 不具合格控制/运动解释性。任何 partial 的 full J_F 和 gain 均为 null，已观察的 prefix 积分另列，不删除失败。

力使用原 5 ms 左积分；真实运动来自 0.25 ms native Human。独立复核使用原 `control/independent_recompute.measure`。原始 trace、native、receipt、case/source/候选 hash、START/END 必须闭合。所有结论止于 `PHYSICAL_LEVEL1` 仿真，最终 STOP，不训练、不搜索、不进入工作包 B。
