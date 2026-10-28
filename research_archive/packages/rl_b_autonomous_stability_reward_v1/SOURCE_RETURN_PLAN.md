# 长期源码回流准备

本包只提供可审阅patch与回归证据，不覆盖固定GitHub checkout，不执行commit/push/merge/rebase/reset/stash/clean。

1. **P0：真实执行区间force/moment积分。** `patches/runtime_sac_expert_v1.py.patch` 从固定GitHub sealed capsule生成；未执行准入拒绝的边界拥有0秒，partial异常只归属真实已执行native时间；moment按完整实际边界区间累计。新包scratch应用后与现用冻结科学模块逐字节一致，见`audit/SOURCE_RETURN_PATCH_VERIFICATION.json`。真实完整、提前拒绝、重复零时长边界与partial账目由每次独立force/receipt审计覆盖；不能用本修复抹去原失败证据。
2. **P0：三phase期限优先级。** `patches/activation_validation.py.patch` 保留原期限和1e-12边界约定，使已超期限不能被arrival/dwell覆盖。该改动早已存在于云端414项闭包，本轮只复制和检验，不把它冒充本轮新控制改动。严格G4自然HOLD/绝对安全完整矩阵仍须独立闭合。
3. **P1：模型/Adam/RNG与恢复合同。** 以`runtime/checkpoints.py`的metadata最后原子提交和显式执行allowlist为基础；本轮新job记录父checkpoint、配置、内容地址source bundle和恢复snapshot，control逐transition复演是回归证据。长期接口不应包含本轮绝对T0、历史seed或STOP文件。
4. **P1：可复用训练证据与资源工具。** `scripts/research_common.py`包含锁定attempt预留/结算，异常native按完整预留保守计数；`run_job.py`和`watchdog.py`核验PID启动身份并管理独占进程组；owned dummy测试见`audit/OWNED_STOP_TEST.json`。应提取为通用配置schema后另审，而非整份campaign脚本进入主线。
5. **研究版本：完整episode聚合与Reward。** `scripts/worker.py`的聚合组织、`scripts/rewards.py`、Reward公式/权重及本轮候选保留独立身份。它们改变学习语义，不能因开发成功就自动成为主线。每版本使用`source_versions/<SHA256>`保存准确源码。
6. **评价与审计。** `motion_metrics.py`只读取已保存实际native Human状态；tracking沿原scorer唯一时间边界约定，derivative使用真实pre-TASK历史。full/partial、训练/dev/最终未见动作流分开。当前nominal指标不能替代原B/H150同父prefix/live matched资格。

建议回流顺序：先P0独立回归，再P1基础设施抽取，最后单独审阅有正证据的PPO/Reward科学候选。历史合同、原scorer和科学证据持续只读。

## 固定active主树的只读适用性检查

- runtime_sac_expert_v1.py：git apply --check returncode=0；目标源码前后SHA一致。固定主树可通过补丁上下文检查。
- activation_validation.py：git apply --check returncode=0；目标源码前后SHA一致。固定主树可通过补丁上下文检查。

命令未执行实际apply；HEAD与git status前后相同，GIT_OPTIONAL_LOCKS=0。完整证据见audit/SOURCE_RETURN_ACTIVE_MAIN_CHECK.json。通过上下文检查不替代科学回归、G4或live matched资格，不授权自动合并。

## 完整pending与部分更新的实际回归证据

补充UTC：2026-10-20T23:25:01.525996+00:00。完整episode数据的序列化、policy/Reward身份绑定和原子提交可作为P1恢复合同的抽取候选；aggregate64阈值、末批组织及Reward选择仍保留研究身份，不整体移入主线。

- `audit/PENDING_BUFFER_EQUIVALENCE_TEST.json`：无物理的连续30与10+20恢复路径，最终policy/Adam/Python-Numpy-Torch RNG和计数完全一致；64次合成Adam另计。原聚合测试另16次合成Adam，均不作MuJoCo任务学习证据。
- `audit/REAL_PENDING_CONTINUATION_AUDIT.json`：真实R1/163恢复59个transition、4完整episodes，与第11集新增24个严格按序组成实际83-transition更新。生成policy、Adam、边界、计数及全部输入逐项匹配；实际24Adam发生于原真实训练，该只读核验没有再做Adam或physics。
- `before_update_checkpoint`和`COMPLETE_UPDATE_INPUT.json`保存完整更新前状态及输入；若更新中断，`PARTIAL_UPDATE.json`记录真实已做步数，emergency明确标为partial、需要显式恢复。不能把部分更新权重直接晋级。
- `scripts/recover_update.py`是显式的无新物理恢复入口，恢复pre-Adam状态再重放完整保留输入；本轮尚未实际调用故障重放，不能把接口存在说成真实故障恢复已测试通过。恢复前仍须核对所用update实现与原job的内容地址版本。

通用源码抽取应去掉本轮绝对路径、seed、T0和候选名，并将buffer schema/生成策略身份/Reward身份/完整episode边界作为独立接口审阅。以上补充没有改固定checkout、scorer、原物理或硬安全，也没有新增正式资格。

## emergency父checkpoint的强制准入拒绝

本轮worker已在创建模型接口或预留物理attempt之前，拒绝`partial_attempt`或`resume_requires_explicit_offline_pending_recovery`标记的父状态，错误为`PARTIAL_PARENT_REQUIRES_EXPLICIT_RECOVERY`。完整正常pending checkpoint不带这些emergency标记，继续使用原恢复合同。负向真实启动探针见`audit/PARTIAL_PARENT_ADMISSION_PROBE.json`：synthetic partial metadata、无model ZIP，正确拒绝，未创建interface/episode，未登记物理attempt，0physics/0Adam。当前已运行worker保留加载版本，新job使用独立内容地址源码；原update函数、Reward、动作和安全均未改变。该检查是P1数据完整性候选，不是一次实际故障重放通过的证据。

隔离worker的最小准入改动另存`patches/worker_partial_parent_admission.patch`，以旧worker SHA7314e741…为基线；仅在本包新scratch应用，结果与当前worker逐字节一致，PPO update函数AST不变，见`audit/SOURCE_RETURN_PARENT_ADMISSION_PATCH.json`。这是研究工具版本的可审阅diff，不声称固定GitHub主树已具备同名文件或可直接应用；没有向主树复制或apply。
