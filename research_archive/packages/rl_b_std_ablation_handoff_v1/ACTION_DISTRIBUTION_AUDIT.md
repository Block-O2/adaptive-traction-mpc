# 动作分布与执行身份审计

全状态恢复审计覆盖policy（含critic）、Adam、Python/NumPy/Torch RNG与计数；每次物理前完整核对，前后policy/Adam/计数不变。加载数值如下，顺序为两个协调动作维度：

|父seed|log_std|actual std|checkpoint ZIP SHA256|
|---|---|---|---|
|1495656323|[-0.013552633114159107, -0.018911371007561684]|[0.9865387678146362, 0.9812663197517395]|a2fb5efe642b460ee19ebd0997052997e5157bc21d7931299b2fa10eee8f3132|
|1630784693|[-0.00158663687761873, -0.02863452024757862]|[0.9984146356582642, 0.9717715382575989]|0f559270cdad9ad4a8bbbdb3820713ae38ec516579b09d1c3e4fc8e760a74992|

实现为SB3 DiagGaussianDistribution，state-independent可学习log_std；use_sde=False、squash_output=False，41D因果观测，2D action Box[-1,1]。A读取checkpoint实际各维std；B仅以float32 `.20000000298023224` 参与采样，未写入模型；C直接取mean，不采样、未修改std参数。C继承日志中的effective_std=.2字段未被执行使用，衍生审计明确标记N/A。

A/B使用预生成PCG64标准正态npy，raw=mean+std*z；同父同流共享每个RL决策noise_index，状态分歧后不重新对齐噪声。每次保存mean、checkpoint_std、effective_std、z、raw和clip。`logp_original_checkpoint`只作原分布诊断，B不把它当作有效训练log_prob；本轮所有梯度入口禁止。

原Gaussian raw → 原[-1,1]裁剪提议 → 原native-planner-event进度fraction协调参数 → 原snapshot/certificate/admission → 已接受参考 → robot六关节实际command_torque_nm。提议不是torque；拒绝后旧合法控制仍可能执行。逐请求proposed/executed delta与实际receipt分开，原native审计逐0.25ms证明单owner、torque等于receipt、计数与source-age一致。

同一配对噪声不代表同一状态/相位/物理轨迹。每对保存相同pre-TASK完整物理prefix SHA、相同initial obs、各共同决策obs/mean差以及重叠native时间的Human q/dq差。没有把reset seed当成独立物理初态。

|父seed|A clip分量|B clip分量|A完成|B完成|
|---|---|---|---|---|
|1495656323|97/248 (39.113%)|3/206 (1.456%)|4/6|5/6|
|1630784693|87/196 (44.388%)|35/192 (18.229%)|3/6|6/6|

clip率是各自闭环访问状态上的分量计数，不能当作共同状态的纯参数因果效应。实际apply保存在每次run的TASK_APPLIED_RECEIPTS_v2.npz；完整raw/receipt和SHA仍保留。

source-age两套实测量分别保留：receipt.start_physics−immutable source_sample以及planner activation.sim_time−immutable source_sample；host apply/activation−capture纳秒另报。科学仿真时钟符合原合同，不转化为主机100ms或实时硬件资格。

每次原native/receipt/reward/force/motion审计、独立重算、动作提议数值链核验见 audit/FINAL_FROZEN_RECHECK.json。源码bundle与全包manifest可以定位每次实际执行代码。

## 相同初始观测上的clip分布一阶矩

STD只在pre-clip Gaussian算式中变化，但经clip后的提议均值也变化；不能称为bounded action上纯方差变化。解析一阶/二阶矩已经独立数值积分核对，见CLIPPED_GAUSSIAN_MOMENTS.json。以下是bounded proposal，不是已接受动作或applied torque期望。

|父seed|网络mean|A bounded E[action]|B bounded E[action]|C mean+clip|
|---|---|---|---|---|
|1495656323|[0.7919893264770508, 0.6379732489585876]|[0.507217, 0.420508]|[0.776559, 0.63519]|[0.7919893264770508, 0.6379732489585876]|
|1630784693|[0.6684557199478149, 1.0796456336975098]|[0.433741, 0.656464]|[0.664404, 0.95379]|[0.6684557199478149, 1]|

163父初始第二维网络mean=1.0796456已在边界外；该维解析clip概率由A约54.88%变为B约65.48%，尽管B方差更小。整体闭环clip率与单个坐标/状态的clip概率不可混淆。C部署会裁为1，B的bounded均值约.953790，A约.656464。

STD=.2仍有实际RETURN几何拒绝反例，见失败表。若失败决策raw与clip相等且位于内部，就不能把所有拒绝归咎于边界clip；没有同一失败状态的mean/planner反事实，不能唯一归因为末步扰动还是此前闭环轨迹。

继承raw中的entropy/entropy_mean是原checkpoint Gaussian参考诊断，不能当成B override或C部署entropy。STD_ABLATION_RESULTS另列checkpoint_reference_preclip_entropy与evaluation_preclip_gaussian_entropy；B joint differential entropy约−0.380999，C记N/A。clip后为含边界点质量的混合分布。
