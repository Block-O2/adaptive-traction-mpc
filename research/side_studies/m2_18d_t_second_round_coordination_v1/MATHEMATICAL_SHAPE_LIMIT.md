# Fixed-boundary quintic shape limit

这是数学证据，不是Human物理结论。令原quintic为q0，任意C2分段干预q=q0+h保持外端q、dq、ddq及duration。三次分部积分，边界h、h′、h″为0，内部C2边界项抵消，q0的六阶导数为0，因此∫q0‴·h‴dt=0。故∫||q‴||²dt=∫||q0‴||²dt+∫||h‴||²dt，原quintic已是这些外端合同下的reference积分平方jerk最小解。

内部q-only平滑可以改变velocity TV、加速度峰或其分配，但不能在同一段外端合同下继续降低reference积分平方jerk。实际Human闭环响应并不受上述最小值直接约束，仍可能通过改善tracking降低实际jerk；必须看native结果。不能用这个数学事实宣称本轮负结果必然、证明Human波动不可避免，或替代物理资格。

对实际执行的每个reference对象，独立按多项式精确积分的原/新jerk energy在audit/INTERVENTION_EXECUTION_AUDIT.json中。此限制支持避免无依据增加内部q点密度，下一步应优先明确外端通过速度、局部闭环响应与允许改变的协调合同。
