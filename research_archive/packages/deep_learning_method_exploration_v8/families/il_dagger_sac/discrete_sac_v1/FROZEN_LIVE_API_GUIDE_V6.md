# 冻结SAC纯OUT0接口（源码候选）

source/frozen_live_api_candidate_v6.py的`predict_before_B(package, config, study)`无写文件/派发。当前仅AST解析，未import、restore或predict；未新增任何forward。Root审核冻结后在实际OUT0捕获已保存且B未执行时调用，先保存完整返回值，再执行原sequence。

该接口返回AGG三机制actor、vanilla同Q greedy/softmax、B/best-fixed/if/nearest，共9个selector；实际只需3次SAC predict+4次control predict+3次只读restore。sameQ两个对照复用主法同一次Q，不另fit/forward。不选择开发CV最好者，主法始终SAC_AGG_VANILLA_ACTOR。FRESH三个模型冻结留存作预登记诊断，接口不擅自换主cohort。

所有module/bundle都按manifest SHA加载。复用已冻结A3 actual proof adapter，从实际job SOURCE_MANIFEST、原saved OUT0、七个源文件/loaded module path与实际bound callback code filename生成严格proof；不接受调用侧自称source。原checksum/OUT0/task_s=0/QA经已冻A2 causal_api转25D，77整体INVALID保持。支持profile需实际c425 worker_v2/dc73 loader及其它五角色全部匹配；任意其它callback不能自动放行。

```python
# SOURCE_ONLY范例；本次未执行。原worker已保存study.prefork_causal_context。
block = frozen_live_api.predict_before_B(P, C, study)
put('audit/' + GROUP + '_SAC_FROZEN_PRE_B_SELECTIONS.json', block)
# root在上项持久化之后，原sequence才yield B。
# 每choice_action必须按原recipe执行；共享相同recipe不是独立重复或省试。
```

底层已冻结纯API同样可用：`learner.restore(snapshot, expected_source_sha256=..., expected_contract_sha256=..., expected_recipe_sha256=...)`，再`learner.predict(model, feature_names, commissioned25, qa_validated=True)`。restore只复原冻结bytes，不初始化/fit新model。原scope source/QA的核验由上述owner adapter负责，传递qa_validated=True并不替代证据。

输出保留原abstain；执行fallback B是事前固定规则，返回值同时标记abstain和fallback，不授予原资格。BEST_FIXED无共同动作会abstain，原真实B强控制已存在；fresh-table UNKNOWN不等于B物理失败。原门、原时钟、owned物理、费用和选择先于结果仍由root负责。

静态覆盖仅AST/签名/固定source-menu绑定；未来真实loaded-source/OUT0联调尚NOT_RUN。当前adapter额外forward/fit/physics均0。
