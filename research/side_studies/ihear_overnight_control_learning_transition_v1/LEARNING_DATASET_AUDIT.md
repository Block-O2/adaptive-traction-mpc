# 数据审计与历史设计诊断

历史线性Q/M2的Q(s,p)=a(s)+b(p)，比较同一状态候选时a(s)相消。状态导致的mask/carry变化不是学习到的state-conditioned ranking。来源：CURRENT_RESEARCH_BASELINE.md、b_native_q_realtime_integration_v1/REPORT.md与Q_STRUCTURE_AUDIT。

历史motion-aware Neural Q的80条合法branch row只有13个snapshot与4条父轨迹，不能按80个独立状态解读。32×32模型两个诊断测试state的mean regret为9.9306 N·s，linear为1.6207 N·s；没有显示优势。早期96D ridge包含显式交互，不能一概断言所有历史线性模型都没有交互。来源：m2_neural_q_motion_v1/REPORT.md。

scratch SAC的22次正式评估全部OUTBOUND失败，replay缺少HOLD/RETURN完整成功覆盖；降低rejection没有转化为完整任务。DAgger/anchored SAC另有任务获取、探索尺度、critic return-scale和资源问题；其更旧动作/任务/时序接口与本轮H150完整资格并不自动等价。来源：single_human_sac_failure_diagnosis/output/SAC_SEED1_300K_FAILURE_DIAGNOSIS_REPORT_V1.md、dagger_anchored_sac_v2/output/DAGGER_ANCHORED_SAC_V2_REPORT.md。旧的任务成功不是本轮motion合同通过。

因此，本轮优先采集少量同完整live parent的配对完整结果，保留全部失败，使用小模型。既有W1/W2只用于历史审计和开发，不能再称本轮未见测试。原始native truth只用于离线motion标签；七个在线特征在live decision boundary写出，不从未来trace反向挑节点。各动作必须在第一次姿态差异之前具有相同特征，并由完整fork hash、父进程未变化和实际receipt共同证明配对。

机器可读逐行合同见derived/DATASET_*.json及npz；proposed action、accepted/rejected、实际参考和receipt、完整结果、资格、cost分开保存。失败/partial/父对照不伪装成成功动作。TRAINING模型身份与split检查见models/VALUE_FREEZE.json及最终PACKAGE_VERIFICATION.json。实验结束时由结果报告补充实际行数、合格数与缺失，不预填。

## 最终实际规模

11父状态、44动作行，其中33行完整合格；其余保留失败标签。train/validation/test分别6/2/3父状态。Q测试分支另计3条，真实重复pilot单列，不混入冷状态训练集。完整START=83，父进程/fork/失败/边界都计入；详见ATTEMPT_ACCOUNTING.json。没有不同Human数据。
