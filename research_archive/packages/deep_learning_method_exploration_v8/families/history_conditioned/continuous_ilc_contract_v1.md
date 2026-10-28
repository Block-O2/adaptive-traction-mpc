# 真实连续Trial ILC扩展合同 v1：源候选，0 physics

状态：`SOURCE_PREPARED_REQUIRES_MAIN_AGENT_REVIEW`。先通过已批准B→boundary→B工程门；本合同不授权任何新START、模型fit或物理。本扩展只覆盖一个已知heavy工程case，独立患者泛化不成立。唯一ACTIVATION与原T0/硬截止不变。

## 活对象与三层owner

T1是实际完整原B。原inter-rep boundary后，同一plant/updater/observer在T2 OUT0进入新Study；串行真实fork顺序为B、H150_ZERO_MODAL、H150。先执行zero-modal，再执行最后的H150，目的是H150 child结束T2时可读取已完成的同父zero raw并立即验证等效，再由自己的真实末态继续T3，而无需重复H150或从外层B重建。

T2 H150 child只有在完整原task、安全、motion、receipt和zero raw等效均通过后，才冻结本臂H150历史的T3 ILC决定，经原boundary到T3。T3建立全新Study实例，child=None/独立condition.name/独立active_owned_child_pid；其初始plant仍是T2 H150 child本臂对象。T3串行真实fork比较B、固定H150、zero-modal、ILC、history-disabled、较小gain与正负固定小扰动。各层只在真正os.fork child内设置原child字典，禁止伪child。外层T2 parent只wait/join及校验自己未变，不能接管H150 child的末态。

T2和T3各自都先以原B臂建立本live父的资格分母。父随后自身B原运行是原fork完整性核验，不增加独立患者或训练标签。T2 H150不合格时保留失败并停止该连续链，不能删H150失败或改用更容易的冷初态。嵌套子孙均须在deadline/信号时join或清理。

## 零动作与x3精确语义

采用已存在 `RetimedModalPlanner` 的RETURN relative坐标x[3]；其它7坐标为0，legacy=[0,0]，底层完整H150 recipe不变。对零基slot s，w=sin²(pi*clip((s+.5)/6,0,1))。RETURN direction=−1，所以原target的精确提案位移为degrees `[-0.30*w*x3,+0.30*w*x3]`。某关节原target在公开phase goal的1e−10 rad内时，该关节shift按原retimed源码锁为0；若整个target已到goal，则不申请modal替代。HOLD和OUTBOUND不受该坐标影响。

这个公式是目标参考的数学效果，不是对真实force或闭环state的灵敏度。endpoint mask必须以原decision记录的 `terminal_reference_selection.reference_target_rad` 为准：它是原planner的内部合法参考终点，可能不同于名义spec中心；缺该记录不得用spec或零值补齐。Retimed调度器仍可因原最小时长或证书改变最终执行/拒绝，必须记录实际duration/velocity和fallback；不能说x3天然只改变knee，也不能假定实际轨迹线性响应。x=0时原源码先返回完整TerminalTimingPlanner原决定，没有额外_evaluate；仍要在T2/T3分别逐raw证明零modal和固定H150相同，门失败则不继续非零ILC。

## ILC信号与增益

只用本臂已完成T2 H150的因果estimated−issued-reference误差。请求的phase/slot/request_id/public goal在原decision callback中只读记录；用原summary decisions的timing_request_id、learning_records的实际selected target、activated标志及原receipt lineage正native步确认窗口归属。只对RETURN原中间目标、实际已执行的slot积累dt加权误差，不用future T3标签、native Human或真实模型参数。

对slot i的参考基向量b_i=[−.30*w_i,+.30*w_i] degree（应用原endpoint mask），时间均值误差e_i与实际执行时间d_i，更新 `x3=clip(gain*sum(d_i*b_i·e_i)/(sum(d_i*||b_i||²)+1e−6),−0.5,+0.5)`。主gain=.25，较小gain=.10。它是历史误差的低维投影，不是识别了负担梯度或norm-optimal force ILC；可能增加完整JF，结果必须保留。

history-disabled运行完全同一投影函数，但slot误差来自事前冻结的population文件，不能传本患者T2数据；population文件须保存来源/SHA，所有权重/slot模板在T1前冻结。若无此合法文件，则strict disabled为NOT_RUN；可额外保留零更新弱消融，不能冒充严格history检验。固定小扰动x3=±.25无需历史；ILC与fixed参数相同则复用同父已完成raw并记录alias，不重复新增物理、不增加样本数。

## 增量与累计探索负担

DirectB bridge以invoke开始time计native，只适用于无fork任务。含fork的T2/T3每child真实新增native必须以真实fork time起算；公共bootstrap/prefix由活parent实际执行一次，不能每个child重复计。原child['_DATA'].metric实际increment和parent自己的plant-time delta分别登记，原absolute metric另存。T2 H150的END native只包括其T2任务，后续T2→3 boundary、T3 parent、每个T3 child均另有唯一START/END；H150父等待的wall可包含整个后续链，但native不能包含子孙后再双算。

每条真实boundary额外登记原held command及继承receipt、实际native数、测得force/moment成本；不混入task JF，计入累计探索负担。T1、失败、zero等效、B对照、parent、KEEP/H150、所有ILC与fixed臂都不能免费。当前工程不能声称少数患者运动效率；完整标签来自昂贵fork反事实，必须给总成本。

## BO后续，不在本源启动

至少有实际同父x3正负/零响应后，才拟合同父action−H150的JF、JM及原motion margin独立头。先检查动作响应是否超过重复/初态漂移和插值误差，再比较保守收益LCB与固定最优；原门仍最终裁决。不得把T1 B成本和未知Trial2动作当同一平稳GP观察。训练及下一轮物理均须另交合同并主Agent批准。
