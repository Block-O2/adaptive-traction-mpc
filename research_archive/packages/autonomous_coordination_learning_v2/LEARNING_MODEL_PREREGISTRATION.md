# Learning模型事前合同

在CORE任何新物理START前冻结。缺失信息是名义参考负荷没有闭合的实际tracking、离散调度/准入响应和原motion余量。

完整任务的JF/JM及原motion ratio用于同一固定上下文RBF GP残差；完整但motion失败仍保留其真实成本和余量。任务不完整时完整JF/JM未定义，不填成0、不当作低成本训练标签；这些样本保留在模型的all_feedback_attempt_ids、undefined_full_JF_attempt_ids及二元completion标签中。

另以全部本臂已完成/失败结果建立固定length .55的kernel-weighted completion score，prior(.5,.5)，作为阈值 .65 的候选筛选启发式。它不是校准概率或安全证书。GP motion/JM screen与completion score如果没有候选通过，会记录screen fallback，并保留原真实门作为最终 authority。名义B和直接A各自使用其历史完整资格选best，C不读取其它臂未公开反馈。

事前预测、模型/训练ID和候选池必须早于START。冻结后在固定独立失败域与新prefix计算覆盖、排序和completion-score错误；不因看见失败改阈值。所用仿真真实motion余量是完成后评价标签，不宣称患者可用的新增传感能力。
