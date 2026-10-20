# 本轮中文验收报告

本轮采用兼容Stage3/4/5的长期结构，原科学源码不搬家。deployment承载可移植维护入口、配置、CPU锁、身份清单；research保留封存科学版本；大型数据用外部版本化目录，Git保存必要fixture和摘要。依据见REPOSITORY_ARCHITECTURE、RESEARCH_DIRECTORY_MAP及DATA_MANAGEMENT_POLICY。

| 用户验收问题 | 实际结论与范围 |
|---|---|
| 1. 建议结构 | Stage3核心物理、Stage4估计/MPC、Stage5算法与训练，原模型/vendor/config/tests同Stage；deployment维护，research冻结，runs输出，research-data外部数据 |
| 2. 已实际调整 | 未移动科学源码；补3份原runtime fixture；新增配置/90模型身份清单/校验/结果provenance/数据catalog/5失败测试；改进安装、README和忽略规则 |
| 3. 129.61MB归档是什么 | 32个真实parent/B/H150历史输入/参考文件，解包146542129bytes；27必要fixture、5历史参考，无源码或完整checkpoint |
| 4. 最大单文件 | parent/runtime_artifacts.json.gz，34310122bytes=32.72MiB；gzip内部JSON更大但原scorer原生读取压缩格式 |
| 5. 需要Git管理多少 | 整体32路径保持身份；已有29项，本轮仅新增3文件102850708bytes；27必要fixture146086851bytes，另5项历史参考455278bytes已很小且原已在Git |
| 6. Release/分卷是否需要 | 不需要。三原生文件各低于50MiB，正常Git；未启用LFS、未创建Release、未拆分数据，原TAR保持不变 |
| 7. B/H150能否仅GitHub复现 | 原D01R/W1 parent/B/H150离线评分GITHUB_ONLY_PASS；原阈值/收据/运动/指标/资格结果一致；full fork与新live matched未通过或未运行 |
| 8. RL-B部署基础 | 源码450项、414原生来源、28vendor、35 wheel锁、PPO/train/evaluate/checkpoint接口和原合同齐备；新环境import/5原检查PASS；物理资格/训练/实际checkpoint恢复NOT_RUN |
| 9. 外部依赖实验 | full fork缺完整父checkpoint；其他历史全raw/轨迹/训练checkpoint按47组CSV索引；URL为空明确NOT_PORTABLE；近期德国服务器研究未回收 |
| 10. 源码重复 | 有较重历史快照重复：47852路径/8552唯一内容，39300额外同内容路径；RL-B414中412与主树相同，另2不同/缺失。保留冻结版本，未新复制科学源码；未来新开发不再建立整树副本 |
| 11. 新鲜clone | GitHub网络clone、固定payload commit、新Python3.12 CPU环境、旧研究根访问门、真实fixture、原scorer、模型编译、RL-B轻量测试全部按范围通过；见FRESH_CLONE_VALIDATION |
| 12. GitHub最终commit | 精确值以最终独立GIT_SYNC_VERIFICATION.json和交付最终答复为准；本报告所在Git树内不能自引用包含自身的commit hash |
| 13. 德国服务器现在可恢复 | 在满足OS/CPU依赖并clone固定commit后，可恢复当前源码、原模型、原离线评分、封存RL-B环境/静态工具和受原门限制的入口；未实际连接/部署，不能宣称云端最近PPO或full fork恢复PASS |
| 14. 长期数据管理 | data_id+版本+逐文件SHA/bytes+实验/源码/用途/必要性/恢复来源；缺远程来源NOT_PORTABLE；原子checkpoint generation、独立存储备份、每次新目录与provenance/output hash，Git只放摘要/必要小fixture |

原B/parent JF=1436.456498145051 N·s，H150=1402.6432114861727 N·s，gain=2.353937394034738%。OFFLINE_SCORER_READY=PASS；FULL_FORK_REPLAY_READY=NOT_RUN_NO_COMPLETE_PARENT_CHECKPOINT；MATCHED_EVALUATOR_READY=NOT_RUN_NEW_LIVE_MATCHED_EXPERIMENT；历史matched comparison独立PASS。旧Stage1仍40处mesh引用FAIL，未伪装全仓库所有历史功能PASS。

保全证据：最终重算181180原文件120936706184bytes，181179项原字节不变；唯一差异为获授权的research/README追加10行、删除0行，原始比较FAIL与逐项维护分类PASS收据均保留；科学源码/模型/checkpoint/合同未变。54200起始tracked文件再次逐项检查，只改7个维护路径，科学源码/模型/checkpoint/合同零修改；32个Git blob与原fixture SHA相同。9合同、16锚点、23 scorer、1426 v6和450 RL-B封存文件均一致，原TAR SHA=4d57c25005da7ac02c6f9d206c661399b8babd229066c2d468e07fc1234c8001。

本轮没有调参、修改正式物理/算法/科学结论或降低门槛；没有原数据删除、checkpoint覆盖、force push、reset、clean、stash、rebase、main合并、LFS/Release；没有物理步进、PPO训练或服务器连接。安全提交/推送及最终收据完成后STOP。唯一后续建议见NEXT_RESEARCH_DECISION，本轮不执行。
