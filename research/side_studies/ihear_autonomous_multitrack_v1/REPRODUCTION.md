# 复核与复现合同

Canonical: /home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1
Python: /home/hank/envs/adaptive-online-rl-v1/bin/python
Distribution: Ubuntu-Research-Verify

本包关闭后只读复核入口（不启动physics）：
```
/home/hank/envs/adaptive-online-rl-v1/bin/python -B /home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1/analysis/readonly_verify.py
```

本轮真实physics命令记录在*_OWNER.json；入口control/owner.py Adev development及Bmap development，每次START登记group plan与execution manifest SHA。原owner/STOP/时间预算阻止关闭后自动重跑；继续须新的显式版本化包。

code/source/deps/weights由Early RETURN canonical复制，只对新包绝对路径重定位。原控制、安全、native源保持，新增control/terminal_approach_planner.py；候选参数见CANDIDATE_PLAN.json与各group_PLAN。初始所有历史metadata/SHA见audit/HISTORY_BEFORE.json（镜像可不包含完整大清单）。

离线分析入口：analysis/historical_audit.py、state_and_contracts.py、deep_diagnostics.py、experiment_analysis.py、verify_execution.py、independent.py；只有独立算术模块用于最后分离复核，绝不调用MuJoCo/planner。报告由analysis/write_reports.py生成。所有这些脚本随canonical保存；封存后不运行写入型分析去改历史报告，只读验hash。

完整native与receipt: source/results/<run>/runtime_artifacts.json.gz；trace.npz是原5ms轨迹，motion_series/<run>.npz是原0.25ms真实Human及冻结导数。EXPERIMENT_RESULTS记录完整指标，ATTEMPT_ACCOUNTING记录实际新steps、父状态/候选/hash/returncode、partial和失败边界。
