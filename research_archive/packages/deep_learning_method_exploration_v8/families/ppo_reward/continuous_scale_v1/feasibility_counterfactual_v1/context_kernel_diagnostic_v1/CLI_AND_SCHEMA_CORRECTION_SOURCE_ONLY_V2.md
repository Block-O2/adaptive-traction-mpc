# GateK V2：实际 context 标签与 closed endpoint 键分开

V1 把物理 job group `V8BETA01H/L` 当成 proposal 的 `context_group_evaluation_only`，触发身份前置检查失败。实际导出使用：

| Proposal 的实际 context 标签 | Closed result endpoint key | 两个原 attempt ID |
| --- | --- | --- |
| DEVELOPMENT_HEAVY035 | V8BETA01H | V8BETA01H_OP_BETA_RF_RAW_01 / 02 |
| DEVELOPMENT_LIGHT065 | V8BETA01L | V8BETA01L_OP_BETA_RF_RAW_01 / 02 |

V2 将三种身份显式绑定，context 特征和 Gram/梯度结果以实际 context 标签记名，读取已保存 RF1 endpoint 时才使用相应 closed endpoint key；不从 case 名称、模型输出或失败标签推造 context。

原 V1 源、合同、manifest、授权和 `diagnostics/GATEK_ONCE_V1/FAILED.json` 均保留。失败 SHA `e48d154b3d8e5999a9ff4cd5ee4418ac3f8801956e34d37ac5ac5a39f7dff86b`；已付费19个SHA读取、13个JSON decode，normalization/dot/derivative/model/score/physics均0。这是入口 schema 适配错误，不是负kernel或学习机制的数值结果。

新增 [SCHEMA_VALUE_REVIEW_V2.json](SCHEMA_VALUE_REVIEW_V2.json) 对相同10份闭合JSON做79项独立字段核对，均通过：真实context与baseline标签、固定attempt顺序、合法25D/QA/原causal SHA、同context两draw完全相同raw25、G0无pending及2×26截距权重、冻结normalization、四个原sample的policySHA/alpha2/beta2/raw logits、原RF/PPO首步trace的lambda/oldlogprob/advantage与梯度结构、完整RF1/PPO3步数、两种baseline全部endpoint键及policy身份、两组DONE→RESULT均一致。此检查只做读取、布尔/类型/有限值及canonical hash核对；没有调用V2、normalization、数值dot或模型。

V2 在任何 normalization/dot 前增加整批metadata preflight，逐项校验相同字段；保留原数据、reward、总梯度分解数学、rank/residual失败门、所有数值次数、步长/原clipscale和可证伪条件。新增计数为4条context绑定检查、8条endpoint结构检查，不新增推理或拟合。

拟数值诊断仍为≤60s、CPU1、AS1GiB，19个26D dot + 16个2D dot = 526 scalar products、4个2×2分解求解、16个mean方向导数，0训练/新score/Beta forward/新物理。旧 [V1数学合同说明](CLI_AND_MATH_SOURCE_ONLY_V1.md) 的分解公式保持有效；身份和实际调用入口以V2为准。Gram退化或重建不一致停止，不补score，不作自动重试。

当前 V2 仅源码与AST解析/元数据检查，未 import 或 execute；也未生成真实V2审批或初始化诊断clock。必须由主线程另批一次独立有限诊断，绑定V2 source manifest和同一 input_refs object SHA；不会重置旧clock或原Beta/全局窗口。

未来主审命令模板（不是执行授权）：

```bash
timeout --signal=TERM 60s env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python -B \
  deep_learning_method_exploration_v8/families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/context_kernel_diagnostic_v1/run_context_kernel_diagnostic_candidate_v2.py \
  --approval /home/hank/ihear-lab/deep_learning_method_exploration_v8/families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/context_kernel_diagnostic_v1/MAIN_APPROVAL_ACTUAL_V2.json \
  --output /home/hank/ihear-lab/deep_learning_method_exploration_v8/families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/context_kernel_diagnostic_v1/diagnostics/GATEK_ONCE_V2
```

V2不会写V1输出、真实run、CURRENT、checkpoint或四meanfreeze，不读取新验证结果。未来数值结果仍只解释原四个已暴露固定behavior draw，不能称资格/JF/JM改进、fresh onpolicy、方差结论或新物理收益。
