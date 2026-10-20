# 下一研究决策

本包已STOP；以下只登记下一项决策，不启动实验。

冻结D在W1完整资格：失败；失败项=['velocity_deg_s/p95_abs', 'acceleration_deg_s2/max_abs', 'acceleration_deg_s2/p95_abs', 'jerk_deg_s3/rms', 'excursion']。

最小下一步：保持W1、原D及所有失败不变，先根据本包控制结果另行预注册一个有界motion修复合同。优先处理D之前已出现的RETURN1速度负担以及末段累计加速度/下冲；允许改变的reference量、幅度/时长边界、原current-state certificate/admission与全部资格门必须先冻结。不得把按W1修改的参数重新命名为原D。

修复开发与新prefix资格应分开：W1与本轮控制均已暴露，修复若依赖它们，应先开发，再用新的合法prefix进行matched B/T/修复候选验证和合法重复。若不能构造合法、匹配且通过原门的控制，停止并记录具体certificate/admission阻塞，不直接设置Human状态。

18D+Waypoint第二轮优化的重启条件：有明确适用域、经过原task/safety/motion/receipt全资格与新prefix验证的冻结基线；预算与独立验证合同另立。数学平滑或局部峰降低不足以重启大规模搜索。

不训练RL/Q/Neural Q，不自动创建下一研究包。

新增重点：W1 D在16.700s的实际Human加速度/jerk峰之前，16.695s有allocator/command脉冲，未观察到clipping、接触或receipt过期。终末RETURN5请求16.540s之前，膝velocity/acceleration高值样本已达4234/4353，均超过保留原时长容差后允许的3827个；膝excursion也已超过最终B+0.5°。因此严格晚于该请求的终末修复不能使W1全门合格。下一项最小修复实验应另立候选，预注册一项更早RETURN1的有界reference-timing改动，固定背景、原18D/T与D姿态规则，通过原证书后再运行配对物理；完整检查早期p95、excursion和终末脉冲，不保证一定可修复。原D不变。此处只提出下一合同，不运行。
