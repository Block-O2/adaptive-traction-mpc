# 介入前归因审计

只读核对11个完整历史run；3个RETURN-only均未在RETURN入口之前执行非零native协调。

- 005_return_history_scale_0.1：OUTBOUND ΔJ_F=-53.240123769 N·s，全部记为 pre-intervention imbalance，不能归功于RETURN residual。
- 016_validation_2026100902_candidate：OUTBOUND ΔJ_F=12.181106495 N·s，全部记为 pre-intervention imbalance，不能归功于RETURN residual。
- 019_validation_2026100903_candidate：OUTBOUND ΔJ_F=31.273287564 N·s，全部记为 pre-intervention imbalance，不能归功于RETURN residual。

三次B-zero J_F=[1499.0113949347622, 1484.5901136146686, 1472.9438855567455] N·s，range=26.067509378 N·s；n=3不是随机误差界。

模型beta/residual、commissioning几何拟合、TASK入口、最初command及native时序均保留逐run和逐对证据。最早force/运动差异在commissioning期间已可观测。现有观测不能确定哪个因素是主要独立原因。

所有实际非零执行均按native元数据、原学习区间、positive-step receipts核验；完整时间线、首command、carry/reject/expiry见reports。科学层级为历史host development仿真，未升级正式实时资格。

原初始population beta/residual相同；五个候选/零重复对照的force差都早于首个aligned estimator更新。详见commissioning_causal_order：不能把后续拟合beta差当作已经证明的最早外生原因。早期执行/采样时序和后续模型拟合存在连锁关系，独立OS根因仍未识别。
