# 18D方法定义（源码审计，physics前冻结）

历史primary是离线有限约束搜索选出的固定参考意图参数，不是学习策略，不调用Q-learning、Neural Q或在线RL。在线仍由原B的因果状态/模型估计、有限waypoint MPC、quintic scheduler/governor、current admission、FAST/cuff allocator和六轴torque执行。18D不是一条预存真实Human运动，也不是直接施加关节状态。

实现：`code/rich_planner.py:RichFreePlanner.parameters/decide/_waypoint_terminal_velocity`；原反对称残差在`source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py`。全部18项及数值见PARAMETER_MAP.json，冻结完整candidate见FROZEN_18D.json。

对B已选出的非终末target，以本phase起点和跨度将hip/knee归一化为p，m=mean(p)，u=2m-1，e=sin²(pi*clip(m,0,1))。OUTBOUND j=0,k=10；RETURN j=5,k=14（零基索引）。

`c=e*(x[j]+x[k]*u+x[k+1]*u²)`；`d=e*(x[j+1]+x[j+2]*u+x[k+2]*u²)`；新target进度`p+[c+d,c-d]`，再乘各关节跨度恢复rad。c改变共同进度；d改变相对姿态；tilt/curve改变其沿进度形状。RETURN跨度负向，不能把正负系数直接解释为绝对屈曲方向。范围越界或原可行性不通过时保留B原执行目标。

非终末waypoint的原B终端速度乘以`1+e*[x[j+3]+x[j+4]+x[k+3]*u, x[j+3]-x[j+4]-x[k+3]*u]`。这是通过速度偏置，完整实际速度仍由quintic、桥接、governor、反馈与contact响应决定。HOLD、接近phase终点及最终目标保留原B行为。18D本身不增加内部quintic控制点。

完整赢家还包含RETURN第1和第2槽（零基）的native差分plateau，分别-0.020和-0.022。相对remaining causal progress在[0,.001,.5,.999,1]形成[0,a,a,a,0]，前端按当前start_m映射并在全局0补零；该层先作用于native目标，再施加18D。不得仅凭文件名NATIVE_SCALAR_18推断维数，更不能丢掉这两个plateau。

历史优化入口为`code/overnight_runner.py`及`runner.py`，有限COBYLA及预注册probe/repair/quality候选，以完整J_F最小化并受冻结运动、剂量、时长、tracking、moment/peak、安全/task/ownership约束。选择primary为开发合格候选中最小完整J_F，不保证收敛或全局最优。冻结后不得按验证重选；secondary也不能替换primary。运动阈值逐字节继承MOTION_ACCEPTANCE_PROTOCOL.json：原始velocity/acceleration/jerk比较1.10、excursion/边界0.5°、剂量0.95–1.05、时间0.1s、moment1.25、tracking增加0.5°、peaks1.05；phase-shape和jerk max为诊断，不偷改为PASS规则。

开发状态/模型：high_rom_nominal_sync_120_v1，同一已暴露被动Human，75kg/1.72m，rest[5,10]°，任务[5,10]→[120,120]→[5,10]°，ROM[0,125]°；完整case/options/模型来源hash见provenance中的CURRENT_MODEL_AND_TASK。合同HOLD dwell为0.5s，实际HOLD阶段约1.02s，两者不可混淆。开发seed=2026101303。完整历史B=1438.6134984674875，18D=1400.697221153 N·s，约2.635613%；完整19.03s。

历史primary合法prefix motion 0/4必须保留：V1膝velocity p95；V2 acceleration p95及phase-boundary；V3 velocity/acceleration p95及excursion；V4 acceleration max/p95、jerk RMS及excursion失败。历史更低力1196.685445候选motion失败，不是合格赢家。正式Native LEVEL2、host-clock LEVEL3/strict55/R2/FAST负结果和硬件/临床未验证均保留。仅PHYSICAL_LEVEL1同模型研究。
