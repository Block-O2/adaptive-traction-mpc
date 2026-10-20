# Git 同步报告 — 开始 2026-10-20，收尾 2026-10-21（Asia/Shanghai）

原主仓库 `/home/hank/coding/adaptive-traction-mpc-learning`；新独立分支 **codex/local-research-sync-20261020**；origin `git@github.com:Block-O2/adaptive-traction-mpc.git`，SSH 身份 Block-O2。未连接德国服务器。

## 起点与恢复

原 branch `codex/expert-strength-value-adequacy-v1`，HEAD `8bb04662b1578b72c097f546be9e836167e280e8`。GitHub 同名分支 0 ahead/0 behind；相对 main 83 ahead/0 behind，main 原 SHA `2c2140deac8ef91aa69c57af886243f68df485ec`。

初始 staged 332、unstaged tracked 0、untracked 1961。原 index 和完整 staged/unstaged patch、本地 34 引用完整 history bundle 已保存到 Windows `local_research_sync_20261020_work`，bundle verify PASS；未将私有恢复包入 Git。

## 本轮普通提交

| 组 | commit SHA | 文件数 |
|---|---|---|
| main_source | fc3b9ca035b230bfc073c35b4c902e23c075b685 | 179 |
| side_source | 6cf4659c71dcffe2ff48f86a5348f6515baec44d | 47746 |
| rl_b | f469536593793329316396501156d5eb54206392 | 451 |
| main_evidence | bcd6d54ea1bffc6b4628865bfd67e492671de109 | 151 |


本报告及 README/.gitignore/字节保留属性/逐文件清单在最后 maintenance commit。其最终 SHA 用 `git log -1 --format=%H -- docs/repository_sync_2026-10-20/GIT_SYNC_REPORT.md` 获取；本报告无法嵌入自身尚未生成的 SHA。交付最后一次 push 后，精确 HEAD/远端核对保存在本地 FINAL_VERIFICATION.json，并在用户交付中报告。

## 已完成的 GitHub 核验

源码/合同四组已通过普通 push 上传，远端分支存在且 SHA **bcd6d54ea1bffc6b4628865bfd67e492671de109** 与当时本地完全相同。main 仍为 `2c2140deac8ef91aa69c57af886243f68df485ec`。最后维护提交随后作普通 fast-forward push，最终一致性另见交付核验。没有 force、amend、rebase、reset、stash、clean、合并 main 或删除分支。

原有全部 refs 保持不变、起点仍为新 HEAD 祖先，Git fsck connectivity PASS。源码组共有 7913 个新增唯一 blob、94777820 bytes（约 90.39 MiB）；没有超大文件。包含大量路径副本的归档没有把历史证据重复打包成 GB ZIP。

## 验证、科学保护及数据边界

- 48,527 个保存文件的独立 SHA256 检查 PASS；55 项数学/状态/资源/接口单测 PASS，封存 450 文件、189 Python import/static 和 28 vendor 身份、现有环境 pip check PASS。
- 第二遍全量原件检查 **166069 文件、135292204010 bytes，非授权差异 0**；仅原根 README 和 .gitignore 做维护性追加。原科学源码、配置、checkpoint、失败记录、物理模型没有被修改、移动或删除。
- 本地库存共 166,071 普通文件约 126.001 GiB；外部/未入本轮 Git 身份清单共 113,696 文件约 124.556 GiB，全部留原位。D 盘符号链接目标内容没有本轮独立 hash，明确 NOT_HASHED_EXTERNAL，不将链接存在性当作数据字节验证。
- 候选文件安全扫描+逐 index blob 核查未发现真实凭证；一处私钥头命中为扫描规则文字，经人工复核。用户请求、账号目录、环境转储和恢复补丁未上传。
- 未进行 physics、训练、完整 evaluator 重算、native 编译、锁定 Python3.12 CPU 环境再建或服务器对照；均 NOT_RUN/UNVERIFIED。

## 工作区保留的原始 dirty 状态

**工作区不干净，原因是主动保全既有研究证据。** 最终维护文件提交后仍应保留 staged **207**、unstaged tracked **0**、untracked **1756**，共 **1963** 条原有状态；逐项列于 `manifests/remaining_uncommitted.csv`，分组列于 remaining_groups.csv。

| 原目录/组 | 保留文件 |
|---|---|
| .stage_closeout_local_20261014/FINAL_DELIVERY.json | 1 |
| .stage_closeout_local_20261014/initial_cached.patch | 1 |
| .stage_closeout_local_20261014/initial_index.z | 1 |
| .stage_closeout_local_20261014/initial_status.z | 1 |
| .stage_closeout_local_20261014/initial_unstaged.patch | 1 |
| stages/stage5_personalized_motion_learning/docs/action_representation_switch_audit_v1 | 1 |
| stages/stage5_personalized_motion_learning/docs/adaptive_human_online_interface_v1 | 28 |
| stages/stage5_personalized_motion_learning/docs/bc_reproduction_gate_v1 | 25 |
| stages/stage5_personalized_motion_learning/docs/coordination_research_interface_v1 | 46 |
| stages/stage5_personalized_motion_learning/docs/coordination_residual_realization_v2 | 92 |
| stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2 | 215 |
| stages/stage5_personalized_motion_learning/docs/dagger_to_sac_expert_v1 | 109 |
| stages/stage5_personalized_motion_learning/docs/demo_assisted_sac_task_acquisition_v1 | 75 |
| stages/stage5_personalized_motion_learning/docs/expert_strength_value_adequacy_v1 | 336 |
| stages/stage5_personalized_motion_learning/docs/single_human_expert_e_v1 | 725 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_expert_v1 | 116 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_memory_v1 | 56 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_seed1_300k_failure_diagnosis_v1 | 26 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_seed1_continuation_v1 | 3 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_seed1_continuation_v1_attempt2 | 53 |
| stages/stage5_personalized_motion_learning/docs/single_human_sac_seed1_continuation_v2_guardfix_attempt3 | 31 |
| stages/stage5_personalized_motion_learning/scripts/action_representation_switch_audit_v1 | 1 |
| stages/stage5_personalized_motion_learning/scripts/coordination_research_interface_v1 | 5 |
| stages/stage5_personalized_motion_learning/scripts/coordination_residual_realization_v2 | 15 |


其中 `.stage_closeout_local_20261014/` 的 FINAL_DELIVERY、initial_cached.patch、initial_index.z、initial_status.z、initial_unstaged.patch 共五个私有恢复文件留在原位；其余为密集历史结果/报告/CSV/原始请求，以及未选 source_history 版本。没有为清洁状态改变或丢弃任何一项。

## B/H150 与云端

原 scorer 源码与九个合同 SHA 锚点具备本地身份验证；原 analyze_matched/explore_common/independent_recompute 等与 v6 manifest MATCH。D01R B/H150/parent raw 可定位，主要需独立数据传输。缺合同引用的 FROZEN_SOURCE_CHAIN_HASHES 索引、parent_CAUSAL_STATE；未找到完整可序列化恢复的 fork parent checkpoint。实际 fork_core 在 deps/，不是 code/；已归档实际依赖。

最近云端三 seed/240 episode 对应的源码、dirty diff、checkpoint、原始 logs/receipts 和 evaluator 当前版本均待只读回收，没有逐文件服务器证据。**不能声称 GitHub 包含全部云端最新成果。** 下一步仅推荐源/hash/episode/checkpoint 台账回收审计；本轮 STOP。

七个新增主包模块另经实际 import 闭包验证 PASS，physics API 全部被拦截；见 main_module_imports.json。最终加强的凭证模式扫描（含 JSON 引号键）零真实命中，见 final_secret_scan.json。
