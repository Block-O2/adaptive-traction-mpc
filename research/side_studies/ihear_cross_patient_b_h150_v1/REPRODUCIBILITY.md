# 复核入口与数据位置

本包只执行工作包 A。最终状态以 `PACKAGE_VERIFICATION.json`、`PACKAGE_CLOSED.json` 与 `STATE.json` 为准；未生成这些最终记录时，不应把中间快照当作最终交付。

完整 canonical 包位于 WSL `Ubuntu-Research-Verify`：

`/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1`

Windows 中可通过 `\\wsl.localhost\Ubuntu-Research-Verify\home\hank\coding\adaptive-traction-mpc-side-studies\ihear_cross_patient_b_h150_v1` 访问。当前 Windows 工作目录的同名文件夹是便于阅读的报告镜像；原始 `source/results` 和 `motion_series` 仍保存在 canonical 包内。`REVIEW_MIRROR.json` 列明实际镜像范围，不宣称镜像包含全部 native 数据。

使用的 Python 为 `/home/hank/envs/adaptive-online-rl-v1/bin/python`。原控制器源码快照、native 适配器、B/H150 参数和原资格门保存在 `source/`、`code/`、`control/`、`deps/`；实际冻结身份见 `EXECUTION_CODE_MANIFEST.json`。与历史源码的路径重定位逐文件记录在 `audit/PATH_REBASE.json`，没有以重新调参替代路径迁移。所有正式 START 均记录所用 manifest、患者 case 和计划 SHA-256。

## 原始证据

- `patients/Pxx/case.json` 与 `static/model.xml`：患者实际物理参数、完整生成 MJCF；`MODEL_STATIC_AUDIT.json` 保存编译和初始几何检查。
- `source/results/Pxx_B/`、`Pxx_H150/`、`Pxx_parent/`：`summary.json`、5 ms `trace.npz`、包含 native truth/command receipt 的 `runtime_artifacts.json.gz`。
- `output/*_DATA.json`：fork、branch、完整执行身份；`reports/*_SNAPSHOT.json` 保存完整 live 状态摘要，不能跨患者复用。
- `motion_series/*.npz`：由原始 native 轨迹提取的真实运动序列；真值仅作离线评价。
- `reports/*_MEASURED.json`、`*_CROSS_EVALUATION.json`：完整积分、运动与逐项资格；`derived/` 与 `audit/INDEPENDENT_COMPLETE_*.json` 保存独立复核。
- `learning/`：因果观测、请求、reference 和冻结 action 身份。字段的单位、采样时刻及新增解释见 `LEARNING_DATA_SCHEMA.json` 和 additive causal-schema audit。原请求参考误差不能直接当作与当时发出参考同步的 tracking error。
- `ATTEMPTS.jsonl`：所有 START/END；`ATTEMPT_ACCOUNTING.json` 对继承前缀和新增 native 计算分别记账。

## 仅离线重建分析

以下命令只读取现有物理记录，不启动仿真。应从 canonical 包运行；Windows 镜像并不包含全部原始数据。

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python -B aggregate_delivery.py --package "$PWD"
/home/hank/envs/adaptive-online-rl-v1/bin/python -B extract_cross_sensitivity.py --package "$PWD"
/home/hank/envs/adaptive-online-rl-v1/bin/python -B make_cross_figures.py --package "$PWD"
```

重新生成会改变分析文件的生成时间及 SHA-256，因此正式归档后的再次分析应写入新分析版本，并保留本轮最终 manifest。独立积分复核入口为 `cross_analysis.independent_verify`；它读取完整 native/receipt/trace，不调用物理步进。

`serial_campaign.py` / `cross_runner.py` 是本轮物理执行记录中的封装，不是自动续跑入口。正式结束后所有 owned 物理进程退出，禁止对本包重复 START，也不自动开展 P1、工作包 B 或 Learning。新研究必须建立独立版本和新的预注册。

## 可复现性的边界

本轮为确定性科学仿真，最高证据等级 `PHYSICAL_LEVEL1`。P00 与历史 W1 的科学 trace/native/receipt 字段要求精确复现，墙钟 profiling 不属于该恒等要求。相同配置的确定性复现不构成新的患者样本，host wall-age/实时调度、硬件与临床资格均未由本研究证明。
