# Gate0通过；Beta optimizer仍为未执行候选

CONFIRMED：已按主Agent批准完成20秒局部数学/纯映射Gate0，真实FROZEN_18D/PARAMETER_MAP/H150来源解析与所有计划检查通过；没有启动环境、真实训练或物理。Gate0只授予数学及接口结构层，原B/λ0/.5/λ1任务/motion工程门仍由主Agent另行判定。

原SOURCE_MANIFEST的6个本地文件与12个原源码SHA逐项核对PASS；数学结束后和合成API fixture开始前再次核对来源。原文件与已通过的density/mapping源码未改。

## 合成数学与API计算分账

|操作|实际计数/结果|边界|
|---|---|---|
|直接数学门|wall .042204秒；5组Beta密度各8192节点积分；25次score、50个central-difference分量/100次扰动logpdf|没有构造actor或改参数|
|直接数学Beta RNG|4040次draw，其中20次是RNG恢复后的重复复现|合成随机数，不是实际控制尝试或独立患者|
|直接数学logpdf|41060次外部+25次score内部=41085|不是learned actor forward|
|合成API fixture|初始化1个Beta linear actor；34 forward=32 sample+1 mean+1 score_for_weights；logpdf66、raw score1、shape transform35|仅zero25 fixture，权重和policy SHA不变；明确禁止部署|
|全部Gate0合计|Beta数学draw4072、logpdf41151；actor初始化1、forward34、参数更新0|真实fit0、真实on-policy0、env0、physics0|

完整精确误差、积分值、RNG和实际字段在`GATE0_ACCOUNTING_AND_BOUNDS.json`、`gate0_math_v1/END.json`、`gate0_policy_fixture_v1/END.json`。测试不改density、sample、Jacobian或clip语义；原Beta样本保留(0,1)，未用clip或静默重采样制造通过。

原最大18D归一化绝对值约.998079，故λ∈[0,1]仍在原对称box内。实际H150姿态为RETURN2/3 [+.3,−.3]°，early factor1.1/1.2、timing1.5；缩放域核验通过。λ0仍保留T×1.5、原RETURN两plateau和零intent列表，数学门从未改名为B。

## 新的独立optimizer候选（仅AST检查）

`beta_optimizer_candidate_v1.py::BetaArm`使用独立连续λ schema，未复用categorical action index或五菜单。以下功能已写代码，**未初始化、导入或执行该optimizer，也未做任何真实fit**：

- Proposal保存实际λ/α/β/old scalar logpdf、axis与完整recipe、source policy、RNG before/after、原B完成反馈及因果25D身份。数值no-proposal保留消耗的RNG，不clip或换sample。
- Constructor要求主训练合同、Gate1 pass及case split SHA，实际axis内容和全部依赖源码SHA一致；Gate0 synthetic checkpoint不能作为真实训练父。
- 原回执绑定λ及完整action/recipe，而非离散索引；所有engineering censor与normal protected failure分开。hard safety True先于任意censor。
- RF一个epoch；PPO固定三个epoch和old Beta scalar logdensity、ratio clip .2；解析dlogpdf经softplus形状导数计算两head权重梯度，SGD默认LR .15、梯度norm≤1，无Adam/隐藏moments。
- Raw/gain20与原离散分支同资格/JF单目标口径，JM分列；每批记录rewards、advantage、是否全floor/无目标差异、完整原/裁剪梯度、每sample ratio及clip inactive、精确参数变化与模型计数。
- 先验证整批collection policy/density，再在私有policy副本更新；数值失败保留私有模型计算/已发生步数而不提交live权重。根runner仍须四臂统一预检、复制对象事务和整组generation提交。
- Snapshot/restore保存policy、SGD步计数、完整RNG、pending proposal/原物理回执、seen attempt IDs、数值失败与私有update失败、原local/global deadline、axis/source/Gate1/split身份；不重置时钟、不回滚物理或RNG。

源码候选只有AST有效性；不能写成optimizer数值/恢复等价已通过。后续若需要合成optimizer机械验证，应另外批准且显式标fixture，不能伪造“genuine physical receipt”进入研究训练账。真实训练继续等待Gate1及主合同。
