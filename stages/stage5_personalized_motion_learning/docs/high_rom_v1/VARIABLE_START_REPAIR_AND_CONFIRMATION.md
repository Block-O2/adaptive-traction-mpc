# High-ROM 变起点修复与原16例功能确认

**状态：HIGH_ROM_VARIABLE_START_CONFIRMED。** 原预登记清单16/16例在同一冻结版本下完成并通过；01–07复用原始结果，本次只执行08–16共9次完整MuJoCo仿真。此前额度读数失败造成的7例暂停记录已原样保存在 `VARIABLE_START_PREVIOUS_PAUSE.json`。

## 版本与修复

- 分支 `codex/full3d-cr12-high-rom-v1`，HEAD/基线 `c72760ae76a5b77a7291b9108ca20ff10b6c3be6`；172个冻结源码、配置和评分文件均无漂移。16个原payload的case哈希一致，80个原始产物SHA-256另见 `VARIABLE_START_EVIDENCE_FINGERPRINTS.json`。
- 根因是 `scenario.py` 将High-ROM起点强制等同于(5°,10°)。现从登记任务显式传递起点/RETURN目标，检查有限值、125°硬ROM、起点几何和commissioning；旧(5°,10°)默认行为保留。任务目标、arrival容差、0.5秒dwell、RETURN、超时、安全限值、125°模型、5°软限层及100ms方案有效期均未放宽。
- 任务公开起点属于已知启动姿态的工程标定假设。物理reset数组与任务目标在代码中分离；估计器从因果测量层接收观测，不读取reset真值或隐藏几何。该假设尚无硬件验证。

## 验证与结果

- 前置检查：8项起点/非法输入测试通过；16/16配置构造、MuJoCo XML加载与一致性预检通过。原起点(5°,10°)、新起点(6°,11°)/(8°,13°)各一次完整局部试跑均通过。
- 原16例逐项状态、原评分条件和失败分类见同名JSON；16次COMPLETE、16次confirmed，任务/安全/时序/实现失败均为0，未跑为0。矩阵期间未改代码、案例或评分，也未重跑01–07。
- 全16例从原生0.25ms人体q/dq节点验证120°/120°到达、连续有效dwell和各自登记起点RETURN；最短连续有效dwell **0.525 s**。Auditor核对全16例共1,933,054个原生节点，未见dwell重计事件。
- 原生监控累计最小小腿间隙 **0.010082 m**、峰值袖套接口力 **123.055 N**、力矩 **16.376 Nm**；已建模接触、ROM和阶段超时事件均为0。5ms采样最小袖套间隙 **0.012486 m**。
- 共272次激活，全部小于100ms，最大 **67.063 ms**，过期激活0；原任务质量、速度/加速度、机器人力矩和时序评分16/16通过。
- 本次08–16仿真host耗时合计 **478.8 s**；全16原始运行耗时合计 **851.3 s**。

## 独立Auditor与证据边界

**ACCEPT**，限于冻结High-ROM工程模型下的变起点原16例仿真功能确认。Auditor只读核对172/172冻结文件、16/16原始案例、80/80原始产物哈希、到达/逐步dwell/各自RETURN、272次激活及观测初始化真值隔离；未改文件或运行仿真。

原生q/dq是逐0.25ms保存节点；力、力矩与间隙是监控器逐步计算后保存的累计极值，不能称为从逐点原始载荷独立重算；袖套间隙和部分运动学为5ms采样。结果不证明步间连续安全、硬件实时/安全或新鲜资格。125°硬限仍是工程假设。

## 额度、命令与停止

- 原累计周额度起点14%，本次开始14%、结束14%；周窗口10080分钟、重置时间Unix 1790917420。续跑前取得连续两次有效同窗口读数，08–16每例前检查。16%停止新增实验、17%最大授权及45%外层项目停止线均未触及。额度解析工具未修改；前次失败记录保留。未验证在途worker硬中断，每例独立使用STOP检查和300秒host cutoff。
- 运行方式（从工作区根）：`/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage5_personalized_motion_learning/scripts/high_rom_v1/run_dev_case.py --case stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_function_fresh_XX_v1.json --output stages/stage5_personalized_motion_learning/results/high_rom_v1/variable_start_v1/case_XX --host-monitor-limit-s 300`，本次仅XX=08…16。评分：`/opt/homebrew/Caskroom/miniconda/base/envs/mpc_learn/bin/python stages/stage5_personalized_motion_learning/scripts/high_rom_v1/score_variable_start.py --output stages/stage5_personalized_motion_learning/docs/high_rom_v1/VARIABLE_START_PROGRESS.json`。
- 未提交、暂存、推送、合并、重置、stash、clean或删除；原工作区和基线分支未修改。阶段C具备本工程功能门槛依据，但本轮停止于功能确认；未开始提速、RL或其他资格实验。
