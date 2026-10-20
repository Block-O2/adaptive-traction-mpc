# 活跃能力与保护证据

本轮保留所有既有源码、数组、模型、训练标签、native library、配置、短摘要和 trace；20 个历史范围只删冻结清单中明确的详细 runtime 历史及9个旧 process-scoped snapshot。保留不是对每个文件作永久保护承诺，下一轮须再按真实依赖判断。

## ACTIVE

- 主仓库 B/commissioning/observer/native scheduler/governor、安全阈值、当前 harness 及其环境保持原路径和内容。
- 所有近期 M2 包、b_fast_jitter_m2_host_v1、b_runtime_qualification_decoupling_v1 完整保留；活状态 fork、same-action replay 和非零 native 执行证据完整保留。
- b_native_learning_matrix_v1 完整保留：旧 `_DATA.json`、80 分支 dense/native qpos/qvel 原始来源仍供当前 Neural Q / counterfactual motion 标签审计使用；不能仅保留其报告。
- m2_neural_q_motion_v1 的 NEURAL_DATASET、Q_32/Q_64、validation histories 和恢复后的旧 MLP，direction-prior 的各版 weights/DATA/candidate masks/labels，全部保持。
- 061/062 durable 原生输入、主库 `.pkl.z`/模型 checkpoints 以及科学 fork 实现/依赖均未删除或解包执行。

## KEY_EVIDENCE

每个已删历史范围的基线、最优/确认、same-action replay、代表性失败/abort/mode 的详细 raw 保留清单，逐条见原包 STORAGE_RETENTION_V2.md。所有已有 sampled trace、summary/config、结果、request/decision、失败记录与来源 hash 保留。保留集用于原 task-sampled 指标核对；不能代替已经删除的 dense 原生步证据。

## 已完成保护验证

- 93,261 个原有保留常规文件的 device/inode/size/mtime/mode/nlink 一致。
- 50,448 个保护文件，共 43.152785 GiB 内容，前后 SHA256 一致；聚合摘要 `6d55a9cf30c07dd0c47d9f38533e213b55e2d5890636a2eee310c7752d1c774e`。
- 2,575 个原链接保持 target 和可访问性，无新断链；删除条目 nlink 均为1。
- 原科学报告字节未修改；新增 main REPORT 为原报告的完整带来源拼接，删除前生成；20 个范围的保留补充在删除前冻结。
- 4 个当前 NPZ 完整 CRC/数组读取通过，浮点/复数数组有限值检查通过；没有加载 pickle 或运行控制器。

## 关键权重、数据与 fork 文件

| 文件 | bytes | SHA256 |
|---|---:|---|
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1/weights/frozen_Q_v1/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1/weights/frozen_Q_v1/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_multirate_realtime_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/weights/v1_repeat_seed2026100691/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/weights/v1_repeat_seed2026100691/weights.npz` | 283741 | `bf29ac2ce51935922f25979ebf10dde3c0122a10f7d300a78e1d3cac6357b2dd` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/weights/v1_seed2026100611/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1/weights/v1_seed2026100611/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_q_realtime_integration_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_q_realtime_integration_v1/weights/frozen_Q_v1/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/b_runtime_qualification_decoupling_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/15a727c8a9452016e915e3e7a044e990a6fa6d6bc15f66df6b8d7bc914c93ddb/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/1aef66d76d884bf389deda67db431cc22af7700a5561af1ef199ec711b20eaac/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/1b5767807b30a052a1c9a19a5fd717e22ea7648a5732230948b02092f20e0e4f/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/1c22a4075906c959009715dda55a1df49dc40520f5b7f985433d171ea387f582/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/2625d028a758ec0e0997204eeeeba995c50d0a087a40d88756f2deef7870dd51/deps/fork_core.py` | 4727 | `f08cfd96dafb96f122a9ee24f9960f05d708c6a7cc25a2de110e686b31c3c35a` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/287188499c2d483bab1f6a1b4b4aa08cb9d4be80377dcfa37df583a4ab4bd15c/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/32f6b94c5ef4919b00548f84f96f5156e33c8fd1c4186f4ead3ebf34ff093148/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/33f196730c638658baeef3ff04d3f98173300309708f362c2d869372ebd38801/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/354a5fbe5d4abcb4624e1e03fafade1ff5749a8a98146e48ea3da55e335e0cb8/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/4acbd631a269fedd74768c4beabc16ba1122fa7937fc5251628a80d42bf0f8b3/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5130b95999bd88dad14265161bb3ce38f1addc31fa8e877a57fef6f27a361a40/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5458ab06d39fa8385cbfdda9a9e98b74c535ae86d551edf71d0f544f0e337527/deps/fork_core.py` | 4727 | `f08cfd96dafb96f122a9ee24f9960f05d708c6a7cc25a2de110e686b31c3c35a` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5a6b0ec17aead1df88176cf0907961a6487d9a8bd6792bec0080d641678c64ad/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5a6f625f0f58c1b424b2cfa5647f006bc07b5e2689e232e672a2abb7f3f169a5/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5b40f6b8e88aae1083546a44628c29e056caefb1cef265b0efd846d4dec8ab45/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/5f740a1206f61eaec499764ca1ff0595ce7aa6705654098bad36745be4b3f09e/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/71cde17aa721688d52a3e110c10898dc71f3eeaa142fd7824ff0ab1f20f1de12/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/738fc69398249aa17ec67615c30a96936b3928c7d11772d3b2cbefe32260c21b/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/7bb836400e911bb58dc9272ea83b3f6dc9b3fd537fe44f2c3e26326251a846f5/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/7eac6d82799bbb7d64ea0526c75271293a67b24e5535b0b6f16bfc263bd037c6/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/8db7ab35deaf280dd2811af2db6312188c237cdc4cb0b4d6fbde62c2d52555bb/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/90b111c9daa23fe237a43581709d1d037ced796ba7be91e6264d3e76bfda43a9/deps/fork_core.py` | 4727 | `f08cfd96dafb96f122a9ee24f9960f05d708c6a7cc25a2de110e686b31c3c35a` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/98f16d76d995e20bffdc2dd7958f97cd62165c2a786f879571ada178d1723191/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/bfb358fb8e64c5027d5f1f8c80165c9bd8864df5d70c90f63996e118a65e08a8/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/c3838634e4e40852df9e4cfd845c561050994804b64edf37c315c1dcff58c1c4/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/c852f3e5530b66735c8e6b9322cbcdff4cc4143499dfb4880362fe51be8eca26/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/d31da8fbb34c4c4fbff36af2bc7c2c5580287cc1d15414f15c869a904bc5741b/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/db0a0c3821f1f4fde2b4bbe263e1cab10d978eefd76253b7ebb4b1ec8bfd6929/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/e61d1f6be6ccf08c997e51297c0b415c5faf76f60109990f0c2acdac46426659/deps/fork_core.py` | 4168 | `22e90d4c092333dd9f7eef35ac41e18e8168ee324ab2749e4555a765285c43fb` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/eb7b2e9793ecab76d8c82a25c7ab1e5ca4ad00fe4688a024688c832ed9e646a2/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/ebe8f5bebb7f719ee0165fa4cc4db30a4b2d8466da46d52d6204a8b01a5e0230/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/ec022473c95dbdd0e7e255e59124f80748362ba2e061136547f2899058732076/deps/fork_core.py` | 4727 | `f08cfd96dafb96f122a9ee24f9960f05d708c6a7cc25a2de110e686b31c3c35a` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/f1715903218437ef1ffcb63ac840ed6efef07b95a7d0a86f573268150723719b/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/f70975b11288600c07a7f6644cd6d66d8b8b8066a1e6aef7e895adc3e1391af9/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/code_history/fd537c119024b08faf64e6e9567387e2239c3ac0f6b4b5ff1ccd2e4ba76cbd13/deps/fork_core.py` | 3632 | `69b0a6ba0d66ba845b6e8cf8b62a0706cbb32c13e99c0dea9cb830bfd4020a04` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/v_horizon_continuation_audit_v1/code_history/75134ed481922babf168ede927c8a161a66e32d3a411a32a861d3a737f066a48/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/v_horizon_continuation_audit_v1/code_history/8a7850ce64b6707197473c87fee3403fd97d3fab438e1150defb256e9978c3e6/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/v_horizon_continuation_audit_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/weights_v1_seed2026100601/networks.npz` | 276628 | `4d65c03a41a0767c8a8395bdf91e8739b460dba60a544eafc9e19cde4a5e41c6` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/weights_v2_seed2026100602/networks.npz` | 275903 | `b74dd6a82b8e5c1028e85459663dc8bfe62de74459ae349e55b845fa83ac16ae` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1/weights_v2_seed2026100603/networks.npz` | 275755 | `d6baf236e44953ee2778528897e6671d02b0d2f3b861335b5021da2da69e845e` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_coordination_space_exploration_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_coordination_space_exploration_v1/weights/frozen_Q_v1/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_coordination_space_exploration_v1/weights/frozen_Q_v1/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/weights/frozen_Q_v1/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/weights/frozen_Q_v1/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/deps/fork_core.py` | 4712 | `1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/weights/frozen_Q_v1/DATASET.npz` | 31752 | `ddc3dd6d581ec2e9c52465fbf5d8a685b8091edf4e2617303c6286c3ea73d9f4` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/weights/frozen_Q_v1/weights.npz` | 283720 | `3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_neural_q_motion_v1/NEURAL_DATASET.npz` | 7787 | `17cee97378e1e7ed65d9fb5e2776738ec85864c7316023956c6bb8a28bdcc33f` |
| `/home/hank/coding/adaptive-traction-mpc-side-studies/m2_neural_q_motion_v1/models/Q_32.npz` | 21647 | `2f242e87218063fc22ced59434aa85efafc3691e53a718b60b1bdb5fd939716d` |

## Git 保护

| 仓库 | branch | HEAD | index SHA256 | staged diff SHA256 |
|---|---|---|---|---|
| `/home/hank/coding/adaptive-traction-mpc-learning` | `codex/expert-strength-value-adequacy-v1` | `41cdddef117caa4b191a52129c4ff83e481fd5a8` | `1bc691b825d8bf3b528ce84dd0384fbbd1b84aace4e45156094b6b60c64208d5` | `3ae02237deadca6c8833cedf8eb4cef59f2933ac471d445b88ac01d0472e2461` |
| `/home/hank/coding/adaptive-traction-mpc-human-closeout-git` | `codex/lab-human-adaptation-r2-closeout` | `4246c4ea9edb74866ca0ae5946599be913486676` | `590febc51ffcbf455d2854eae6eac8d5f085a9ca15ac25e6515004e5220e012f` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `/home/hank/orca/workspaces/adaptive-traction-mpc-learning/codex-direct-rl-expert-v1` | `codex/direct-rl-expert-v1` | `41cdddef117caa4b191a52129c4ff83e481fd5a8` | `4207a1911ad2efbd0f9303e61c95865bc9ef2e4ce0f66229ad8efbdaeffc77f5` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

主库 status 保留 2288 个 porcelain NUL 记录。三处 branch/HEAD/status/untracked/worktrees/refs/index/staged diff 前后完全相同，完整基线在 DELETION_MANIFEST.json 和 PACKAGE_VERIFICATION.json。Git read 使用 GIT_OPTIONAL_LOCKS=0；无 clean/reset/stash/checkout/commit/push。
