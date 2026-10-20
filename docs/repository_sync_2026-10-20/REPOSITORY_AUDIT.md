# 本地仓库审计 — 2026-10-20

本轮仅在本机 Windows/WSL Ubuntu-Research-Verify 进行；未连接德国服务器、未运行 MuJoCo physics、PPO/SAC/ILC 训练、完整 scorer 重算或大规模科学计算。

## 核实的边界与 Git 起点

- canonical 主仓库：`/home/hank/coding/adaptive-traction-mpc-learning`；隔离研究：`/home/hank/coding/adaptive-traction-mpc-side-studies`。
- Windows 辅助根：`/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc`（Windows 原生路径为 `C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc`），本身不是 Git checkout。
- 原分支：`codex/expert-strength-value-adequacy-v1`；HEAD `8bb04662b1578b72c097f546be9e836167e280e8`；原 upstream 未设置。
- origin：`git@github.com:Block-O2/adaptive-traction-mpc.git`；GitHub SSH 身份 `Block-O2`。
- GitHub 同名研究分支 ahead/behind = **0/0**；相对 main = **83/0**。GitHub main/默认分支为 `2c2140deac8ef91aa69c57af886243f68df485ec`。
- fetch refspec 原来只抓单一 migration 分支；已使用直接 `ls-remote` 核实相关实时引用，没有把缓存引用当作所有远端分支。
- 初始：**332 staged 新增、0 unstaged tracked、1961 untracked 文件**；共 2293 条逐文件状态。HEAD 3848 文件，index 4180 文件。
- Stage 3/4 初始修改分别 0/0；新增研究主要在 Stage 5。原始完整状态在 `manifests/initial_changes.csv`。

## 审计范围、恢复基线

只读哈希库存 166071 个普通文件、135292213581 bytes（126.001 GiB），含主仓库、42 个 side-study 目录和 Windows 辅助资料；排除 Git 内部、venv、GPU/site-packages 安装树及可重建缓存。每个被列入库存的普通文件均计算 SHA256，不按时间戳选择版本。

发现 2593 个 Linux 符号链接，检查时没有断链；原目标及存在性另记，外部 D 盘目标内容没有自动继承本次字节哈希资格。主仓库是扫描边界内唯一 `.git`；没有 side-study 嵌套 Git 或 submodule。已记录其他 worktree，未更改其文件或分支。

本地私有维护目录 `local_research_sync_20261020_work` 保存：original.index、baseline.json、44 MB 初始 staged patch、空 unstaged patch、完整本地历史 bundle。bundle 包含 34 个分支/标签引用，`git bundle verify` PASS。这些恢复文件不上传 GitHub，不含本轮产生的训练产物。不要直接用旧 index 覆盖当前 index；恢复应在独立 checkout 进行。

## 安全与科学边界

提交候选逐文件经过来源 SHA256、AST/JSON、安全模式和 staged blob 检查。唯一私钥头模式命中位于 `human-side-studies-closeout-v1/export_compact.py:71` 的密钥扫描规则字符串，经人工复核为误报。没有发现真实凭证；原用户请求、主机环境转储、私有补丁、运行 raw 和账户目录未进入 payload。

原科学源码、配置、Human/robot/cuff XML/STL 未编辑；新研究副本保持原字节。仅原根 README 和 .gitignore 作维护性追加，归档路径增加 -text 属性以保存历史 SHA 身份。归档不将研究变体提升为正式 B、不改变参数、阈值、物理或科学结论。

## 完整性与限制

当前 Stage 3/5 的静态模型引用完整，RL-B 28 个 vendor 资产身份检查 PASS。历史 Stage-1 `scene_rod.xml` 保留旧 macOS 绝对 meshdir，20 个 mesh 引用在本机不存在；未重写该历史 XML，legacy Stage-1 model reproduction 标为 NOT_RUN。

已运行 55 项无物理数学/状态/接口/资源检查，全部通过；另有 450 文件 payload hash、189 Python 文件与 import/28 vendor 检查和现有 WSL 环境 pip check PASS。完整测试套件、native 编译、CPU/Python3.12 锁定环境重建、物理一致性及 scorer 全量重算为 NOT_RUN。

5 份历史 code_history/data_collection.py 副本存在同一缩进错误；原件与 SHA 保留，未进入本轮源码 payload。原 README 聚焦 Stage 4，追加 Stage-5 当前基线与本审计入口；未改写历史结果。详见其余七份报告及最终 GIT_SYNC_REPORT。

## 收尾二次原件校验

166069 个原始普通文件逐项 SHA256 复核 PASS，135292204010 bytes，非授权差异 0。两个原根文档的维护追加单列；外置链接目标内容仍为 NOT_HASHED_EXTERNAL。最终剩余清单见 remaining_uncommitted.csv。

七个新增主包模块另经实际 import 闭包验证 PASS，physics API 全部被拦截；见 main_module_imports.json。最终加强的凭证模式扫描（含 JSON 引号键）零真实命中，见 final_secret_scan.json。
