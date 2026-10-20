from pathlib import Path
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name
text='''# 复核与重现入口

本版本完成后禁止原地重启physics或覆盖任何raw/账本。新增physics须新版本并另有用户授权。本轮owner命令、pid、START/END与冻结manifest引用见V1_OWNER.json、V2_OWNER.json、ATTEMPTS.jsonl和ATTEMPT_ACCOUNTING.json。

canonical：/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_expanded_prefix_validation_v1
Python：/home/hank/envs/adaptive-online-rl-v1/bin/python -B
发行版：Ubuntu-Research-Verify。实际库版本见audit/EXECUTION_ENVIRONMENT.json。

冻结执行闭包：source/、code/、deps/、weights/、control/，逐文件SHA在EXECUTION_CODE_MANIFEST.json，事前PREPHYSICAL_CHECKS.json确认语义只有路径迁移、T源码字节等同上一轮，所有18D参数及门不变。analysis/是后续离线算术/报告源码，明确不属于物理执行闭包。

每臂真实raw：source/results/<id>/{trace.npz,summary.json,native_reference.npz,runtime_artifacts.json.gz}。全部native状态只用于evaluation。reports/*_MEASURED.json保留完整与phase指标；*_EXECUTED_RESIDUAL_RECEIPTS.json保留原执行归属；motion_series/来自0.25ms真实qvel，含未经删点的gradient加速度/jerk。EXPERIMENT_RESULTS.json收录B/18D/T/重复完整与phase数据及配对差。

可用control/independent_recompute.py只读重算完整/phase力矩积分、native映射/导数/dose、receipt torque/steps与source SHA。关闭包不直接调用它的main写回原derived。将其复制到另一个新审计目录，或用importlib加载后将模块P绑定canonical、put绑定新的独立输出sink，再逐id调用measure(id)。它不导入controller/plant，也不启动physics。数值schema与全部源SHA应精确闭合。

时间审计入口：analysis/author_audit_contract.py针对历史N2/U1；analysis/new_time_audit.py针对本轮V1/V2。两者会写审计输出，重算时同样须绑定新sink，禁止写回已关闭包。它们独立从schedule边界求quintic，并逐suffix/carry receipt对照q/dq/progress、检查native torque/steps归属；原request/activation与phase physical clock均保存。receipt无直接plan_request_id的限制已明示。

完整保护范围、原Git状态和最终SHA/metadata核验在audit/及PACKAGE_VERIFICATION.json。E的所有旧/新失败和N2/U1历史结果保留，不用重算结果追改历史资格。
'''
(P/'REPRODUCTION.md').write_text(text)
print('REPRODUCTION_WRITTEN')
