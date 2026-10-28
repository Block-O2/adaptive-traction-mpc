# 启动与证据来源

本轮先在正确原交接目录运行 `python3 unattended/next_launch.py --inspect` 并审查源码/全部hash。该正式inspect函数在隔离v2 launcher中原样复用，未删除任何原检查。

发现原模板STD可累计120集且只预留15分钟停止新物理，与当前用户STD总上限80及最后45分钟要求冲突；因此从已审计模板创建新版本，修正为两个screen后只延长一个方法。新启动器还保留无稳定STD时的独立R1/R4路径，增加完整候选SHA锁，未修改原交接文件。

实际启动命令（cwd为原交接包）：

```bash
python3 /tmp/ihear_v2_authorized_preparation/launch.py --prepare-authorized --start-authorized
```

启动器已归档在 audit/launch.py，其原正式来源在 audit/original_next_launch.py。激活前完成两父完整状态恢复、56项保存轨迹Reward重放和两个无物理队列场景测试，见 audit/ADMISSION_PREFLIGHT.json / QUEUE_TESTS.json / QUEUE_TEST_SOURCE.py。

训练与服务统一使用原已验证CPU环境：
`/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/cpu-env/bin/python`。

只读状态命令：`python3 scripts/status.py`。阶段进度在 PROGRESS_REPORT.json / RESOURCE_TELEMETRY.jsonl / STAGE_REPORT_{2,4,6}H.json，分支训练结果在 ALL_ATTEMPTS.jsonl / UPDATE_LOG.jsonl / jobs/ / runtime/jobs/。

独立只读分析可用 `analysis_tools/analyze.py --live`；完整finalizer由关闭器自动调用，不能在物理队列活着时手工重复finalize。所有分析代码的实际SHA和原始执行源码保存于 analysis_source_versions/ 及最终OUTPUT_MANIFEST。

未执行任何Git commit/push/merge/reset/stash/clean或原GitHub长期源码修改。
