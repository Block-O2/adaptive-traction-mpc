from pathlib import Path
import json,time,hashlib
P=Path(__file__).resolve().parents[1]
def load(n):return json.loads((P/n).read_text())
def write(n,x):(P/n).write_text(x,encoding='utf-8')
def put(n,x):write(n,json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
d=load('DIAGNOSTIC_RESULTS.json');m=load('MATH_VALIDATION.json');b,c=d['runs'][:2]
root='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
write('CURRENT_ACTION_AUTHORITY_AUDIT.md',f'''# 当前控制权限与密度审计

结论：有效密度先受“每个原生请求选择一个目标与通过速度→单段quintic及全路径证书→端点触发下一请求”约束。数学插点本身不是主要障碍。SOURCE_CONFIRMED / TRACE_VERIFIED。

源码前缀：`{root}`。1376/1376个历史源码/模型/权重文件SHA256核验通过后复制，改动仅为本包路径迁移。实际import闭包见audit/IMPORT_PREFLIGHT。主HEAD为8bb04662b1578b72c097f546be9e836167e280e8；不能认为干净HEAD自带全部runtime。

|问题|回答与源码证据|置信|
|---|---|---|
|1 下一对waypoint|反馈MPC对估计状态加二维action，原池排序；native residual在名义目标progress处采反对称delta再评价。human_waypoint_feedback_mpc.py:214–238,258–291,407–427；full3d_adaptive_integration_v1/coordination_residual_v2.py:17–41。|高|
|2 步长与方向|span×.20×scale×direction；scale=(.5,1)，五方向(1,.5),(1,.75),(1,1),(.75,1),(.5,1)，临近目标截断和去重；终末策略另处理。feedback_mpc.py:35–43,224–237。|高|
|3 候选与执行|通常评价10个初始候选，只选一个计划；端点截断/terminal/residual会改变计数。本B的14次candidate_count={b['counts']['candidate_counts']}。18D={c['counts']['candidate_counts']}。|高，TRACE_VERIFIED|
|4 重规划触发|phase start、旧schedule endpoint，非零通过速度端点处prefetch。原40ms继续桥支持等待，不是每5ms调用planner。runtime_coordination_residual_v2.py:3184–3234。|高|
|5 完整任务request|B/18D各14次TASK、20次全session；强低力失败代表有16次TASK，不是固定永远14。事件与phase见DIAGNOSTIC_RESULTS。|高|
|6 接受/激活/生效|本配对各14个ACTIVATED、14个边界C2记录、10个实际SPLICED。逐native行连接positive-step receipt，力矩一致且steps闭合；proposal-only未当执行。|高|
|7 独立可调项|正式native residual只改目标上的反对称progress delta；scheduler控制内部q/dq/ddq。10D/18D隔离研究额外改共同/差分目标与通过速度，仍只在旧请求处形成单段quintic。任意内部状态不在正式B权限内。|高|
|8 速度/加速度/时间|通过速度取限速/1.875、制动距离、剩余量限制的最小值；终点/HOLD为0。feedback_mpc.py:184–212。duration在reference网格上取可行值，解析运动极值、因果20ms窗口、ROM和clearance均检查。scheduler.py:218–246,459–565。|高|
|9 C2保证|记录边界q/dq/ddq连续到原1e-10检查精度；不保证jerk、恒速或真实Human C2。rolling_suffix_splice.py:21–30；runtime:3008–3016。|高|
|10 端点a约定|原_quintic_coefficients的c2=0、末端二阶导RHS=0。scheduler.py:180–205。插入内部点后沿此约定重建一般会改变原曲线。|高，MATH_VERIFIED|
|11 K3与slots|K3是一次graph的三个参数结点；native residual.py:21–27在一次名义m处np.interp只产生一个delta。每phase五个研究slots是干预请求索引，不是K3点各执行一次。code/interfaces.py:5–7,19–22。|高|
|12 不加planner频率能否加点|数学与普通pickle可表达。当前scheduler/admission/clearance没有任意多段路径资格。原RollingSuffixCompositeSchedule确可拼接已认证旧桥+单段suffix，但不授权任意新样条。rolling_suffix_splice.py:15–63；online_planning.py:29–49。|高；扩展可行性INFERRED|
|13 密度瓶颈|具体阻塞为coefficients==(2,6)及绑定该多项式的全路径证书，之后还有通过状态、endpoint触发、governor/current admission和实际动力学限制。不能把瓶颈只归数学表达。|高/中|

分母不能混用：candidate count通常10；waypoint count为14个已选段的目标（含重复HOLD目标）；新增trajectory control points属于数学参考。activated=14，actual suffix splices=10。每组整session共5817条receipt（其中5816条positive-step），116320个0.25ms步；TASK为3806个5ms成本区间、76120个native步、76121个真值边界样本。FAST带宽、planner频率与这些数量不同。

Human为被动hip/knee，robot六轴力矩经原cuff耦合，本包不向Human写状态或增加执行器。18D是隔离LEVEL1，不据此升级Native-B LEVEL2或host LEVEL3。
''')
phase_table=''.join(f"|{ph}|{b['phase'][ph]['J_F_N_s']:.9f}|{c['phase'][ph]['J_F_N_s']:.9f}|{d['phase_gain_N_s'][ph]:.9f}|{b['phase'][ph]['duration_s']:.6f}|\n" for ph in ['OUTBOUND','HOLD','RETURN'])
write('FORCE_MOTION_MECHANISM.md',f'''# Force—motion机制诊断

先对复制保存的完整raw独立核算；新复现另列BASELINE_REPRODUCTION。不把历史值伪装成新rollout。每个native步均对实际receipt区间、完全一致applied torque与receipt steps核验。TRACE_VERIFIED。

原I_F口径：TASK 5ms边界上cuff force范数左积分；force单位N、moment单位N·m、积分N·s/N·m·s。TV_v与TV_a按0.25ms native true dq微分后作梯形累计，单位rad/s、rad/s²。reference使用解析ddq与5ms采样ddq的梯度诊断。口径分开，均非临床标准。

|阶段|B J_F|18D J_F|收益N·s|时长s|
|---|---:|---:|---:|---:|
{phase_table}
完整B={b['J_F_N_s']:.12f}、18D={c['J_F_N_s']:.12f}N·s；总收益{d['force_gain_N_s']:.9f}N·s / {d['force_gain_percent']:.6f}%，分母为一个已暴露Human的同条件B。全程19.03s，phase积分闭合误差<1e-8N·s。

A. 收益在OUT/RETURN形成18.725259/19.191012N·s，HOLD几乎不变。15–16s单秒收益9.996502N·s；4–5s与5–6s分别4.907485与5.192261。TRACE_VERIFIED。

B. 峰谷与高力只部分重合。0.25s分箱，B的OUT force与speed-L1/acceleration-L1相关为.717/.371，RETURN为−.178/−.048；18D为.665/.195、−.384/−.268。序列自相关、姿态和阶段混杂未分解。CORRELATIONAL，不作显著性或物理因果结论。

C. reference本身有宽尺度速度峰谷。按0.5°/s prominence、峰间≥100ms定义的时刻保存于DIAGNOSTIC_RESULTS；正常分段加减速不自动等于抖动。原C2不消除段内极值。SOURCE_CONFIRMED / TRACE_VERIFIED。

D. 终末tracking偏差突出：18D膝约9.542°/s在TASK7.000s，髋约4.963°/s在16.900s，分别在最近suffix后230/360ms。TRACE_VERIFIED。

E. ±150ms移位相关中，18D OUT hip/knee最佳相关滞后40/65ms、RETURN50/60ms。这是整phase相关，并非激励辨识的因果响应延迟；也不等同于D的峰值距splice时间。CORRELATIONAL。

F. 分段固定通过速度、duration、端点零加速度与终末制动提供反复加减速的结构线索。没有消融证明哪些“不必要”，也不能单归cuff或估计器。具体因果份额UNRESOLVED。

G. 高力不必伴随大速度变化：18D1.0–1.25s平均104.094N而acceleration-L1均值12.995°/s²；1.25–1.5s平均106.454N、TV_a仅.6180rad/s²。高力/较低acceleration阈值分别为全运动分箱force75%分位与acceleration中位数，完整值见audit/FORCE_MOTION_WINDOWS。它们仍在运动，不称静止。force与moment分箱相关更高（18D OUT/RETURN .775/.744），支持下一轮同时查姿态/支撑、moment和tracking；gravity是否主因仍UNRESOLVED。

H. 5–6s收益5.192261N·s，但TV_v从.560375升至.579751rad/s、TV_a从7.557340升至8.015063rad/s²。15–16s收益9.996502N·s而TV_a从8.681795升至10.622485。不能用“jerk更低”解释所有局部收益。TRACE_VERIFIED。

完整actual TV_v：{b['TV_v_actual_rad_s']:.9f}/{c['TV_v_actual_rad_s']:.9f}rad/s，下降{100*(1-c['TV_v_actual_rad_s']/b['TV_v_actual_rad_s']):.3f}%；TV_a：{b['TV_a_actual_rad_s2']:.9f}/{c['TV_a_actual_rad_s2']:.9f}rad/s²，仅下降{100*(1-c['TV_a_actual_rad_s2']/b['TV_a_actual_rad_s2']):.3f}%。真实J_F不能用平顺性代理替代。

建议五个局部开发区间：0.75–2.50s（持续高力/较低加速度）；4–6s（约10.099746N·s收益且TV方向不一致）；6.60–7.40s（去程终末tracking）；15–16s（最大单秒收益而TV_a增加）；16.50–17.50s（回程终末髋tracking）。这些已用作开发诊断，未来不得称未见时段。

数值微分：np.gradient(raw native dq,t,axis=0,edge_order=2)，再微分求jerk。端点保留二阶单侧差分，未删除峰值。绝对时间平移引入微小浮点舍入差，已量化，未改历史口径。SG5/21三阶窗口敏感性另存，raw仍主诊断。reference jerk是5ms解析ddq序列的梯度，跨段样本不等于严格连续时间jerk积分，与0.25ms actual raw不混用。

每5ms都有receipt，尖峰邻近receipt不是因果识别；不能将峰值直接归因新suffix。三张对齐图见figures/。不修改原历史PASS/FAIL。
''')
put('SELECTED_REPRESENTATION.json',dict(selected='A_LOCAL_C2_QUINTIC_STATE_CHAIN',status='MATH_ONLY_NONZERO_INTERFACE_BLOCKED',alternative='degree5 BSpline',reasons=['exact restriction of original quintic','explicit q/dq/ddq states','two-neighbor local updates','future reuse of original degree5 extrema/clearance primitives'],not_proven=['lower physical force','higher FAST bandwidth','Native-B LEVEL2','cross-state robustness'],code_sha256=hashlib.sha256((P/'prototype/continuous.py').read_bytes()).hexdigest()))
write('REPRESENTATION_COMPARISON.md','''# 表示比较

|标准|A：局部C2 quintic状态链|B：五次B-spline|
|---|---|---|
|复现/加密|原系数仿射限制，28段零修改通过|原quintic转Bezier/钳制样条，28段插结通过|
|通过状态|显式q/dq/ddq，内部速度/加速度可非零|控制系数经基函数作用，通常不是插值路点|
|局部性|节点更新只影响相邻两段|单系数影响至多k+1个knot spans|
|约束|可复用degree5极值/clearance数学核；20ms窗口须跨节点检查|需局部power/Bezier转换或基函数界，不能只限控制点|
|时间|单独bounded monotone clock，保持端点与phase总时间|同样需要独立时间映射与导数检查|
|旧接口|多段shape被2×6合同拒绝|无knots/控制系数载荷语义|
|stop/bridge|需完整不可变链+原末端escape证书|同样需要完整路径和escape证书|
|跨重复|稀疏局部状态更新便于审核，尚无物理结果|局部basis更新也可，尚无物理优势|

选A作为主要工程原型，B保留备选，因为A更接近现有quintic核、局部状态和安全审核，不因阶数宣布优胜。两者数学加密不增加ACTIVATED数或FAST带宽。任意非零新曲线尚未进入S/P/J物理搜索。

第三种选择是加密现有18D waypoint意图场：旧请求位置可增加参数，但请求间未采样的局部支撑可能没有效果。它没有兑现真正连续内部自由度，未包装为新样条成功。MATH_VERIFIED；物理优劣UNRESOLVED。
''')
write('CONTROL_POINT_AUTHORITY.md',f'''# 数学门与控制点权限

实现prototype/continuous.py，精度事前固定于prototype/MATH_PROTOCOL。

M0：28个冻结selected quintic schedule系数再现；schema_gate另外直接import原_quintic_coefficients核验。范围是原选中多项式，不冒称已恢复整个governor/bridge连续时间链。

M1：三个内部点零修改加密，q/dq/ddq最大误差{max(r['M1_errors'][0] for r in m['rows']):.3g}/{max(r['M1_errors'][1] for r in m['rows']):.3g}/{max(r['M1_errors'][2] for r in m['rows']):.3g}，小于冻结1e-10/1e-10/1e-9。B-spline插结也通过。

M2：更新新增节点使q峰值变化{m['M2']['changed_control_peak_rad']:.9f}rad，且支持非零通过速度。

M3：q/dq/ddq接续、端点与duration保持；不承诺jerk连续。

M4：A只影响相邻两段，支撑外q差{m['M4']['outside_max_rad']:.3g}rad。phase分离对象不相互污染。

M5：单调局部clock固定q路径而改变速度，路径恒等误差<1e-10；另一更新固定时间节点而改变hip/knee协调。这只证明数学可区分，不保证Human路径恒定。

M6：完整物理安全接口未通过。fail-closed适配器只允许精确collapse回原不可变quintic的零修改情况，非零曲线被拒绝。

首次M0有8.88e-16系数差，未通过更强的exact断言；只修复一次浮点减法顺序，精度不变，保留prototype/repairs/原失败。一次有限旧接口适配试验把子段加速度强制为0，导致q/dq/ddq误差.001774082rad/.018061431rad/s/.656758031rad/s²，M1失败，未放宽容差。

最小接口反例：旧构造器接受2×6，对4×2×6抛出“coefficients must be a finite 2x6 matrix”。外部q/dq/ddq与duration固定时，每关节6×6边界矩阵满秩；端点压缩会丢失内部0.3°变化(.005235988rad)。证据PHYSICAL_INTERFACE_PREFLIGHT和control/schema_gate.py。普通pickle并非瓶颈；真实缺口是scheduler对象和全路径geometry/current admission/escape证书。原rolling composite不等于任意多段认证。

下一接口合同：typed immutable N×2×6载荷、严格局部时间、phase与内容/model/geometry hash；每段原ROM/解析运动极值/continuous body clearance；跨节点20ms历史不可重置；当前状态和tracking offset绑定同一整链；保留40ms bridge、100ms lifecycle、版本/phase/age规则及末端safe escape；每个issued reference仍需receipt/native ownership。原型不能把sample改成新曲线却保留旧coefficients证书。

必须先完整零修改issued/reference/native/receipt等价，再非零局部reference→command→Human响应，再P2完整task/安全/冻结motion。当前不具备优化force资格。不证明更完整多段接口不可能。
''')
write('REPETITION_ADAPTATION_DESIGN.md','''# 跨重复设计，未执行

新表示未通过非零物理门、没有新合格非零改进，不满足可选跨重复先决条件；跨重复START=0。基线fork和历史counterfactual不算患者repetition。

未来可保留上一合法完整repetition的固定参数、receipt-owned参考、force/moment/tracking分段统计和模型预测残差；未来force与evaluation-only真值不得进入决策。下一轮只在事前局部支撑内有界更新q/dq/ddq或clock，完整认证后才执行，拒绝时保留合法原运动/fallback。起点必须合法native前向产生并保留完整控制状态。

冻结不更新、每轮同初始化、保留历史后三个对照；相同任务、可比较初态、完整评价。先证明历史信息确实影响下一轮合法参数，所有真实物理调用计数。当前不声称few-repetition学习、跨患者或三轮收敛。
''')
write('NEXT_RESEARCH_DECISION.md','''# 唯一推荐下一步

优先实现并单独资格化“不可变多段quintic路径+绑定同一路径的geometry/current-state/跨节点20ms/escape证书”，按零修改整链等价、非零receipt生效、完整TASK与冻结motion过门。

两个原型已经有数学局部自由度。当前扩大控制点/搜索维数不能替代接口资格，学习模块也没有合格的新动作空间。没有证据证明全局force下限或1000N·s可达。本轮不自动启动下一包。
''')
put('DIRECTION_DECISIONS.json',dict(decisions=[dict(unix=time.time(),branch='G',trigger='A/B mathematical refinements incompatible with original nonzero full-path schedule contract; bounded legacy-compatible repair fails M1',action='stop nonzero force search; finish baseline audit and engineering diagnosis',evidence=['MATH_VALIDATION.json','PHYSICAL_INTERFACE_PREFLIGHT.json']),dict(branch='mechanism',trigger='force benefits in bins with higher TV_a and high-force lower-acceleration intervals',action='do not optimize jerk alone; retain coordination/moment/tracking questions')]))
print('research documents saved')
