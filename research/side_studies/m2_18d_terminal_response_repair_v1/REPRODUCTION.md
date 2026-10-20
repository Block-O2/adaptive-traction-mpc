# 复核入口

本包已关闭。禁止原地重跑physics或清空账本；新增physics必须新版本、重新登记合同。

指定Python：`/home/hank/envs/adaptive-online-rl-v1/bin/python`，带`-B`。canonical：`/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1`。真实raw位于`source/results/<id>/trace.npz`、`summary.json`、`native_reference.npz`、`runtime_artifacts.json.gz`；native真值通过`wall_physics`存档，仅用于evaluation。

执行闭包与physics前SHA：`EXECUTION_CODE_MANIFEST.json`。原18D固定参数和RETURN plateau：`FROZEN_18D.json`；原门：`MOTION_ACCEPTANCE_PROTOCOL.json`；候选新增源：`code/terminal_repair.py`。唯一新因子1.5，无搜索或训练。完整命令见`N2_OWNER.json`、`U1_OWNER.json`及`ATTEMPTS.jsonl`；最后START已锁止。

只读数值复核：将`control/independent_recompute.py`复制到另一个新审计输出目录，绑定本包为读取根并单独绑定输出sink，再调用`measure(id)`；禁止直接覆盖本包已关闭的derived。它不导入controller/plant，逐行重算native映射/导数、积分、phase、dose、receipt ownership和source hash。`analysis/verify_archives.py`示范这种读写根分离方式。报告/图与对齐来源在`analysis/`，不属于physics执行闭包的后改文件。

执行前preflight用原scheduler重建存档N2因果模型与边界，original_duration=.220、T=.330，原mechanics与连续几何PASS。真正current-state admission和40ms桥在新物理链再次执行，不以数学测试替代物理资格。

