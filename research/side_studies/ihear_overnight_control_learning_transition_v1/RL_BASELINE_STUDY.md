# 受约束RL baseline合同

当前状态：NOT_RUN，尚未启动P2物理或PPO/SAC更新。本文件是一份可复现的设计合同，不代表RL已经有效；最终是否执行由Stage C的科学价值、剩余时间与原接口资格决定。

若启动，必须沿用同一四动作集合、七维因果状态、完整任务及所有原资格。策略输出离散参考动作id，不能输出直接torque。新episode由原冷启动commissioning和合法prefix开始；连续重复必须用既有persistent session与真实inter-rep settle/hold。不得直接设置/回放Human qpos/qvel，不能为了训练另建宽松代理环境。

算法对照可使用离散categorical PPO：CPU单线程，固定seed=2026102401，学习率3e-4、clip=0.2、gamma=1、batch覆盖4个完整episode、每批4个epoch，状态归一化只用开发数据。完整合格reward=-J_F/1000，失败单列failure label并使用-10的预注册惩罚；partial积分不得成为成功reward。此定义必须在真正启动前再次登记精确代码/权重身份与执行预算，不以本文替代运行manifest。

P2硬上限为24 episodes、2,400,000 native steps、3600秒墙钟，先到者停止；所有P2串行且与P1互斥。P1的同父对照与验证START另计，二者不得互相充抵。最后60分钟不启动physics或training，T0+10h强制退出。PPO的24集只能作最小探索，通常不足以声称稳定训练收敛或strong baseline。

独立评价必须在冻结checkpoint后使用全新合法prefix，完整task/safety/motion/causal通过后才报force收益，并与固定H150及价值方法比较总physical成本。仅有能训练的代码或checkpoint不得标注RL_BASELINE_QUALIFIED。Stage C数据不足时优先保留完整合同和负结果，不用昂贵RL掩盖主要学习问题。

## 本轮最终决定

NOT_RUN。P2 episode=0、native steps=0、policy/critic update=0、无训练checkpoint、无训练曲线。V01/V02中本合同的四个RETURN2动作全部不合格，重新探索同一确定性集合不能生成不存在的合格动作；需要先处理动作时点和可行集合。主要实验显示动作资格边界与状态辨识是首先需要解决的问题；在单Human、少独立父状态及24集探索预算下运行PPO不足以提供可信strong baseline。这是研究价值判断，并非已经耗尽10小时。用户允许提前停止低信息量方向及交付最小合同，因此将资源用于L1完整对照、真实反馈pilot及数值/保护审计。此结论只针对本轮有限动作合同，不否定其他合法动作空间中的PPO/SAC；本轮也不能与RL进行经验性能排名。
