# 公平对照与当前增量（研究进行中）

必须区分预先冻结对照、打开结果后训练的简单规则、以及事后菜单最优。以下四条件审计了完整五recipe菜单，使用相同原任务/guard/scorer与同一存活OUT0父态。动作权限仍有差异：A1与对应简单对照可选五种；早期离线RF/PPO/BC和C3B History Value实际只覆盖B/LATE_H150/EARLY_H150三种。后两类在三动作范围内比较固定B/H150，不据此与五动作A1跨权限排名。相同recipe只执行一次并连接多个selector，不计为多个独立rollout，也不声称实际省试。

|方法/对照|冻结四条件选择|完整原资格|相对同条件B的合格收益|可支持范围|
|---|---|---|---|---|
|固定B、事前best-fixed、事前stump|B/B/B/B|4/4|JF 0，JM 0|共同安全/成本锚|
|事前nearest|phase/B/phase/phase|2/4|不能按合格子集与4/4直接排名|该冻结nearest未解决资格迁移|
|A1 ABS25主|B/H150/phase/phase|3/4|合格子集JF −79.0494，JM +11.0605|改变选择，但原资格迁移仍失败|
|冻结PPO、RF、BC，含尺度变体|B/H150/B/B|4/4|JF −42.4121，JM +6.1230|相对登记固定/stump有限增量；没有超越BC的PG独有增量|
|history-enabled/additive/interaction|B/H150/B/B|4/4|同上|相对history-disabled全B有条件差异；与commissioned25相同，无history独有增量|
|history-disabled|B/B/B/B|4/4|JF 0，JM 0|固定禁用对照|
|逐条件事后最佳|B/H150/H150/H150|4/4|仅评价上界|读取完整菜单结果，不能作为事前可部署baseline|

H150在此表指EARLY_H150，phase指EARLY_PHASE；完整recipe同时绑定激活时点、18D/T底层、posture、timing、legacy、slot overrides及planner源SHA。每次结果的JF/JM、motion失败与原receipt见[汇总](analysis/FROZEN_TRANSFER_COMPARISON_V1.json)。这些stock条件具有历史参数暴露，属于本轮冻结新执行迁移，不能称终身未见的患者或临床泛化。

扩充这四条件之后的A2/A3、BC聚合及depth2/nearest均属于开发后重训。A3预定39维主开发LOCO10/10，聚合BC与depth2/nearest开发10/10，都不是对这四条件的第二次独立验证。真实PG将BC三动作显式lift成五动作：保留原三logit、新phase行取两个H150行均值，softmax分母改变，不能声称概率未变。未来新参数验证必须同时冻结五动作parent/首更新/末更新、BC聚合与对应强简单规则，再打开结果；三动作C3B另列。开发集表现不得混入本表冻结成绩。

持续ILC将与同起点固定±小扰动、H150、zero及事前固定异质prior比较；同一真实H150上一轮末态经过原boundary生成下一轮父态，不与冷重放混排。连续Beta轴比较须包含同轴固定λ/传统搜索及H150；λ0不等于B，优于B不能替代相同动作权限的强对照。终末离散SAC须与同Q的greedy/softmax及BC比较，不能把名称改变当成额外能力。

效率目前未建立：冻结五菜单审计付出了所有候选的物理成本，训练/失败/取消/父prefix与边界额外计账。后续是否减少真实试验必须以完整原资格相近为前提计算净成本。


## 原两新参数冻结对照（VAL03/04闭合）

两个条件只计两份参数测试。第一组四个nonB原断言partial，只有B/HISTORY_B完整合格；第二组固定EARLY_H150完整合格JF1323.213957/JM101.447711，Beta12均值同选λ=.5的一个付费child、完整合格JF1333.056546/JM100.645502。均值相对B有降JF/增JM，但未超过原固定H的JF；同轴固定λ.5与这个未改变的均值是同一完整recipe、连接同一份付费结果，不能归因为学习更新。原λ0partial保留，余固定点NOT_RUN；不据此断言全区间能力。

A1/A2/A3/A5 JF主法及BC聚合主法为0/2合格，A4 margin主法2/2均选B、零增量。所有已冻结seed、parent/first/last、目标变体逐项保留；不能挑出某个安全B变体替换预定主法。六可行性均值和连续Trial第二组仍在独立程序内执行，不能用本表预填其结果。
