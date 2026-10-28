# B真实on-policy：V2修复与主runner接线

状态：CODE_ONLY_NOT_RUN。旧`onpolicy_update_driver.py`与正在使用的`categorical_policy.py`不修改。新`onpolicy_update_driver_v2.py`在constructor/propose/finish/snapshot/restore校验每个实际contract的digest、声明action_sha及独立冻结五菜单一致；propose再核采样返回的实际contract。硬安全True在任何engineering censor之前检查。最终source manifest必须含冻结categorical依赖。

## 主Agent需确认的schema（派发前）

1. **原物理身份/哈希范围**：`runtime/ATTEMPTS.jsonl`的START/END逐记录原字节SHA还是canonical记录SHA；两者需明确，不能称整个持续追加文件的SHA等于单条记录SHA。原source确认字段为event/id/unix/pid/start_ticks；START含snapshot_hash/group等，END含joined/returncode/parent_hash_equal。这些PID是fork父记录，不应猜成子物理owner PID。若要求子PID/start_ticks，需主runner提供实际保存来源。
2. **完整结果与protected failure分支**：`Study.last_row`原字段确认为id/action/complete/qualified/JF/JM/error/actual_new_native_steps/axes/metrics_path，以及失败时可能的`protected_task_failure={abort_reason,hard_safety_conditions,partial_JF_unranked}`。缺字段不能补False；请确认所有正常保护失败、工程失败与硬违规的可区分来源。
3. **原ownership**：完整任务的`MEASURED.execution_lineage_path`指向原`*_EXECUTED_RESIDUAL_RECEIPTS.json`，其status与native join由原analyzer产生。不能伪造该legacy文件。请确认partial时是否存在真实同口径ownership证明及其字段；缺失则工程censor，不能默认为PASS。
4. **实际applied stream**：原`runtime_artifacts.json.gz`存在command_receipts数组（receipt_index/applied/native_steps/start_physics_s/end_physics_s/q_ref_rad/dq_ref_rad_s/command_torque_nm等）。请选择并登记“整个真实artifact容器SHA”或“逐条原receipt的canonical stream SHA”及解析来源；不把proposal行当applied receipt。部分plan_request_id/reference_version可null，不能null相等当直接ID绑定。
5. **硬安全判定**：请确认原common safety条件集合、完整与partial读取路径、缺失值语义。adapter必须独立返回true_hard_safety_violation三值（True/False/未知），True永远先停；不能因engineer不全吞掉True。
6. **context与baseline绑定**：主协议给两个logical development_context_id→case path/SHA/真实plant的评价路由；B descriptor与每sample receipt均绑定logical ID及精确commissioned25输入digest。route ID不进actor。B必须原完整合格；B JF/JM用完成后的真实完整积分，不能借新case未知结果调整policy/normalization。

本模块不猜这些映射。主Agent须提供并冻结一个纯证据adapter模块，声明`ADAPTER_SCHEMA='v8.reviewed_onpolicy_receipt_adapter.v1'`，实现以下函数：

```python
build_baseline_receipt(*, package, config, context25, logical_context_id, row) -> dict
build_onpolicy_receipt(*, package, config, context25, logical_context_id, proposal, row) -> dict
```

adapter只读取该真实attempt的原保存证据，不construct env/step/重新scorer、不补造receipt或忽略失败。新的sidecar descriptor是带来源的映射，不改变原raw/scorer。返回值最小字段：

|对象|必须返回|
|---|---|
|B baseline|complete=True、original_qualified=True、JF_N_s/JM_Nm_s、result_source_sha256、context_group_evaluation_only、causal_features_sha256|
|sample physical receipt|attempt_id、arm_id、proposal_identity_sha256、selected_full_recipe_sha256、context_group_evaluation_only、causal_features_sha256；genuine_new_physical_attempt=True、historical_or_cached_outcome=False；attempt_start_sha256/attempt_end_sha256/result_source_sha256/native_ownership_sha256/applied_reference_receipt_stream_sha256；actual_new_native_steps；engineering_complete、ownership_and_causality_audit_pass、complete、original_qualified、protected_task_failure、true_hard_safety_violation；合格完整时JF_N_s/JM_Nm_s|

各SHA附实际路径与hash_scope，proposal/arm/context字段来自绑定的预采样记录，资格/安全/动作字段来自原执行证据。零new-native或缺证据样本保留为censor，不冒充完整新物理rollout。普通guard保护失败若有完整owner/原安全证明仍可作为−1反馈。

## Sequence配置与加载

子Agent文件仅在families目录。baseworker当前`algorithm`导入和source manifest均预期`source/<algorithm>.py`；主Agent需建一层薄wrapper，将family路径加入sys.path并`from onpolicy_sequence_v1 import sequence`。wrapper与下面所有依赖放入config.frozen_artifacts：family sequence、driver_v2、categorical_policy、critic value_api、adapter、五recipe菜单、合同与四个**直接snapshot JSON**。不能只hash wrapper而漏实际family依赖。

`config.onpolicy_sampling`字段：

```json
{
  "schema": "v8.onpolicy_sampling_job.v1",
  "development_context_id": "<两个预冻结logical开发ID之一>",
  "approved_contract_path": "<合同相对路径>",
  "approved_contract_sha256": "<SHA>",
  "menu_path": "<五recipe菜单JSON>", "menu_sha256": "<SHA>",
  "receipt_adapter_path": "<已审adapter.py>", "receipt_adapter_sha256": "<SHA>",
  "arm_inputs": [
    {"arm_id":"RF_RAW", "snapshot_path":"<direct V2 snapshot>", "snapshot_sha256":"<SHA>"},
    {"arm_id":"PPO_RAW", "snapshot_path":"<direct V2 snapshot>", "snapshot_sha256":"<SHA>"},
    {"arm_id":"RF_SCALED", "snapshot_path":"<direct V2 snapshot>", "snapshot_sha256":"<SHA>"},
    {"arm_id":"PPO_SCALED", "snapshot_path":"<direct V2 snapshot>", "snapshot_sha256":"<SHA>"}
  ],
  "output_directory": "families/ppo_reward/onpolicy_runs/<unique cycle>/<unique job>"
}
```

菜单schema沿`ACTION_MENU.json`，但action_names严格为`[B,LATE_H150,EARLY_H150,LATE_PHASE,EARLY_PHASE]`且五个完整recipe unique。第一批状态由BC3→5 lift初始化，再构造四`OnPolicyArm`；constructor新增frozen_menu_sha256、categorical_dependency_sha256，local_stop_unix预先设约2h且≤全局截止，不在恢复时重置。

每job先真实B fullqual；随后四臂各两个当前policy随机样本，八个不同attempt ID逐次真实START/END，即使recipe相同也不共享。每次proposal及RNG在physics前落盘，完成后将adapter真实receipt附到对应pending。该job**从不调用finish_batch/update**，只写`PENDING_CHECKPOINTS.json`。第二case加载前一case的四个pending snapshot，补齐每臂两case×2条；根runner等待两个WORKER_DONE及所有parent/child账闭合后才准更新。

正常跨case恢复受支持。中断同case若有未绑定物理结果的旧proposal，sequence明确拒绝自动重跑；主Agent先查原START/END/raw补真实receipt或整组censor，不能创造替代好sample。

## 四臂事务

根runner先对四臂调用`preflight_batch_metadata()`，零forward/update检查硬安全、完整case数量、actual recipe、proposal与receipt身份。任一engineering censor，四臂全部`cancel_pending_batch(group_transaction_id, reason)`，保留已消耗物理、已推进RNG与seen ID，不回滚预算；硬安全True仍拒绝censor。

全部通过后根runner复制四对象，再调用各copy.finish_batch；任何异常则全部copy不提交并登记已实际发生的模型计算。全部成功后用一个generation manifest原子提交四checkpoint，early/endpoint使用同一对齐generation。主runner另独立核对source、deadline、四臂训练量、原物理账与RNG；单arm方法不擅自授予四臂事务完成。
