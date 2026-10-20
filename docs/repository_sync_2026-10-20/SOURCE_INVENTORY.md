# 源码与资产来源清单

`manifests/source_inventory.csv` 是全部库存源码/模型逐文件路径、大小、SHA256 和 Git 归属。`manifests/source_origin_manifest.csv` 是本轮精确提交白名单与复制目标；重复版本保留原目录边界，逻辑大小不等于 Git 新增唯一 blob 大小。

| 组 | 文件数 | 逻辑 bytes（重复版本计入） | 代码文件 | 模型资产 |
|---|---|---|---|---|
| main_evidence | 151 | 2895937 | 0 | 0 |
| main_source | 179 | 2392295 | 179 | 0 |
| rl_b | 451 | 47196605 | 191 | 30 |
| side_source | 47746 | 855543983 | 37824 | 387 |

Stage 3/4 正式底座沿用初始 HEAD。Stage 5 新增在线 reference/Gym、online/SAC runtime 与 coordination residual 变体按历史原字节保存；这些是已有本地研究代码，并非本轮新实现或新的正式 B。研究脚本包括 DAgger/SAC/BC、负结果诊断与恢复、memory/seed continuation；完整参数/合同身份保留。

Neural Q、ILC、Value/个体化、native 学习、FAST/HOLD、多速率、18D/M2、B/H150 跨患者研究均按以下隔离包单独归档。冻结权重与 branch dataset 若未在白名单中，则仅外部 SHA 登记，不能宣称仅靠 clone 完整复现。

| 原 side-study | 库存文件 | 提交副本 | 副本 bytes | 资格 |
|---|---|---|---|---|
| adaptive_continuous_coordination_interface_v1 | 1809 | 1417 | 24265059 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| adaptive_continuous_coordination_optimization_v1 | 1850 | 1377 | 22978397 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| adaptive_continuous_coordination_overnight_v1 | 1582 | 1408 | 23652502 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_fast_jitter_m2_host_v1 | 1897 | 1314 | 23447619 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_fast_runtime_completion_v1 | 4552 | 2178 | 25087993 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_hold_return_critical_path_v1 | 2600 | 1341 | 22963848 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_multirate_realtime_v1 | 1731 | 1212 | 21901494 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_native_learning_matrix_v1 | 4122 | 1086 | 27080770 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_native_q_realtime_integration_v1 | 17848 | 1473 | 35068216 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| b_runtime_qualification_decoupling_v1 | 1455 | 1261 | 22078405 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| commissioning-to-recovery-geometry-compatibility-v1 | 241 | 156 | 11850716 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| direction-prior-value-v1 | 8127 | 2221 | 42584211 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| force_mechanism_waypoint_v3 | 1813 | 1386 | 23184127 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| force_motion_coupling_diagnosis_v2 | 190 | 44 | 626083 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| human-side-studies-closeout-v1 | 25 | 9 | 267132 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| human-size-contrast-v1 | 172 | 152 | 11822584 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_autonomous_multitrack_v1 | 1740 | 1395 | 23313862 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_cross_patient_b_h150_v1 | 2708 | 1456 | 23869650 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_history_to_next_trial_learning_v1 | 3486 | 1458 | 24549872 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_model_terminal_compensation_v1 | 1910 | 1394 | 23420520 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_overnight_control_learning_transition_v1 | 3448 | 1547 | 24979645 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| ihear_overnight_research_retrospective_v1 | 3778 | 1429 | 24800058 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| lab-human-adaptation-contrast-v1 | 644 | 197 | 12108597 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_autonomous_review_v1 | 1705 | 1433 | 25192269 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_baseline_qualification_v1 | 1805 | 1427 | 24938325 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_early_return_motion_repair_v1 | 1739 | 1388 | 23142684 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_t_second_round_coordination_v1 | 1925 | 1399 | 24132845 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_terminal_expanded_prefix_validation_v1 | 1649 | 1377 | 22815007 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_terminal_response_repair_v1 | 1650 | 1374 | 22777101 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_w1_d_qualification_v1 | 1718 | 1380 | 23257541 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_18d_waypoint_smoothing_overnight_v1 | 1987 | 1405 | 23676763 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_comprehensive_coordination_search_v1 | 3824 | 1353 | 23677561 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_coordination_space_exploration_v1 | 2147 | 1363 | 24749023 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_free_trajectory_feasibility_v1 | 2737 | 1382 | 23067215 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_host_generalization_attribution_v1 | 1644 | 1318 | 22986036 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_lowforce_repair_explore_10h_v1 | 5966 | 1407 | 25072375 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_matched_bidirectional_exploration_v1 | 1658 | 1339 | 23120110 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_motion_counterfactual_ranking_v1 | 289 | 27 | 195367 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_neural_q_motion_v1 | 71 | 23 | 180014 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| m2_sequential_teacher_oracle_v1 | 2668 | 1432 | 26083044 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| research_deep_cleanup_v2 | 7 | 5 | 492114 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |
| research_storage_cleanup_v1 | 4 | 3 | 87229 | ISOLATED_ARCHIVE / runtime qualification UNVERIFIED |


RL-B CPU handoff 采用本地封存 SHA256_MANIFEST 的精确 450 文件集合，另保存 manifest 自身。原 ZIP、r1/r2/r3/relocation 副本和全部 runs 不重复入 Git。其 requirements 是历史 CPU 包锁；本轮只在已有 Python3.10/CUDA Torch 环境验证 import，不把它当作锁定 CPU 环境一致性。

恢复原始布局时用来源清单及归档中的相对路径；历史源码含 canonical 绝对路径、过期 owner 预算与 STOP 标志，不能直接删除 guard 或在老目录运行。正式执行资格及科学有效性均不因版本控制而自动扩大。
