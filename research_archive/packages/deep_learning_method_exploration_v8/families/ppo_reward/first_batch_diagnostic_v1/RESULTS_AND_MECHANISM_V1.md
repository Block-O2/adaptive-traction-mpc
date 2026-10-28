# 首个真实batch与固定48次推理诊断

首个完整更新已闭合：GEN0002来自16次实际新policy child，heavy8次原合格、light8次完整motion失败，失败floor保留−1。主owner执行了8次SGD（RF各1、PPO各3）、32次sample-score gradient等价计算、48次训练forward，Adam0；这些是此前主owner已付费工作，本次没有新训练/物理。

本次固定GEN0000/GEN0002全部四臂，在6个指定closed开发context逐个调用select_out0，48次实际API/forward全部完成；相同权重也逐一计数。6次原raw→commissioned25、8次policy deepcopy，initialize/restore/RNG/gradient/update/physics均0。保存全部概率、entropy、双向KL、argmax、policy/file/source/raw及25D身份SHA。只连接同完整recipe实际观测的38条原RESULT/binding，parent/HISTORY_B不作标签，缺动作UNKNOWN。

| context | 首批前四臂argmax | 首批后RF_RAW | 首批后PPO_RAW/PPO_SCALED | 首批后RF_SCALED |
|---|---|---|---|---|
| CTX01 | B | B | B | B |
| CTX02 | EARLY_H150 | EARLY_H150 | EARLY_H150 | EARLY_H150 |
| CTX03 | B | B | B | B |
| CTX04 | B | B | B | B |
| heavy035 | B | B | B | B |
| light065 | EARLY_H150，实际已测失败 | B，实际已测合格 | LATE_PHASE，当前授权closed结果未测：UNKNOWN | EARLY_H150，实际已测失败 |

五个context的argmax均未变。light改变分布不等于完成资格/控制改善：RF_RAW改选已观测B，但未新执行这个冻结端点；PPO改选未知LATE_PHASE，不能把降低已知失败质量当作已合格。light概率详细如下（顺序始终B/LATE_H150/EARLY_H150/LATE_PHASE/EARLY_PHASE）：

| policy | p(B) | 已知失败概率质量 | UNKNOWN概率质量 | KL(末||初) |
|---|---:|---:|---:|---:|
| GEN0000全部四臂 | .190799 | .529832 | .279369 | 0 |
| GEN0002 RF_RAW | .287478 | .410358 | .302164 | .089213 |
| GEN0002 PPO_RAW/PPO_SCALED | .197034 | .353686 | .449280 | .081796 |
| GEN0002 RF_SCALED | .221804 | .412406 | .365790 | .031830 |

PPO两臂源权重与六context概率逐项完全相同。其本批两个heavy动作都是B、reward0；两个light动作完整失败、reward−1。gain1/20只缩放完整合格JF增量，0和−1不变，所以实际reward support、梯度和三epoch更新相同；这不能推断reward scale一般无效。RF_RAW唯一合格LATE_PHASE heavy样本相对B JF下降32.683033N·s、JM上升4.798604N·m·s，应按两成本分列；其raw正reward约.021522。其他臂heavy未抽到该动作，不能进行同数据reward因果比较。

RF_RAW在工程取消批次已额外消费1个真实抽样，RNG按主批准保留、未倒回；首批前forward5而其他臂4。该暴露差异解释了后续sample序列不再相同，raw/scaled RF差异不能单独归因于尺度。取消批GEN0001没有梯度；首个completed为GEN0002，端点固定，无best checkpoint选择。

权限修正按audit/ACTION_PERMISSION_CORRECTION_V1.json：先前冻结offline PG/BC实际只有3recipe；统一物理执行5recipe不自动扩大actor权限。此处genuine PG是明确BC3→5lift的新5recipe版本，不能跨权限把历史3recipe失败归为PG特有问题；强传统/BC聚合对照须使用相同5recipe权限。旧41D actor/scorer桥接未因此修复。

原系统Python运行在import numpy前失败，实际forward0；START/FAILED与源/inputSHA保留。主Agent随后明确批准一次环境修正，新inference_once_v2用原venv Python3.12.3、NumPy2.2.6/SciPy1.15.3，先保存实际module路径/版本后完成48次。成功wall.353582s、CPU.326881s、PID1148804/startticks60872670，单CPU affinity；RSS19472→71228KiB。ru_maxrss612080KiB在START已有且END未变，不能归因给本次。失败的CPU末值未记录，不能补造。

数据133文件身份及INPUTS SHA d753cbdce66bbab5b748491bb72cf0cff0a32f6997737f4b78dd100845447547，在两次运行之间完全不变。本诊断是已暴露开发条件上的分布/机制观察，无独立validation、无后训练端点新物理、无新增动作标签、无插值。活动H2及sealed未读，Beta冻结源未改。
