# 首个共享物理rollout上的Reward梯度竞争

两seed各自R0/H2与R1在首次更新前具有精确相同的obs、raw actions、old values/logp、episode边界及policy身份。使用已实际训练时保存的Reward/GAE目标、同一固定minibatch排列，在未更新参数处逐批计算梯度，禁止Adam.step。所有批次均值如下：

|seed|首个共享完整rollout transitions|R0/H2 critic平方范数占比|R1 critic占比|R0/H2 actor裁剪后范数均值|R1 actor均值|
|---|---|---|---|---|---|
|1495656323|80|98.712459%|99.788376%|0.04494253|0.01792163|
|1630784693|77|95.751798%|99.740261%|0.08216451|0.02221753|

R1在此局部共同样本上加重critic主导，使joint norm clip后actor梯度更小。不能把放大失败惩罚假定为改善actor信用分配；也不能据此否定R1可能保留mean任务的真实结果。这里没有模拟实际shuffle顺序、Adam动量、后续epochs或新的闭环访问分布，不是唯一优化根因或任务资格证明。
