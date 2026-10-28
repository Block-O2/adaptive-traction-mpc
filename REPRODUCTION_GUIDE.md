# 从 GitHub 重新搭建与复现

本指南区分模型加载、离线历史重算和新的完整动力学闭环。动态入口均拒绝`python -O`，原科学资格断言必须启用。已完成的本轮检查、干净clone路径、环境、耗时及失败见 [ARCHIVE_VERIFICATION.md](ARCHIVE_VERIFICATION.md)。历史包中的 PASS 不自动算作本轮重现。

## 从归档分支启动

```bash
git clone --branch archive/research-closure-20261028 https://github.com/Block-O2/adaptive-traction-mpc.git
cd adaptive-traction-mpc
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r deployment/requirements-rl-b-cp312.lock
```

该锁定环境为 Linux x86_64 / CPython3.12 的完整CPU依赖：核心为 numpy2.2.6、scipy1.15.3、MuJoCo3.10.0、gymnasium1.1.1；Learning检查还用 torch2.7.1+cpu、stable-baselines3 2.6.0。动态传统复现不训练模型，也不要求GPU。锁定文件带完整wheel hash，原机器 `.venv`、pip缓存和隐藏文件不属于归档依赖。

运行现有 `deployment/check_models.py`、`deployment/score_b_h150.py`、`deployment/check_rl_b.py` 前先用 `--help` 查看其参数；这些检查的最终命令和结果以本轮核验记录为准。首次离线评分可以使用较小的 `requirements-offline.lock` 环境，但它没有动力学完整依赖。

## 先做便携闭包检查

```bash
.venv/bin/python deployment/reproduce_trad_combo.py --repo . --output /tmp/ihear-combo-prepare --prepare-only
.venv/bin/python deployment/reproduce_traditional.py --repo . --output /tmp/ihear-d01r-prepare --prepare-only
```

每次 `--output` 必须不存在；prepare目录不能作为随后运行的同名output。准备会复制源码、冻结配置与模型资产，记录路径重绑定和hash；它不创建物理通过回执。`PREPARATION.json` 为实际复制清单。归档阶段曾完成零物理 import/Study构造/原case adapter绑定检查；这些也不是完整任务成功。

## 原始无prefix B：完整19.03秒任务

```bash
.venv/bin/python deployment/reproduce_original_b.py --repo . --output /tmp/ihear-original-b-run --timeout-s 1800
```

该入口使用原Git `research/side_studies/m2_18d_baseline_qualification_v1/{source,code,deps}`，严格检查原 `BASELINE_CONTRACT.json` 和 `RUN_PLAN.json` 的seed2026101303、名义原case及零prefix；原manifest中目前存在的1346个对象逐一SHA一致才可准备。原B接口继续使用原MatchedInterface.control的全零residual，直接执行完整cold commissioning与原TASK；不运行E/search、不训练。只有原scorer/task、绝对安全、native receipt、matched、原motion全部通过，且实际TASK时长19.03s，才能写PASS。`RESULT.json`记录JF/JM、时长、资格、运行依赖版本和prefix backend；`reports/original_b_MEASURED.json`保留native jerk等完整指标。

原manifest有38个当前Git树中缺失对象；launcher逐项报告，不称完整历史镜像。三个实际依赖JSON（PHASE_B_MATRIX、HISTORICAL_NATIVE_GRAPH_ACTIONS、HISTORICAL_SPATIAL_GRAPH）仅在v8归档对象SHA与原manifest完全一致时恢复。其余缺失包括旧CPython3.10 native扩展、metadata、旧source_history及Q权重；原该B路径默认`prefix_backend='numpy'`，不主动切换为其它backend。若实际调用需要缺失对象，应原样失败，不用新实现偷偷替代。原源码只重绑定字面路径和新的host允许时长，所有来源hash与差异保存在PREPARATION。

历史原B参考JF为1438.613498467N·s。使用新依赖/平台运行且未与旧native raw逐字段比较时，只能宣称归档原源码/任务/参数的重新执行；`historical_raw_exact_identity=NOT_TESTED`。新的实际通过/失败仍以 [ARCHIVE_VERIFICATION.md](ARCHIVE_VERIFICATION.md) 为准。

## 主复现：强传统 TRAD_COMBO

```bash
.venv/bin/python deployment/reproduce_trad_combo.py --repo . --output /tmp/ihear-combo-run --timeout-s 1800
```

精确来源为 `research_archive/packages/autonomous_learning_smoothness_v7/experiments/DEVPC02.json`，worker为原 `source/v7_worker_v5.py`。三个实际子分支依次为 `DEVPC02_B`、`DEVPC02_V6PHASE`、`DEVPC02_TRAD_COMBO`，从 seed2026102690 的实际cold commissioning与合法prefix执行到 OUTBOUND slot1 后，完整live address-space fork。完整原TASK继续执行，不能拿父prefix视为完整任务。

冻结prefix为 OUTBOUND `[[.068,.042,.024]]`、RETURN `[[.047,.026,.019]]`。TRAD_COMBO的8D为 `[-.18310670132483464,0,0,-.9571745795248379,.5,1,-1,-.95]`，legacy为 `[.8245887463260377,-.9835625245511301]`，OUTBOUND slot1覆盖坐标4/5为0、坐标7为−1；主launcher会逐项断言该配置身份。不要手工重新输入四舍五入后的参数。

输出至少包含：

- `RESULT.json`：实际complete/qualified和JF/JM；只有三臂全部完整原合格，且COMBO对phase通过原冻结额外质量门，才给PASS。
- `attempts/DEVPC02_*_RESULT.json`：冻结动作、完整资格、具体原门失败、执行metadata。
- `runtime/source/results/DEVPC02_*/summary.json`、`trace.npz`、`runtime_artifacts.json.gz`：完整新raw和receipt。
- `runtime/reports/*_MEASURED.json`：JF/JM、phase积分、native jerk、tracking、motion和安全轴；`*_EXECUTED_RESIDUAL_RECEIPTS.json`为真实native归属审计。
- `analysis/native_metrics/` 与 `analysis/DEVPC02_PAIRED_METRICS.json`：调用原v7_metrics_v3完整native jerk/wrench复算，使用原freeze/DEVPC02.json的jerk RMS≤1.001、force norm-rate RMS≤1.004界，并要求COMBO的JF/JM均不劣于phase。
- `audit/DEVPC02_PARENT_RAW_GATE.json`：新parent与新B逐字段/receipt/native比较；`jobs/DEVPC02/WORKER_DONE.json`和父状态不变回执。

历史同条件参考为B `1437.971420 /100.829734`、V6PHASE `1405.990071 /105.481425`、TRAD_COMBO `1405.935078 /105.464006`（JF N·s / JM N·m·s）。这些是历史对照值，先检查任务和评分资格，再看数值误差。跨平台数值不同应原样报告，不调参数“对齐”结果。

该有限入口移除GP候选臂，并显式省略原可选 `historical_repeats` 跨包大raw审计，记录于PREPARATION。原seed/prefix、controller、plant、scheduler、motion/scorer、安全、receipt、同父raw gate仍执行。因此新PASS证明本归档闭包能完成冻结研究条件；与历史逐raw相同需要另行保留旧raw并比较，不能从数值接近推断。

## D01R B/H150 完整19.03秒对照

```bash
.venv/bin/python deployment/reproduce_traditional.py --repo . --output /tmp/ihear-d01r-run --timeout-s 1800
```

它使用 v8 `runtime/` 继承闭包中的原 `campaign_v6.Campaign` 与 `study_common.run`；参数来自原Git `research/side_studies/ihear_overnight_control_learning_transition_v1/D01R_PLAN.json`。seed2026102001，OUTBOUND prefix `[[.08,.04,.03]]`、RETURN prefix `[[.04,.02,.03]]`，OUT1后B/H150从同一live父状态fork。它是原合法prefix条件下的完整B/H150任务，**不是无prefix冷启动B**，也不是canonical18D开发状态。

历史D01R JF为B1436.456498、H1501402.643211N·s。H150以原T为基础，RETURN槽2/3姿态 `[+.3,-.3]°`、槽1/4时长×1.1/1.2、槽5×1.5。每次修改重新经过原certificate/admission。原任务仍从5°/10°到120°/120°再返回；MATCHED接口要求OUTBOUND/RETURN至少各9秒、HOLD phase至少1秒且原有效连续dwell成立，历史完整含HOLD 19.03秒；模拟总时长包含commissioning，不能用trace最后时间误当TASK时长。

输出 `RESULT.json`、`PARENT_B_GATE.json`、`runtime/D01R_RESULTS.json`、两臂与parent完整raw、MEASURED和native motion。动态入口没有训练、参数搜索、truth动作输入或硬件操作。

## 运行资源与耗时

历史单分支timeout为600s；新launcher默认1800s是host允许时长，不改变科学任务的30s timeout、phase deadline或物理步长。D01R为parent+2子分支，TRAD_COMBO为parent+3子分支，串行执行；历史数据提示应预留数分钟至数十分钟，实际耗时必须在新回执记录，不能保证实时比率。D01R/COMBO默认完整外层预算分别约170/200分钟量级；原无prefix B单次host上限默认30分钟，超时保留partial。prepare复制的便携源码与模型资产也需要磁盘空间。

原worker保留可用内存>6GiB、磁盘>20GiB等资源门。建议运行前至少保证这些门和新raw所需余量；不要为省时删除native trace记录或关闭scorer。出现资源不足、原断言或过期，应新建另一个输出目录保留失败，不覆盖旧结果，不把partial列入成功排名。

## 必需闭包

两类完整执行都需要所选快照的整个 `runtime/source/stages/`（含Stage3/4/5模型与配置、mesh/XML、原scorer）、`runtime/code/`、`runtime/control/`、`runtime/deps/`、小型冻结JSON。特别容易遗漏：

- `runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json`：原接口在构造时直接读取，虽然在output目录却是依赖。
- `runtime/deps/HISTORICAL_NATIVE_GRAPH_ACTIONS.json` 与 `HISTORICAL_SPATIAL_GRAPH.json`：ResidualInterface构造必需。
- `runtime/FROZEN_18D.json`、`PARAMETER_MAP.json`、`MOTION_ACCEPTANCE_PROTOCOL.json`、`ACTION_SET.json`。
- v7 `source/` 的planner、tap、worker与case_adapter全链，以及 `freeze/VARIED_HUMAN_SPLIT_V1.json`、`audit/CLOSURE_RELOCATION.json`。
- v7/v8使用不同根路径的同名模块，应分别复制，不能混用Python import cache；每次在全新进程运行。

代表性Learning接口的调用、权重和训练配置见 [LEARNING_ARCHITECTURE.md](LEARNING_ARCHITECTURE.md)。传统原B/H150执行只需上面传统闭包，不需要历史全部checkpoint。重启长程训练须重新冻结科学合同，归档launcher不具备自动训练权限。

## 从raw重新评分

`analyze_matched.measure` 必须同时读取summary、trace、metric、`*_DATA.json`与完整native states/command receipts；它检查4kHz步长，识别Human qpos/qvel映射，二次差分native dq，保留raw与SG5/21敏感性，逐native步验证应用命令归属，再计算原motion。`compare`使用原阈值且只将ownership字段绑定到科学模式。

JF/JM为整个TASK包括HOLD的200Hz measured force/moment模长左积分；4kHz wrench变化率来自原native tap，不能用200Hz曲线替代。对于只保留CSV/PNG/derived JSON的历史实验，可读结论和来源仍保留，但原大raw已筛除就不能再声称逐native重算可通过，具体见 [ARCHIVE_MANIFEST.md](ARCHIVE_MANIFEST.md) 与 [DELETION_IMPACT.md](DELETION_IMPACT.md)。

## 失败处理与重新研究

先报告缺失对象/依赖、原异常、真实partial步数和输出目录，区分导入失败、资源门、模型加载、完整任务失败、原motion失败、host资格未执行。可以修复纯路径/加载缺陷并记录patch；禁止通过更换Human、prefix、缩短时长、调参数或放宽门让复现通过。下一代研究应复制本归档到新分支，保留冻结历史和失败，先另写新合同，不能直接续跑已STOP的旧队列。
