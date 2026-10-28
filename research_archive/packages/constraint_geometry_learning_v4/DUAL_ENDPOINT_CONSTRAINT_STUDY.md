# 双端点约束研究与晋级门

CONFIRMED：2,437个远离竖直奇异的解析检查点，min(g_−,g_+)与原sleeve gap差为0；梯度差分最大误差约1.28×10⁻⁹m/rad，方向曲率差分误差约4.67×10⁻⁸m/s²。检查是数值核验，点态等价另有代数证明。几何本身没有修改。

设v=(1,−1)，a'=−p_x,z sinφ+p_z,z cosφ，t(q_h)=p_x,z cosq_h+p_z,z sinq_h，ρ=√(1−a²)，c_±=d_c±L。∇g_±=l_t t' e_h+(c_±+ra/ρ)a'v；H_±=−l_t t e_he_hᵀ+[−(c_±+ra/ρ)a+r(a')²/ρ³]vvᵀ。模型曲率为dqᵀH_i dq。各端点通常相对加速度阶2；梯度退化或实际torque映射退化必须单列。

开发候选同时施加∇g_i·a≥required_i−dqᵀH_i dq，并与原加速度box相交，使用原exact 2D半空间投影；禁止依次投影而漏掉第一端点。双约束冲突、退化梯度与box可产生空集。点态等价不保证该QP递归可行，也不保证filter和robot饱和后约束仍成立。

保护缺口得到构造性说明：g0=20μm、ġ0=−.02m/s、T=.08s、adverse=1.5时，原所需加速度为1.996875m/s²；真实恒定加速度2满足该不等式，T末gap为4.82mm，但5ms处gap已为−55μm。这是标量反例，不是声称该危险轨迹在plant发生。它说明该时域末端条件本身不是连续安全证书，不能因双端点同样满足它而晋级。

已推导更强的条件关系：若真实每端点gap在[0,Δ]的加速度下界为α_i，且g_i/v_i为有效因果下界，则要求α_i≥sup_{0<t≤Δ}2(d−g_i−v_i t)/t²可保证整个采样间隔。令c=g_i−d>0，先取−2(c+v_iΔ)/Δ²；当v_i<0且t*=−2c/v_i≤Δ时，再与v_i²/(2c)取max。该条件对10,000标量样本核验，最低残差约−4.6×10⁻¹⁷m。上述反例在Δ=5ms时需要20m/s²。详情analysis/SWEPT_GAP_CONDITIONS.json。

尚缺：因果测量g/v误差界、模型Hessian随时间变化界、实际最终饱和torque到端点加速度下界、contact/Human响应误差界，以及空集时可证的backup/stop。原1.5 adverse常数不是这些界已经成立的证据。原1201节点quintic reference certificate也不是实际Human闭环证书。

DECISION：双端点候选只执行零物理诊断，未接入物理、未继承正式guard资格。保留原guard，按预授权备选研究分支感知上层预测。不能将NOT_PROMOTED写成“证明双端点无效”或“证明不可实现”。

## 相对阶与实际输入的区别

前述“二阶”针对虚拟Human加速度a_H或直接Human广义输入。实际plant施加的是robot torque，经allocator、robot动力学和柔顺cuff作用于Human，不能直接把∇g·a_H约束当作robot torque上的相对阶二CBF。

作为结构性说明，在无额外刚性耦合的两质量KV模型中，m_H q̈_H=K(q_R−q_H)+D(q̇_R−q̇_H)，m_R q̈_R=u_R−对应界面力。h=q_H−d时，ḧ不含u_R，而三阶导数含D/(m_Hm_R)u_R；若D=0，输入可到四阶导数才出现。这是简化模型推导，不是对本3D系统所有状态、接触和奇异位置的相对阶定理。

源码traction_mpc_stage3/coupled.py的robot executable command路径、spring_damper_interface.py和controller_interface.py的因果反演共同说明了这一层次区别。现有incremental response、response_s和adverse是局部近似，不能取代实际输入/接触/离散模式的可验证保护关系。因此2D acceleration QP的可行解，并不直接保证最终actuator能在所需时间实现它。
