# 连续重复协议 v1

本文件在本包首次 physics START 前冻结。研究对象是 MuJoCo robot–cuff–passive Human；最高证据为 PHYSICAL_LEVEL1。安全、任务完成、性能依次优先。原 B-relative motion/fairness 是工程可比资格，不是临床安全阈值。

1. 每患者独立 cold initialization，通过原物理 commissioning 和 W1 合法 prefix，执行第一次完整 B 运动。保存全 OUTBOUND/HOLD/RETURN 因果历史，不以第一次的 native truth 为学习器输入。
2. 完整结束后确认原 wall session 已关闭、planner 无 outstanding request。使用原 `advance_inter_rep_boundary`，最多 2 s，以原末次已执行 command 进行 settle/hold；观察包装器逐 native step 保存控制、时间与继承 receipt。记录这部分额外时间、力和力矩成本，不能隐去。
3. 第一次的学习输入、ILC 提案和模型更新在下一次分支结果出现前写入不可覆盖的 decision 文件并哈希。父进程保存完整 live session，使用 Linux `os.fork` 复制完整地址空间。禁止通过 qpos/qvel、pickle 物理状态或 trajectory replay 重建。所有分支串行运行并 join，父状态前后哈希必须相同。
4. 每分支从该相同 state 调用原 persistent-session runtime。保留 plant、measurement layer、observer、allocator、last command、command-response history、commissioning fit、updater/belief；原接口重建 task、supervisor、monitor、authority、planner lifecycle、reference history、receipt epoch。执行原 fresh TRACK bootstrap，并记录额外成本。这个 preparation 是相同起点下的方法无关物理流程，不假定两次运动初态相同。
5. 第二次每方法完整执行，记录 proposed → certified/rejected → activated/spliced → receipt-owned native execution。拒绝后原父动作可能继续，拒绝提案不能计作实际动作改变。
6. B 固定策略与禁用历史 ILC 的规则完全相同；首患者加做独立相同动作复现。H150 使用冻结参数，失败保留。学习策略只能读取第一次的 allowlist 和已冻结开发模型；不能读取同患者第二次对照结果来选择当前动作。
7. 可选第三次只在各自子分支上继续，不拼接其他方法的最终状态。完整 B-relative 资格需要该次起点的匹配 B fork；否则仅记录描述性重复趋势。

隔离序列化遵循已有修复：每次调用后通过 `streaming_reuse.restore(rt)` 恢复注册的唯一 serializer；禁止恢复安装前的旧闭包。先做零物理两次调用 owner probe，再做真实相同动作连续重复复现。

父状态 fingerprint 覆盖原 MuJoCo integration state、runtime 全图、updater、完整历史和 Python/NumPy RNG；原生句柄、锁和闭包不由哈希重建，而由真实 fork 保留。记录不能遍历的对象类别。所见哈希相同不是独立物理同一性的充分条件，必须同时有 fork provenance 与完整控制/native/receipt 的重复复现。

预算：T0=2026-10-19 22:00:08（Asia/Shanghai）。至 2026-10-20 05:00:08 关闭新 physics START，至 06:00:08 必须停止。最多 80 START，含父、fork、失败、partial、重复和准备边界；静态无步进检查单独计数。不得自动恢复或开启下一包。
