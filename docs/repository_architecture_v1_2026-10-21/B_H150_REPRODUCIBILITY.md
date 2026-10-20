# B/H150 原离线评价复现

## 最小操作

在固定commit的新clone根执行，Linux x86_64 / CPython3.12。系统需有python3.12-venv；缺ensurepip时，可设置PIP_BOOTSTRAP_PYTHON为受信的带现代pip的Python解释器，它只向新venv安装hash锁中的wheel。不得把旧研究环境site-packages放入PYTHONPATH。

```bash
bash deployment/install_offline.sh
python3.12 -B deployment/verify_b_h150.py --config deployment/configs/b_h150_original_v1.json
.deployment-work/offline-env/bin/python -B deployment/score_b_h150.py \
  --config deployment/configs/b_h150_original_v1.json \
  --work-dir .deployment-work/D01R-original-score-001
```

每个输出目录必须新建，禁止python -O。无需外部归档、手动解包、旧研究根或parent checkpoint即可重算这份历史输入。校验失败退出非零；原断言保留启用；新输出包括OFFLINE_SCORER_RESULT、RUN_PROVENANCE、OUTPUT_MANIFEST及原MEASURED/receipt/motion/independent结果。

模型Hash和XML引用静态校验由verify_repository/verify_b_h150完成；编译模型需RL-B CPU锁环境，见RL_B_REPRODUCIBILITY中的check_models。离线算术只需NumPy2.2.6、SciPy1.15.3，不导入MuJoCo/Torch/runner。配置seed2026102001来自原D01R_PLAN.condition，不重新运行随机实验。

| 项目 | 本轮范围 / 结果 |
|---|---|
| OFFLINE_SCORER_READY | PASS：真实parent/B/H150输入原scorer重算；新clone证据单列 |
| 历史D01R/W1 matched comparison | PASS：原科学模式receipt ownership与原运动门，全部比较字段一致 |
| FULL_FORK_REPLAY_READY | NOT_RUN：缺完整父checkpoint，不可从摘要恢复live os.fork状态 |
| MATCHED_EVALUATOR_READY | NOT_RUN：指新cold commissioning/prefix/live matched物理评价；不把历史重算当新资格 |
| 原模型XML编译 | PASS：robot-only UR10e/CR12三上下文；动态物理NOT_RUN |
| host realtime / hardware / clinical | NOT_RUN / 未取得资格 |

冻结9合同在config中逐项固定，并与23项来源、16项历史锚点和1426项v6检查。原FROZEN_SOURCE_CHAIN_HASHES SHA=21c72a6081bda991928a07fb5ede5c606ac0807d56c14c55ddcc3245de8e9274。完整fork还涉及原CPython3.10 Linux扩展和不透明原生状态，Python3.12 import通过不能消除此问题。

原B是D01R/W1非零prefix下B；H150是完整FROZEN_18D + T/D/ER/RETURN5 hip timing。完整TASK prefix+suffix、5ms左积分、0.25ms native、100ms年龄、receipt/torque/step和运动阈值不变。B/parent JF=1436.456498145051、H150=1402.6432114861727 N·s；gain=2.353937394034738%。这是历史科学仿真数据算术复核，不能解释为新的独立实验或新患者结论。

原实验生成时Git commit未在本轮可证据中确定，保留UNKNOWN并使用原SHA闭包。RUN_PROVENANCE的source_commit是本次重算源码commit；published_source_payload_commit是源码发布基线，二者不冒充原实验生成commit。
