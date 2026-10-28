# 根因与边界

证据先于修复：`audit/HISTORICAL_RAW_DIAGNOSIS.json` 从上一轮完整 trace 与在线 tick 独立左积分，未使用 summary 作为真值。

slow episode 的 trace TASK 行1779：native时间18.944999999999446s，TASK8.895000000000193s，下一行时间完全相同；力范数111.02181066943028N。旧行预写入0.5551090533471514N·s。原 `_execute_interval` 在 `CURRENT_MODEL_ACTIVATION_REVALIDATION` 处拒绝，未apply、未推进native physics。异常分支置 `execution_rejected_before_apply=True`，保留行后回到同一物理边界，但未撤销预写的5ms成本。正确归属为零时长、零积分。

这不是 OUTBOUND/HOLD phase交接、episode终止或reset重复累计；出错发生在同一OUTBOUND内部的admission拒绝。自然terminal行本身成本为0，reset前后的force/reward累计器独立清零。重复callback在wrapper按实际dt=0积分，未重复收费。

修复：拟执行行初始积分为0；成功执行后才按 `actual_interval_duration_s` 计入；异常只按真实已推进native时长计入。拒绝记录完整保留，未减去固定常数。未改5ms左积分定义。

另发现同一重复行使moment summary用 `min(executed_interval_count,len(rows)-1)` 截断，漏掉最后真实区间0.04000901910159N·m·s；改为全部相邻边界左积分，零时长行自然贡献0。旧114.71605487166386，独立/修复后114.75606389076545N·m·s。

独立deadline反例：原reference-safe handoff对OUTBOUND/RETURN在10.005s、reference_ready=True时仍接受HOLD/COMPLETE。新检查在原10s期限已经超过时先ABORTED，精确边界惯例沿用原terminal commit；没有放宽期限。见 `audit/DEADLINE_BEFORE_AFTER_TEST_ONLY.json`。它不是random20.165s的原因，后者各phase均小于10s。

random与maximal的总TASK差1.135s，来自不同合法progress提议、5次而非1次planner拒绝/fallback及到达/settling时刻。没有governor附加减速，实际receipt的delay_added_s合计0；无超时收尾或commissioning混入。原物理任务终止器为10s/phase与30s/task；19.030s±0.050s另见封存执行回归。当前代码未把19.030s编码为全局终止deadline。保持两者证据并报告执行FAIL，不能把30s改写为一个历史上存在的19.030s配置。

科学限制：9个episode是固定development输入和TEST_ONLY，不是新held-out研究。一次隔离修复周期已完成；没有通过调参改变行动含义来强迫random达到19.030s。
