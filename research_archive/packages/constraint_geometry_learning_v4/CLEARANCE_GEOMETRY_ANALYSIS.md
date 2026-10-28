# Clearance几何与原反馈机制

CONFIRMED：保留原几何。令 φ=q_h−q_k，a=p_x,z cosφ+p_z,z sinφ，z_c为原模型cuff中心。袖套两端约束为 g_±=z_c±La−r√(1−a²)−z_b；原包络 g=min(g_−,g_+)=z_c−L|a|−r√(1−a²)−z_b。相同阈值下min≥d与两端都≥d点态等价。原combined envelope还保护shank、thigh、bar、adapter；袖套双端点不能替代这些组件。

原guard以因果Human接口pose/twist给出gap及gap-rate，以估计Human q/dq与校准几何计算模型梯度/曲率。关节梯度步长10⁻⁵rad，方向模板q±h·dq的h=10⁻⁵s。h虽数值相同，单位不同。原FAST/torque更新5ms，native物理0.25ms，不能把10μs差分视作执行周期。

A：a=0处的min连续不可微。两光滑端点的右方向导数最小值为ż_c−L|ȧ|（再加径向项）；原sign(0)=0公式在精确零轴时没有给出该方向导数。远离|a|=1各端点局部光滑；竖直轴的径向sqrt仍可能退化，不能宣称全球光滑。

B：方向差分跨水平端点分支时，曲率额外项近似−2L·max(h|ȧ|−|a|,0)/h²。这是包络有限差分的大负项，不是真实gap加速度，也不是gap跳变。固定非零偏置状态在h足够小时回到单支，不能一概声称h→0发散。极小h还有浮点抵消。零物理解析/差分结果见analysis/ENDPOINT_STUDY.json。

C：原shortfall/active-set/box激活为控制模式，随后filter、allocator、supervisor、scheduler各有独立模式。D：guard返回Human二维Nm修正，再经实际6轴robot扭矩分配与饱和，二维修正不等同实际六维torque；post-filter约束另行记录。E：真实Human q/dq、a、jerk只从原native重建，保持原未滤波gradient口径。

原required=2(d−g−Tġ)/T²+adverse，d=10μm；C19实际T=.08s、adverse=1.5m/s²。原单约束迭代投影在加速度box内尝试修正，返回constraint_satisfied；空集/饱和并未在该函数中强制STOP。原conservative_shank模式可调用显式2D半空间投影，空集返回clip(a)和False。后续原安全、任务、receipt和supervisor仍保留；不能把局部标志当成整个系统停止证据。

C19和PPO第9次原函数对历史gap/rate充分标量的精确重放再次执行；模型曲率及correction误差为0。历史trace cuff pose并不自动等于guard消费的Human接口，试用该proxy所得gap/rate误差被明确拒绝，见analysis/CAUSAL_ENDPOINT_REPLAY.json。不能由其轴偏差推断真实模型姿态偏差。新运行branch_diagnostics直接保存传给guard的model/state/interface量，原返回correction不变。

## clearance与实际几何的关系

原interface是`EstimatedInterfaceState`。`controller_interface.py:InterfaceAwareHumanStateObserver`用robot attachment pose/twist和cuff力/矩，经名义Kelvin–Voigt界面的有记忆因果反演，得到Human pose/twist；然后几何逆解形成估计q/dq。因而原字段虽称measured_sleeve_gap，它不是直接读取隐藏Human真值或直接测量真实collider最低点。trace中的cuff pose是robot attachment侧量，不能跳过柔顺位移/转角与observer历史，直接代替Human interface。新日志记录的是guard实际消费的该因果估计接口，仍不是oracle几何。保护证明还需覆盖界面参数误差、反演离散误差和估计不确定性；已有3.2μm观测误差不能自动升级成全局界。真实shank/contact和因果估计sleeve的原评价分别保留。

## 局部模式与误差敏感性

六个新微扰显示：跨支曲率幅度虽不同，超过可行范围后原guard在相同加速度box角点饱和，实际jerk RMS接近同一平台；因此不能用曲率下降比例预测运动改善。原native jerk保持未滤波。冻结局部响应模型的严重冲击参数带约为x[3]相对C19的[−0.000331,0.000403]，仅适用于已冻结同父同cell。10μs差分半宽远小于5ms采样周期；额外φ误差会移动窄失败带。analysis/BRANCH_UNCERTAINTY_SENSITIVITY.json列出假定误差1e−8至1e−5rad的敏感性，不把很小LOO拟合残差当成真实observer误差界。

## 关节梯度模板与曲率模板分开

C19和PPO第9次的两个q±10⁻⁵rad关节梯度模板也跨端点分支，原梯度逐项精确复现。水平轴局部可写成∇g_FD≈∇smooth−L·clip(φ/ε_q,−1,1)(1,−1)，是在较宽q模板内对端点法向进行数值平均；这不等于同时保护两端点。相较之下方向曲率模板的关节幅度是h·dq，二者带宽和单位不同。固定原gradient、a_requested、因果gap/rate，只在算术中把曲率替换为单端点曲率，两例shortfall都变0；直接确认该局部控制修正的计算触发来自方向曲率项。此算术干预没有应用于物理，独占物理中介归因仍未建立。详情analysis/GRADIENT_STENCIL_STUDY.json。
