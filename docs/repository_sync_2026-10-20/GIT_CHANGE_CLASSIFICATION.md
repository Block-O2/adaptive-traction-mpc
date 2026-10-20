# 修改与提交分类

初始 332 个 A 状态、1961 个未跟踪文件逐项列于 `manifests/initial_changes.csv`，未暂存 tracked diff 为空。没有把本轮前已有代码记为本轮科学开发。

| 组 | 文件数 | 逻辑 bytes（重复版本计入） | 代码文件 | 模型资产 |
|---|---|---|---|---|
| main_evidence | 151 | 2895937 | 0 | 0 |
| main_source | 179 | 2392295 | 179 | 0 |
| rl_b | 451 | 47196605 | 191 | 30 |
| side_source | 47746 | 855543983 | 37824 | 387 |

| 类型 | 处理 |
|---|---|
| Stage-5 src / scripts 新增 | 179 个文件原字节入独立 source commit；实验变体仍与正式 B 区分 |
| 小型研究合同/配置/复现 Markdown | 151 个白名单文件单独提交；不把历史门结果重新跑成 PASS |
| 隔离研究源码与必要模型 | 单独归档；每一副本的原路径和 SHA 可查 |
| RL-B 原生事件部署源码 | 按封存 manifest 独立保存，native callback 变体不覆盖 WSL 主 runtime |
| 原先暂存的大型/密集结果 JSON、CSV、日志、原用户请求 | 保留原 index/worktree 状态，未混入其他 commit |
| code_history/source_history/retained_code 与五份语法失败历史副本 | 保留原件、哈希和外部恢复身份 |
| raw、checkpoint、weights、ZIP、缓存/venv | 留原位；数据逐文件 manifest，安装树/缓存排除且不上传 |
| README/.gitignore/research .gitattributes/本轮报告 | 维护提交，不改科学定义 |

未使用 add -A/add .、stash、reset --hard、clean、amend、rebase、force push 或自动合并。分组使用精确 NUL pathspec；检查 git diff --cached --raw/唯一内容 patch 与每个 index blob 的 SHA256 后，普通 commit --only 只消费本组路径。未被批准的原暂存项继续保留。

UNVERIFIED：没有冻结来源锚点的历史辅助文档、未做 runtime 闭包验证的研究脚本、未对照服务器逐文件 hash 的近期云端修改。字节一致与语法通过不等于科学通过。
