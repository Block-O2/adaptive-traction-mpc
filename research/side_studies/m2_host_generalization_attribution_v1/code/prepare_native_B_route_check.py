"""Resolve original-runtime vs native zero-Q baseline routing, no new control."""
from prepare_tasks import *
from prepare_next_versions import frozen_sources
def main():
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[e for e in events if e['event']=='START'];done={e['id'] for e in events if e['event']=='END'};assert all(e['id'] in done for e in starts) and len(starts)+5<=160
 sources=frozen_sources()
 for f in ('deferred_evaluation.py','lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 save(STUDY/'versions/NATIVE_B_ROUTE_CROSSCHECK_PROTOCOL.json',dict(physics_before=len(starts),science_id='320_NATIVE_B_ROUTE_science_zero_Q',science_reference='280_E7_DEFERRED_science_B',science_seed=2026100621,comparison='Existing original=True runtime_sac_expert_v1 versus original=False runtime_coordination_residual_v2 with PrefixBInterface empty prefix, no Q or residual. The latter is the original frozen B-native/CASE4 M0 baseline route. Compare complete native trajectory, all references/decisions, R2 and metrics before interpreting original-runtime B timing as the same native chain.',source_mutations=0,new_public_B_repairs=0,Q_updates=0,remaining_conditional_actual_cold=4,projected_max_physics=len(starts)+5,algorithm_sources=sources))
 enqueue('320_NATIVE_B_ROUTE_science_zero_Q',method='M0',original=False,prefix={},seed=2026100621,timing_version='E5_DEFERRED_v1',execution_mode='SCIENTIFIC_SIMULATION',pipeline_batch=False,research_profile=False,deferred_evaluation=True,algorithm_sources=sources,baseline_route_crosscheck=True)
 print('ONE_SOURCE_UNCHANGED_NATIVE_B_ZERO_Q_SCI_ROUTE_CROSSCHECK_QUEUED')
if __name__=='__main__':main()
