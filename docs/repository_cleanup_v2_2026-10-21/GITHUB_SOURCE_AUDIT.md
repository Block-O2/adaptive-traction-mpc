# GitHub 实际源码审计

起始 fetch 实核分支为 `cfcb0d44d7866a594d4b96148ba2f5f649a495da`，远端树 52535 文件。不是根据上轮报告推断：本轮读取 Git tree / blob，独立计算 SHA；上轮归档 48527 个来源身份全部与实际远端、本地一致，见 manifests/LOCAL_GITHUB_SOURCE_COMPARISON.csv。原远端完整树见 manifests/GITHUB_INITIAL_TREE.csv。

本轮源码提交 `a60686f30aaee5e950fa7e9ae7e802cd74df4cc2` 已正常推送并通过新的 GitHub 网络 clone。每个新增/维护文件与该 clone 的身份对应见 manifests/NEWLY_PUBLISHED_CONTENT.csv；原执行与资产闭包 3079 文件，2237 Python 语法通过，Stage3-5 XML 文件引用 141 项均可解析。

| 能力 | LOCAL | GITHUB | MISSING / 限制 |
|---|---|---|---|
| Stage3 / Stage4 / Stage5 正式源码、测试、配置 | PASS | PASS | 独立历史 Stage3/4 全部实验环境重建未运行；现存 Py3.10 CUDA freeze 仅 observed |
| Human / robot / cuff 物理实现及当前资产 | PASS | PASS | 原文件 hash 保持；UR10e / CR12 与 scorer UR10e model compile 通过，无物理步进 |
| RL-B sealed CPU 原生执行接口、PPO / evaluate / checkpoint | PASS | PASS | 450 封存文件与28 vendor匹配；最近云端训练源码、episode、checkpoint UNVERIFIED |
| RL-B Linux Python3.12 CPU 依赖与导入 | PASS | PASS | 35 wheel完整锁；原 READINESS仍NOT_RUN，不能直接宣称训练资格 |
| B/H150原 analyze_matched / explore_common / independent_recompute | PASS | PASS | 23项来源验证；原task_bootstrap也纳入离线依赖闭包 |
| 九项合同 / FROZEN_SOURCE_CHAIN_HASHES | PASS | PASS | 恢复的真实原索引在 audit_execution；原预期根目录路径仍无同名文件，未伪造补造 |
| B/H150/parent 小型原 fixture、DATA/metric/motion_series | PASS | PASS | 32项完整输入身份见 deployment manifest；3个大型native raw保留归档 |
| 原native raw完整输入归档 | PASS | EXTERNAL | 归档存在且SHA验证，发布下载URL MISSING |
| deps/fork_core.py真实依赖 | PASS | PASS | code/fork_core.py并非实际解析位置，缺该别名不等于依赖丢失 |
| D01R_parent_CAUSAL_STATE / 可移植完整parent checkpoint | MISSING | MISSING | 不影响已经通过的离线评分；完整fork重演UNVERIFIED |
| 旧Stage1 Mac路径UR5e资产 | FAIL | FAIL | 40处引用对应两个历史XML；不属于当前Stage3-5恢复通过范围 |
| 德国服务器当前源码/dirty/训练/raw状态 | UNVERIFIED | UNVERIFIED | 本轮没有连接服务器 |


原 side_source 47746 路径的保留是研究归档。新增必要输入后 side_studies 快照有 47852 路径、8552 个唯一 blob，逻辑 934192096 bytes、唯一 179480822 bytes。Git 已按对象去重；冻结路径和科学变体没有为缩小工作树而强制合并。重复身份与可追溯 canonical Git 路径见 manifests/DUPLICATE_SOURCE_IDENTITIES.csv。

当前源码中 484 处机器路径引用已定位到文件/行，见 manifests/MACHINE_PATH_REFERENCES.csv。历史原文保留；已验证的 RL-B 包自身可重定位，离线 scorer 新入口显式按文件加载原模块并重绑定路径。其他历史 runner 的跨机执行不因此自动获得 PASS。

结论：当前明确范围可以作为可信源码/配置/必要模型基线。它不是全部 raw/state 的存储替代，也没有证明覆盖服务器最近研究版本。完整缺项及云端 UNVERIFIED 单列于 manifests/MISSING_AND_UNVERIFIED.csv。


## 完整 v6 执行包身份

本轮又逐项核对整个 EXECUTION_CODE_MANIFEST_v6：1426/1426 原件匹配历史 SHA，1426/1426 已在 GitHub 副本中匹配。补回42项小型原件，包括冻结 weights/DATASET、历史 graph JSON、原校验/说明、历史 source_history 和 manifest 明确包含的包元数据。没有通过排除条目或降低身份门取得PASS。完整结果见 manifests/EXECUTION_V6_FULL_AUDIT.json。

两份原 _prefix_native 库分别是 CPython3.10 Linux x86_64 ELF 与 Darwin arm64 Mach-O；原 C 源文件、setup.py 和原包说明也在相同 source 树中。这两份二进制仅作为原身份资产保存，未加载，不能当作 Python3.12 的可用扩展。原离线 scorer 不需要这些原生库；Python3.12 RL-B CPU 封存包单独通过导入预检。完整fork的原生ABI/构建与物理执行仍未验证。
