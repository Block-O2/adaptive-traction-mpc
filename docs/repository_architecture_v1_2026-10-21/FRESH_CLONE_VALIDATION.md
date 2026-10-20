# 新鲜 GitHub clone 验收

结果：**GITHUB_ONLY_PASS**，适用范围为原D01R/W1历史离线scorer、当前Stage3–5资产、封存RL-B CPU导入和轻量单测。不是物理运行、训练、checkpoint恢复、新live matched、host realtime或完整科学资格PASS。

## 固定提交与隔离

真实网络clone：`git clone --depth 1 --single-branch --branch codex/local-research-sync-20261020 git@github.com:Block-O2/adaptive-traction-mpc.git`，新独立目录，随后detached checkout `fc0dc94d417a83caf8453070173ee08ad5b929fb`。clone从GitHub取得32项原始fixture，不使用旧TAR、不读取旧研究根作为输入、不用合成fixture替代历史数据。clone最后保持clean。

两个全新CPython3.12.3 CPU venv，分别按2包离线锁和35 wheel RL-B完整锁安装；pip --require-hashes和pip check成功。系统缺ensurepip，使用受信本地现代pip的--python向新venv引导，未复用旧研究site-packages。公共依赖wheel下载是环境安装，不是额外研究数据恢复。

测试访问门以独立.pth导入唯一模块放进新venv site-packages，sys.addaudithook拒绝旧main/side根的open/listdir/scandir/chdir，子进程继承；先用两个必失败probe验证生效，再执行全部测试，未出现额外旧根访问尝试。它是Python文件访问门，不是操作系统/C库文件系统沙箱；XML编译使用clone中明确列出的6条模型路径，scorer模块绑定和输入SHA也核实来自新目录。原hook源码在deployment/tests/sitecustomize.py；日志见evidence/logs/expected_guard_probes.jsonl。

| 检查 | 状态 | seconds |
|---|---|---:|
| network_clone | PASS | 119.588 |
| checkout_fixed_commit | PASS | 0.132 |
| install_offline | PASS | 7.094 |
| install_rl_b | PASS | 32.986 |
| install_guard_offline | PASS | 0.139 |
| install_guard_rl_b | PASS | 0.068 |
| guard_probe | PASS | 0.034 |
| source_static | PASS | 5.886 |
| fixtures_and_contracts | PASS | 0.926 |
| identity_failure_tests | PASS | 0.318 |
| models_compile | PASS | 1.319 |
| original_offline_scorer | PASS | 15.362 |
| rl_b_import_and_units | PASS | 6.237 |
| shell_syntax | PASS | 0.038 |

## 实际通过范围

- 3079来源、2237 Python语法、Stage3–5的141项XML资产引用、450封存RL-B文件、28 vendor身份。
- 32项真实fixture146542129bytes、9合同、23 scorer来源、16历史锚点、1426完整v6、90模型资产身份。
- UR10e/CR12三个上下文共6份XML编译通过，零物理步进。
- 原parent/B/H150 measure与独立算术，原receipt逐字段、原motion数组逐元素、原MEASURED指标/资格与comparison全部字段一致。parent/B JF=1436.456498145051、H150=1402.6432114861727 N·s、gain=2.353937394034738%。
- 原RL-B verify_package/test_guard/test_g4/test_execution_contract/preflight共5入口通过；5项维护完整性失败测试通过。
- RUN_PROVENANCE记录实际commit `fc0dc94d417a83caf8453070173ee08ad5b929fb`、source_dirty=false；OUTPUT_MANIFEST的53文件逐一重算SHA通过。上述输出目录均新建，不覆盖冻结证据。

| 能力 | 分类 |
|---|---|
| 原历史D01R/W1 offline scorer | GITHUB_ONLY_PASS / OFFLINE_SCORER_READY=PASS |
| 封存RL-B环境、导入与原轻量单测 | GITHUB_ONLY_PASS |
| 当前模型身份与robot-only XML compile | GITHUB_ONLY_PASS；动态物理NOT_RUN |
| 历史Stage1两份Mac/UR5e XML | FAIL，40处缺失mesh引用；未扩大本轮PASS范围 |
| Full fork / 完整parent checkpoint | EXTERNAL_DATA_REQUIRED且完整checkpoint未找到；执行NOT_RUN |
| 新live matched evaluator资格 | NOT_RUN；历史配对离线comparison单独PASS |
| 原RL-B checkpoint实际restore / PPO训练 | NOT_RUN；接口及原门保留 |
| 其他全量历史raw/轨迹/checkpoints | EXTERNAL_DATA_REQUIRED，多数NOT_PORTABLE |
| 德国服务器当前版本或部署 | NOT_RUN / UNVERIFIED_NO_CONNECTION |

首次访问门自检失败及仅测试层修复完整保留于evidence/failed_access_guard；失败后未执行科学验证，另起全新clone/环境重新验收。完整命令/退出码/时间见evidence/FRESH_CLONE_RESULT.json；实际环境、独立算术、模型和访问门日志随报告提交。README中的命令使用相同入口和参数；原封存README物理smoke/训练段未执行。

## 文档提交与最终收据

本文件记录已实际测试并推送的payload commit；随后的验收文档提交只增加/更新docs。Git跟踪的GIT_SYNC_VERIFICATION.json因此是明确的payload收据，不能在文件自身嵌入其所属commit hash形成自引用。最终推送后会从GitHub fetch/checkout最终commit，复核并输出独立FINAL_POST_PUSH_RECEIPT；用户交付的GIT_SYNC_VERIFICATION.json记录最终精确HEAD。最终验收不通过则不得使用PASS收据。
