# N2去程末段：证据诊断

本节首先依据已保存的真实native物理记录，不依赖新增physics。时间均为TASK时钟；物理时钟=TASK+10.05s。raw acceleration/jerk为0.25ms native qvel的数值导数。±0.5°首次进入时间仅用于同步性诊断，不等于任务完成、稳定停住或临床舒适度。

## 目标、参考与真实运动

|臂|最后非终末请求|目标hip/knee °|通过速度hip/knee °/s|最终请求|最终suffix s|
|---|---:|---|---|---:|---:|
|N2 B|5.490|118.31775 / 117.97848|5.60750 / 8.08606|6.935|0.275|
|N2 18D|5.510|120 / 117.78453|0 / 8.86233|6.785|0.220|
|N1 18D，motion PASS|5.700|120 / 115.27087|0 / 18.92080|6.790|0.295|

精确rad、全部请求和事件见`derived/TERMINAL_DIAGNOSIS.json`，表中角度为显示近似值。N2 18D真实hip/knee首次进入120±0.5°分别为6.56350/7.01900s，差0.45550s；匹配B为7.16400/7.16775s，差0.00375s。N1 18D为6.58650/7.08500s，差0.49850s，因此“hip先到、knee后到”不是N2独有，也不能单独区分motion PASS/FAIL。

N2 18D在1.515、2.925、4.240s的空间意图被接受；5.510s空间意图因`NORMALIZED_TARGET_OUT_OF_RANGE`拒绝。原18D源码是在完整原选目标后尝试空间偏移，不做越界截断；拒绝后保留此前已筛查的target。注意动态方法调用：原目标评估已经通过18D的速度扩展方法，故空间意图拒绝不能表述为“全部18D作用撤销、纯原B重新接管”。最终goal分支不施加18D空间偏移，目标通过速度为0。

## 精确局部时序

|事件|N2 18D TASK s|直接证据|
|---|---:|---|
|最后非终末request；空间意图拒绝|5.510|summary决策和learning record|
|复合参考activation；bridge开始|5.515|rolling splice record|
|40ms bridge后新suffix开始|5.555|原splice_elapsed=0.040|
|非终末suffix结束|6.780|activation+bridge+1.225|
|最终request|6.785|summary timing_request_id=11|
|最终复合参考activation|6.790|rolling splice ACTIVATE|
|最终quintic开始|6.830|保留40ms bridge|
|issued膝参考负加速度最大样本|6.995|-148.302772°/s²，5ms参考采样|
|最终quintic结束，参考dq=0|7.050|连续quintic+issued reference|
|native实际膝负加速度最大|7.07225|-90.058623°/s²；实际膝dq约5.917977°/s|

因此不能把6.790s误当最终quintic开始，也不能用6.790+0.220=7.010s作为实际参考终点。最终实际峰落在参考负加速度样本后77.25ms、参考停下后22.25ms。完整任务仍在9.005s切换HOLD，并非目标附近出现峰值就提前终止TASK。

## 原B与N1对照

原B通过速度由reference到target的位移、target到goal的剩余距离，以及原速度/加速度上限计算：速度上限/1.875、sqrt(2a×制动距离)、a×剩余距离/速度上限三者取小，并按方向门归零；末端双关节进入原容差时目标dq为0。原scheduler在5ms网格选最短可行quintic，mechanics不通过时才尝试更长时长。这些是源码直接确认的规则，见`provenance/SOURCE_RULES.md`。

N2 B最终request=6.935s，activation=6.940s，quintic=6.980–7.255s，双关节同步制动。它全程膝amax=72.093488°/s²，发生于2.84925s，**并非末段**。N2 18D的90.058623/72.093488=1.249192，超过冻结1.10门；允许上界为79.302836°/s²。

N1 B/18D的膝amax分别128.347787/133.522019°/s²，比值约1.0403，motion PASS。N1 18D也有空间越界拒绝、单关节先到、40ms bridge和终末膝参考约149.736°/s²。它不能证明这些结构无影响，但直接反驳“这些事件一出现就必然造成motion FAIL”。N2资格失败还取决于匹配B分母显著较小。

最早差异须区分比较对象：N2与N1从第0个合法prefix不同开始分叉，5ms trace最早issued reference及command差异在0.010s、真实q/dq差异在0.015s；这不是末段新故障。N2内部E与B共享prefix，第一条18D空间意图在1.515s请求，复合参考1.520s激活，保留bridge后1.565s出现issued/command差异，1.570s的5ms实际采样已不同。native分辨率和带量级的差异时间另见`derived/EARLIEST_DIFFERENCES.json`。不同prefix的末段比较不能当同状态单因素实验。

## 跟踪、反馈和执行归属

N2 18D最终request前150ms，hip/knee q跟踪RMS约0.16555/0.39108°；request后300ms变为0.07669/0.51240°。膝dq误差RMS由0.38526变为4.51022°/s。6.995s参考负加速度最大时，实际膝尚约10.924°/s、实际a约-14.674°/s²；7.050s参考已停，实际膝仍约7.887°/s、a约-84.458°/s²。之后出现7.07225s实际峰。这支持“参考终端制动后存在有时延的真实闭环响应”的时序解释。

同两窗口robot分量范数RMS：base约92.249→92.378Nm，position约5.570→6.262Nm，velocity约4.749→4.733Nm，allocator约40.291→41.274Nm，clipping为0。6.75–7.40s的130个执行区间中，clearance反馈修正和incremental acceleration projection都未激活。没有观察到这些限制器在峰前突然切换的证据；分量范数变化也不足以识别某个allocator轴的独立贡献。具体带符号向量、5ms执行反馈、positive receipts和原生命令归属在`derived/RESPONSE_CHANNELS.json`。所有native step均独立核对对应receipt、施加torque与步数，见`audit/ARCHIVED_RAW_INDEPENDENT.json`。

## 解释边界与干预选择

直接观察：目标不同步、空间意图拒绝、参考制动形状、参考先停而实际膝仍运动、随后真实加速度峰、原安全链通过。源码直接确认：范围门、通过速度公式、网格quintic、40ms bridge、100ms scientific source-age、current admission及receipt ownership。

机制解释：18D改变上游目标/通过状态及请求时序，在短终末suffix中形成不同的速度波形，随后经反馈/allocator/contact闭环形成延迟响应。单靠时间顺序无法唯一断言空间不同步、某个torque分量、contact动力学或估计误差是主因；C/R历史干预也同时改变多个闭环量。

本轮选择合法的单一末段参考时间因素，保持原18D选目标和通过速度，最后去程suffix倍率1.5，继续由原全部检查执行。事前协议见`INTERVENTION_PROTOCOL.md`。其新增真实物理结果与机制证据应在`MECHANISM_FINDINGS.md`中单独报告，不反写本节存档事实。

![局部共同时间轴](figures/N2_terminal_timeline.png)
