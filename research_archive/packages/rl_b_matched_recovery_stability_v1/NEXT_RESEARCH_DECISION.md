# 下一研究决策

唯一下一步：审阅本包后，单独授权 **H1：小步继续更新能否保留成功均值策略** 的有界开发验证。当前STOP，不执行下述方案。优先改训练策略，保留原reward/动作/安全合同；证据尚不足以先大改reward或替换PPO。成功checkpoint应始终保留为版本化父策略，开发选择按预先冻结完成门进行，不能覆盖原80集失败或追认3-seed成功。

## H1（首选）：固定小学习率减少累计漂移

- 支持证据：050→080 mean/实际动作链已改变，RETURN可行性丢失；每seed继续120epochs、188–220 Adam步而无成功策略保留门。单次记录KL小、clip fraction0，故先检验累计更新步幅，不预设“爆炸”。
- 最小实验：从原3份050 checkpoint做paired continuation，原LR3e-4对照与LR3e-5实验，其他PPO/reward/rollout/动作完全相同；每5episode保存父子checkpoint和固定观测Gaussian KL，定时评价deterministic与预注册sampled RNG；不按JF挑seed或checkpoint。
- 训练预算：3 training seeds ×2 arms ×30episode=180episode（失败也计）；原两个成功seed为主要终点，1106823814为预注册失败control。不能把只挑两个成功父策略的验证叫从零3-seed复现。若资源/开发准入不足则先停止，不自动缩小到有利seed。
- 成功标准：两原成功seed的最终30集后mean在nominal均保持2/2完整原runtime；预注册4个真正独立且合法的初态，每初态两次，实验臂每个退化seed至少7/8完成且不低于其050父策略；所有原安全/causal审计通过。其余control描述性报告。只有同时优于对照的保留结果才支持该机制，不据任一seed偶然成功推广。
- 失败标准：任一主要seed nominal丢失完成、独立初态显著掉出预注册门、审计异常或比对照无保留优势；全部负结果留存。若对照也不退化，结论为对该训练随机性下的机制不确定，不强行判PASS。
- 初态：需要4个未用于本轮诊断/调参的合法独立物理初态；先冻结生成规则并做工程准入。现有reset(seed)不改变nominal物理，不能用四个seed数字冒称四初态；如果当前接口不支持合法独立初始化，该部分BLOCKED，不放松门。不得借此更改ROM/torque/cuff/Human/任务期限。
- 合同影响：只改变PPO学习率的开发配置；原2D进度动作、物理、安全、task、reward不变。新配置需版本化开发准入，不能继承原冻结hash或正式资格。

## H2（仅H1审查后再考虑）：聚合完整episode减少singleton权重噪声

- 支持证据：65/240单transition；76/240出现singleton minibatch；原SB3对singleton跳过advantage标准化，critic解释力弱。reward/GAE的存储算术本身已通过，不先改reward系数。
- 最小实验：同原LR3e-4，收集完整episode累计至少64 transitions再更新，保留所有episode边界与terminal=0；minibatch16，并使用预注册划分保证无单样本批。对照仍单episode更新。每transition仍4epochs，单列真实Adam步和更新次数，承认更新节奏改变也是该机制的一部分，不能伪称优化暴露完全相同。
- 训练预算：3 seeds×2arms×30episode=180episode，独立授权、与H1不自动串行。30集结束的未更新余量必须按预注册终末批规则处理并保留；不能静默丢transition。
- 成功/失败：沿用H1的父策略保留、nominal和独立初态标准；只有无singleton且保留完成更好才支持假设，singleton消除本身不是学习成功。完整分布和失败必须公开。
- 初态及合同：同H1，先准入真正独立初态；动作/安全/物理/task/reward不变。只改rollout组织和advantage/批组织的开发版本，需重新冻结配置。

Stage2低force/平顺优化继续NOT_RUN；正式campaign为NOT_READY。原B/H150离线评分已恢复，但新live matched同父状态链、full-fork可移植性、G4严格矩阵和独立初态稳定性仍是独立门，不能用本轮PASS替代。没有扩容依据，不调整Hetzner或发起收费计算。
