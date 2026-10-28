# 失败机制与未排除解释

已证实的执行机制：固定时长的新空间proposal会被速度certificate拒绝，实际参考回退；RETURN逐关节终点未锁住会触发原task断言。保留初版全部raw/partial；修复只改变表示编译与原scheduler的调用，没有放宽原门。

已支持的预测机制：事后实际reference名义负荷重建与粗前向模板之间误差很大；数值导数输入消融解释一部分，剩余映射/准入/闭环差异需前瞻响应测试。事后结果不证明新学习器能预测未来。

失败/不合格计数：{'NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE2_POS': 1, 'NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE2_NEG': 1, 'NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE3_POS': 1, 'NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE3_NEG': 1, 'acceleration_deg_s2/max_abs': 2, 'jerk_deg_s3/rms': 4, 'excursion': 21, 'velocity_deg_s/p95_abs': 4}。

|ID|任务完整|原门合格|JF仅在完整任务可比较|错误/原门原因|
|---|---|---|---|---|
|INTERFACE_MODE2_POS|False|False|PARTIAL_UNRANKED|NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE2_POS|
|INTERFACE_MODE2_NEG|False|False|PARTIAL_UNRANKED|NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE2_NEG|
|INTERFACE_MODE3_POS|False|False|PARTIAL_UNRANKED|NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE3_POS|
|INTERFACE_MODE3_NEG|False|False|PARTIAL_UNRANKED|NATIVE_PHYSICAL_FAILURE:INTERFACE_MODE3_NEG|
|CORE_C_019|True|False|1399.857062|['acceleration_deg_s2/max_abs', 'jerk_deg_s3/rms']|
|CORE_B_021|True|False|1399.062933|['excursion']|
|CORE_B_022|True|False|1399.113108|['excursion']|
|CORE_A_023|True|False|1398.876018|['velocity_deg_s/p95_abs']|
|CORE_B_023|True|False|1399.880919|['excursion']|
|CORE_B_024|True|False|1398.639461|['excursion']|
|CORE_C_024|True|False|1400.772296|['excursion']|
|CORE_B_025|True|False|1400.441623|['excursion']|
|CORE_B_026|True|False|1399.079980|['excursion']|
|CORE_B_027|True|False|1398.740900|['excursion']|
|CORE_A_028|True|False|1398.740192|['velocity_deg_s/p95_abs']|
|CORE_B_028|True|False|1398.487410|['excursion']|
|CORE_B_029|True|False|1399.087532|['excursion']|
|CORE_A_030|True|False|1398.537938|['velocity_deg_s/p95_abs']|
|CORE_B_030|True|False|1398.314860|['excursion']|
|CORE_B_031|True|False|1399.690503|['excursion']|
|CORE_C_031|True|False|1398.262147|['excursion']|
|CORE_B_032|True|False|1399.547271|['excursion']|
|PPO_SCRATCH_TRAIN_0009|True|False|1400.243102|['jerk_deg_s3/rms']|
|PPO_SCRATCH_TRAIN_0030|True|False|1398.823083|['jerk_deg_s3/rms']|
|PPO_SCRATCH_TRAIN_0046|True|False|1400.343262|['excursion']|
|RESPONSE_MODEL_01|True|False|1397.711027|['excursion']|
|RESPONSE_MODEL_02|True|False|1397.820457|['excursion']|
|RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL|True|False|1397.711027|['excursion']|
|LOCKED_REPEAT_CF01_LEARNED|True|False|1399.857062|['acceleration_deg_s2/max_abs', 'jerk_deg_s3/rms']|
|LOCKED_REPEAT_FAILURE_DOMAIN_02|True|False|1402.030458|['excursion']|
|LOCKED_REPEAT_FAILURE_DOMAIN_05|True|False|1403.620489|['excursion']|
|LOCKED_REPEAT_FAILURE_DOMAIN_06|True|False|1400.967338|['excursion']|
|LOCKED_STATE_1_FROZEN_A|True|False|1397.026680|['velocity_deg_s/p95_abs']|


未完成任务的低积分不参与优胜比较。motion失败由原native速度/加速度/jerk、excursion、phase/endpoint及JM门定位；原绝对安全与原任务合格分开。没有由有限负结果推断Learning普遍无用，没有证明有限最优达到物理上限。跨患者参数、可部署motion观测和真正少次历史适应仍为未验证问题。


原链motion反例CORE_C_019已完成任务，但加速度max和jerk RMS不合格。原guard在27.070000 s的髋膝近等角位置，对圆柱最低端点切换做中心差分，得到曲率-1432.356195 m/s²、模型广义力矩修正[14.915400528209446, -4.408732069397653] Nm；native少数20点贡献jerk平方和约70.23%。原函数以已记录因果q/dq、gap/gap-rate充分输入重放，曲率和修正量误差均为0。直接物理trace几何与控制器重建Human点存在1.3mm差异，已单独保存；充分输入适配器只用于代数重放，不冒充完整物理状态重建。原native绝对安全审计仍通过；内部近似半空间不可行与原motion失败分别报告。

原始证据：`audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`；扫描差分模板跨越几何端点分支时曲率可达数千，留在同分支时接近0。该结果确认了既有反馈计算的冲击机制；时序参数能否稳定避免它，需下列预登记实测，不能从代数重放推出患者运动或安全替代方案。


四个原链条件干预（移除RETURN时长、±0.10、只保留该RETURN时长；初始±0.01因原5ms量化别名在实测前改为±0.10并保留原登记）：

|条件|结果|完整|合格|JF|JM|最小guard曲率|原motion失败|
|---|---|---|---|---|---|---|---|
|CORE_C_019|EXECUTED|True|False|1399.857062|108.090021|-1432.356195|['acceleration_deg_s2/max_abs', 'jerk_deg_s3/rms']|
|MOTION_CAUSE_TIME_ZERO|EXECUTED|True|True|1399.145959|107.732360|-0.068248|[]|
|MOTION_CAUSE_TIME_PLUS_010|EXECUTED|True|True|1399.849199|108.032128|-0.068248|[]|
|MOTION_CAUSE_TIME_MINUS_010|EXECUTED|True|True|1399.867996|108.146093|-0.068248|[]|
|MOTION_CAUSE_ONLY_RETURN_TIME|EXECUTED|True|True|1400.191384|108.101676|-0.068248|[]|


没有关闭guard或修改原门。`MOTION_CAUSE_RESULTS.json`保留全部四结果及开销；此分支不回填主A/B/C模型。


相同机制也在PPO_SCRATCH_TRAIN_0009出现：任务完整、仅jerk RMS不合格。22.000000s时实测gap约0.428376m，原包络差分曲率-449.597641m/s²触发广义力矩修正[8.880443536095054, -2.8059660784551106]Nm，随后髋native jerk在22.0005s达到约28608deg/s³。用原函数及该次已记录因果充分输入重放，曲率/修正量误差均为0。这支持GP与PPO的部分motion失败共享原低层非光滑反馈机制；不解释所有excursion或速度失败，也不代表PPO全部负结果都由它造成。 见 `audit/PPO_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`。


PPO第30次同样完成任务但jerk RMS失败，JF=1398.823083不能计为合格收益。原函数因果输入重放PASS：21.995s时gap约0.428344m，差分曲率−624.933894m/s²触发约[8.85168,−2.80086]Nm修正，髋native jerk在21.9955s达到约28503deg/s³。该证据单独保存在 `audit/PPO30_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json`，不将所有PPO失败自动归于此机制。


零native解析分解进一步确认：C19原差分曲率−1432.356195几乎全部来自端点最小值项−1432.356216；PPO第9次的−449.597641中端点项为−449.568162，光滑项仅−0.029479。两个观测点的10μs原差分均跨分支，单分支解析曲率很小。精确切换点差分存在1/h尺度项，但这些非零偏置状态在足够小h下回到同分支，不能笼统称h趋零发散。详见 [解析说明](CLEARANCE_CUSP_ANALYTIC_NOTE.md)。


补充motion余量回退已实测2/2个固定候选，最佳原门合格JF=1398.034615。这是原参考模型与传统成本模型共同低力动作失败后，利用过去单模态反馈只减小R_pass_speed的传统修复；不归于主GP或PPO收益，2候选+4冷启动/参照另计。0.49deg仅为额外余量目标，原0.5deg门保持。 见 [固定回退](MOTION_MARGIN_BACKOFF.md)。
