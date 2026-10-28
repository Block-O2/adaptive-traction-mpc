# 提前协调：几何分支与交接分开

显式几何模型只读当前估计、已签参考、scheduler几何及当前tracking误差，预测5ms栅格的端点模板距离；0.1s误差衰减和2e-4 axis不确定带是排序启发式，不是安全证书。STRICT01在原相对模式box内裁剪候选，实际变化可能低于0.02度。是否改变选择、是否激活、是否改善真实Human/wrench分别报告。

交接感知方案依据原receipt确认的q保持而dq非零现象，提前降低原通过速度坐标。强固定十个固定邻近窗口覆盖约83%原始jerk平方和；这是描述性窗口重合，不是已识别独占中介比例。原guard在该强固定TASK内未激活。

| 身份 | 原门 | 权限 | JF N·s | JM Nm·s | native jerk RMS 髋/膝 °/s³ | 200Hz ‖F‖ rate RMS N/s | 4kHz ‖F‖ rate RMS N/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HANDOFF01_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| HANDOFF01_BOTHHALF | PASS | original domain | 1399.794462 | 107.906134 | 309.76/656.28 | 17.5036 | 19.0283 |
| HANDOFF01_BOTHLOW | PASS | original domain | 1401.756380 | 107.779354 | 299.53/635.53 | 17.2949 | 18.7538 |
| HANDOFF01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| HANDOFF01_OLOW | PASS | original domain | 1400.392567 | 108.128124 | 306.80/654.35 | 17.3199 | 18.8462 |
| HANDOFF01_RLOW | PASS | original domain | 1399.398428 | 107.622247 | 313.20/660.23 | 17.7192 | 19.2440 |
| STRICT01_ANTREF | FAIL | original domain | 1397.930115 | 108.149856 | 321.88/682.92 | 17.8026 | 19.4086 |
| STRICT01_ANT | PASS | original domain | 1398.007158 | 107.973664 | 320.15/678.36 | 17.7435 | 19.3341 |
| STRICT01_BEST | PASS | original domain | 1398.034615 | 107.971017 | 320.15/678.37 | 17.7435 | 19.3341 |
| STRICT01_B | PASS | original domain | 1436.456498 | 101.253695 | 305.08/714.73 | 19.3905 | 20.9137 |
| STRICT01_REF025 | PASS | original domain | 1397.949604 | 108.076996 | 320.80/680.17 | 17.7690 | 19.3659 |
| STRICT01_REF050 | FAIL | original domain | 1397.957504 | 108.147215 | 321.88/682.93 | 17.8027 | 19.4086 |
| STRICT01_REF100 | FAIL | original domain | 1398.084987 | 108.241982 | 323.28/686.75 | 17.8689 | 19.4872 |


源代码与前瞻菜单见source/v5_bounded_anticipatory.py；实际签发、torque和native证据不经过事后滤波。对照与跨prefix资格见冻结验证和最终REPORT，不能从单个C19恢复推广为一般模型收益。


最终冻结验证、失败分母与补充反事实见[冻结验证汇总](FROZEN_VALIDATION_SUMMARY.md)、[补充执行反事实](SUPPLEMENTARY_EXECUTION_COUNTERFACTUALS.md)和[力／力矩波动分解](WRENCH_COMPONENT_TRADEOFF.md)。主结果不使用未来资格mask，不改变原积分、原阈值或开发固定预算。
