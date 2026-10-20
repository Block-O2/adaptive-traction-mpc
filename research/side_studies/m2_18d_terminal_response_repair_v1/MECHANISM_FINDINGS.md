# 机制证据与受控修复

本轮找到可合法实施、可重复的N2末段运动修复。唯一因素为最终OUTBOUND suffix由原0.220s改为0.330s；原18D参数、此前所有schedule、最终target/通过速度、request/activation和40ms bridge保留。原fixed-duration接口完成数学、连续几何、mechanics检验；真实physics继续接受原current admission与100ms lifecycle，无旁路。

## 直接受控证据

独立对齐检查在6.830s splice之前，参考q/dq/ddq、真实Human q/dq、施加robot torque和contact force均保持在1e-10原单位误差内；全部上游schedule逐字相同。首次参考/命令差异=6.835s，5ms实际运动差异=6.840s。新轨迹的accepted metadata、request id、实际activation、native positive receipts和每个native step已贯通核对。T恰好有一个ACCEPTED末段干预，未靠接口拒绝后fallback冒充修复。

N2 T实际末段膝amax=52.141224732°/s²；完整TASK膝amax=75.571947196°/s²，峰值已转移到原先存在的2.93475s前段。原18D完整峰90.058623°/s²下降16.085829%；对匹配B比值=1.048249290，通过1.10原门。完整motion/fairness所有冻结条款通过，不只是膝最大加速度单项。该变化在相同完整父状态的确定性重复中逐字段复现。

完整JF=1409.539442142N·s，对B降力=2.410231%，对E变化-0.022167424N·s。这个微小力差不构成额外降力里程碑，结论是保留18D收益的运动修复。完整阶段时长9.005/1.020/9.005s，TASK19.030s，HOLD和RETURN没有缩短。

## 能推断到哪里

同完整live状态、相同上游运动，只改变合法末段参考时间形状，实际膝峰和资格随之改变。因此在该确定性模型与N2条件内，末段参考时间形状对异常具有可控的总效应，且无须先消除“hip先到”便能修复N2原motion失败。它不证明该因素是跨状态唯一根因，不证明某个allocator分量放大系数，也不能把数学参考amax等同真实Human amax。

源代码可直接确认的规则、存档的时序事实、基于时序的响应解释和仍未分离的机制，在`N2_TERMINAL_DIAGNOSIS.md`及`provenance/SOURCE_RULES.md`分别标识。clearance/acceleration projection在存档末段未激活，torque clipping为0；没有证据归因于这些限制器的突然切换。FAST位置/速度反馈、allocator、被动Human和contact之间的具体中介贡献仍未独立分离。

## 新prefix验证

U1事前固定为OUTBOUND=[[-0.075,-0.045,-0.05]]、seed=2026101801。107份历史执行结果/完整fork context检查未见该prefix执行；上一轮仅登记未运行。T未根据U1重选。

U1 T完整JF=1409.836483114N·s，对匹配B降力=2.417010%，motion=PASS，原绝对安全=PASS，causal=PASS。新prefix综合资格=PASS 1/1。重复不增加状态数；这是同一Human的remaining-suffix验证，OUTBOUND0已由prefix消费，不能称整串策略未见初态泛化或不同患者验证。

![N2受控参考与真实响应](figures/N2_intervention_response.png)

