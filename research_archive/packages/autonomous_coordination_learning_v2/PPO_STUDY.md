# PPO在新协调表示中的真实探索

已完成scratch训练64个episode，即64个高层RL决策；policy更新epoch为31，mean/std/value三组Adam共93次参数组更新。 训练sample最佳合格JF=1398.995849；训练后已实际评价mean最佳合格JF=1399.918272。两者分别报告。 末次实际mean检查点为PPO_SCRATCH_MEAN_0064：JF=1399.918272、JM=107.492306、原门合格=True。开发检查点择优和末次策略分别保留。

|mean检查点|完整|合格|JF|JM|归一化最差motion比例|
|---|---|---|---|---|---|
|PPO_SCRATCH_MEAN_0016|True|True|1399.925754|107.531918|0.955783|
|PPO_SCRATCH_MEAN_0032|True|True|1399.997218|107.465419|0.955769|
|PPO_SCRATCH_MEAN_0048|True|True|1400.014110|107.475459|0.955767|
|PPO_SCRATCH_MEAN_0064|True|True|1399.918272|107.492306|0.955767|


新8D actor从零mean、STD=0.2开始scratch；固定合法上下文用8维高斯mean/logSTD和scalar critic表达，每个任务只commit一个高层计划。没有语义不兼容的旧checkpoint或rollout复用。tanh动作使用精确变换密度且采样后不clip；同generation的8个episode来自一个冻结behavior，每批后更新。policy clip=0.2、全局梯度norm=0.5、mean/std LR=0.01/0.002；STD更新边界[0.05,0.7]、最多8个epoch，exact Gaussian KL和经验ratio KL任一>0.03后停止后续epoch。最后一次更新可超过阈值，没有宣称硬KL约束或回滚。entropy项为变换前Gaussian。

合格任务reward为 `5*tanh((strongJF-JF)/5)`，在合格集合内严格保持JF排序；完整但不合格为负惩罚，未完成=-20。return=单次reward，raw advantage=reward-同批前value；同批中心化/标准化。同批constant scalar value在advantage中心化时完全相消，因此critic不贡献本固定上下文的actor排序；这是单决策PPO探索对照，不是状态依赖value学习。不存在本任务必须依靠多步GAE的证据。

探索与信号诊断：

```json
{
  "training_attempts": 64,
  "complete": 64,
  "qualified": 61,
  "training_best_id": "PPO_SCRATCH_TRAIN_0058",
  "best_sample_JF": 1398.995849252443,
  "best_evaluated_mean_id": "PPO_SCRATCH_MEAN_0064",
  "best_evaluated_mean_JF": 1399.9182718110073,
  "known_common_design_best_JF": 1399.3900453674864,
  "samples_matching_or_beating_known_design": 4,
  "reward_min": -10.665784422251017,
  "reward_max": 1.0767547236886645,
  "strict_force_order_within_qualified_reward": true,
  "one_decision_per_episode": true,
  "closest_sample_distance_to_known_design_action": 0.3121476504007606,
  "distance_is_not_probability_of_good_region": true
}
```

独立重放状态：`PASS`；重算seed采样、变换密度、原任务reward、advantage、五点差分clip目标梯度和Adam状态，详见 `audit/PPO_ON_POLICY_REPLAY.json`。真实native积分不是独立RL样本。完整budget含mean评价，按相同累计物理预算与A/B/C比较，额外64集结果另列。


相同机制也在PPO_SCRATCH_TRAIN_0009出现：任务完整、仅jerk RMS不合格。22.000000s时实测gap约0.428376m，原包络差分曲率-449.597641m/s²触发广义力矩修正[8.880443536095054, -2.8059660784551106]Nm，随后髋native jerk在22.0005s达到约28608deg/s³。用原函数及该次已记录因果充分输入重放，曲率/修正量误差均为0。这支持GP与PPO的部分motion失败共享原低层非光滑反馈机制；不解释所有excursion或速度失败，也不代表PPO全部负结果都由它造成。


PPO第30次同样完成任务但jerk RMS失败，JF=1398.823083不能计为合格收益。原函数因果输入重放PASS：21.995s时gap约0.428344m，差分曲率−624.933894m/s²触发约[8.85168,−2.80086]Nm修正，髋native jerk在21.9955s达到约28503deg/s³。该证据单独保存在 `audit/PPO30_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`，不将所有PPO失败自动归于此机制。


实际执行与信号摘要：

```json
{
  "training_attempts": 64,
  "completed_task_count": 64,
  "qualified_count": 61,
  "rollout_records": 64,
  "unique_completed_actual_reference_profiles": 64,
  "exact_strong_reference_repeats": 0,
  "slot_counts": {
    "ACCEPTED": 439,
    "ACCEPTED_AND_ACTIVATED": 439,
    "REJECTED": 137
  },
  "execution_permissions_by_local_timing_sign": {
    "OUTBOUND/nonpositive": {
      "samples": 48,
      "accepted_slots": 60,
      "rejected_slots": 132,
      "accepted_fraction": 0.3125
    },
    "OUTBOUND/positive": {
      "samples": 16,
      "accepted_slots": 64,
      "rejected_slots": 0,
      "accepted_fraction": 1.0
    },
    "RETURN/nonpositive": {
      "samples": 20,
      "accepted_slots": 95,
      "rejected_slots": 5,
      "accepted_fraction": 0.95
    },
    "RETURN/positive": {
      "samples": 44,
      "accepted_slots": 220,
      "rejected_slots": 0,
      "accepted_fraction": 1.0
    }
  },
  "nonqualified_full_tasks_with_lower_JF_than_public_strong": [
    "PPO_SCRATCH_TRAIN_0030"
  ],
  "qualified_reward_order_mismatches": [],
  "critic_role": "For one constant context and one RL decision per episode, subtracting a common scalar value then centering advantages cancels that scalar exactly. Critic updates do not create state-dependent actor ranking here."
}
```

每generation的STD、mu、reward方差与饱和、实际激活/拒绝计数、critic相消误差详见 `PPO_EXECUTION_AND_SIGNAL_DIAGNOSIS.json`。
