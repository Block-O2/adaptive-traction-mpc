# 上层快速协调优化

A为直接pattern search，B为粗名义负荷引导，C为同类名义模型加GP残差/经验completion筛选。各32个候选，前16个方向设计分别实际执行、各自保留反馈，后16才自适应。共同参照在预算0已公开，各方法可保留它；共同设计中的收益不能归于Learning。

|方法|候选尝试|完整|原门合格|最佳JF|对应JM|共同前16最佳JF|后16最佳JF|
|---|---|---|---|---|---|---|---|
|A|32|32|29|1398.549121|107.967222|1399.390045|1398.549121|
|B|32|32|20|1399.335523|106.546391|1399.390045|1399.335523|
|C|32|32|29|1399.188323|106.957822|1399.390045|1399.188323|


|候选物理预算|方法|最佳合格sample/候选JF|PPO已评价mean最佳JF|新增native|
|---|---|---|---|---|
|8|A|1399.390045|NOT_RUN|554080|
|8|B|1399.390045|NOT_RUN|554080|
|8|C|1399.390045|NOT_RUN|554080|
|8|PPO|1399.687389|1400.089728|554080|
|16|A|1399.390045|NOT_RUN|1108160|
|16|B|1399.390045|NOT_RUN|1108160|
|16|C|1399.390045|NOT_RUN|1108160|
|16|PPO|1399.687389|1400.089728|1108160|
|20|A|1399.136967|NOT_RUN|1385200|
|20|B|1399.335523|NOT_RUN|1385200|
|20|C|1399.390045|NOT_RUN|1385200|
|20|PPO|1399.687389|1399.925754|1385200|
|24|A|1398.712410|NOT_RUN|1662240|
|24|B|1399.335523|NOT_RUN|1662240|
|24|C|1399.188323|NOT_RUN|1662240|
|24|PPO|1399.286089|1399.925754|1662240|
|32|A|1398.549121|NOT_RUN|2216320|
|32|B|1399.335523|NOT_RUN|2216320|
|32|C|1399.188323|NOT_RUN|2216320|
|32|PPO|1399.286089|1399.925754|2216320|
|40|PPO|1399.286089|1399.925754|2770400|
|48|PPO|1399.193197|1399.925754|3324480|
|64|PPO|1398.995849|1399.925754|4432640|


曲线见 `figures/MATCHED_BUDGET_CURVES.png`。PPO mean评价消耗真实预算；最佳训练sample与已评价策略mean分开。cold parent、共同参照、接口开发、旧历史先验和补充分支在总账单列。单次搜索轨迹不能给出多seed统计优势；便宜代理未被宣称满足5ms在线控制。

补充参考响应模型使用共同的17条因果控制历史（强固定+16个单向设计），学习参数到实签q/dq/ddq的有符号局部响应，再由原估计Human模型与allocator算负荷。仅用于离线排序，实际控制仍接收普通modal参数、经过原certificate和执行链。相同17条历史及相同候选池的传统成本响应模型、原粗名义模型各有一个冻结实测对照；另测两个参考响应候选。额外4次测试、cold parent及B/H150/strong均计账。它没有学习跨状态模型，没有原生motion预测或校准不确定性。

|冻结测试|完整|合格|参考响应预测JF|传统成本预测JF|实际JF|参考响应预测JM|传统成本预测JM|实际JM|
|---|---|---|---|---|---|---|---|---|
|RESPONSE_MODEL_01|True|False|1397.863943|1397.714495|1397.711027|108.064186|108.094352|108.076503|
|RESPONSE_MODEL_02|True|False|1397.886565|1397.783431|1397.820457|108.073885|108.099234|108.086399|
|RESPONSE_NATIVE_SCALAR_COUNTERFACTUAL|True|False|1397.863943|1397.714495|1397.711027|108.064186|108.094352|108.076503|
|RESPONSE_NOMINAL_COUNTERFACTUAL|True|True|1400.348351|1400.838311|1400.844093|105.845986|105.818261|105.996606|


同族坐标优化：每臂上限8候选，前4个物理设计相同且分别付费；后4个使用原坐标轴或旋转方向，两臂使用相同备选物理步长集合、实际x平方域相同；边界/重复点过滤后的实际逐次步长另按原账核验。共同cold parent/B/H150另计3条实际START。此分支从H150开始，不混入新8维优化主比较；单次8点结果不证明一般坐标优势。

|旧二维同族坐标|实际候选尝试|完整|合格|最佳JF|对应JM|
|---|---|---|---|---|---|
|NATIVE|8|8|8|1400.143110|107.758496|
|ROTATED|8|8|8|1401.395800|107.488072|


新实测共同设计4对的科学raw身份核验=PASS；实际逐次步长检查=DEVIATION_ACTUAL_STEP_NORMS_DIFFER。原搜索的相同步长备选集合并不保证边界/重复点过滤后实际步长相同。若有差异，完整8次成绩仅作该受约束搜索的描述；严格等实际步长的比较使用预先登记的、只由步长决定的最长匹配前缀。详见 `audit/COORDINATE_COMMON_DESIGN_RAW_IDENTITY.json` / `COORDINATE_ACTUAL_STEP_AUDIT_ADDENDUM.json`。

|坐标|严格匹配前缀候选数|原门合格|最佳JF|对应JM|
|---|---|---|---|---|
|NATIVE|7|7|1401.134395|107.555547|
|ROTATED|7|7|1401.395800|107.488072|


含cold parent及B/H150/strong的完整成本比较：

|方法|含启动参照实际START子集预算|最佳合格JF|PPO已评价mean最佳JF|新增native|
|---|---|---|---|---|
|A|12|1399.390045|NOT_RUN|878180|
|A|20|1399.390045|NOT_RUN|1432260|
|A|24|1399.136967|NOT_RUN|1709300|
|A|28|1398.712410|NOT_RUN|1986340|
|A|36|1398.549121|NOT_RUN|2540420|
|B|12|1399.390045|NOT_RUN|878180|
|B|20|1399.390045|NOT_RUN|1432260|
|B|24|1399.335523|NOT_RUN|1709300|
|B|28|1399.335523|NOT_RUN|1986340|
|B|36|1399.335523|NOT_RUN|2540420|
|C|12|1399.390045|NOT_RUN|878180|
|C|20|1399.390045|NOT_RUN|1432260|
|C|24|1399.390045|NOT_RUN|1709300|
|C|28|1399.188323|NOT_RUN|1986340|
|C|36|1399.188323|NOT_RUN|2540420|
|PPO|12|1399.687389|1400.089728|878180|
|PPO|20|1399.687389|1400.089728|1432260|
|PPO|24|1399.687389|1399.925754|1709300|
|PPO|28|1399.286089|1399.925754|1986340|
|PPO|36|1399.286089|1399.925754|2540420|
|PPO|44|1399.286089|1399.925754|3094500|
|PPO|52|1399.193197|1399.925754|3648580|
|PPO|68|1398.995849|1399.925754|4756740|
|PPO|72|1398.995849|1399.918272|5033780|


A/B/C各方法的实际记录子集均包含同一组4条CORE启动参照；这些子集有重叠，总账按union只计一次。PPO使用其自身4条启动记录。没有虚构额外执行或隐藏父前缀成本。见 `MATCHED_TOTAL_INTERACTION_BUDGET_RESULTS.json` 与 `figures/TOTAL_INTERACTION_BUDGET_CURVES.png`。


固定目标首次达到成本（先登记阈值、后看自适应结果）：

|方法|评价对象|降JF目标 N·s|结果|首次真实候选尝试|新增native|
|---|---|---|---|---|---|
|A|best_actual_sample_or_candidate|0.1|REACHED|3|207780|
|A|best_actual_sample_or_candidate|0.5|REACHED|8|554080|
|A|best_actual_sample_or_candidate|1.0|REACHED|22|1523720|
|A|best_actual_sample_or_candidate|2.0|NOT_REACHED|None|None|
|B|best_actual_sample_or_candidate|0.1|REACHED|3|207780|
|B|best_actual_sample_or_candidate|0.5|REACHED|8|554080|
|B|best_actual_sample_or_candidate|1.0|NOT_REACHED|None|None|
|B|best_actual_sample_or_candidate|2.0|NOT_REACHED|None|None|
|C|best_actual_sample_or_candidate|0.1|REACHED|3|207780|
|C|best_actual_sample_or_candidate|0.5|REACHED|8|554080|
|C|best_actual_sample_or_candidate|1.0|NOT_REACHED|None|None|
|C|best_actual_sample_or_candidate|2.0|NOT_REACHED|None|None|
|PPO|best_actual_sample_or_candidate|0.1|REACHED|2|138520|
|PPO|evaluated_mean|0.1|REACHED|17|1177420|
|PPO|best_actual_sample_or_candidate|0.5|REACHED|21|1454460|
|PPO|evaluated_mean|0.5|NOT_REACHED|None|None|
|PPO|best_actual_sample_or_candidate|1.0|REACHED|61|4224860|
|PPO|evaluated_mean|1.0|NOT_REACHED|None|None|
|PPO|best_actual_sample_or_candidate|2.0|NOT_REACHED|None|None|
|PPO|evaluated_mean|2.0|NOT_REACHED|None|None|


补充motion余量回退已实测2/2个固定候选，最佳原门合格JF=1398.034615。这是原参考模型与传统成本模型共同低力动作失败后，利用过去单模态反馈只减小R_pass_speed的传统修复；不归于主GP或PPO收益，2候选+4冷启动/参照另计。0.49deg仅为额外余量目标，原0.5deg门保持。 见 [固定回退](MOTION_MARGIN_BACKOFF.md)。
