# 最小复现与只读重算

canonical包保存code/source/build/native/weights及冻结参数，原主Git未写入。Python为`/home/hank/envs/adaptive-online-rl-v1/bin/python`，WSL为Ubuntu-Research-Verify，用户hank。PACKAGE_LOCATION指定canonical路径。

已完成同父zero/prior/repeat实测。完整关键raw、dense motion、trace、receipts及输出可重新核验；普通中间raw已在原核验完成后报告化，不能声称所有候选均可重新raw复验。

数据重算（不仿真，但会更新派生JSON）：从control依次运行`analyze_overnight.py`、`analyze_validation.py`、`analyze_mechanisms.py`、`actuation_evidence.py`。它们读取numpy/raw/json并写派生报告，不训练或调用plant。重算前应保留最终交付副本，或另设独立分析输出，不能把晚于deadline的重算当本次交付。verify_package会核验来源与实际资源，但09:30历史绝对deadline过后不应期待final时限PASS；final文件是本次实际关闭证据。

原physics启动命令由control/LAUNCH_*完整记录；runner在code/overnight_runner.py。launch/runner保留本次绝对时限与attempt账，不应覆盖旧目录或删除截止保护后重跑。本包已STOP，未来物理复现需另行授权、独立新目录/新时间预算合同、原模型与零调整复现；不能将现有结果当新unseen验证或续跑冻结搜索。

CODE_MANIFEST保护执行源码与复用文件；control/ANALYSIS_MANIFEST另列分析/绘图脚本。初始Git/复用源hash与晚捕获主工作区字节证据的边界见PACKAGE_VERIFICATION，不混称完整t0镜像。
