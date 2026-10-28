当前两条件结论：FMEAN03 六项TASK因原H150 partial而NOT_RUN；FMEAN04六项原完整合格。后者没有相对原合格固定λ.5的资格率增益，也未在原JF主目标下超过强固定H150；JF/JM取舍、机制修正、泛化与效率须分层。全部六固定最终端点保留，不选best。下方原03记录保留，随后补04闭合结果。

FMEAN03 的六个冻结 feasibility 模型已在原 cold OUT0、B 前各真实返回一次 mean；均无数值拒绝。原 B 完整合格，原 EARLY_H150 为工程 partial，因此 λ1 repeat 与六个模型 TASK 均未执行。该记录既不把 NOT_RUN 当模型失败，也不授予控制收益或泛化结论。

|原证据|状态/实际计数|
|---|---|
|六模型选择|6 logical copies、6 mean entered/returned、6 internal forwards、0 数值拒绝；七角色 proof、causal39、25D projection 各1，fixed λ1 map1|
|原 B|complete+qualified；JF 1587.100832423440 N·s，JM 109.908685005448 N·m·s；76,120 新 native steps；原 hard violation=false|
|原 EARLY_H150|complete=false；NATIVE_PHYSICAL_FAILURE；69,300 新 native steps；JF/JM 保持 null；原 hard violation=false|
|λ1 repeat / raw gate|NOT_RUN / 无 gate，不能补 PASS|
|六模型 TASK|六项均 NOT_RUN，原 alias 指向 MEAN_01..06；不是六次控制失败|
|原物理投入|2 个独立 child proposals；parent END 116,320 steps 单列；child END 未给 steps，采用原 receipt 的逐 child steps，不补0或编造总量|

Global RF/PPO、context LOO RF/PPO、span geometry RF/PPO 全部保留，policy/weights 身份见原报告。只有原 pre-B 调用已有6次 forward；本次与 V2 metadata 核查均为0新模型/训练/物理，不得重复记成新的6次推理。原冻结源、模型、配置与 clock 均未改变。

原 V2 核查 START 为 2026-10-27T12:13:07.728577+00:00，实际 Python PID 1227712/startticks 63085925。main 的 outer child 1227710/start63085925 与 launcher1227709/start63085922 分列；三者当前均已退出。core wall 0.035767794s / CPU 0.035764s / peak RSS 20856KiB；main 报告外层 wall .07810s / inclusive-child CPU .07763s，不能混成 core 资源。原核查计数17 JSON、6 event JSON、158 hashes、6 policy digests、6 weight digests、2 receipt checks。

V1 的预算拒绝保留在 `audit/ROOT_PREFLIGHT_ERRORS_1214_PRESERVED_V1.json`，SHA `add0d858e153fdc84d11b5bc49b70c1ec5fb16a4c1c9ca6472ff19acc198bbf8`；该文件实际 recorded_unix=1793102928.4834003，不用文件名历史时间标签推断时间。原V1 authority/external refs和exit1保留；它在输出前拒绝，0模型/物理。V2按新主批准一次完成，修正原 END 无group的schema关联，没有放宽预算或物理guard。

原 REPORT SHA `e73f04fef59d982c5e55b2bc0e0d93e3e84f21f9b812768cc6232bdbf725c115`，DONE SHA `02eb5e5d62bcfb4805c00e4e500ad568933c4b9791686c58bf87af5d031d977f`。未读取活动 VAL04、原raw/scorer或real_runs。DevCap仍为未运行source提案，等待mandatory six闭合及独立root授权，不因本次结果调网格、模型或阈值。

完整metadata reconciliation：`families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/actual_FMEAN03_reconciliation_v1/REPORT.json`。

FMEAN04 的六个冻结最终 feasibility 端点均完成原任务且原资格通过；FMEAN03 因原 H150 partial，六项 TASK 仍全部 NOT_RUN。两个条件不能拼成六个独立新患者；本次没有挑选最佳端点。

六模型都在原 OUT0、B 前各真实返回一次，0 数值拒绝。FMEAN04 原9个child完整合格（B/H/λ1 repeat+六mean），10 START/10 END；λ1为独立付费原H150完整raw等效。原新增六mean forward是已有部署调用，本次metadata补记及原核查均不新增helper/model/scorer/fit/RNG/raw/physics调用。

|固定端点/对照|JF N·s|JM N·m·s|原状态|
|---|---:|---:|---|
|原B|1360.417482264978|95.666539200290|complete+qualified|
|固定EARLY_H150|1323.213957482708|101.447711328803|complete+qualified|
|λ1独立付费repeat|1323.213957482708|101.447711328803|complete+qualified/rawPASS|
|固定λ.5（main提供VAL04同recipe）|1333.056546000000|100.645501800000|已合格/本次未重读原文件|
|Global RF1|1333.041091875790|100.648602454945|complete+qualified|
|Global PPO3|1333.008642063499|100.649224913055|complete+qualified|
|LOO RF1|1333.057347283847|100.645486326639|complete+qualified|
|LOO PPO3|1333.058950531706|100.645455413784|complete+qualified|
|Geometry RF1|1333.054967384905|100.645532216529|complete+qualified|
|Geometry PPO3|1333.051808907144|100.645593123109|complete+qualified|

JF 与 JM 必须分别解释。六mean 的 JF 都高于原合格固定 H150，JM 则都低于 H150；因此在原JF主目标和完整原资格下，六mean未超强固定H，但H不双成本严格支配mean。固定λ.5本来已合格，六mean在此没有相对半轴初始化的资格率增益。固定.5数值来自main本条消息，属同原条件/同recipe对照，不是本次重新读取VAL04，更不是额外新FMEAN04 child。

|固定比较|ΔJF N·s|ΔJM N·m·s|
|---|---:|---:|
|Geometry−LOO RF1|-0.002379898942|+0.000045889890|
|Global−LOO RF1|-0.016255408057|+0.003116128307|
|Geometry−LOO PPO3|-0.007141624562|+0.000137709326|
|Global−LOO PPO3|-0.050308468207|+0.003769499271|

Geometry 相对同算法 LOO 的微小 JF下降/JM增加，以及 Global 的变化，均为该确定条件上实际控制副观测/方向支持。GateC/L/G优化的是旧4个fixed-behavior失败draw的feasibility margin，不是这个新case的JF；不能把这些微差改称事前JF优化成功、统计安全改善或总体方差结论。

|证据层|当前能支持的范围|
|---|---|
|实现|两case各6原mean返回，冻结source/policy/weights身份已核；没有新restore或训练|
|决策|原cold OUT0合法25D、七角色proof、全部选择beforeB；每case实际6forward/0拒绝|
|任务|03六项NOT_RUN；04六项原complete+qualified；完整H和新λ1rawgate仅04通过|
|学习机制|旧4draw GateG的span几何/范数invariants与旧context方向修正得到既有实证；新case不是训练目标，不据此调模型|
|强基线成本|04六mean无原JF主目标下对固定H的增量；JM有取舍，固定.5已合格，无资格率增益证明|
|泛化|只剩1个完整新参数条件可比较六模型，另1被工程门阻断；不能称六个独立患者、总体统计或广泛个体化|
|效率|全部真实parent/child/失败/metadata付费保留；不称省attempt或净效率；额外rawreplay仍未宣称全部收到|

原04 metadata REPORT SHA `fafc9d64de04751613f97e7a1484b6b08041341a1a46bb2399b79644f14d03d7`，DONE SHA `9880ddaa20129fc6aa805deca81c86eb0daaf2cd0f2b2f22f5d888fcbfefc10d`。核查core wall 0.063691854s / CPU 0.063679000s / RSS 21140KiB；main报告外层 wall .114254s / inclusive-child CPU .111908s，分列不混用。原核查32 JSON、20 event JSON、173 hashes、6 policy/6 weights digests、9 receipt checks。实际reviewer PID 1235711/startticks63320768当前已退出。

每个原child实际新native steps均76,120，parent END116,320另列；child END缺少steps保持null，不补0或凭raw trace行数推实际新步数。source/模型/程序/阈值/clock原样；未读活动C4、raw或real_runs。rawreplay45909未在本次读取、未写全部已收。DevCap仍待最后CONVAL02 closed和独立root授权，未运行map/模型/physics，未据任何新结果缩网格。

完整04 metadata reconciliation：`families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/frozen_six_mean_deployment_v1/closed_metadata_review_v1/actual_FMEAN04_reconciliation_v1/REPORT.json`。

冻结函数迁移的原单次算术诊断已独立metadata复核，见 `NEW_CONTEXT_SPAN_RESULTS.md`：03/04的旧span外平方能量比为.5845464351/.7169288579；六端点的参数变化几乎都在旧span，Geometry−LOO的mean差在03为负、04为正，原一阶分解对齐。这一解释不读取新TASK成本/资格，不构成导致上述物理资格的因果证据；没有新增模型/物理或改变任何冻结端点。
