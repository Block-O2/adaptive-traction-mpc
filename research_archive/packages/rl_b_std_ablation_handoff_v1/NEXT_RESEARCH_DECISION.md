# 下一研究决定

首个优先实验：['CHECKPOINT_STD', 'STD_INIT_0p2']，固定R1/60两父和R1奖励，先10再按同一门延长至30；这是对本轮evaluation-only结果的训练机制检验。

第二优先：选定稳定方法后，同一个checkpoint分别分叉R1/R4各10集×两父。明确检查moment/force/knee tracking/RETURN/native jerk权衡；没有一致优势就保留R1及失败证据。

当前结果只支持小样本nominal开发分配；本轮改变冻结采样STD不证明训练STD更好。原050、H2/R0/60和R1/60全部保留，不换未测试父，不做STD网格。

下一轮160训练episode/36冻结评价/33M native/8小时硬限，预留12条新动作流。最终候选在打开保留流前锁定，之后不得换Reward/PPO/std或模型。完整父hash与配置见NEXT_PARENT_CHECKPOINTS.json及unattended/NEXT_PLAN.json。

仅在下一轮明确授权后启动inactive launcher；本轮STOP。G4/live matched/Stage2/final Campaign仍未具备。
