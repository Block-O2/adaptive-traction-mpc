# 参数合同最终采用说明（记录说明，不修改预注册）

记录时间：2026-10-19T14:46:39.862949+08:00（Asia/Shanghai）；原预注册时间：2026-10-19T13:55:58.547818+08:00。

本说明解释 `PATIENT_VARIATION_CONTRACT.md` 草案中已经由执行前预注册确定的选择。草案原始字节保持不变，备份为 `audit/PATIENT_VARIATION_CONTRACT_BEFORE_ADOPTION_NOTE.md`，SHA-256 为 `1d0d4589ef66c3abbbc4cc111be4a8b24bc08d192cb6357bc3958c1074015b4a`。原草案是否绑定于执行源码 manifest：false；是否在 `PREREGISTRATION.json` 中记录其独立哈希：false。因此不把本次补充说明回写成历史预注册文件，也不宣称新增了一项执行前注册。

实际采用的患者顺序为 **P00 → P01 → P02 → P03 → P04 → P05 → P06 → P07 → P08 → P09 → P10 → P11**。依据是执行前的 `VIRTUAL_PATIENT_COHORT.json::order`、`PREREGISTRATION.json` 和 `serial_campaign.py`。队列文件 SHA-256 为 `5b8b9826b5db56169763120ddb1cb83cf9632149857040594b3f303b5b0ac4e7`，核对结果与预注册一致，注册时间早于首个 START。草案曾给出的另一“建议顺序”没有被采用；本说明不依据后来结果调整次序、患者或阈值。

质量扰动统一采用现有 `HiddenHumanV2` 的 `thigh_mass_scale` / `shank_mass_scale`，构造基准 `body_mass_kg=75.0` 在全部 12 个配置中保留。段质量为 `75 × 0.099 × thigh_mass_scale` 和 `75 × 0.060 × shank_mass_scale` kg，未再对基准体重重复缩放。P01 使用 0.8/0.8，P02 使用 1.2/1.2，P11 使用 1.1/0.9；所有实际段质量已逐项与 `patients/{id}/static/MODEL_STATIC_AUDIT.json::resolved_properties` 一致核对。COM、长度和惯量仍按原生成模型一致更新。这里的 75 kg 是构造基准参数；这些是下肢段的工程敏感性扰动，不构成临床体重或人体参数分布声明。

实际执行环境为 `Ubuntu-Research-Verify`，Python `/home/hank/envs/adaptive-online-rl-v1/bin/python`（3.10.21），MuJoCo 安装发行版 `3.10.0`，NumPy `2.2.6`。原生物理步长为 0.25 ms，控制/主积分轨迹为 5 ms，证据模式为 `SCIENTIFIC_SIMULATION`。版本号通过安装包元数据读取，本说明未导入或启动模拟器。

规范源码位置为 `/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1`，历史冻结来源为 `/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1`，执行源码总 manifest SHA-256 为 `dd86ed21f9ae3ef64537cacb8f0b9780165212081605e60cc022f1adc1a0641c`。生成侧是 `patient_models.py` 和冻结 `source/.../fresh_qualification_v1/scenario.py::hidden_plant / HiddenHumanV2`；执行侧是 `cross_runner.py` 继承冻结 `control/campaign_v2.py`，由 `serial_campaign.py` 串行拥有各患者进程。每患者实际模型/控制先验身份见 `audit/{id}_RUNTIME_MODEL_IDENTITY.json`；P0 控制先验仍是冻结 `high_rom_deployable_prior`，真实患者参数只进入 plant 生成及离线审计。该身份核对不等价于任务通过。

本说明不重写患者参数、B/H150 动作、任务目标、安全界限、运动接受协议、失败规则、积分口径或未来患者保留规则。P1 仍仅为协议，Learning 未训练。全部执行结局及分母另见 `CROSS_PATIENT_EXPERIMENT_RESULTS.json`、`CROSS_PATIENT_QUALIFICATION.json`、`derived/REPORT_STATISTICS.json` 和最终报告；本文件不添加任何成功或失败结论。

机器可核验记录：`audit/CONTRACT_ADOPTION_RECORD.json`。P09–P11 在当前描述性研究中已暴露，未来若据此设计模型或控制策略，需要另外未接触的患者身份作为确认集。
