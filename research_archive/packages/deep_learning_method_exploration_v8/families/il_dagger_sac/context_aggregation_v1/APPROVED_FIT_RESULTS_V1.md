# D coverage correction：批准fit完成，结果仅限开发

主Agent已审完整数据SHA与99来源后批准一次≤60秒单CPU离线拟合。MAIN_APPROVAL.json和FIT_SOURCE_MANIFEST_V1.json在任何新模型调用前冻结；新runner AST通过后才运行。实际wall 0.601167s、CPU 0.601163s，3个BC各240次SGD全部完成，1次新normalization预处理、6个强规则fit/search完成，0Adam、0新物理/环境、0sealed验证读取。未重跑、未调新轮。

数据文件SHA保持`50feef0643aa4b5fb8ce0b75fbd3fb5ce7178de71bb7a45b92196261c16e335a`。唯一预登记primary仍AGGREGATE_5_OLD_NORM；没有根据下表换primary。

| 固定selector | teacher匹配/10 | 原完整合格/10 |
|---|---:|---:|
| OLD_ONLY_5_OLD_NORM | 8 | 9 |
| AGGREGATE_5_OLD_NORM | 10 | 10 |
| AGGREGATE_5_NEW_DEV_NORM | 10 | 10 |
| 多数teacher常数EARLY_H150 | 6 | 6 |
| 成本表保守强常数B | 3 | 10 |
| exhaustive stump | 9 | 9 |
| depth2 tree | 10 | 10 |
| nearest，父norm | 10 | 10 |
| nearest，新dev norm | 10 | 10 |

这里均复用已暴露开发结果表。OLD_ONLY的两个teacher错选是CTX03/04都选EARLY_PHASE，其中CTX03原不合格；聚合两个BC纠正为EARLY_H150。但聚合数据也正包含这些标签，不能当独立泛化或新增on-policy收益。depth2和两nearest也完全匹配，当前没有证据显示BC超过简单强对照。nearest在自身训练点命中尤其不能当泛化证据。

两聚合BC及depth2/nearest在全部10个原合格选项上的ΔJF合计−274.272070N·s、ΔJM+40.091344N·m·s；这些是已付费动作结果的开发表复用，不是新执行控制收益，也不表示双成本下降。失败selector的部分合格子集JF和不能与10/10合格模型作同等总收益比较。全部原motion失败与缺失规则保存在DEVELOPMENT_EVALUATIONS.json。

## 初始化与尺度/稀有类

逻辑五动作policy实际构造1次（BC3→5 lift），随后3份独立训练copy；categorical.initialize API实际0次。新增phase两行取原H150两行均值；保留旧logit不等于保持三动作softmax概率。训练前同一raw-input函数解析重参数化1次；训练后另外创建同函数坐标验证view1，不是额外fit。此前未更新lift参照由冻结parent/runner唯一重建，且BEFORE_TRAINING里保存完整10context logits/probabilities/选择；没有伪造另一个训练checkpoint。

训练前父norm与新dev norm的raw-input logit最大误差4.44e−16、概率误差1.11e−16。训练后把同一个新norm模型解析换回父norm，10个实际开发输入logit误差8.88e−16、概率误差2.08e−17。解析恒等式对任意有限raw输入成立；数值检查只覆盖当前开发输入。两个不同norm模型训练后不要求函数相同。

新norm仅来自4个新增开发context，25维std均未触发1e−12置1，亦无std<1e−8。相对父norm尺度比最小约.10577。新norm下历史输入最大|z|12.849，有6个feature标量超过10；父norm下新增开发输入最大|z|3.04166，1个标量超过3。这是已暴露上下文的尺度诊断，不是独立OOD测试。

teacher类别数[B,LATE_H150,EARLY_H150,LATE_PHASE,EARLY_PHASE]=[3,0,6,0,1]。唯一EARLY_PHASE正例是EARLYN01；新增4个context没有该类正例。两LATE类均0正例，保留菜单不等于学会这些动作的选择边界。

| BC | 末步更新前CE | 最小teacher概率，全部10开发点 | 最小任意类概率 | 梯度norm clip次数 |
|---|---:|---:|---:|---:|
| old-only | .007866（只在旧6训练） | .03923 | 2.57e−5 | 0 |
| aggregate父norm | .015332 | .95510 | 6.32e−6 | 2 |
| aggregate新norm | .020190 | .92722 | 5.73e−8 | 2 |

所有记录概率均有限且无精确0。EARLYN稀有teacher概率：父norm聚合.95796，新norm聚合.94389。两变体均匹配10/10，开发结果不支持“必须重新normalization才学得会”的解释；也不能从训练标签拟合认定覆盖具有独立控制价值。

## 精确工作与资源账

| 项目 | 实际 |
|---|---:|
| BC fit / normalization fit / 传统规则fit-search | 3 / 1 / 6 |
| 逻辑共享五policy构造 / 独立训练copy / 验证坐标view | 1 / 3 / 1 |
| categorical.initialize | 0 |
| categorical.update，每次epochs=1 | 720 |
| 训练probability forward / manual backward-equivalent | 6240 / 6240 |
| 新部署API BC调用 / 规则调用 | 60 / 60 |
| categorical probabilities，含训练前后API验证 | 6300 |
| 直接logit数值检查forward | 70 |
| 全部线性forward求值 | 6370 |
| categorical design / choose / select_out0 / policy_sha | 12610 / 60 / 60 / 1500 |
| stump阈值候选 / 分区标量比较 / leaf score | 219 / 2190 / 439 |
| depth2阈值候选 / 分区标量比较 / leaf score | 17272 / 107910 / 34281 |
| depth2重复subset cache命中 | 264 |
| 成本常数availability / qualification / JF累加行数 | 36 / 30 / 10 |
| nearest训练点标准化标量 / 查询 / 距离 / 平方差项 | 500 / 20 / 200 / 5000 |

70次直接logit数值检查由训练前30+训练后30+训练后坐标验证10组成，是主Agent追加等价检查带来的明确额外计算；不藏入原6300次概率forward预算，也不增加fit或SGD。所有阈值/leaf标签访问等细账见RULE_SEARCH_COUNTS.json。

START PID1132442/start_ticks60472213，RSS23792KiB→25932KiB。RUSAGE_SELF peak_RSS在START前已为612080KiB，结束未增加；不能把该先前高水位归因于本轮fit。原START/END还保存绝对本地与原全局deadline、CPU/RSS、源和授权SHA。源码、父checkpoint、categorical与全部3个onpolicy源未改。

## 冻结部署输入

9个独立冻结模型文档位于approved_fit_v1/models/；每个是`{"bundle":...,"bundle_object_sha256":...}` envelope。以document['bundle']调用context_aggregation_api_v1.select_out0，并提供document['bundle_object_sha256']及外部冻结五menu SHA列表。API只接收commissioned25与QA，实际完整contract逐项digest匹配外部menu，原最终资格仍由worker审定。

approved_fit_v1/DEPLOYMENT_FREEZE.json保存9个bundle对象SHA、模型文件SHA、API/runner SHA及预登记primary。输入、配置、teacher规则、normalization、模型和6个强对照均已冻结。本轮没有触及后续两个sealed条件；后续是否执行及物理账由主Agent另行决定，当前不继续拟合或自行物理。
