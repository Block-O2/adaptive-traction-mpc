# History-based iterative correction

规则在下一次结果可见之前固定：选择 OUTBOUND/RETURN 参考进度 0.2–0.6 中平均测量力较大的窗口；`a_next=clip(a_previous+0.25*(estimated_actual-reference knee lag), ±0.3deg)`。OUTBOUND[1] / RETURN[3] 的中间膝姿态经原证书和 admission 执行，终点不改。其可证伪假设是顺应误差方向减小 cuff 负担；没有已识别的力梯度或收敛证明。

| 患者 | 动作 | 相对 B 降力 | 相对 disabled 降力 | 完整资格 | 严格消融 |
|---|---|---|---|---|---|
| P00 | OUTBOUND[1] 膝 -0.096095° | 0.119799 | 0.119799 | True | False |
| P05 | OUTBOUND[1] 膝 +0.013343° | -0.012753 | -0.012753 | True | False |
| P08 | OUTBOUND[1] 膝 -0.122828° | 0.147562 | 0.147562 | True | False |
| V12 | OUTBOUND[1] 膝 -0.158598° | 0.239097 | 0.133849 | True | True |
| U14 | OUTBOUND[1] 膝 -0.125116° | 0.179960 | 0.080135 | True | True |
| U15 | OUTBOUND[1] 膝 -0.065163° | 0.101012 | -0.005210 | True | False |
| U16 | OUTBOUND[1] 膝 -0.007044° | 0.007628 | -0.066505 | True | False |

| 患者 | T3 B JF | T3 KEEP JF | T3 更新 JF | 更新相对 KEEP 降力 | 三个分支均完整合格 | 重复获益 |
|---|---|---|---|---|---|---|
| P05 | 1140.566809 | 1140.579562 | 1140.591080 | -0.011518 | True | False |
| P08 | 1438.149056 | 1438.001493 | 1437.850356 | 0.151137 | True | True |

开发 disabled=B 零更新；验证和测试 disabled=三个开发患者平均合法特征，使用同一修正律，当前患者历史 withheld。后者防止把一项普遍有效的固定扰动误认作个体历史学习。直接跨 repetition 的 JF 减少受起始状态漂移影响，不能代替 matched KEEP/B。

方法背景参见 [Bristow、Tharayil、Alleyne，2006 ILC survey](https://experts.illinois.edu/en/publications/survey-of-iterative-learning-control-a-learning-based-method-for-/)。本实验只是受历史误差启发的有界迭代修正，不声称满足综述中的线性系统收敛条件。
