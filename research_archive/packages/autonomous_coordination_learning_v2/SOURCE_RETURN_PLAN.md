# 源码回流建议（未执行Git变更）

起点为只读detached commit 1adb1de177d6f5f32de6d01c4e629cbfae9ce121；实际云端起点以历史learning_guided包manifest与本包CLOSURE_RELOCATION/SOURCE_MANIFEST为准。本轮代码在独立目录，未commit、push、merge、reset、stash或clean。

建议先review这些可独立回流的改动：

1. acl2_modal_retimed.py：可解释路径/时长/通过速度模式、逐关节终点锁与原scheduler最短合法时长；保留旧v1失败作为回归案例。
2. acl2_worker_owned.py / acl2_validation_worker.py：完整地址空间fork、源/config/PID/startticks身份、全部失败/partial计账、原scorer资格及冻结验证分工。
3. acl2_supervisor_v2.py 与独立watchdog/finalizer：有限队列、原T0绝对截止、活PID接管、每job后代停止与幂等结果保护。
4. acl2_scorer_replay.py、failure_audit和PPO audit：缓存外原scorer重放、独立native剂量/导数、采样密度/advantage/Adam复算。
5. 参考响应诊断与学习器：仅在本包实际forward/独立验证支持的范围内回流；不把事后参考重算或粗代理修正宣传为一般Learning优势。

先将这些新代码整理为可配置模块和有边界的回归检查；本包源码和失败证据保持原样。MuJoCo Human/robot/cuff资产、安全阈值、原scorer和历史checkpoints不作为本轮算法改动回流。大raw与模型权重按研究资产政策保存，本文没有授权自动上传任何数据。


原clearance包络的非光滑差分问题应先作为独立协议调查，保留原几何、阈值、物理与scorer，比较分段约束或保守处理；本轮没有修改原guard。当前GP motion预测存在低于指标结构下界的外推与原门反例，不能直接回流为安全筛选器。参考响应与传统成本模型若选同动作，不能把性能独归于复杂Learning。
