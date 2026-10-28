# PPO 功能测试

PPO_UPDATE_SMOKE_PASS=PASS；CHECKPOINT_RESUME_PASS=PASS。类别全程 UNQUALIFIED_TRAINING_SMOKE。不是正式训练，也不是RL学习成功。

随机初始化CPU MLP，actor/value各[16,16]，seed20261021，单环境，gamma=1，n_steps=8、batch=4、epoch=1。原robot–cuff–Human MuJoCo、证书/准入/governor/真实native执行链完整保留，无B/H150教师或模仿权重。

初始进程PID27443用8个真实transition完成1个PPO训练epoch、2次Adam step；保存checkpoint并退出。新进程PID27885核对policy、完整Adam tensors/超参数、Python/NumPy/Torch RNG、num_timesteps、n_updates、total_timesteps、progress_remaining和episode_num，8项完全一致；再用8个真实transition执行第2个epoch，Adam step计数2→4，权重再次变化。第三进程PID28279载入最终checkpoint且policy/optimizer冻结，执行完整有界任务评价。

总计2次PPO train调用、4次实际optimizer梯度更新。梯度裁剪后L2约0.5，全部有限非零，每次权重改变。不能把SB3 n_updates=2或13个parameter tensor的Adam step总和52误称为真实optimizer调用次数。checkpoint内部历史命名 `gradient_optimizer_steps_total` 是逐parameter step之和26/52，正确全局次数见 PPO_UPDATE_RESULTS.json。

两个训练rollout各8 decisions后，分别额外19个动作完成当前episode供raw审计；这38个tail动作没有进入optimizer。共16训练decisions +38审计tail +24冻结评价 =78真实RL决策；native physics343520步（含commissioning），其中TASK222920步，3个完整或失败终态episode。

恢复采用已声明的fresh physical episode：不恢复MuJoCo中途状态/partial rollout。policy、optimizer、RNG和SB3训练计数精确恢复；checkpoint `episodes_completed` 是本进程完整物理episode数1，累计数沿不可变parent链为2，另评价1个。SB3 episode_num为0是因为训练收集的8步没有包含终态，后续终态发生在审计tail；不伪造这个计数。

|进程|TASK s|结果|完整reward分项(progress,completion,force,variation)|
|---|---:|---|---|
|ppo_initial|19.280|COMPLETE|[14.999999999999996, 20.0, -0.288716042049172, -0.002147906464875215]|
|ppo_resume|19.840|ABORTED|[1.7763568394002505e-15, -10.0, -0.3019532769320867, -0.0017319750102000135]|
|ppo_evaluation|16.610|ABORTED|[1.7763568394002505e-15, -10.0, -0.25253031050231356, -0.002373309281909684]|

冻结评价0/1成功，16.610s原planner拒绝将进入shank-table geometry的候选并ABORTED；这表示保护拒绝了该提议，不是实际Human发生穿透。PPO_TASK_SUCCESS=FAIL、PPO_FULL_QUALIFIED=FAIL。首个训练episode19.280s完成时policy中途更新，不作为冻结策略评价成功。

3/3新episode独立force/moment/phase积分、reward、终止、真实Human运动、certificate、immutable source、receipt/native torque ownership和executor退出全部PASS。恢复失败episode总progress仅1.78e-15浮点误差，completion=-10，无成功奖励。

两代checkpoint模型SHA256：
- 初代 `6f2803b17ee8d103d8cca0bc75fbe96a08803833bafc5f5ad339083351eade6e`
- 恢复更新后 `d1988bd9a36de3b1803aa70c2e895e36388ca80b4dc5fa14b5837d47b47d1a2a`

各zip/RNG/metadata SHA与逐字段恢复核对见 CHECKPOINT_RESUME_AUDIT.json。训练loss见 PPO_UPDATE_RESULTS.json，所有原始RESULT/START/END/日志保留在runs/。

物理子进程合计238.349s，含guard启动合计247.989s；用户CPU 240.694s、system CPU 4.242s。单进程峰值RSS 958.6MiB，最低可用RAM 28.551GiB，高于6GiB。guard将进程限制在单CPU affinity、单线程，无并行扩展。

当前实际端到端78/238.349≈0.327 decisions/s，约1441 native steps/s或0.360仿真秒/墙钟秒。此数字包含commissioning、tail和日志；16个优化器训练样本/两个完整审计episode的总wall是功能测试效率，不是长期训练吞吐估计。3个episode平均79.4s。资源足够最小工程测试，尚无长期稳定性/多环境扩展证据。
