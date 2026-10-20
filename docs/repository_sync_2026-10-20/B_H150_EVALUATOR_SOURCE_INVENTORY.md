# B/H150 原始评价与恢复清单

canonical：`/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1`。原合同来自 `ihear_cross_patient_b_h150_v1/FROZEN_B_H150_CONTRACT.md`，D01R/W1 seed 2026102001；该 B 有冻结 prefix，不是零 prefix 开发 B。原 B candidate `5908d9453a12b2aae83c88d46d4926979b223ff4732a3984eda43ec3ca9af60b`；H150 `255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931`，均由本地 D01R_PLAN 核实。

H150 为完整 FROZEN_18D（含 RETURN plateau）+ T/D/ER/RETURN5 hip timing；不能只拿 18 数字向量或近似 scorer 替代。保留原 5 ms 左积分、0.25 ms native Human、完整 TASK prefix+suffix、原门限、原 receipt/age/版本和实际 intent 执行检查。

## 原源码身份与 Git 归属

9 个合同 SHA 锚点全部 MATCH；原 scorer/依赖另按历史 EXECUTION_CODE_MANIFEST_v6 验证。REPRODUCE.md 没有独立历史 hash 锚点，标 UNVERIFIED；`code/fork_core.py` 不存在，但实际导入由存在且 MATCH 的 `deps/fork_core.py` 满足，不是丢失依赖。

| 原相对路径 | 身份 | 进入 Git | 当前 SHA256 |
|---|---|---|---|
| D01R_PLAN.json | MATCH | YES | aba229fec433f1900dc6a419a0f3e52edb1f9a019368fac082754b50b0bcdbb5 |
| FROZEN_18D.json | MATCH | YES | 1d04594ff2ff088b83c94e424c6bd2cd02afa6f94330ffae2beb5727e545fc67 |
| ACTION_SET.json | MATCH | YES | 6f17b17e37160316323e8627638d5ed2e704a72addae794abcbb5ffcd80811be |
| MOTION_ACCEPTANCE_PROTOCOL.json | MATCH | YES | 0f41463cab96b71ea39cc06f9fe86f432de07efe307bd486bc1c4df6cc196ece |
| control/campaign_v2.py | MATCH | YES | d240993a5137c00d2336a80765165fda705553847282493b6b55a917b33c5d72 |
| control/base_campaign.py | MATCH | YES | 98cfe2df845a41dac272aaa71cc0d7ffffd84c0ec9b59ed97c1ae24270b64ad6 |
| code/study_common.py | MATCH | YES | 1f7c761cfda788778c18d0ee2d24e3d41ea4f43b4ca888b1334f52edcd67daa0 |
| source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py | MATCH | YES | 74d0f6b97b35671111bdd86bb4dfff845c90f2a12ee1cd9518de9445de99de79 |
| source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json | MATCH | YES | d9f4d636b98db5792cf4b50915f4509bf2274c1c80764d6d8629bf22e3ae9b96 |
| code/analyze_matched.py | MATCH | YES | 350ee608128c8799862cb5f9aa292083040647113bda93e2a85f03b76e84b997 |
| code/explore_common.py | MATCH | YES | 04299ca98f3c260cd4fb2e8043e195ad1ba880ccc2c191a6f2449001a10bb120 |
| control/independent_recompute.py | MATCH | YES | 6397d76fdde217c0a235b5686fecfed57fcf1b4fab6fbd06111470e54f377db7 |
| code/matched_harness.py | MATCH | YES | 10ed05441028084e727148c5b546f746aa33a050a71b43e08a239d05979ca719 |
| code/stream_runtime_evidence.py | MATCH | YES | c856bb8fed1532eaea204ea0fbcee962c8e72ad43a41eb957bbe858e01b7f619 |
| code/attribution.py | MATCH | YES | ce78805d3dc65163dcc621b62dac87888ddc28724a7a14e0c684508a79918403 |
| code/fork_core.py | MISSING | NO / optional or absent | MISSING |
| deps/fork_core.py | MATCH | YES | 1f5c4525932efe5df5514b2cfac18c6c369beb8f9e5438c3c8393256512008f4 |
| REPRODUCE.md | UNVERIFIED | YES | bc866f24069c4d39ed882196e3c00e7fe284303a9aa4ae187b8ae417aebd1948 |
| RUN_PLAN.json | MATCH | YES | 28c595dfb8c5a0e11624c331ea8dc10e40d08dbbbd55c974acfc164452a611d8 |


执行链：campaign_v2/base_campaign → matched_harness/study_common → 原 runtime；评价链：analyze_matched.measure/compare → explore_common.compare + stream_runtime_evidence，独立复核为 control/independent_recompute.measure。均保存原实现，没有新增近似评价。

## fixture/state/raw

| 原相对路径 | 存在 | bytes | 存放 | SHA256 |
|---|---|---|---|---|
| source/results/D01R_B/trace.npz | True | 3725337 | EXTERNAL | 9fa9b8d3b8f6c687e540dc9aefddd786f3cea8c477a4d14e1c0bcc134a3fb2c0 |
| source/results/D01R_B/summary.json | True | 2834454 | EXTERNAL | c877f77b949df154ccc10365f201163cdd321f70ac5db4810ae0eb846122c58b |
| source/results/D01R_B/runtime_artifacts.json.gz | True | 34306027 | EXTERNAL | f48fc5ad434a4502a2cfe5ba3cae7242ce81d5b528d00a627079ec2bfb7e79ff |
| source/results/D01R_B/config_snapshot.json | True | 2895 | Git | 19ac8b6bb9ada8ad1ef67c68de27f2b2ffbffecc0e191e8c11a40eaa79954140 |
| source/results/D01R_B/native_reference.npz | True | 148730 | EXTERNAL | c86e9eeeec9b65497007487500fc7c11b5935f2fc89c1dbbffef9e4f9ef52a94 |
| output/D01R_B_DATA.json | True | 39818 | EXTERNAL | 1e17dfb2b576195c1cef605e93555a0fd9b76d59ff6afe7ecd164cbc86cac912 |
| output/D01R_B_CAUSAL_STATE.json | True | 1215 | Git | d2008b2d8670763804590335f562bd78499eaf78287acdb14264821808779b17 |
| reports/D01R_B_MEASURED.json | True | 101480 | Git | b0e6489c80e1d88808fbc6d6d1dd211e5fd253170ef9ca6eef995d6c6d1ee9b2 |
| reports/D01R_B_EXECUTED_RESIDUAL_RECEIPTS.json | True | 3247346 | EXTERNAL | 50e992a6810fd7a699409c2069c71a0c376333d8e9dd8d3cf28a516070c2c35d |
| source/results/D01R_H150/trace.npz | True | 3717440 | EXTERNAL | 351c4a84e17ba26677b7d81a137bfaa0cb184551ef2469fa8fc0654df5515426 |
| source/results/D01R_H150/summary.json | True | 3090424 | EXTERNAL | ec041f5092a0d7070a5e89c0214b0708950cf2a7e342d66f0d404a98adcbd61a |
| source/results/D01R_H150/runtime_artifacts.json.gz | True | 34234559 | EXTERNAL | c6bc71330a0b83a6d852696b00c4c7a27424fef64c565f821f4358563564f68c |
| source/results/D01R_H150/config_snapshot.json | True | 2895 | Git | 19ac8b6bb9ada8ad1ef67c68de27f2b2ffbffecc0e191e8c11a40eaa79954140 |
| source/results/D01R_H150/native_reference.npz | True | 155385 | EXTERNAL | 1de473a6945a68bfa94560091e6a81528824ccec41d24f27ccce54ed66366c4c |
| output/D01R_H150_DATA.json | True | 39857 | EXTERNAL | 01accf05d0b7971b21ca3439255a51e33e5491236d93e418861d2d16b7250ffa |
| output/D01R_H150_CAUSAL_STATE.json | True | 1218 | Git | 7c4247a2625786d7376d3e334ce53335797fba3782a9b671265cea6d0a6d01b5 |
| reports/D01R_H150_MEASURED.json | True | 101637 | Git | 34012fbcb7f5f2af0e5900ae27d4b8c583c7bfdd2bdc995178113b8564917660 |
| reports/D01R_H150_EXECUTED_RESIDUAL_RECEIPTS.json | True | 3245693 | EXTERNAL | 8738153cf5247419ae060fcedb7aa72d36933d2eafa895528168c2d784d6b362 |
| source/results/D01R_parent/trace.npz | True | 3725337 | EXTERNAL | 9fa9b8d3b8f6c687e540dc9aefddd786f3cea8c477a4d14e1c0bcc134a3fb2c0 |
| source/results/D01R_parent/summary.json | True | 2834776 | EXTERNAL | 55b715c59ab8d25c0e8b2a4806317dbdbefaa397af35c539c3d4fdf88ef645d4 |
| source/results/D01R_parent/runtime_artifacts.json.gz | True | 34310122 | EXTERNAL | 01f6a526461c1a20bb3354dacc94e6eba6eb7f871c0fb1cff7ef0f00c7a8dc44 |
| source/results/D01R_parent/config_snapshot.json | True | 2895 | Git | 19ac8b6bb9ada8ad1ef67c68de27f2b2ffbffecc0e191e8c11a40eaa79954140 |
| source/results/D01R_parent/native_reference.npz | True | 148730 | EXTERNAL | c86e9eeeec9b65497007487500fc7c11b5935f2fc89c1dbbffef9e4f9ef52a94 |
| output/D01R_parent_DATA.json | True | 38193 | EXTERNAL | b687c3588c1b115005f38b9220a3a5aa7bd02d9854ef9ca53d787d1333c59b01 |
| output/D01R_parent_CAUSAL_STATE.json | False | None | NOT_LOCATED | MISSING |
| reports/D01R_parent_MEASURED.json | True | 100267 | Git | 7a4119f75af007752e92ca9a47587dd7ec9738d34db217a9486fe060dd44b54f |
| reports/D01R_parent_EXECUTED_RESIDUAL_RECEIPTS.json | True | 3250962 | EXTERNAL | 6abd7a2428c2b0357927495a667cd82eaf82e8f839fecb8237ffe54e9cf78278 |


上述可定位输入约 133407692 bytes；绝大部分 raw 需独立传输。D01R B/H150/parent 的 trace.npz、summary、runtime_artifacts.json.gz、native_reference、config_snapshot 已定位。紧凑 config/因果摘要/MEASURED 白名单可入 Git；raw 和 receipt/native 压缩证据不直接入 Git。

`output/D01R_parent_CAUSAL_STATE.json` 未定位；B/H150 的因果摘要存在。因果摘要不是完整 parent checkpoint；原 same-state 配对通过冷 commissioning、合法 prefix 后 os.fork 继承完整进程地址空间。**未定位可脱离进程独立恢复该父状态的序列化完整 checkpoint**，不能由 hash、qpos/qvel 或因果摘要代替。其他学习 state snapshots 保持其原合同，不能自动当作该 parent。

合同所指 `ihear_cross_patient_b_h150_v1/FROZEN_SOURCE_CHAIN_HASHES.json` 未定位；现有九个合同锚点和 v6 manifest 可核实，但缺失索引没有凭空补造。完整原始 evaluator 本轮 NOT_RUN。

## 下轮最小恢复集合

1. clone 本同步分支，选取完整 `research/side_studies/ihear_overnight_control_learning_transition_v1` 的 code/control/deps/source configs/models 与全部原执行 manifest、FROZEN_18D、D01R_PLAN、ACTION_SET、MOTION_ACCEPTANCE_PROTOCOL；恢复 canonical 相对目录，记录路径重定位差异。
2. 单独传输同一 D01R B/H150/parent 的 trace、summary、runtime_artifacts.gz、native_reference、config snapshot、output/*_DATA 与 reports/*_MEASURED、*_EXECUTED_RESIDUAL_RECEIPTS；用上述 SHA 逐项验证。需要独立复核的 reports/output 也在外部数据 CSV 中。
3. 先只读使用原 independent_recompute/analyze_matched；输出写全新目录，禁止覆盖冻结 reports。运行前必须按原源码依赖解析 canonical 路径，不能通过改门限或近似 scorer 获得 PASS。
4. 如果需要重建同父 matched physical run，则另外明确授权冷 commissioning+合法 prefix+原 os.fork，而非加载不存在的 parent checkpoint。本轮不执行该步骤。
