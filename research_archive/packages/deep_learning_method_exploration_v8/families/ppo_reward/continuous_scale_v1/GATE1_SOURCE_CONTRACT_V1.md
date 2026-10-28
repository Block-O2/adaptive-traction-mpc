# 连续轴Gate1：source-only候选

主Agent授权本轮只准备源码、冻结axis和合同；本文件不授权物理派发。实际config与source薄wrapper由主Agent审查创建。本候选不修改v8_worker_v1或原guard/task/scorer。

目标是已经暴露的knownheavy工程条件。一次cold commissioning后，在同一存活完整OUTBOUND/slot0父进程分叉完整任务：B → 原H150 → AXIS_L1 → AXIS_L0 → AXIS_L05。原H150动作是`{"family":"H150","legacy":[0,0]}`，没有先施加old18d override，也没有推迟激活；λ1才是轴映射的old18d动作。每个child必须有独立真实START/END和新native步数；λ1虽应与H150逐raw一致，仍是独立付费物理任务。父prefix只由原worker最终parent闭包计一次，不能乘child数，也不能把多个selector当多次独立rollout。

B和H150必须原完整合格。λ1提交worker原`repeat_of=H150`，使用base_campaign.compare_raw逐字段完全比较：所有trace字段、native body/contact/command torque及科学receipt/reference/source/ownership字段；原比较器只排除wall profiling。worker先检查并保存`audit/<group>_AXIS_L1_REPEAT_GATE.json`；生成器恢复后检查该门确为本组H150与AXIS_L1且PASS，并要求λ1完整原合格，然后才允许λ0、λ.5。不放宽容差，不将数值近似称等效。

λ0保留原T的OUTBOUND terminal repair和RETURN原生PWL residual plateau，零posture/unit duration intent仍走原内部断言与证书；因此λ0不是原B或zero-noop。5ms量化与guard切换仍可能使收益不连续；box合法不证明可执行或motion资格。λ0或λ.5若完整但不合格，分别保存原motion失败、JF与JM，不作合格收益；普通受保护任务失败/原worker可回收工程失败可保存后进入下一预登记点，任何真实全局hard安全违规沿原worker立即停，生成器不捕获后继续。

原RESULT在`attempts/`，原MEASURED与EXECUTED_RESIDUAL_RECEIPTS在`runtime/reports/`，原raw/summary在`runtime/source/results/`，原execution_binding在`attempts/`。生成器保存这些实际文件SHA与完整原learning_records/decisions/lineage，保留selected_plan_activated、activation outcome、rejection、fallback、证书和实际command receipt。原lineage的非零协调残差计数不单独证明整条18D或posture/timing执行，必须连同完整execution_screen/activation和receipt审查。失败缺失的证据明确留null，不造receipt；部分JF不排名。

每条`actual_new_native_steps`来自原worker RESULT，单独列出；整组最后还需主Agent核对ATTEMPTS每个START/END、独立child归属、最终parent DONE、parent_checks未变和实际prefix步数，生成器不能提前宣布整组物理闭包。

建议局部窗口30分钟、单attempt沿RUN_PLAN原300秒或主Agent现有更严窗口；绝对硬截止2026-10-27T15:25:40Z不能重置。实际资源/窗口在主Agentconfig冻结后才生效；没有自动重试或额外episode。0学习器初始化/forward/update，0reward fitting，结果只支持映射/可执行性与已暴露条件收益空间，不支持独立泛化或真实on-policy学习成功。

## root config接口

`algorithm`为主Agent创建的`source/<name>.py`薄wrapper，其`sequence(study, config)`转发本候选。原worker自动SHA绑定该wrapper；config.frozen_artifacts还必须显式包含本候选、axis_mapping.py、FROZEN_AXIS_GATE1_V1.json、本合同、axis全部source_files_sha256，以及source/v8_worker_v1.py、source/acl2_shared.py、runtime/code/analyze_matched.py、stream_runtime_evidence.py。原worker其余依赖仍由原SOURCE_MANIFEST冻结。

config保留原B/H150完整候选，必须与ACTION_SET逐对象相等。fork_phase=OUTBOUND，fork_slot=0。新增`continuous_axis_gate1`字段：

```json
{
  "schema": "v8.continuous_axis_gate1_job.v1",
  "exposed_engineering_condition": "knownheavy",
  "independent_generalization_test": false,
  "axis_path": "families/ppo_reward/continuous_scale_v1/FROZEN_AXIS_GATE1_V1.json",
  "axis_file_sha256": "主Agent核对GATE1_SOURCE_MANIFEST_V1.json",
  "axis_object_sha256": "主Agent核对GATE1_SOURCE_MANIFEST_V1.json",
  "approved_contract_path": "families/ppo_reward/continuous_scale_v1/GATE1_SOURCE_CONTRACT_V1.md",
  "approved_contract_sha256": "主Agent核对GATE1_SOURCE_MANIFEST_V1.json",
  "output_directory": "families/ppo_reward/continuous_scale_v1/gate1_runs/<独立新group>"
}
```

`exposed_engineering_condition`是协议标签；实际condition/case_path及其物理human/geometry来源仍由主Agent绑定已有knownheavy参数。不得仅把未绑定的新条件改名knownheavy。生成器本轮只做AST/source审查，不导入worker、不创建环境、不物理执行。
