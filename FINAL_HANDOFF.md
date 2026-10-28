# iHEAR Lab 最终交接

归档源码及代表证据已上传独立分支，并从真正远端干净clone完成 **11项实际验收PASS**。原研究工作树与分支保留；没有新算法探索、Learning训练或服务器删除。

## GitHub身份

- 仓库：[https://github.com/Block-O2/adaptive-traction-mpc](https://github.com/Block-O2/adaptive-traction-mpc)，原公开可见性不作更改。
- 独立归档分支：[`archive/research-closure-20261028`](https://github.com/Block-O2/adaptive-traction-mpc/tree/archive/research-closure-20261028)。
- **已完整实际核验的源码commit：[`5586b946024c4a979aaa66287d9f2250a51dddb8`](https://github.com/Block-O2/adaptive-traction-mpc/commit/5586b946024c4a979aaa66287d9f2250a51dddb8)**。
- 原Git基点：`1adb1de177d6f5f32de6d01c4e629cbfae9ce121`。后续交接提交只增加文档、回执、清单与字节保真规则；执行源码/模型/参数不变。
- 最终交接提交SHA以 `git log -1 --format=%H -- FINAL_HANDOFF.md` 或分支HEAD为准；聊天交付会给出最终完整SHA，不把文档自身哈希写进自身形成循环。

## 保留成果与边界

完整传统执行底座及模型依赖、B/H150/18D和重要固定/平顺性方案、原任务/运动/安全/评分逻辑保留；更早与v1–v8 Learning的真实接入、训练/物理范围、失败和未探索方向综合写入知识库。原文件23,756项按SHA保真；代表原证据122项、151.54MB，另有实际新回执和原B native/trace约12.46MB。数据和图没有补写不存在的实验。

主要入口为 [README](README.md)、[系统架构](SYSTEM_ARCHITECTURE.md)、[传统控制](TRADITIONAL_CONTROL.md)、[Learning架构](LEARNING_ARCHITECTURE.md)、[方法历史](LEARNING_METHODS_HISTORY.md)、[实验与图](EXPERIMENTAL_EVIDENCE.md)、[失败分析](FAILURE_ANALYSIS.md)、[下一代讨论](NEXT_GENERATION_ARCHITECTURE.md)、[教授技术简报](PROFESSOR_TECHNICAL_BRIEF.md)。范围与精确身份见 [ARCHIVE_MANIFEST](ARCHIVE_MANIFEST.md)。

## 实际通过

- 新环境hash安装、现代源码/资产身份、模型加载、主文档/图片/源码链接、真实图表重建通过；原目录Python访问事件0，clone没有本地Git alternates。
- 无prefix原B完整19.03s，JF/JM=**1438.613498467 /100.417251110**。
- 同父DEVPC02的B、V6PHASE、TRAD_COMBO均完整且原合格；组合JF/JM=**1405.935077633 /105.464005963**，对phase微小双成本改善并通过原冻结额外jerk/wrench界。
- 同父D01R B/H150完整19.03s、原门通过；JF分别**1436.456498145 /1402.643211486**，H150的JM上升，不能称全指标支配。
- 两类历史原scorer/ownership/native重放、已训练25D Value接口真实predict、RL-B合同检查通过；训练/Adam更新0。

详细数值、耗时、原B/现代native和范围见 [ARCHIVE_VERIFICATION](ARCHIVE_VERIFICATION.md)。这是科学仿真与限定条件复现，不是全局理论最优、跨患者、host硬实时、真机或临床资格。

## 仍然未通过/未执行

legacy Stage1仍有40项模型引用缺失；旧m2不是完整历史镜像（22个缺位置对象已有SHA别名）；部分更早History训练数据/权重原本缺失。没有重跑全部历史变体/跨Human、新训练、旧活父状态跨机恢复、新OS或硬件。原G4/旧评价桥限制仍保留。见核验报告，不以理论可重建代替实测。

## 未来重新启动

```bash
git clone --branch archive/research-closure-20261028 https://github.com/Block-O2/adaptive-traction-mpc.git
cd adaptive-traction-mpc
git rev-parse HEAD
bash deployment/install_rl_b.sh /tmp/ihear-env
/tmp/ihear-env/bin/python deployment/archive_checks.py --output /tmp/ihear-static.json
/tmp/ihear-env/bin/python deployment/reproduce_original_b.py --repo . --output /tmp/ihear-original-b
/tmp/ihear-env/bin/python deployment/reproduce_trad_combo.py --repo . --output /tmp/ihear-combo
/tmp/ihear-env/bin/python deployment/reproduce_traditional.py --repo . --output /tmp/ihear-h150
/tmp/ihear-env/bin/python deployment/check_learning_interface.py --repo . --output /tmp/ihear-value
```

先按 [REPRODUCTION_GUIDE](REPRODUCTION_GUIDE.md) 安装Linux CPython3.12的venv/GL系统前提，保留≥6GiB可用RAM和≥20GiB磁盘门；output目录每次必须全新。旧campaign已截止，不直接续跑其队列。新Learning研究先建立新分支与科学合同，再决定架构，不由本次归档自动启动。

## 删除与费用

**服务器保持运行；本轮禁止的删除、重建、关机与整盘Snapshot均未执行。** 未选独有raw/中间权重/活状态等在删除后可能不可恢复，完整影响和约111.79GB未选路径盘点见 [DELETION_IMPACT](DELETION_IMPACT.md)。该体量包含重复/缓存，不等于全部独有损失。

Hetzner实例及可能存在的Volume/IP/Backup等资源仍可能计费；云账户清单和金额未核验，不宣称已经停止费用。新树排除了PRIVATE工作树状态，旧公开历史副本不能被本次删除撤回。

完成最终核验记录上传与可访问性确认后 **STOP**。服务器删除由用户另行确认。
