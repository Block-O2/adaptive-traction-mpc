"""Publish canonical latency evidence from measured, hash-bound profiles."""
import json
from research_campaign import R,D,RAW,save,sha

def main():
 sources={
  'full_host_profile':RAW/'latency_host_profiles_v3/CLEAN_LAZY_HOST_PROFILE.json',
  'actual_cpu_models':RAW/'latency_cpu_models_scientific_v1/CPU_MODEL_LATENCY.json',
  'promotion_gate':D/'ONLINE_LATENCY_PROMOTION_GATE.json',
  'architecture_budget_audit':D/'ONLINE_DECISION_BUDGET_AUDIT.json',
  'pilot_update_lifecycle':D/'LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json',
  'boundary_continuity_audit':D/'LATENCY_BOUNDARY_CONTINUITY_AUDIT.json'}
 evidence={key:json.loads(path.read_text()) for key,path in sources.items()}
 save(D/'ONLINE_DECISION_LATENCY.json',{'schema':'canonical_actual_latency_evidence_v1',
  'status':'COMPLETE_SCIENTIFIC_MEASUREMENTS_HOST_MOVING_BUDGET_UNDEMONSTRATED',
  'units':{'decision':'milliseconds','model_update_and_harness_processing':'seconds'},
  'scope':'actual scientific simulation host; independent CPU profile; no GPU or hardware realtime qualification',
  'source_artifacts':[{'role':key,'path':str(path.relative_to(R)),'sha256':sha(path)} for key,path in sources.items()],
  'measured_evidence':evidence,
  'quantile_interpretation':'empirical sample percentiles; components not summed into artificial end-to-end quantiles'})
 section=(D/'LATENCY_REPORT_SECTION.md').read_text().replace('实际在线模型生成：|','实际在线模型生成：\n\n|')
 (D/'LATENCY_REPORT_SECTION.md').write_text(section)
 (D/'ONLINE_DECISION_LATENCY.md').write_text('# 实际在线决策延迟与更新证据\n\n'+section+'\n\n原始数字、组成项、候选数量、预算来源及 SHA 见 `ONLINE_DECISION_LATENCY.json`。训练更新完整事件保留于 `TRAINING_UPDATE_LATENCY.json`；去重与生命周期审计见 `LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json`。\n')
 print('canonical latency outputs complete')
if __name__=='__main__':main()
