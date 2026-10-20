# Track A — 物理前协议

最新Early RETURN的RETURN1×1.10、RETURN4×1.20，D的RETURN2/3[+0.3,-0.3]°，18D全部参数/plateau与T规则冻结。新干预仅RETURN3膝通过速度×0.90；有条件第二候选×0.80。该槽原选目标、髋通过速度、原选时长不变；后续活态重规划可因果响应。每次重建原fixed-duration证书、安全逃逸、40ms bridge与当前状态准入。

实际膝参考停稳前已有下冲，故不预设纯惯性唯一原因。失败、未执行和局部/完整代价分别记录。

{
  "version": "multi_track_v1",
  "eligibility": "Full original task/safety/motion/receipt plus actual intervention acceptance; gain>=1% vs own matched B and retain>=80% of ER saving; terminal overshoot must decrease vs ER",
  "selection": "Prefer AV090 if eligible. AV080 only if AV090 remains ineligible but reduces excursion without new failed axes or >10% raw amax/jerk RMS increase vs ER. No minimum-force search. At most two A candidates.",
  "validation": "Freeze first eligible identity before one deterministic repeat and unused legal W2 matched B/T/D/ER/candidate. Never retune on W2.",
  "stop": "Task, absolute safety, causal failure stops all physics. New motion failed requirement vs ER or >10% amax/jerk RMS vs ER or tracking RMS>ER+.5deg pauses further A candidates; record and switch tracks.",
  "budget": "60 total START, development <=42, reserve18; all parents/forks/failures count; serial only"
}
