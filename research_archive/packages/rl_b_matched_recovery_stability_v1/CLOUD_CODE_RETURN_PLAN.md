# 云端代码回流审核方案

本轮只生成可审核差异，不应用到长期仓库，不自动 commit/push。保留 GitHub 原 sealed capsule 和D01R合同身份；修复进入新的 active 开发版本，历史研究包继续可复现。

|优先项|云端证据/拟目的地|审核与进入条件|
|---|---|---|
|P0：force/moment实际拥有区间积分|`source_diff/sealed_science__...runtime_sac_expert_v1.py.diff` → active Stage5 同模块；`force_audit.py`、independent_physics_audit、stream_json → 通用审计工具|分别覆盖未施加拒绝、零时长重复边界、partial异常、正常完整任务；与实际native步/receipt积分回归，再逐字段确认正常任务旧指标不变。保留失败边界而不伪造积分。|
|P0：G4期限优先级|`activation_validation.py` 原精确diff → active Stage5；历史g4_repair的边界测试|确切边界前/等/后以及所有三个phase；保留原10s期限、1e-12边界约定。自然HOLD失败、绝对安全触发和完整矩阵未闭合，必须单独科学回归，不能用当前8次替代。|
|P1：native RL接口在主树的显式版本|capsule已有 `rl_native_proposal.py`，active main缺对应文件；native_rl_env/ready_env接口|与原planner/certificate/admission/40ms bridge/100ms lifecycle、因果41D输入完整回归；不得把多个不同 source 树隐式混在 sys.path 中。|
|P1：可复用checkpoint/恢复和资源工具|checkpoints的显式冻结allowlist合同、原model/Adam/RNG、gzip reader、6GiB资源门|单独模块/配置schema；破损/未完成generation/合同变更拒绝、跨进程恢复、仅新目录写入。不要把历史绝对T0/STOP/预算作为长期默认。|
|P1：训练/冻结评价与证据分离|`replication_run.py`、rollout npz、真实Adam统计、sampled raw→clip→proposal及frozen hash检查|抽取通用入口后独立回归。保留gamma=1有限终止和所有transition；本轮没有为新入口赋训练资格。|
|需另审的科学版本：reward v3 floor|`pilot_env.py` 与 `test_pilot_reward.py`，对应独立reward审计|修复失败partial成本偏好有明确历史动机，但floor及其界限是研究合同，非通用最佳reward。作为显式版本保留；本轮172失败均−11.5，未证明它导致或解决退化。|
|仅历史实验特化|campaign_manager/replication_analysis/build_reports/stage2_*、seed列表、80集门、budget/停止文件、临时cache路径和脚本|归档于本研究版本/工具数据层，不直接替代长期算法入口；Stage2门仍关闭。|

精确配置和逐文件hash见 `source_diff/CODE_LINEAGE_AND_CONFIG.json`。原cloud_v1→g4_repair只有两份科学源码改变；后续414科学闭包未再改变。`independent_physics_audit.py`的零时长拒绝处理和`audit_reward_physical.py`终止通知例外需要按明确事件模式审核，不能成为任意重复时间戳的通行证。模型/vendor无需“修复回流”，已逐文件一致。

审核顺序为 P0科学回归、P1通用基础设施、再单独授权有界训练验证；不得在回流时顺便换reward、物理、action或放宽G4。当前源码恢复/离线评分通过，只是回流审查的证据。
