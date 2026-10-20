# Neural Q 数据审计

状态 **EXPLORATORY_SUFFICIENT_FOR_BOUNDED_PROTOTYPE**。存在真实同状态、多候选remaining J_F，不是只有已执行单计划的监督；规模不足以建立独立泛化与motion qualification。

原freeze DATASET：349×120，253train、73dev，SHA256 `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4`。本轮从原 *_DATA.json 恢复branch-start row，**不把其后续相邻value_rows扩增成独立状态**。使用80条候选分支：train47（8完整snapshot、2父轨迹）、validation16（3snapshot、1父轨迹）、test17（2snapshot、1历史诊断父轨迹）。候选分支与完整来源轨迹整体隔离；按causal58 round4排除later-split重复snapshot的全部候选。Cross-split causal58 overlap=0；同snapshot的state/history/carry/count特征一致。原parent_train_0/1重复RETURN因都在train未拆分。验证初始snapshot被整体剔除，烟测outside split；具体排除保存，不按结果删差样本。

原branches由CPU quiescent Linux fork复制完整address-space、物理状态、scheduler/governor/interface、随机状态；branch manifest包含完整状态hash。原BRANCH_GATE确认zero-branch full trace equality、parent before/after digest equal、child waitpid joined。新包仅复用旧trace及receipts，未将JSON hash manifest当作可恢复实时状态，也未以q/dq重建counterfactual。新增物理rollout=0。

监督任务为 `native-certified-committed-K3-suffix-v1`：候选完整合法masked K3后缀由一致的原生B规划/执行规则实现。remaining J_F=完整任务native integral−fork时prefix integral，并核验等于第一个value_row；输入candidate slot重新按counts mask核验。**这不是仅当前slot后立即zero-B，也不是持续Neural-Q replanning policy的已验证价值**。故可训练plan-conditioned剩余cost，但不能直接把offline regret差称为完整host policy收益。

所有回归/比较分支均native-valid COMPLETE。原始失败数量3条保留于 BRANCH_LABELS.json，未变成低成本标签。该筛选是完成与安全资格，原全部source/hash、失败metric和排除原因均保留。

训练只用原生120D：causal55 observation + previous3 + maskedcandidate30 + maskedcarry30 + counts2。真q/dq、未来force与clearance仅作label/审计；无真值部署输入。labels另导出sampled真实速度、加速度、jerk、force peak、remaining moment、tracking、clearance、原native safety、完成、剩余时长与真实幅度。旧分支trace约5ms，辅助motion峰值不具备0.25ms native保证；新host-motion audit有dense native真值，但这些host轨迹没有同状态完整counterfactual候选标签，**未伪造候选价值**。

原生MLP128×128的32,229参数相对该规模过大；本轮限定16×16与32×32，只能作为EXPLORATORY。chosen32×32共4961参数。不能仅凭训练误差评价决策成功。

Test v1_committed_attribution 是已公开历史诊断来源，曾用于fixed-versus-committed归因；它未参与本轮拟合/模型选择，但并非新Human、前瞻性未见数据或独立人口样本。Old Q也已有train/development来源暴露。64个test候选pair来自2个状态，不是64个独立实验。临床舒适度、跨Human泛化、在线个体化均NOT_EVALUABLE。

模型训练前 protocol固定，按validation regret再RMSE选择；选定后才计算三模型的test对照，不根据test重训。Manifest保存全部source IDs、split、normalization、config、model hashes。训练数据 `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_neural_q_motion_v1/NEURAL_DATASET.npz` SHA256 `17cee97378e1e7ed65d9fb5e2776738ec85864c7316023956c6bb8a28bdcc33f`。

主要补数条件：保留能够合法fork/恢复的完整原生执行状态，在独立来源轨迹上覆盖相同合法计划、不同状态下真实最优候选变化，并保存dense运动/force与所有安全结果；原生B continuation语义应先明确冻结。当前仅hash快照不足以新启动counterfactual，本轮不重建plant冒充原Human session。
