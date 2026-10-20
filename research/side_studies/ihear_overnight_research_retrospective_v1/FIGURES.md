# 图表阅读与来源

## 1. 两次转变：固定参考→Goal torque→online waypoint

![两次转变：固定参考→Goal torque→online waypoint](FIGURES/01_ARCHITECTURE_BEFORE_AFTER.png)

结构图来自历史源码；不能追认早期已具有后期lifecycle。

## 2. 问题推动结构变化

![问题推动结构变化](FIGURES/02_PROBLEM_DRIVEN_EVOLUTION.png)

日期与分母见timeline/ledger；教授上次实际边界未确认。

## 3. 科学、原接口、host与临床能力分开

![科学、原接口、host与临床能力分开](FIGURES/03_CAPABILITY_BOUNDARIES.png)

图中旧2.457489%/1of2是历史结果，本轮结果另见第7图。

## 4. 同完整父开发集force与冻结motion权衡

![同完整父开发集force与冻结motion权衡](FIGURES/04_FORCE_MOTION_TRADEOFF.png)

完整候选保留；FAIL低力不能升级为优质运动。

## 5. 真实Hip/Knee角与速度、发出参考分别显示

![真实Hip/Knee角与速度、发出参考分别显示](FIGURES/05_ACTUAL_HUMAN_MOTION.png)

原0.25ms native真实q/dq，每16点显示，所有统计用全部点；无滤波。

## 6. 全TASK原左积分及实际phase收益

![全TASK原左积分及实际phase收益](FIGURES/06_CUMULATIVE_FORCE_AND_PHASES.png)

共享任务/HOLD；不因小幅变化称治疗等效。

## 7. 四条件固定分母和真实prefix状态

![四条件固定分母和真实prefix状态](FIGURES/07_FROZEN_VALIDATION.png)

同一Human合法前向生成状态，仅验证剩余suffix，不改选primary。

数据来源：EXPLORATION_RESULTS、各_MEASURED/trace/native motion、VALIDATION_RESULTS；绘图不新增physics。图片显示抽样不用于验收统计。
