# 合法匹配状态验证

科学复现门限：PASS。116,320个native行与5,817个receipt的同动作轨迹检查通过；有限数值误差为0，NaN日志字段仅核对一致缺失。

新发现四个干预分支完整OUTBOUND入口hash一致：True；RETURN-entry两个分支完整hash一致：True。

完整活进程address-space由os.fork复制；JSON只记录验证摘要，未用来恢复。MuJoCo integration、Human/commissioning、estimator/controller、reference/phase、planner/scheduler、carry/issued slots/lifecycle、RNG与native context全部继承。每个child恢复完整hash、parent在child退出后的完整hash都核验。

科学仿真冻结物理epoch；原科学模式source≤100ms、native admission/governor/physical safety保留。Host 40ms bridge/100ms wall lifecycle原代码未改，但本包不证明其host资格。Wall plan-age的原FAIL和mode-aware realtime N/A均保留。

初次两个零分支的serial snapshot差仅为gc_events诊断列表长度2→4；该诊断记录未被scrub，逐branch完整复制/parent不变证据保留。后续每个分支组只collect一次，新发现组完整hash相同。
