# History / ILC / BO 家族结果

当前`NOT_FULLY_EXPLORED`。真实连续工程与原两新参数程序验证已闭合，当前证据优先见下文；早期离线报告保留为历史阶段记录。子Agent dispatch physics仍0，实际物理由主统一owner执行，不能把早期新增physics=0当当前全family成本。

## 原两新参数条件的闭合程序验证（2026-10-27 13:38 UTC）

冻结的同一C4自适应程序已在原heavy065和light035两条件闭合。它检验冻结更新程序在新虚拟参数上的表现，包含当次合法局部拟合；并非冻结权重的纯推理、临床个体化或参数字节盲测。只有这两条件，TASK/fork/重复parent不能增作独立患者数。

- `V8CONVAL01`（heavy065，seed2026102753）：6对START/END，3完整B原合格、2个ZERO/H150 partial、1原boundary。两partial均KNEE_REFERENCE_MUST_BE_CONSTANT中止，hard11全true但不可完整排名；T3/ILC/disabled/固定扰动/BO全部NOT_RUN。既有新增native407220，不是本次审查新增。
- `V8CONVAL02`（light035，seed2026102754）：16对START/END，14完整TASK均原合格、2原boundary各20native，既有新增native1106000。T1→T2以及本臂T2_H150→T3的真实session/时钟、11个parent不变检查与四对parent/B、zero/H150 raw等效均通过。14个TASK不是14名患者。

light的T3决定由本臂已完成T2_H150的6个RETURN因果slot产生，estimated-reference误差与正receipt/原内部目标对齐；决定在第二boundary前冻结。gain.25 x3=−.04291765064389352、gain.10=−.01716706025755741，disabled=−.10428030739734558。五个非零臂都有实际激活、positive native及reference差异，支持历史→动作→执行，未重跑数学或scorer。

| 同父T3臂 | x3 | JF N·s | JM N·m·s | ΔJF/H150 | ΔJM/H150 |
|---|---:|---:|---:|---:|---:|
| B | N/A | 1360.929558448038 | 96.016341149227 | +36.946393353 | -5.765194634 |
| H150 | 0.000000000000 | 1323.983165095152 | 101.781535782827 | +0.000000000 | +0.000000000 |
| ZERO_MODAL | 0.000000000000 | 1323.983165095152 | 101.781535782827 | +0.000000000 | +0.000000000 |
| ILC_ENABLED_G025 | -0.042917650644 | 1323.902035051143 | 101.791027066076 | -0.081130044 | +0.009491283 |
| ILC_ENABLED_G010 | -0.017167060258 | 1323.950724079688 | 101.785330300444 | -0.032441015 | +0.003794518 |
| ILC_HISTORY_DISABLED | -0.104280307397 | 1323.786406773582 | 101.804329552796 | -0.196758322 | +0.022793770 |
| FIXED_X3_MINUS025 | -0.250000000000 | 1323.510983590399 | 101.836060465175 | -0.472181505 | +0.054524682 |
| FIXED_X3_PLUS025 | 0.250000000000 | 1324.451769315780 | 101.727712398868 | +0.468604221 | -0.053823384 |

全部表中臂原完整资格PASS。gain.25相对H150仅降JF .081130044 N·s，增JM .009491283 N·m·s。它的JF比disabled高.115628278、比固定−.25高.391051461；后两者的JM代价也较大，不能称严格双成本支配。支持本条件的小幅力/力矩交换，不支持当前history超过强固定或广泛个体化。disabled仍为事前异质nominal earlyH/light lateH先验，非同完整recipe标签。

light BO使用同一真实T3父状态的6个唯一x3，独立JF/JM/45margin头，原42个多RHS solve×47头，实际ABSTAIN、0新增候选；不能称未拟合，也不能把弃权当整体BO失败。未试grid±.125被预登记力增量、JM及原motion风险门拒绝；不确定性未校准。已有原提取+fit CPU28.238230s，其中最终fit/选择CPU.012099s；receipt为累计计数，不重复相加。

CONVAL02原closed raw审计core104.818161CPU/105.281270wall/RSS611768KiB；外层105.40wall、99.30user/5.63sys，二者重叠。原physics外层1415.75wall、1396.53user/36.04sys、RSS1557016KiB也已在主账本；本次metadata审查0raw/scorer/投影/模型/physics。

证据：原审计RESULT `60797de3083752adece20846b5051a1d27c36a3da0d357cfb3764f1eadb7b9a2`；metadata复核 `b443ceec5b6425b125342075f5ea18ec2929888545357f2b6810d1a6e18d06c9`。总体仍`NOT_FULLY_EXPLORED`：LEVEL3真实history影响及本light条件LEVEL4小JF改善成立，LEVEL5未超过强固定；LEVEL6只有原两条件程序验证，其中heavy门失败、light未显示强固定外JF优势；LEVEL7省试未证明。未充分探索更广动作/多轮history/校准BO与跨条件重复，不能整体否证家族。

新APP连续机制保留原合同草案。主线程报告已closed POSTAPP01新H complete=True、qualified=False，因此预设完整/motion/科学资格进入门未满足，明确`NOT_RUN_THIS_ROUND`，不实现/prepare/run。具体motion失败项待主线程原审计；本次未打开POSTAPP工件。该门失败不是family失败，也不修写原C4结果。

## 早期离线阶段记录（历史时点，已由上文更新）


`NOT_FULLY_EXPLORED`。v8本家族完成历史恢复、冻结决策诊断、6个完整B因果history提取、批准的C3B离线相对收益回归及消融、文献与纯因果Trial接口。新增physics=0；新训练为28次多头ridge求解，无梯度训练。历史缺raw性能为`SUPPORTED`；v7现有raw的因果提取/积分闭合及本轮离线fit为`CONFIRMED`，不等于新完整任务部署通过。

## 历史完整Trial的正负证据

旧包报告：79 START/79 END、68完整任务及独立复算，7独立患者、9完整live父状态、5,500,360新增native steps；训练仅P00/P05/P08三个患者、三个Trial2父、15完整动作标签。P00R只是重试。V12验证、U14–U16旧未见患者均已公开，不能继续用于新变体严格测试；V13旧包NOT_RUN不能自动继承本轮未见资格，须先核查全历史暴露。

|方法|实际改变/患者|完整合格（原报告）|相对同父B合格获益|严格history消融|强固定外独立收益|
|---|---|---|---|---|---|
|ILC .25 gain|7/7|7/7|5/7|V12、U14；U15/U16不胜population-disabled|未证明|
|BO独立cost/margin+CEI|1/4|4/4|0/4|0/4|未证明|
|History×action Value|3/4|4/4|3/4|V12、U14、U15|未证明；3次干预都是RETURN[3] knee−0.3°|

Value相对B降力V12=.636836、U14=.580099、U15=.639314 N·s。ILC相对严格disabled分别V12=.133849、U14=.080135、U15=−.005210、U16=−.066505 N·s；因此“改变动作/胜B”不能替代当前患者历史必要性。BO在U16选OUT[1] knee+0.3°，JF增加.330361 N·s，同时JM降低.096051 Nm·s，是明确取舍，不能叫降力成功。

开发统一固定O−0.3°平均相对B降力.342192，R−0.3°=.456185 N·s，均高于开发ILC平均.084870。Value的独立患者没有R−固定臂，故history-enabled胜disabled只能说明当前context导致启用，不证明个体化排序超过强固定小扰动。H150在部分患者原motion失败，必须逐患者分开，不能用其低JF掩盖资格问题。

历史连续T3仅ILC：P05更新相对KEEP降力−.011518；P08 +.151137 N·s。BO/Value未验证不同前动作/多轮收敛。

## 本轮实际离线诊断

运行 `audit_historical.py` 只读4患者冻结T2决策。产物与SHA在 `HISTORICAL_DECISION_DIAGNOSTIC.json` 和 `HISTORICAL_SOURCE_MANIFEST.json`。8行是决策诊断，不是8新状态。

|患者|BO选择/均值最优/eligible数|Value选择/disabled|history对action−B预测最大影响：BO / Value N·s|
|---|---|---|---|
|V12|B / R− / 0|R− / B|.068212 / .470207|
|U14|B / R− / 0|R− / B|.032905 / .314606|
|U15|B / R− / 0|R− / B|.032242 / .228474|
|U16|O+ / R− / 3|B / B|.022128 / .227561|

`CONFIRMED`：Value并非完全可抵消的纯history偏置；history改变action-relative预测。BO前三患者被代理margin eligibility全拒绝；U16均值更好的O−和R−被margin gate拒绝，最终CEI选O+。这证实了选择机制，不证实真实margin边界。旧Value rank=11/17、LOO floor≈.480664 N·s；标准化在LOO外拟合，内部校准不是严格独立，但验证/旧heldout没有进入训练。

`SUPPORTED`：以T1基线预测T2完整cost，绝对差含重复初态漂移（GP噪声1.607214 N·s），远大于局部动作收益；同父action−固定标签与fold内预处理是有依据的新变体。不能只增加episode解决目标/数据身份问题。

## 本轮待物理闭合与建议

统一OUT0菜单下，先做强固定动作的跨状态同父配对，确认剩余可学排序。优先C3B相对收益交互/配对ranking与C2B分量化相对GP，以action-only、纯加法、history-disabled、强固定做消融。传统局部回归也要同权限；没有超强固定就不升级神经网络。

ILC要么采用确切合法参考效果描述投影已有菜单，要么明确申请连续参考参数新合同；不能把旧直接膝−0.3°硬映射成modal坐标。先完成真实Trial1→2→3物理对象连续性和末boundary积分闭合，再研究C1C自适应gain、C3C不同前动作history与效率。

LEVEL1纯接口可运行不等于整条物理链通过；v8已实际验证离线数据身份、拟合语义和决策变化，尚未由本家族运行新的完整任务部署，LEVEL4–7待主Agent独立核验。仍有多项合理机制未验证，整体否证证据不足。

## C3B批准离线fit与相对收益目标

主Agent明确批准单CPU120秒合同后执行，实际CPU .126832秒，28次多头ridge solve（4个模型×6整context LOO及1全开发fit），18个同父完整menu标签，4个独立目标头：JF(action)−JF(B)、JM差、原资格0/1、原motion worst_ratio−1。新physics和fresh on-policy=0。不是重训旧3患者NPZ；模型、标签、数据身份全部新建。

history8来自EARLYN01/EARLYH01/EARLYL01/CFACTORH01/CFACTORL01/HOLDSS03，各3806行已保存causal history与trace的estimated/reference/measured/time/phase逐项exact相同；从真实COMPLETE commit与trace补已有第3807末boundary。JF最大闭合误差2.96e−12 N·s，JM1.42e−13 Nm·s。未加载evaluation-only Human/native truth键，没有缺字段补零。此6context全已暴露，且history是同冷父完整B的反事实结果；不代表真实连续Trial1→2。

|模型/消融|6context LOO动作（依以上顺序）|原资格合格|合格子集JF收益和/相对B|结论|
|---|---|---|---|---|
|action-only|E,B,E,E,B,B|3/6|0|3个E运动失败，低JF不排名|
|history纯加法|E,E,B,B,E,B|5/6|79.627565 N·s|EARLYN误选E，excursion失败|
|history×action|E,E,B,B,E,B|5/6|79.627565 N·s|与纯加法同动作，无交互决策增量|
|同权重history-disabled|E,B,E,E,B,B|3/6|0|当前历史影响资格启用，但不是强固定外泛化|
|commissioned25×action独立对照|B,E,B,B,E,B|6/6|79.627565 N·s|相同收益且少1次失败，history8没有超过它|

E表示同一确切EARLY_H150，B为原B。表中只在原合格子集求收益，不能把5/6和6/6条件均值当同一完整安全策略。每个失败、原始JF/JM和native motion在 `c3b_offline_v1/LOCO_PREDICTIONS_AND_REALIZED.json` 保留。

`CONFIRMED`：所有6 LOO、所有模型的无资格约束最低预测JF均为E；历史只改变资格gate，而未发现force动作排序异质性。全开发history交互/加法/commissioned25均6/6合格，均只在H、CFL、HOLDSS03启用E；合格JF收益和118.347887 N·s。该训练内结果不可当独立成功。

`CONFIRMED`：全开发action-only资格为0.5，disabled为0.4999999999999999，恰在冻结 `>=0.5` 门的数值平局两侧，分别选E和B。没有修改合同阈值、加容差或事后重训。不能把这个微小数值差异夸大为可靠history消融证据。资格回归分数也未概率校准。

全开发设计秩：action-only 3/3，纯加法8/11，history交互18/27，commissioned25交互18/78；ridge缓解欠定不等于识别患者机制。本次已实质覆盖相对标签、纯动作、纯状态加法、显式交互、disabled和另一合法表示；在当前3recipe/6暴露context范围，未见history交互超过更简单加法或commissioning对照，限定结论为`CONFIRMED`。BO分量采集、真正连续ILC和不同先前动作history仍`NOT_RUN`，不能整体否定家族。

冻结快照SHA：`d4ac2decc3732e4a22de538d90ddd646a37cce142d258e43f6e9c82ea7b0ada4`；共享dataset SHA：`ea35953cf6e8775a7331a80febf1219b2d2d047677fb2cc57db6e8baf0773ed5`；history dataset SHA：`44336231f662dae704327931a10122b8b1dcf6cfcbc00dffa1081f61e021eaab`。`completed_history_reader.py`通用提取在6旧组特征逐值完全复现，另在已完成V8ENGH01_B上JF/JM闭合到2.27e−13/1.42e−14；该只读probe没有fit或physics。`c3b_inference.select`是纯冻结预测API。

`persistent_session_bridge.py`与 `PERSISTENT_INTEGRATION_PLAN.md`只有源级集成和AST检查，未调用任何physics；真实连续性实现门仍待主worker接入。此前首次synthetic check有一项fixture预期不匹配：同时改时间使future-observation先于nonmonotonic拒绝；保留 `INTERFACE_CHECK.json`，修正fixture同步source timestamp后 `INTERFACE_CHECK_v2.json`12项通过，未减弱接口检查。
