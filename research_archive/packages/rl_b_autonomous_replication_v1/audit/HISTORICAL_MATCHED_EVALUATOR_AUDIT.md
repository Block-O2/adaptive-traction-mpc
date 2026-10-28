# 原B/H150完整匹配评价器审查

结论：MATCHED_BASELINE_EVALUATION_NOT_READY。未运行正式B/H150回归。

已查原ZIP成员、三份历史manifest与各414份源文件（历史差异另存audit/HISTORICAL_SOURCE_DIFFERENCES.json）。可用的是原MuJoCo runtime、RL-B 19.030±0.050s必要回归、完整task/部分安全/motion/causal原始证据审计。唯一实际部署source docs为adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json，标为development/no_training，并非B/H150完整Master Contract。matched_branch、baseline_replay是其他Stage分支/有限replay，不冒充本轮完整scorer。

最小缺失：权威B/H150任务/安全/motion非劣/causal合同及manifest索引；原scorer与原基准轨迹/归一化版本；冻结B/H150入口和依赖闭包；已知PASS/FAIL回归样例与执行模式/host realtime要求。现有manifest未提供这些文件的权威名称，因此不编造路径。具体搜索范围与ZIP证据见audit/MATCHED_EVALUATOR_INVENTORY.json。

迁移：从原封存研究源manifest取得精确路径与SHA，完整复制到新评价子包；先验证基准fixture与模式parity，再做少量B/H150回归；随后消费冻结PPO raw。不得重写motion门、补写近似阈值或以19.030时长独自授权完整资格。

runtime COMPLETE、19.030必要时长、original task/safety、motion非劣、receipt/causal、host实时资格分别判断。此缺失不阻止LEVEL_A开发训练；LEVEL_C仍不授予。
