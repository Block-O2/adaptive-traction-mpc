# 冻结PPO、执行权限与目标区别

| 身份 | 原门 | 权限 | JF N·s | JM Nm·s | native jerk RMS 髋/膝 °/s³ | 200Hz ‖F‖ rate RMS N/s | 4kHz ‖F‖ rate RMS N/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PPOCHECK_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| PPOCHECK_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| PPOCHECK_FROZEN_MEAN | PASS | original domain | 1399.918272 | 107.492306 | 319.39/676.46 | 17.7838 | 19.3655 |
| PPOCHECK_FROZEN_PLUS_RULE | PASS | original domain | 1401.225670 | 107.091388 | 313.38/660.87 | 17.7330 | 19.2597 |
| PPOREPAIR01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| PPOREPAIR01_TIME0 | PASS | original domain | 1399.891500 | 107.501154 | 320.01/677.63 | 17.8024 | 19.3871 |
| PPOREPAIR01_TIME0_RULE | PASS | original domain | 1403.731266 | 107.267783 | 299.71/636.30 | 17.3087 | 18.7694 |
| PPOREPAIRVAL_BEST | PASS | original domain | 1398.122564 | 107.888540 | 320.22/679.30 | 17.7667 | 19.3563 |
| PPOREPAIRVAL_B | PASS | original domain | 1436.773241 | 101.245738 | 305.43/713.01 | 19.4387 | 20.9634 |
| PPOREPAIRVAL_MEAN | PASS | original domain | 1399.998411 | 107.406922 | 319.28/677.49 | 17.8036 | 19.3836 |
| PPOREPAIRVAL_RULE | PASS | original domain | 1401.188430 | 106.947307 | 313.24/661.96 | 17.7504 | 19.2756 |
| PPOREPAIRVAL_TIME0 | PASS | original domain | 1399.971402 | 107.415782 | 319.90/678.65 | 17.8225 | 19.4054 |
| PPOREPAIRVAL_TIME0_RULE | PASS | original domain | 1403.724868 | 107.120254 | 299.56/636.55 | 17.3209 | 18.7795 |


| 身份 | 实际接受modal数 | 拒绝modal数 |
| --- | --- | --- |
| PPOCHECK_BEST | 9 | 0 |
| PPOCHECK_B | 0 | 0 |
| PPOCHECK_FROZEN_MEAN | 5 | 4 |
| PPOCHECK_FROZEN_PLUS_RULE | 5 | 4 |
| PPOREPAIR01_B | 0 | 0 |
| PPOREPAIR01_TIME0 | 9 | 0 |
| PPOREPAIR01_TIME0_RULE | 9 | 0 |
| PPOREPAIRVAL_BEST | 9 | 0 |
| PPOREPAIRVAL_B | 0 | 0 |
| PPOREPAIRVAL_MEAN | 5 | 4 |
| PPOREPAIRVAL_RULE | 5 | 4 |
| PPOREPAIRVAL_TIME0 | 9 | 0 |
| PPOREPAIRVAL_TIME0_RULE | 9 | 0 |


CONFIRMED：原PPO每任务一次高层向量决策，部署动作是checkpoint64的tanh(mean)，不是训练最佳采样。历史72 START=64训练+4均值评价+3anchor+1cold parent，5,033,780新增native和约7935.69秒group wall属于历史投入；本轮新PPO训练为0。原合格奖励只包含5*tanh((base JF−actual JF)/5)，未奖励门内平顺性或JM，不能按本轮新S目标声称PPO训练样本效率差。

CONFIRMED：冻结均值与均值加降速规则两种方案中OUTBOUND四个modal提议均因fixed-duration参考超原速度证书而拒绝，其余五个提议接受。加规则只带来约1.88%/2.30%髋/膝jerk RMS及0.55%force变化率改善，JF增加1.307398 N·s、JM减少0.400918 Nm·s。原guard在两次TASK内均未active。CONFIRMED：名义和补充新prefix的反事实均表明，将OUTBOUND时序坐标置零会恢复modal接受数5→9，原证书仍生效。单独恢复权限使jerk／force变化率略升；加降速规则后才有实际质量收益。补充新prefix相对旧规则髋／膝jerk约−4.37%／−3.84%、力模长变化率约−2.57%，ΔJF=+2.536438N·s、ΔJM=+0.172947Nm·s；不称全面更优或新学到的actor。

补充修复与独立新prefix最多11 START，动作/条件在任何主VAL前已冻结，物理执行顺序在主验证结束后；不改变PATTERN/BO固定12次或主验证结论。实际状态见analysis/PPO_REPAIR_GATE.json及owned/PPO_REPAIR_QUEUE_END.json。所有修复均是显式混合方法，不称actor已经学会状态反馈机制。原始身份、目标、资源审计见audit/PPO_FROZEN_IDENTITY.json、audit/PPO_OBJECTIVE_AND_INTERFACE_SCOPE.json和audit/HISTORICAL_PPO_COST.json。


CONFIRMED：实际历史reward anchor是PPO_SCRATCH_STRONG（legacy2，JF1400.089728），不是原B1436.456498。64条原on-policy reward重放最大误差约4.44e−16；61条合格奖励范围约[-2.9115,1.0768]，无abs(reward)>4.9的饱和样本。由错误原B基准推导的“tanh饱和导致PPO无效”假设被否定；没有门内jerk/JM目标与实际动作证书屏蔽是不同问题，见audit/PPO_REWARD_BASELINE_AND_REPLAY.json。
