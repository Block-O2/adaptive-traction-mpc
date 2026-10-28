# Learning的实际决策贡献

GP要补足粗名义负荷与原motion结果之间的系统残差。它只使用各自已完成历史；完整但motion不合格的样本仍用于成本/余量训练，未完成任务的完整成本保持未定义，并保留completion标签。经验completion score不是校准概率，GP区间不是安全保证。

1. 数值：预序开发统计见 `LEARNING_DECISION_RESULTS.json`，模型逐次变化且测试点由模型选择，不能作冻结无偏泛化成绩。
2. 排序：冻结失败域的Spearman和成对顺序见下表；完整但失败的成本仍保留。
3. 选择改变：自适应阶段已有16条带GP的预序候选，其中14次与同池名义选择不同。
4. 实际价值：先选定最早两次改变的proposal，再对两方动作都进行冻结原链实测；结果如下。

|固定反事实对|原门赢家|Learning JF|合格|同池名义JF|合格|
|---|---|---|---|---|---|
|1|NOMINAL|1399.857062|False|1399.766938|True|
|2|LEARNED|1399.757264|True|1400.770078|True|


冻结6个随机失败域的结果（同状态，非新患者；模型在打开前冻结）：

```json
{
  "all_cases": 6,
  "complete_cost_defined": 6,
  "incomplete_cases": [],
  "motion_failing_complete_cases": [
    "LOCKED_REPEAT_FAILURE_DOMAIN_02",
    "LOCKED_REPEAT_FAILURE_DOMAIN_05",
    "LOCKED_REPEAT_FAILURE_DOMAIN_06"
  ],
  "RMSE": [
    3.382872667113556,
    0.6969093767000903,
    0.12216173365055019
  ],
  "MAE": [
    2.752306072554082,
    0.5625350675617611,
    0.09399885799062961
  ],
  "empirical_95pct_coverage": [
    1.0,
    1.0,
    1.0
  ],
  "coverage_n": 6,
  "JF_Spearman": 0.8285714285714287,
  "JF_pairwise_order": {
    "correct": 13,
    "ordered_pairs": 15,
    "accuracy": 0.8666666666666667,
    "ties_excluded": 0
  },
  "predicted_margin_pass_but_not_qualified": [],
  "motion_margin_not_a_safety_certificate": true,
  "completion_Brier_descriptive": 0.01732423827723453
}
```

补充参考响应模型使用共同的17条因果控制历史（强固定+16个单向设计），学习参数到实签q/dq/ddq的有符号局部响应，再由原估计Human模型与allocator算负荷。仅用于离线排序，实际控制仍接收普通modal参数、经过原certificate和执行链。相同17条历史及相同候选池的传统成本响应模型、原粗名义模型各有一个冻结实测对照；另测两个参考响应候选。额外4次测试、cold parent及B/H150/strong均计账。它没有学习跨状态模型，没有原生motion预测或校准不确定性。

|冻结测试|完整|合格|参考响应预测JF|传统成本预测JF|实际JF|参考响应预测JM|传统成本预测JM|实际JM|
|---|---|---|---|---|---|---|---|---|
|RESPONSE_MODEL_01|True|False|1397.863943|1397.714495|1397.711027|108.064186|108.094352|108.076503|
|RESPONSE_MODEL_02|True|False|1397.886565|1397.783431|1397.820457|108.073885|108.099234|108.086399|
|RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL|True|False|1397.863943|1397.714495|1397.711027|108.064186|108.094352|108.076503|
|RESPONSE_NOMINAL_COUNTERFACTUAL|True|True|1400.348351|1400.838311|1400.844093|105.845986|105.818261|105.996606|


参考响应候选最佳合格JF=无合格候选（已实测2个）；同数据传统成本模型JF=1397.711027（完整但不合格，仅诊断）；同池粗名义候选JF=1400.844093（合格）。 相同动作的多次执行只证明复现；不当作不同学习决策。预测误差另按唯一动作去重，attempt加权误差不作为独立新动作数量。

没有把RMSE、排序、选择改变和最终实际合格JF互相替代。


相同32候选预算下，C最佳JF=1399.188323，最佳A/B=1398.549121；C额外降JF=-0.639202 N·s。C未超过本轮最强传统主对照。

GP worst_ratio结构下界为sqrt(.95/1.05)，因为其定义包含累计行程比的双侧约束；低于该界的mean为结构性外推错误。没有为改善结果修正运行中的模型。

精确同池决策重放：{'status': 'PASS', 'adaptive_proposals': 16, 'decisions_changed': 14, 'GP_mean_changes': 12, 'uncertainty_layer_changes': 3, 'screen_layer_changes': 14, 'screen_had_candidates': 16, 'chosen_motion_predictions_below_structural_bound': 13}。各层次差异只证明算法选点改变，未测动作的物理好坏仍未知，详见 `GP_DECISION_LAYER_REPLAY.json`。

冻结双动作原链实测胜者计数：{'NOMINAL': 1, 'LEARNED': 1}。


补充结构有界motion GP诊断状态=EXECUTED_FROZEN_DIAGNOSTIC。它与原最终GP使用相同32条训练记录、相同核，提前冻结6个原登记点的预测；只检验目标结构和筛选误放/误拒，未参与任何候选选择。 在6/6已完成点上，原/有界模型worst_ratio RMSE=0.12216173365054776/0.20595165182467848，95%覆盖=1.0/0.5，误放=0/0，误拒=2/2。 有界性不是校准或安全保证，详见 [结构诊断](STRUCTURAL_MOTION_DIAGNOSTIC.md)。
