# 冻结 R1/R4 的阶段剂量和真实运动

只读已保存 nominal mean 轨迹，零新物理/Adam。阶段 JF/JM 来自独立原5ms左积分；native速度、加速度、jerk来自完整4kHz序列和pre-TASK anchors。相位RMS仅作诊断，不创造新的jerk合格阈值。

只有两者完整且整体/相位分别等时时才列直接阶段剂量差；失败partial原样列入JSON，不以低剂量比较性能。运动图只为两条完整等时轨迹生成，图内展示全部native序列。

相位差能定位变化阶段，不能据此唯一归因于力臂、旋转阻尼或某一个Reward项。正式B/H150 live matched与G4资格仍未获得。
