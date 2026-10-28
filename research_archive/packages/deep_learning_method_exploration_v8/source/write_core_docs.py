from pathlib import Path
P=Path(__file__).resolve().parents[1]
def write(n,s):(P/n).write_text(s.strip()+'\n')
write('CLEARANCE_GEOMETRY_ANALYSIS.md',r'''
# Clearance几何与原反馈机制

CONFIRMED：保留原几何。令 φ=q_h−q_k，a=p_x,z cosφ+p_z,z sinφ，z_c为原模型cuff中心。袖套两端约束为 g_±=z_c±La−r√(1−a²)−z_b；原包络 g=min(g_−,g_+)=z_c−L|a|−r√(1−a²)−z_b。相同阈值下min≥d与两端都≥d点态等价。原combined envelope还保护shank、thigh、bar、adapter；袖套双端点不能替代这些组件。

原guard以因果Human接口pose/twist给出gap及gap-rate，以估计Human q/dq与校准几何计算模型梯度/曲率。关节梯度步长10⁻⁵rad，方向模板q±h·dq的h=10⁻⁵s。h虽数值相同，单位不同。原FAST/torque更新5ms，native物理0.25ms，不能把10μs差分视作执行周期。

A：a=0处的min连续不可微。两光滑端点的右方向导数最小值为ż_c−L|ȧ|（再加径向项）；原sign(0)=0公式在精确零轴时没有给出该方向导数。远离|a|=1各端点局部光滑；竖直轴的径向sqrt仍可能退化，不能宣称全球光滑。

B：方向差分跨水平端点分支时，曲率额外项近似−2L·max(h|ȧ|−|a|,0)/h²。这是包络有限差分的大负项，不是真实gap加速度，也不是gap跳变。固定非零偏置状态在h足够小时回到单支，不能一概声称h→0发散。极小h还有浮点抵消。零物理解析/差分结果见analysis/ENDPOINT_STUDY.json。

C：原shortfall/active-set/box激活为控制模式，随后filter、allocator、supervisor、scheduler各有独立模式。D：guard返回Human二维Nm修正，再经实际6轴robot扭矩分配与饱和，二维修正不等同实际六维torque；post-filter约束另行记录。E：真实Human q/dq、a、jerk只从原native重建，保持原未滤波gradient口径。

原required=2(d−g−Tġ)/T²+adverse，d=10μm；C19实际T=.08s、adverse=1.5m/s²。原单约束迭代投影在加速度box内尝试修正，返回constraint_satisfied；空集/饱和并未在该函数中强制STOP。原conservative_shank模式可调用显式2D半空间投影，空集返回clip(a)和False。后续原安全、任务、receipt和supervisor仍保留；不能把局部标志当成整个系统停止证据。

C19和PPO第9次原函数对历史gap/rate充分标量的精确重放再次执行；模型曲率及correction误差为0。历史trace cuff pose并不自动等于guard消费的Human接口，试用该proxy所得gap/rate误差被明确拒绝，见analysis/CAUSAL_ENDPOINT_REPLAY.json。不能由其轴偏差推断真实模型姿态偏差。新运行branch_diagnostics直接保存传给guard的model/state/interface量，原返回correction不变。
''')
write('DUAL_ENDPOINT_CONSTRAINT_STUDY.md',r'''
# 双端点约束研究与晋级门

CONFIRMED：2,437个远离竖直奇异的解析检查点，min(g_−,g_+)与原sleeve gap差为0；梯度差分最大误差约1.28×10⁻⁹m/rad，方向曲率差分误差约4.67×10⁻⁸m/s²。检查是数值核验，点态等价另有代数证明。几何本身没有修改。

设v=(1,−1)，a'=−p_x,z sinφ+p_z,z cosφ，t(q_h)=p_x,z cosq_h+p_z,z sinq_h，ρ=√(1−a²)，c_±=d_c±L。∇g_±=l_t t' e_h+(c_±+ra/ρ)a'v；H_±=−l_t t e_he_hᵀ+[−(c_±+ra/ρ)a+r(a')²/ρ³]vvᵀ。模型曲率为dqᵀH_i dq。各端点通常相对加速度阶2；梯度退化或实际torque映射退化必须单列。

开发候选同时施加∇g_i·a≥required_i−dqᵀH_i dq，并与原加速度box相交，使用原exact 2D半空间投影；禁止依次投影而漏掉第一端点。双约束冲突、退化梯度与box可产生空集。点态等价不保证该QP递归可行，也不保证filter和robot饱和后约束仍成立。

保护缺口得到构造性说明：g0=20μm、ġ0=−.02m/s、T=.08s、adverse=1.5时，原所需加速度为1.996875m/s²；真实恒定加速度2满足该不等式，T末gap为4.82mm，但5ms处gap已为−55μm。这是标量反例，不是声称该危险轨迹在plant发生。它说明该时域末端条件本身不是连续安全证书，不能因双端点同样满足它而晋级。

已推导更强的条件关系：若真实每端点gap在[0,Δ]的加速度下界为α_i，且g_i/v_i为有效因果下界，则要求α_i≥sup_{0<t≤Δ}2(d−g_i−v_i t)/t²可保证整个采样间隔。令c=g_i−d>0，先取−2(c+v_iΔ)/Δ²；当v_i<0且t*=−2c/v_i≤Δ时，再与v_i²/(2c)取max。该条件对10,000标量样本核验，最低残差约−4.6×10⁻¹⁷m。上述反例在Δ=5ms时需要20m/s²。详情analysis/SWEPT_GAP_CONDITIONS.json。

尚缺：因果测量g/v误差界、模型Hessian随时间变化界、实际最终饱和torque到端点加速度下界、contact/Human响应误差界，以及空集时可证的backup/stop。原1.5 adverse常数不是这些界已经成立的证据。原1201节点quintic reference certificate也不是实际Human闭环证书。

DECISION：双端点候选只执行零物理诊断，未接入物理、未继承正式guard资格。保留原guard，按预授权备选研究分支感知上层预测。不能将NOT_PROMOTED写成“证明双端点无效”或“证明不可实现”。
''')
write('ISOLATED_GUARD_IMPLEMENTATION.md',r'''
# 隔离实现与实际执行身份

真正新写的dual endpoint代码位于source/endpoint_study.py，包含解析gap、gradient、Hessian和box交集诊断；source/swept_gap_conditions.py给出条件性采样间标量关系。两者均未注册成物理controller。

物理中唯一clearance扩展为source/branch_diagnostics.py：先调用原clearance_acceleration_correction，原样返回其correction；仅在record内附加同次因果model/state/interface的轴、轴速率、差分跨支、两个实测端点gap/rate等。无truth读取，无滤波，无阈值或命令修改。原clearance_feedback.py及plant、原scorer的SHA在最终保护审计核验。新增日志不自动具备host实时资格。

v4_worker继承已有完整live-state串行fork、父状态hash恢复检查、receipt/raw记录、资源计数和原motion门。source/supervise.py为有限队列增加PID/start_ticks身份、局部wall cap、原ACTIVATION硬截止和owned后代清理。不会恢复旧checkpoint进入新动作语义，也没有PPO训练。

FACT仅改变两个预登记compiler权限因子；guard与几何不变，factorial_planner.py在固定modal坐标下独立控制逐关节终点锁和parent duration下限保留。该实验不等于旧18D与新8D的等权限全族优化。
''')
write('LEARNING_DECISION_STUDY.md',r'''
# Learning决策研究

P5神经网络、残差模型训练、action-conditioned value和PPO继续训练：NOT_RUN。clearance解析形式已知，优先以显式分支信息与传统响应拟合检验，不能用网络拟合一个已知min差分公式并宣称Learning贡献。

已冻结一个传统局部线性响应模型：候选只改变C19 x[3]，用历史五条合法完整物理执行中的因果估计q/dq，拟合固定控制cell的φ和φ̇，再代入解析跨模板曲率近似。训练样本与raw SHA、fit/LOO误差见analysis/FROZEN_BRANCH_MODEL.json。模型只在同父和±.001局部参数域有效，候选参数是执行前可用输入，未来Human truth不进入模型。

六个未见微扰的预测在其START前冻结。预测曲率/冲击是第一层；原motion分类是代理性第二层，原完整scorer才是资格。固定候选集没有部署学习决策，不能把预测准确叫作收益。跨prefix模型默认ABSTAIN；另冻结naive-transfer只作外推诊断，不能充当可靠在线控制。

PPO本轮仅复用历史第9次原函数精确重放，未新执行冻结策略、未长程scratch、未继续训练，也未改rollout接口。guard未替换，因此不存在“新guard改善PPO”的本轮证据。保留Learning前景：真实state-dependent编译/闭环响应、不同患者历史与运动余量可能仍需学习；本轮有限样本不能建立少次适应。
''')
write('OPTIMIZATION_IMPACT.md',r'''
# 优化影响研究

原guard与新guard的同优化器等物理预算P3-B：NOT_RUN，因为双端点没有通过保护晋级门。不存在本轮执行层改进，不能宣称其提高优化效率，也不能声称该机制已被排除为主要优化瓶颈。

按备选路线，P3-A冻结合理参照及六个未见局部候选，在原guard中验证分支感知传统预测与实际完整motion资格。随后使用同一冻结菜单、同一历史数据和物理成本标签比较朴素成本排序与加入显式分支风险的排序；该分析与实际在线优化、拟合精度分开报告。菜单策略若选择同一动作，不为追求正结果重复大量无辨别力物理试验。所有真实开发/验证attempt仍计账，固定菜单离线排序不冒充额外物理搜索。

对于全局低force，已有强最佳和旧18D近似非常接近。C19微扰只改变窄分支失败带，不能单凭其局部motion修复可能性声称全任务最优改善。正式JF最优仅从完整、安全且原motion通过的实际运动中报告，并同时给出JM、tracking与native运动负担。
''')
print('CORE_DOCS_WRITTEN')
