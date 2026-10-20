# iHEAR 长期科研仓库架构 v1

本轮采用兼容 Stage3/4/5 的增量架构，不整体搬移历史科学源码。起点为研究分支 `codex/local-research-sync-20261020` 的 `dab1f61d6626b9c5122578e9b1c82987cbea34cd`；已联网确认与 GitHub 相等，已验证源码提交 `a60686f3` 是其祖先。main=`2c2140deac8ef91aa69c57af886243f68df485ec`。

## 目录与责任

```text
stages/
  stage1/, stage2_linkage/                 历史研究，保留身份
  stage3_full3d/                           3D plant / robot / Human / cuff
    src/ models/ vendor/ configs/ tests/
  stage4_adaptive_control/                 estimator / trust / MPC
    src/ configs/ scripts/ tests/ docs/ results/summaries/
  stage5_personalized_motion_learning/     Stage5 算法与研究入口
    src/ configs/ scripts/ tests/ models/ vendor/ docs/
research/
  side_studies/<study>/                    冻结研究包、合同及历史科学变体
    ihear_overnight_control_learning_transition_v1/
      code/ control/ deps/ source/         原执行闭包，不建立第二套 active code
      source/results/D01R_*/               原生真实离线 fixture
      output/ reports/ motion_series/     冻结指标和对照基线
  rl_b_cpu_handoff_v1/                     450 项封存 CPU capsule
    source/                               已封存的 414 项闭包，仅原版本可复现
deployment/                               维护层入口、配置、CPU locks、身份清单
  configs/ tests/ data_catalog.json model_manifest.json
docs/                                     方法、研究结论、审计与复现说明
runs/<experiment>/<run-id>/                新输出、日志、指标、provenance（忽略）
research-data/<data-id>/<version>/         大 raw/checkpoint 的本地挂载位置（忽略）
.deployment-work/                         临时环境、校验输出（忽略）
```

`runs/` 与 `research-data/` 是未来约定，本轮未搬移或删除原数据。现有原生 fixture 留在 scorer 所需目录，deployment manifest 给它明确数据身份；不额外复制到 tests/fixtures。tests/ 只新增维护层完整性失败测试，原 scientific tests 原址保留。

## 真实依赖边界

Stage3 提供 plant，不依赖 Stage4/5；Stage4 当前 src 中有55处 Stage3 import；Stage5 有83处 Stage3、89处 Stage4 import。逐文件/行见 evidence/CROSS_STAGE_IMPORTS.json。这是静态 import 计数，不是独立算法数量。各 Stage 的 pyproject 和研究配置保留；其宽松依赖声明不能冒充已验证的全 Stage Python3.12 lock。

B/H150 必须使用原 analyze_matched / explore_common / attribution / stream reader / independent_recompute。23项身份、16项历史锚点、完整1426项 v6、九项合同均检查。冻结代码中的历史路径保留为身份；维护入口显式按原文件加载、重绑定 S/P，实际读取 clone 和新输出目录。绝对路径的历史字符串不等于可移植下载地址。

RL-B 通过包内 common.py 将 SOURCE 绑定到自身 source/，显式引入同一封存版本的 Stage3/4/5。414项中412项与主树同路径字节相同，2项不同，见 RL_B_REPRODUCIBILITY.md。不能把 frozen source/ 替换为当前主树来“去重”，也不再为新工作复制414份源码。未来新算法应在 Stage5 主源码中开发，通过显式版本契约引用依赖；更新封存 capsule 是独立版本决策。

## 可复现链与身份

固定 Git commit → 新 CPython3.12 CPU 环境 → --require-hashes locks → 校验来源/合同/模型/fixture → 选 deployment/configs 配置 → 调用原入口 → 新目录输出。scorer 的 RUN_PROVENANCE.json 记录实际 commit、dirty 状态与 diff hash、config hash、输入逐文件hash、模型清单hash、候选算法hash、原 seed=2026102001、依赖锁与实际版本；OUTPUT_MANIFEST.json 记录输出逐文件hash。run UUID 区分执行，experiment identity 关联同一输入与软件版本。

历史实验生成时的原 Git commit 若未被原证据记录，明确 UNKNOWN；发布源码 commit 不冒充历史运行 commit。离线重算只读取旧数据，不重新消耗随机种子或生成物理轨迹。

新增源码不得依赖机器绝对路径；外部数据使用 data_id 与逐文件 SHA 解析。对冻结源码的路径兼容在维护适配层处理，保留原hash。历史484处机器路径记录见上一轮 MACHINE_PATH_REFERENCES.csv；其他未适配历史 runner 不因此获可移植 PASS。

## 本轮执行与边界

实际只补三份原生 runtime fixture；增加维护配置、完整性校验、模型编译检查、结果provenance、失败测试、数据catalog与本文档；改进新环境引导、RL-B校验入口和README/.gitignore。没有移动/删除科学源码，没有修改正式物理、算法、阈值、READINESS、原checkpoint或合同。没有 LFS/Release/分卷；没有连接德国服务器，没有训练或物理步进。

源码 clone、依赖 import、模型编译、动态物理、原 scorer 重算、新 live matched 资格及硬件/临床资格必须分项验收，不能共享一个 PASS。

历史Stage1的两份Mac/UR5e XML仍有40处缺失mesh引用，静态报告明确FAIL；不属于本轮Stage3–5/RL-B/B-H150通过范围，未伪造补齐。

起始Side Studies快照47852文件、8552种唯一内容、39300个额外相同路径；逻辑934192096bytes、唯一179480822bytes，见evidence/DUPLICATION_SUMMARY.json。该规模是后续治理负担；本轮保留历史闭包并禁止继续复制源码快照作为新开发默认。
