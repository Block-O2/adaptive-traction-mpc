# 只读恢复 / 封存交接

状态：B原R2未过，M2/Q关闭；本工作包固定t0=1791352438，硬结束1791388438，不能重置。

当前实际物理START 97 次，全部END并join；没有活动plant或TASK worker。启动失败同样已消费ID。未启动queue保留为事前诊断，不是自动待跑任务。

可运行只读入口：

```bash
/home/hank/envs/adaptive-online-rl-v1/bin/python /home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/code/reproduce.py --check
/home/hank/envs/adaptive-online-rl-v1/bin/python /home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/code/reproduce.py --review 099_N13_S2_D2_C6_host_nominal
```

Windows用run_readonly.ps1。Review会重新写该本轮派生资格报告，完成后应重做manifest；Check仅核验，无模型/物理步骤。完整封存hash使用FULL_PACKAGE_MANIFEST.json和封存核验脚本，不改原START/END和结果。

reproduce、fast_dispatch、cohort_dispatch都拒绝PACKAGE_CLOSED下的新物理派发；硬截止也在原派发器保留。不要直接执行run_one或继承的campaign/training/finalize脚本。

下一步唯一建议：新显式普通有界HOLD交接关键路径工作包；以原R2≤1.020 s为gate，保留原sensor dwell/shared minimum/reference/current安全权威。需要新authority则单列，不在本轮解锁。

全部源/环境/输入hash、时间、native/kernel、故障和资源证据留在/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1；查看REPORT.md和reports/RESULTS_OVERVIEW.json。没有持久physical session或在线学习更新可续跑。
