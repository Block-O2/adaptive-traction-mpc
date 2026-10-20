# 研究目录与依赖地图

## 本轮起始 tracked inventory

| 路径 | 文件数 | 逻辑bytes |
|---|---:|---:|
| `research/.gitattributes` | 1 | 136 |
| `research/README.md` | 1 | 1540 |
| `research/local_studies` | 12 | 60976 |
| `research/rl_b_cpu_handoff_v1` | 451 | 47196605 |
| `research/side_studies` | 47852 | 934192096 |
| `stages/stage1` | 370 | 29867911 |
| `stages/stage2_linkage` | 33 | 1771214 |
| `stages/stage3_full3d` | 64 | 34435227 |
| `stages/stage4_adaptive_control` | 976 | 455590971 |
| `stages/stage5_personalized_motion_learning` | 4136 | 166929240 |

这是起始54200项 tracked路径的目录计数，不包括外部raw和临时缓存。完整扩展名统计见 evidence/DIRECTORY_INVENTORY.json；发布后的fixture增量为3文件102850708bytes。

| 领域 | 规范位置 / 使用关系 | 入口与资格范围 |
|---|---|---|
| 核心3D物理 | stages/stage3_full3d/src/traction_mpc_stage3 | Stage4/5 import；本轮只语法/模型编译 |
| adaptive MPC / estimator / trust | stages/stage4_adaptive_control/src/traction_mpc_stage4 | 使用Stage3；原Stage4 tests和研究spec原址 |
| 运动/学习研究 | stages/stage5_personalized_motion_learning/src/traction_mpc_stage5 | 使用Stage3/4；src、configs、scripts、tests同Stage保留 |
| B/H150 | research/side_studies/ihear_overnight_control_learning_transition_v1 | deployment/score_b_h150.py；原冻结scorer |
| 跨患者合同 | research/side_studies/ihear_cross_patient_b_h150_v1 | 冻结B/H150定义与历史来源索引；本轮不运行跨患者fork |
| RL-B CPU | research/rl_b_cpu_handoff_v1 | train.py / evaluate.py / checkpoints.py；当前只导入与轻量单测 |
| 模型与vendor | Stage3/5 models/、vendor/及两个封存source闭包 | deployment/model_manifest.json：90文件；UR10e/CR12各3上下文 |
| 配置 | 各Stage configs/、原D01R_PLAN、原CLOUD_TRAINING_CONFIG | deployment/configs只选择原实验与入口，不另设阈值 |
| frozen fixture | 原包 source/results/D01R_*、output/、reports/、motion_series/ | 32原生文件，其中27必要fixture、5历史参考 |
| 测试 | 各Stage tests/、原RL-B test_*.py、deployment/tests/ | 新失败门不模拟科学结果 |
| 结果摘要 | 原Stage docs/、results/summaries/及docs/审计目录 | 原报告保持原字节，新增解释不重写结论 |
| 大型raw/checkpoint | 旧研究根或未来research-data/<id>/<version> | data_catalog + 原CSV逐项SHA；没有远程URL标NOT_PORTABLE |
| 新结果/缓存 | runs/、.deployment-work/、包内cache/model_cache | 不入Git；不可借此删除旧负结果 |

不新增顶层source/code/scripts镜像。历史source快照属于有hash的研究证据；默认新开发入口是Stage源码和deployment维护适配器。数据路径变化须先核对config、import、XML引用及manifest闭包，不全局替换冻结路径。
