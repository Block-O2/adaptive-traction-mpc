# 原生 fixture 集成报告

只从已验证原TAR复制三个缺失成员到原包 `research/side_studies/ihear_overnight_control_learning_transition_v1/source/results/D01R_{parent,B,H150}/runtime_artifacts.json.gz`。逐成员路径、bytes和原SHA与deployment/b_h150_fixture_manifest.json完全相等。未提交TAR，未新建重复fixture树，未拆分二进制，原归档保持不变。

全部32文件现在由Git原生路径提供；旧29项没有重新复制或改写。保留已有manifest的archive历史身份，deployment/data_catalog.json明确当前数据为GIT_NATIVE_ORIGINAL_PATHS；旧文档“需要外部归档”是上一轮历史状态，新的操作说明以本目录和根README为准。

默认 `deployment/score_b_h150.py --work-dir <新目录>` 使用clone自身的真实fixture；保留--fixture-dir兼容原有外部恢复布局。--config选择原D01R/W1配置。原合同、v6和模型身份先校验；随后调用原measure / compare / independent.measure。原收据报告逐字段、原motion数组逐元素、原MEASURED全部科学字段及上一轮原scorer comparison全部字段均对照。没有减字段、替换scorer或改变阈值；仅原sources/execution_lineage_path位置元数据随新目录变化。

本地实际重算parent/B=1436.456498145051 N·s，H150=1402.6432114861727 N·s，gain=2.353937394034738%。原receipt/motion/指标/资格门一致。新鲜GitHub clone验收结果另见FRESH_CLONE_VALIDATION.md，不能把本地通过冒充新clone通过。

保留9合同、23来源、16锚点、1426 v6全部原hash；原parent checkpoint未找到，没有生成替代品。FULL_FORK_REPLAY_READY=NOT_RUN。不存在通过fixture原生集成自动获得的物理、host realtime、患者泛化或临床资格。
