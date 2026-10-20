# 历史MLP恢复

**CONFIRMED**：至少两条历史线，特征合同、数据与目标版本不同，不能混为同一线性Q对照。

## 原生120D/K3（直接相关）

脚本 `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/code/train_native.py`，feature/candidate `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/code/native_core.py`，物理分支 `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/code/native_data.py`，原DATA与snapshot在output，trace在source/results。checkpoint已恢复：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/weights/frozen_Q_v1/weights.npz` 同时含原linear、Q MLP和G；仅只读Q、未训练G/P。SHA256 `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9`。

MLP=120→128 ReLU→128 ReLU→1，32,229参数；输入state/history、candidate、carry/count通过联合全连接建模，具有state×plan交互能力。训练seed2026100611，Adam lr0.001、1000 epoch、每20 epoch评估；loss=标准化absolute MSE+10×同状态pair差值MSE，最佳Q epoch760。训练集x mean/std只从train计算，std floor0.02；y std floor10N·s。253 train rows、73 dev rows，136同状态train pairs；row多来自同源分支后续状态，不是独立轨迹数。train来源parent_train_0/1，dev parent_dev_0；排除跨split causal58近重复与名义B轨迹状态。原数据集349行，部分行未进入最终train/dev。原training JSON记录排除项、来源hash、完整history与numpy parity。

原验证结果：linear RMSE 8.523668 N·s、mean regret 0.000000、harmful top1 0；MLP RMSE 11.219440、mean regret 0.851245、harmful top1 1。两者5个same-state dev groups含两个零spread组。选择按dev regret再RMSE，故selected_Q=linear；不是因为MLP缺乏交互结构，也不是证明所有神经网络必然差。此历史选择没有独立test gate。

线性native120D模型只做标准化后的线性回归，**没有交叉特征**；当前固定mask/候选排序确为g(s)+h(p)。历史MLP的结构有交互，原验证决策成绩不足以取代linear。

## 更早96D cost-to-go研究

脚本位于 `adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/scripts/value_learning_v1/value_models.py`、`train_value_models.py`、`value_dataset.py`。96D输入包含estimated state/belief、reference、task、continuation与candidate target/delta；MLP=96→32 tanh→32 tanh→1，NumPy CPU、batch256、Adam lr0.003、weight_decay0.001、最多500 epochs、validation MSE patience50。x scale低于1e-6置1，y std floor1。三个seed20260930/31/32；full与1.5s short分别训练。模型按validation **full-return regret**再target RMSE选择，test不参与选择。

train conditions：low_ordinary_early/late、balanced_middle、hip_ordinary、sync_120；validation：knee_ordinary、balanced_high；test：elevated_start、variable_start_120。按physical condition/session划分，同状态candidate留在一起。所有历史条件此前已探索，不能称完全未见科学数据。

| 模型 | val FULL regret | test FULL regret | test top1 | test target RMSE |
| --- | --- | --- | --- | --- |
| mlp_full | 1.2585 | 8.3348 | 0.5000 | 181.2951 |
| mlp_short | 0.6051 | 2.1946 | 0.6667 | 20.5169 |
| ridge_full | 0.6842 | 3.5547 | 0.3333 | 113.2390 |
| ridge_short | 0.6051 | 8.5562 | 0.0000 | 238.9992 |


96D full选择ridge_full_100.0：其validation regret0.6842优于MLP full1.2585。**但short MLP的test FULL regret2.1946优于short ridge8.5562**；不能笼统宣称历史MLP全面更差。short模型的test target RMSE与full RMSE目标不同，不能跨行直接比较。96D ridge具有显式progress/span/beta/phase×candidate_delta交叉项；它不是当前native120D可加线性Q。96D MLP同样具有联合交互。

96D checkpoint保留在原docs/models及Windows `learning_research_v1_evidence/models`；feature合同不兼容120D，不能无定义补零后纳入本轮相同candidate评分。直接离线对照B使用兼容的历史120D MLP。96D实际plan-selection/pilot evidence见 `ONLINE_POLICY_IMPROVEMENT_PILOT.json`；本轮没有重跑旧pilot，没有将cost prediction或ranking成绩等同于host执行收益。

来源原比较JSON `/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/docs/value_learning_research_v1/OFFLINE_VALUE_MODEL_COMPARISON.json` SHA256 `eba58a9cfe6dd5f1a652ce2fe7e3c3e3253c8c4111e04ee15b79fce1b1941822`；原120D TRAINING SHA256 `f55216ef85e30b88a35dfebe56b56d9cf3053def7bd5034de25a326f7e7a9958`。本轮完整source hashes见保护快照及manifest。
