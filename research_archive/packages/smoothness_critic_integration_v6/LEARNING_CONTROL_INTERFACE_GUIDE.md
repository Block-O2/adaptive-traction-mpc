# 执行接口与复核入口

CONFIRMED：仅在独立v6包运行，正式B/H150/18D、Human/robot/cuff物理、原clearance guard、task/scorer与历史模型未被替换。实际Python为../rl_b_cloud_v1/.venv/bin/python，numpy2.2.6/scipy1.15.3/MuJoCo3.10.0与v5相同。首次误查旧报告的不存在环境路径及未使用的本包pip bootstrap只是工程准备，不算物理尝试。

CONFIRMED：source/v6_common_worker.py实现一次当前决策后恢复COMPOSE；v6_test_worker.py增加冻结模型现场预测身份记录；v6_legacy_worker.py保留原B后续；v6_worker.py用于整段固定方案。v6_features.py只读当前因果状态；v6_model.py/v6_eligibility.py/v6_selection.py分开成本、观测峰值风险和完整资格风险；v6_online.py在H保存预测，完整summary尚不存在。每job的SOURCE_MANIFEST与配置SHA为实际执行身份，未使用的复制历史工具不自动运行。

CONFIRMED：source/v6_prescreen.py是传统phase动作库均值规则，执行前打分并依据阶段有效坐标去重，原planner/admission/guard仍决定所有实际写入。代理拒绝/回退不替代原门。S1/S2开发更新与S3/AUDIT冻结验证分离，所有未执行身份可核查。

CONFIRMED：部署入口是v6_selection.select，v6_model.py保留的旧select未用于本轮冻结选择。主模型的score_index=3使用菜单中心化tail JF作相对排序，不能把该score当绝对剩余JF；绝对tail JF/JM/remaining duration另行重算误差。阶段库也使用已付费历史标签，并不是零开发成本。

复核：source/v6_scorer_replay.py直接调用原evaluate_execution_mode，绕开缓存并独立重建native motion；v6_identity_replay.py逐字段比较v5匹配轨迹；protect_history.py审计所有历史文件；VERIFY_PACKAGE.py只读验证本包manifest。主端点结果见END.json，全部物理START/END见runtime/ATTEMPTS.jsonl。

NOT_TESTED：没有廉价候选H状态预测器，因此Critic菜单还不是低成本在线控制器。原native精确资格在线monitor、完整lifecycle历史充分性、host实时、硬件、患者泛化、临床舒适度均未资格化。不自动运行Stage2、最终Campaign、下一轮研究或Git写操作。
