"""Explicit result separation; no approximated B/H150 scorer or promotion."""
def classify(metrics,summary,audit):
 from ready_env import completion_evidence
 runtime=bool(metrics.get('success') and completion_evidence(summary,metrics.get('phases')))
 return {'RUNTIME_COMPLETE':'PASS' if runtime else 'FAIL','MATCHED_19_030_NECESSARY_TIMING':'PASS' if runtime and abs(metrics['task_s']-19.03)<.05 else 'FAIL','MATCHED_TASK_PASS':'NOT_READY_ORIGINAL_B_H150_SCORER_MISSING','FULL_QUALIFIED':'NOT_READY_ORIGINAL_B_H150_SCORER_MISSING_AND_G4_STRICT_FAIL','OBSERVED_EPISODE_PHYSICS_AND_CAUSAL':'PASS' if audit.get('pass') else 'FAIL','HOST_REALTIME_STRICT55':'NOT_EVALUABLE_SCIENTIFIC_SIMULATION'}
