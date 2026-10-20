# Track B — 状态依赖与适用域

## 假设与新增诊断
同一冻结时间修复不必适用于另一合法背景。预先登记Bmap：W1 OUTBOUND0保持，移除RETURN0背景，得到历史已暴露R0。真实commissioning后live fork，完整B/T/D/ER各自执行，B/T/D需与旧R0 raw核验。它是受控背景诊断，不是未见prefix验证；不按结果改ER参数。

|完整运行|J_F N·s|对本组B降力%|膝真实下冲°|膝excursion−B°|原motion|
|---|---:|---:|---:|---:|---|
|Bmap_B|1432.655804346|0.000000|0.819686067|+0.000000000|PASS|
|Bmap_T|1400.293954479|2.258871|1.293504546|+0.324947534|PASS|
|Bmap_D|1399.026179051|2.347363|1.329948278|+0.361391266|PASS|
|Bmap_ER|1399.241294833|2.332347|1.326647973|+0.358090961|PASS|

R0冻结ER原motion结论：**PASS**。其完整资格为True，task=PASS、safety=True、receipt=PASS。R0 ER绝对膝下冲1.326648°反而高于W1 ER的1.275378°，相对excursion门却通过；绝对运动改善与相对资格并不等价。W1中的ER和两个新速度候选失败仍保留；R0不覆盖W1失败，不构成新广泛基线。

## 已有适用域地图
|状态/方法|原完整资格|膝v95 °/s|膝a95 °/s²|真实膝下冲°|excursion−B°|
|---|---|---:|---:|---:|---:|
|N2_T|PASS|22.219639|33.026237|1.293505|+0.368684|
|U1_T|PASS|22.268517|33.065049|1.293505|+0.376090|
|V1_T|PASS|22.219639|33.000433|1.293505|+0.361986|
|V2_T|PASS|22.457528|33.096119|1.293505|+0.376303|
|W1_T|FAIL|22.559290|28.552719|1.261666|+0.534884|
|W1_D|FAIL|22.359217|28.562887|1.270505|+0.543723|
|R0_T|PASS|22.219639|31.915326|1.293505|+0.324948|
|R0_D|PASS|22.211520|31.717245|1.329948|+0.361391|
|O0_T|FAIL|22.559290|32.960832|1.261666|+0.571923|
|O0_D|FAIL|22.359217|32.852949|1.270505|+0.580761|

N2/U1/V1/V2现在全部属于已暴露诊断状态。历史独立验证在当时成立，不能在本轮再算新的未见证据。它们主要改变OUTBOUND，HOLD后RETURN几乎收敛；多个早期prefix不等于多个干预前RETURN状态。W1/R0共享OUTBOUND父历史；O0使用已见V1 OUTBOUND并保留W1 RETURN背景。重复、共享prefix、不同Human分别标注，不能合并为独立样本量。

## 绝对负担与匹配B分母
W1 T膝v95=22.559290，O0 T几乎相同；各自B全程v95却20.225905和20.979395，ratio由1.115366变为1.075307。O0 T a95=32.960832高于W1的28.552719，相对门仍可通过，因为其B参照也更高。R0 T真实下冲约1.29°大于W1 T的1.261666°，却完整资格通过；这并不说明R0实际下冲更小。完整excursion还依赖去程最大q，因此同样RETURN误差可产生不同qualification。

当前瓶颈有两层：动作发生前真实/估计状态与参考历史不同；原完整非劣门依赖全程负担和匹配B。仅phase/slot或当前目标距离不足以代表这两层，也没有足够样本证明某个在线准入阈值有效。

## 只读风险特征与下一证据
derived/STATE_RISK_FEATURES.json保存100条历史请求的deployable estimated q/dq、reference、目标距离、remaining及source age，未来完整资格/真值下冲置于offline-only标签。原完整B未来p95、native真值、最终极值不进入在线features。没有拟合、训练或部署准入器。
W2已复核无历史START；本轮未出现合格新开发候选，故W2保持未使用，未以暴露R0冒充验证。下一轮应先取得合格的机制干预，再按完整历史分组验证近干预状态；必要时补同seed严格匹配的背景因子角，不能把现有不同seed V1直接当完整factorial交互证明。

![state_qualification_differences.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/state_qualification_differences.png)

![W1_R0_state_diagnostic.png](C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_autonomous_multitrack_v1/figures/W1_R0_state_diagnostic.png)
