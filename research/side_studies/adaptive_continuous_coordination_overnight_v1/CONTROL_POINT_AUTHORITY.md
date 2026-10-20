# 数学门与控制点权限

实现prototype/continuous.py，精度事前固定于prototype/MATH_PROTOCOL。

M0：28个冻结selected quintic schedule系数再现；schema_gate另外直接import原_quintic_coefficients核验。范围是原选中多项式，不冒称已恢复整个governor/bridge连续时间链。

M1：三个内部点零修改加密，q/dq/ddq最大误差8.88e-16/1.33e-15/9.16e-15，小于冻结1e-10/1e-10/1e-9。B-spline插结也通过。

M2：更新新增节点使q峰值变化0.005299332rad，且支持非零通过速度。

M3：q/dq/ddq接续、端点与duration保持；不承诺jerk连续。

M4：A只影响相邻两段，支撑外q差6.11e-16rad。phase分离对象不相互污染。

M5：单调局部clock固定q路径而改变速度，路径恒等误差<1e-10；另一更新固定时间节点而改变hip/knee协调。这只证明数学可区分，不保证Human路径恒定。

M6：完整物理安全接口未通过。fail-closed适配器只允许精确collapse回原不可变quintic的零修改情况，非零曲线被拒绝。

首次M0有8.88e-16系数差，未通过更强的exact断言；只修复一次浮点减法顺序，精度不变，保留prototype/repairs/原失败。一次有限旧接口适配试验把子段加速度强制为0，导致q/dq/ddq误差.001774082rad/.018061431rad/s/.656758031rad/s²，M1失败，未放宽容差。

最小接口反例：旧构造器接受2×6，对4×2×6抛出“coefficients must be a finite 2x6 matrix”。外部q/dq/ddq与duration固定时，每关节6×6边界矩阵满秩；端点压缩会丢失内部0.3°变化(.005235988rad)。证据PHYSICAL_INTERFACE_PREFLIGHT和control/schema_gate.py。普通pickle并非瓶颈；真实缺口是scheduler对象和全路径geometry/current admission/escape证书。原rolling composite不等于任意多段认证。

下一接口合同：typed immutable N×2×6载荷、严格局部时间、phase与内容/model/geometry hash；每段原ROM/解析运动极值/continuous body clearance；跨节点20ms历史不可重置；当前状态和tracking offset绑定同一整链；保留40ms bridge、100ms lifecycle、版本/phase/age规则及末端safe escape；每个issued reference仍需receipt/native ownership。原型不能把sample改成新曲线却保留旧coefficients证书。

必须先完整零修改issued/reference/native/receipt等价，再非零局部reference→command→Human响应，再P2完整task/安全/冻结motion。当前不具备优化force资格。不证明更完整多段接口不可能。
