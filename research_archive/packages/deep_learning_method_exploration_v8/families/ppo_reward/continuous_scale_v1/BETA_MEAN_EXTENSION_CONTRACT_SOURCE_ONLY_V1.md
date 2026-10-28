# 连续 Beta 冻结 mean 部署扩展

只交源码/未来 inventory schema，尚无实际 Beta model inventory、部署授权或新 root composer。未 import/forward/init/restore/sample/fit/physics，未修改任何旧 Beta、A3、root 文件。

入口 `predict_before_B(P, config, study)` 供未来 root composerV4 调用。config 使用独立 `beta_mean_extension`；输出 `v8.beta.continuous_mean_and_grid_extras_before_B.v1`，含 `continuous_decisions`、`fixed_axis_controls` 和完整连续 recipe catalog。不能塞入现有只接受五个 core hash 的 parallel adapter。

所有选择在原 cold OUTBOUND slot0、实际 `study.metrics` 为空时完成。复用冻结 A3 `_actual_live_proof`，逐项读取原 job manifest、saved prefork payload、当前已加载模块路径和 bound callback code filename，核验 capture/runtime/observer/observation_contract/history_guard/runtime_loader/callback 七种源角色。随后仅调用 A3 causal API 的原 WRENCH39 子集/QA 准备并按名称投影合法25D；不调用任何 A3 预测。旧77D无效标记保留，case标签与结果不入特征。

未来 main 必须冻结真正存在的十二 checkpoint：parent/first completed/last completed ×四臂。实际完整 generation TRANSACTION inventory 从0到run tip连续，含取消代；first/last只取实际 READY_ALL_FOUR_UPDATED 的最早/最晚，不能best或把取消代当训练更新。若仅一次实际完成，first=last允许，依然分别执行并计费12次推理；没有完成代则拒绝，不能制造模型。每模型只从 checkpoint['policy'] 深拷贝，直接调用原 `beta_policy.deploy_mean`；不构造/restore BetaArm，不采样、不读或延长旧training clock。所有规范化必须等于原冻结G0 RF_RAW规范化。

正常一次入口预计12次deploy_mean entry/completed与12个实际policy.forward计数增量、12份logical policy copy；A3七角色proof一次、scoped context39准备一次、25投影一次。fixed λ=0/.25/.5/.75/1 五次纯map，部署mean内部另外十二次同映射。restore/init/RNG/梯度/fit/physics均0。原输入/源身份失败在推理前拒绝；数值性predict拒绝保留异常并明确请求原B fallback，不假造连续配方或授予资格。其他异常附 `beta_mean_extension_consumed_work` 保留已付费调用计数。

固定 λ 网格是同轴传统一维强对照。parent四mean必须实际为.5，可与fixed .5按实际完整recipe SHA别名；first/last若实际同配方也可在root评价计划中共享同一物理执行。root按连续完整recipe SHA合并评价时，不称独立重复或节省attempt；训练真实rollout永不去重。原B是轴外安全锚；λ0仍为T底层terminal-repair/保留原intent，不是B或zero-noop。

λ1必须在每个未来新job另与原EARLY_H150各自实际付费START/END，保留重复关联并做逐raw及原scorer exact门。输出单列 `required_new_job_paid_exact_raw_repeat_gate`，这两次门不能被通用hash合并消去。已知heavy Gate1的闭合等效证据不替代新job的该门；源码不静态断言物理等效。

root负责composerV4、实际inventory/所有model文件SHA、原guard任务scorer和完整资格、真实物理dispatch及回执闭包。本候选不写磁盘、不派发、不据结果重新选择。主审后才可真实调用；未来部署授权独立于已过期training授权，global15:25:40不重置。
