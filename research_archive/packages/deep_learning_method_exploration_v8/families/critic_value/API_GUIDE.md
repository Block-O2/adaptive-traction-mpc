# 冻结推理接口

数值环境使用既有只读offline-env，Python必须带 `-B`，并设置 `PYTHONDONTWRITEBYTECODE=1`、BLAS/OMP/MKL线程1。source/value_api.py和冻结模型在4case启动后保持不改。

```python
from value_api import to_context25, predict
from controls_api import predict_control

ctx = to_context25(raw_OUT0_causal_payload)
decision = predict(value_bundle, ctx, method="ABS_25", objective="JF_QUALIFIED")
strict = predict(value_bundle, ctx, method="ABS_25", objective="STRICT_JM")
simple = predict_control(strong_controls_bundle, ctx, control="IF_STUMP_TRAIN")
```

API不读文件，不接收当前dataset行或结果。部署调用者加载冻结bundle后只传实际捕获的OUT0因果payload，或经过检查的25D subset。输入顺序beta11→geometry4→residual10，QA保留但不作为成本/actor额外特征。OUT0完整77D继续INVALID；模型不补缺失TASK历史、未来reference、Human、torque或receipt。

`predict`返回每recipe的分量预测、未校准资格failure score、ensemble分歧、支持距离，以及choice_tag/hash/action。ABS输出绝对完整JF/JM，DELTA_B输出相对同父B，DELTA_STRONG输出相对同父LATE_H150，PAIR的实际选择使用独立rank utility，辅助分量仍为deltaB。不同分量语义不能混排数值。无支持或预测risk>=0.5的所有候选均拒绝时返回None/ABSTAIN；主driver事前登记回退B，不用未来资格改选。

`predict_control`支持BEST_FIXED_TRAIN、IF_STUMP_TRAIN和NEAREST_CONTEXT。nearest只读取bundle中冻结的过去已完成训练反馈，不读取当前完整结果；它不是连续Trial个体化。相同完整recipe被多个模型选中，只共享一次实际执行结果，不生成多次独立验证或已实现省试。

完整recipe身份包含顶层action、应用candidate_overrides后的基础候选（不含tag id）、FROZEN_18D、terminal_repair/modal源码及参数映射SHA。统一driver必须逐值绑定config实际action，保留early/late和slot_overrides。只有同tag不够；当前四个冻结config的精确静态核验见analysis/V8_FROZEN_SELECTOR_STATIC_REVIEW_V1.json。

`source/short_window_api.py: select_short(records, horizon_s)`是另一种对照：调用者必须实际取得所有同父候选H窗口的measured JF/JM。它拒绝完整未来资格/成本字段，不作未来mask；这需要真实候选物理，不能当作与廉价value推理成本相同。完整菜单执行后的窗口选择只能用于回顾能力比较，真实attempt仍全部记账。
