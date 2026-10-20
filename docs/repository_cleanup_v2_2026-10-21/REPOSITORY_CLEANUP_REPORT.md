# 本地仓库整理验收 — 2026-10-21

已完成实际整理、分组 commit 和普通 fast-forward push。可验证源码提交 `a60686f30aaee5e950fa7e9ae7e802cd74df4cc2`，分支 `codex/local-research-sync-20261020`。随后仅追加审计文档；最终精确分支 SHA 见交付核验 JSON。起点 `cfcb0d44d7866a594d4b96148ba2f5f649a495da`，main 保持 `2c2140deac8ef91aa69c57af886243f68df485ec`。

实际执行在用户本地 Ubuntu-Research-Verify WSL，工具由 Windows 进入；未连接或修改 Hetzner，未启动 MuJoCo 物理步进、PPO 或其他训练。只编译了三个原模型以检查资产，不创建物理运行。

## 十一项验收

| 问题 | 结果 | 证据 / 限制 |
|---|---|---|
| 1. GitHub 实际功能 | PASS | Stage3/4/5 源码/配置、Human/robot/cuff、RL-B CPU handoff、原 B/H150 scorer 和小型 fixture；见 GITHUB_SOURCE_AUDIT.md |
| 2. 剩余 dirty 处理 | PASS | 1432 项 A 已提交；524 项 B 已校验归档并精确 ignore；7 项 D 保护。REMAINING_DIRTY_MANIFEST.csv 仍列保留文件，不以零 dirty 代替分类 |
| 3. 提交/归档/删除 | PASS | A 原字节提交；另补 118 个原始源码/资产文件；B 归档保留原件；只删 80 个可生成字节码 cache，见分类与删除台账 |
| 4. 原始数据丢失风险 | PASS / UNVERIFIED | 本轮无原始科研证据删除或改写，Linux/Windows 复核通过；全量独立物理备份和 D 盘目标身份未完全验证，不能声称零存储风险 |
| 5. B/H150 原 scorer 完整性 | PASS | 16 个恢复索引锚点、九项原合同 SHA、v6 原依赖身份均匹配；真实冻结函数及断言保持启用，网络克隆隔离复核通过 |
| 6. 离线 / 完整 fork | PASS / UNVERIFIED | 离线 scorer 已重算真实 parent/B/H150；完整 fork 未运行，缺可移植完整 parent checkpoint；parent_CAUSAL_STATE 未找到 |
| 7. RL-B 从 GitHub 独立恢复 | PASS | 450 文件封存 + 28 vendor 身份、35 个 wheel hash、全新 Linux Python3.12 CPU 环境、导入/单测通过；物理与训练资格仍 NOT_RUN |
| 8. 德国服务器现在可拉取 | PASS / UNVERIFIED | 可取得固定提交的源码、资产、锁、恢复/评分工具；服务器本身是否成功部署 UNVERIFIED |
| 9. 额外下载资产 | PASS | 版本化 fixture 归档 129608743 bytes 有 SHA；其 native raw 及其他历史 checkpoint/raw 不经 Git。未发布下载 URL，需先传输 |
| 10. 可信源码基线 | PASS（限定范围） | 当前 Stage3-5、封存 RL-B、原离线评分源码/配置/资产基线可用；非全部历史数据备份，也不代表服务器最近训练版本 |
| 11. 下轮云端 matched 部署 | PASS（有前置） / FAIL（纯 GitHub 全量评分） | 可以从固定源码开始部署；完成原 raw 评分前必须先提供已校验 fixture 归档。不得自行开始 full fork 或训练 |


## 实际处理

初始按文件展开为 207 staged、1756 untracked、0 unstaged tracked；1963 项逐一分类。普通 git status 的目录汇总是 1692 untracked，非 64 个文件丢失。A=1432、B=524、D=7。A 中 20 个历史 Python 文件保持原字节；两个机器链接的有效源码另按原字节放入 research/local_studies，链接本身保留。

524 项 B 共 329948893 bytes，归档 `/home/hank/research_archives/repository_cleanup_v2_2026-10-21/remaining_evidence_v1.tar.gz`，压缩后 44806727 bytes，SHA `cf6dd9d58102606cc59c2511552ce4fc1716511e0ad415c242089609882e6b4a`；全部成员逐个校验通过。原件仍在原路径，仅在归档通过后撤出暂存并按准确文件名 ignore。私有 index / patches / bundle 内容未提交；原 history bundle verify PASS。

只删除 80 个 CPython 字节码 cache，共 1041721 bytes。每个都有存在的源文件、删除前 SHA、生成原因及恢复命令；详见 manifests/CACHE_DELETION_LEDGER.json。37 个无法按该规则确认的 cache 项继续保留。没有删除已跟踪文件，没有移动或改写原 raw、checkpoint、失败结果、模型、算法或冻结合同。

19 个历史 CSV 用精确属性保留 CRLF，防止 Git 转换破坏 SHA。新增 ignore 使用精确证据路径；将机器绝对路径、历史 duplicate 来源和当前部署入口分别索引，没有合并科学变体。

## 保全与边界

Linux 新鲜库存 181184 文件、120936717422 bytes；除 README / .gitignore / .gitattributes / research/.gitattributes 四个维护文件外，181180 文件前后 SHA 一致，2593 链接及其他本地分支未变。Windows 既有 33244 文件、15323265713 bytes 本轮再次哈希全部一致。外部链接目标的全部内容及独立异地备份仍 UNVERIFIED。

当前 Linux 中没有相同 Git blob 的外部证据 62014 文件、118052581939 bytes，按包 SHA 索引见 EXTERNAL_DATA_MANIFEST.json。其他大数据保留原位，没有将索引冒充新备份。本轮两个新归档位于同一台机器，不能当作异地或独立物理备份。

新鲜 GitHub 克隆、全新 CPU 环境和原 raw 离线重算均通过；Python audit hook 禁止访问旧研究目录、Windows 研究根及旧环境根。路径依赖暴露与修复的失败日志保留。原 scorer、执行源码、门限均未改动。

## 源码与部署提交

```text
1e3ab36521d83ff539c58f6b6a90c20d9052d2de research: preserve remaining historical source and portable action audit
75c61f92fe4f97e228c480b5f3083cadb5cafced research: restore original B H150 hash chain fixtures and model closure
24f1e812b5632647e9e2343a42c484bc9f6c4e54 docs: preserve compact research evidence and failure records
97f1c9c61a315d0ab85b360ab3448e32085be395 build: add hash-locked GitHub recovery and original offline scorer tools
6fc8e2acfe8d6a222e83601d5e4574ccf14ab503 fix: isolate frozen scorer imports from historical local paths
956d559fdfa32510287317f5b9ed7d2704a5e75d fix: include frozen stream reader bootstrap in offline import closure
3fa23a9b5ce2278e4657820bdf7a0ae7af3413ee fix: load frozen evaluator modules explicitly from restored source
a60686f30aaee5e950fa7e9ae7e802cd74df4cc2 research: complete all frozen v6 execution assets and identity checks
```

文档收尾提交在其后。使用精确路径分组暂存，逐 index blob 比对 SHA，完成敏感模式扫描、大小、Python 语法、JSON、原 manifest 和必要资产闭包检查。当前树敏感扫描的唯一命中是旧 export_compact.py 第 71 行的扫描规则字符串，经逐字检查不是真实私钥。扫描范围为当前树及本轮增量，不声称完成全部 Git 历史的秘密审计。

没有 force push、历史重写、reset --hard、git clean、自动合并 main 或远端分支删除。科学参数、训练定义、原模型和原评价阈值未改变。

## 交付文件

- [GitHub 源码审计](GITHUB_SOURCE_AUDIT.md)
- [剩余保留文件清单](REMAINING_DIRTY_MANIFEST.csv)
- [外部数据索引](EXTERNAL_DATA_MANIFEST.json)
- [B/H150 原评价器就绪度](B_H150_EVALUATOR_READINESS.md)
- [云端恢复指南](CLOUD_GITHUB_DEPLOYMENT_GUIDE.md)
- [Git 同步核验](GIT_SYNC_VERIFICATION.json)
- [下一研究决策](NEXT_RESEARCH_DECISION.md)

终止状态：COMPLETE_STOP。唯一建议：先转交固定 SHA 的 fixture 归档，再单独授权云端 Codex 从上述固定源码做原 matched 离线部署验收。
