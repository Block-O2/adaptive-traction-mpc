# 来源、复核与关闭边界

Canonical包：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1
审阅镜像：C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_18d_t_second_round_coordination_v1
Python：/home/hank/envs/adaptive-online-rl-v1/bin/python -B
环境：audit/ACTUAL_EXECUTION_ENVIRONMENT.json（Python3.10.21、MuJoCo3.10.0；未安装/更新环境）。

EXECUTION_CODE_MANIFEST.json冻结source/code/deps/weights/control和原参数/门。每次START都逐项核对SHA并记录group plan SHA；所有组使用同一冻结执行manifest。FROZEN_SELECTION及NEW_PREFIX_VALIDATION_PROTOCOL在任何验证结果前冻结，W1停止后没有改primary/阈值/执行代码。

各完整运行raw：source/results/<id>/trace.npz、summary.json、native_reference.npz、runtime_artifacts.json.gz；motion_series为原0.25ms native映射。reports保存完整原指标和receipt lineage，EXPERIMENT_RESULTS收齐20个完整运行及附加full/phase变化指标。W1_parent只有中止partial，output/W1_parent_PARTIAL_COMPUTE.json及其错误/日志保留，不强行补成完整raw。

关键只读复核入口：control/independent_recompute.py的measure；它不导入controller/plant。关闭后不要原地运行main覆盖derived；在新的审计目录import该模块，将P指向本canonical、put重绑定新输出sink后再逐id重算。analysis/independent.py记录本轮独立数值核验，analysis/audit_execution.py核对实际sealed对象/current certificate/receipt，cross_batch_repeat.py逐字段验证跨冷父确定性。它们均只增加算术证据，不启动physics。

原B/历史18D/T只读；原历史代码/证据manifest核对见audit/HISTORICAL_MANIFESTS_VERIFIED.json，Git与全历史保护见audit/GIT_BEFORE、HISTORY_BEFORE及最终审计。若要新物理复现，须新版本化隔离包及新授权；本包有PHYSICS_STOP/CLOSED，禁止原地重启或覆盖账本/raw。

本轮所有physics串行；父、fork、重复、失败均计START。没有Human状态赋值、近似拼接或回放。PHYSICAL_LEVEL1不赋予Native LEVEL2/host LEVEL3、跨患者或临床资格。
