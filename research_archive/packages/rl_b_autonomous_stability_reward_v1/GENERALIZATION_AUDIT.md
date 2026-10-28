# 合法独立初态审查

状态：**BLOCKED_CURRENT_RUNTIME_INTERFACE**。

直接证据：冻结 `pure_rl_env.py:reset` 只向Gym、action_space传seed，随后调用固定case/options的原runtime；options没有用于改变物理初始化。`ReadyEnv.reset` 明示保留nominal确定性物理；`native_rl_env.py:runtime_kwargs` 仅提供native proposal callback。不同reset数字不能产生独立患者或初态。

本轮不修改Human/robot/cuff物理、任务目标、期限或初始化流程来制造泛化。所有物理评价准确标记为nominal开发评价。最终未见动作RNG只检验随机策略动作流，不能授予物理初态泛化资格。训练/dev/动作流holdout三类身份均保存于配置；候选设计使用dev，最终动作流在版本冻结后才读取。

尚缺：原runtime支持并经过工程准入的合法初态接口、冻结开发初态族、独立未见初态集合及各候选共同划分。该缺口不阻止隔离开发训练，也不能被开发成功覆盖。

## 原native启动路径补充复核

不只检查Gym包装：原`run`从`spec.start_return_target_rad`构造`start_q`；`_initialize_loaded_runtime`把该值复制为physical_initial_q_rad并reset物理。case的task.start_deg同时定义任务RETURN目标，改变它会重定义本轮固定任务。已有session_context是完整prefix状态恢复合同，没有为本PPO研究准入的独立初态采样接口。故当前BLOCKED准确限制在当前冻结PPO接口和准入合同；不宣称未来无法新增合法初态支持。直接hash和数据流证据见`audit/GENERALIZATION_INTERFACE_AUDIT.json`。
