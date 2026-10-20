"""Native empty-prefix B route baseline isolation, no new engineering repair."""
from prepare_tasks import *
from full_native_equivalence import full_compare
from prepare_next_versions import frozen_sources
def main():
 a='280_E7_DEFERRED_science_B';b='320_NATIVE_B_ROUTE_science_zero_Q';ra=json.loads((STUDY/'output'/(a+'_RESULT.json')).read_text());rb=json.loads((STUDY/'output'/(b+'_RESULT.json')).read_text());assert ra['metric']['valid'] and rb['metric']['valid']
 result=full_compare(a,b);sa=json.loads((STUDY/'source/results'/a/'summary.json').read_text());sb=json.loads((STUDY/'source/results'/b/'summary.json').read_text());observer_equal=sa['qualification']['true_physics']==sb['qualification']['true_physics'];assert observer_equal
 out=dict(status=result['status'],row=result,original_true_physics_record_exact=observer_equal,source_unchanged=True,tolerance=1e-10,physics_added_by_this_gate=0,classification='BASELINE_ROUTE_ISOLATION_NOT_A_NEW_OPTIMIZATION',interpretation='Identical seed and empty residual, original-runtime B versus the frozen B-native PrefixBInterface baseline route. Complete physical/reference/decision equivalence is tested, not assumed from similar scalar cost. Extra host runs isolate the native no-Q execution chain; no public repair or candidate authority is added.')
 save(STUDY/'reports/BASELINE_RUNTIME_ROUTE_EQUIVALENCE.json',out);print(json.dumps(dict(status=out['status'],issues=result['issues'],native_signature_exact=result['full_native_step_signature_exact'],observer_exact=observer_equal)),flush=True)
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[e for e in events if e['event']=='START'];done={e['id'] for e in events if e['event']=='END'};assert all(e['id'] in done for e in starts) and len(starts)+4<=160 and time.time()+600<START+8.25*3600
 sources=frozen_sources()
 for f in ('deferred_evaluation.py','lean_instrumentation.py','async_native_main.py','async_native_worker.py','certified_snapshot_v2.py','certified_apply.py'):sources[str(STUDY/'code'/f)]=sha(STUDY/'code'/f)
 rows=[dict(id=f'{321+j:03d}_NATIVE_B_ROUTE_cold_{j+1}',seed=2026100841+j,method='M0',original=False,prefix={}) for j in range(4)]
 save(STUDY/'versions/NATIVE_B_ROUTE_HOST_PROTOCOL.json',dict(rows=rows,physics_attempts=4,science_route_equivalence=result['status'],science_signature_exact=result['full_native_step_signature_exact'],input_seeds_shared_with_E7_cold_series=True,causal_latency_pairing_claim=False,scope='Four native zero-Q cold attempts after source-unchanged baseline route crosscheck. Different wall epochs are not a latency causal pairing; strict unchanged realtime evaluator and real advancing physics used.',Q_calls=0,new_public_B_repairs=0,algorithm_sources=sources))
 for r in rows:enqueue(r['id'],method='M0',original=False,prefix={},seed=r['seed'],timing_version='E5_DEFERRED_v1',execution_mode='REALTIME_CHARACTERIZATION',pipeline_batch=False,research_profile=False,deferred_evaluation=True,algorithm_sources=sources,host_series='native_B_route_zero_Q_cold')
 print('FOUR_NATIVE_ZERO_Q_B_HOST_COLD_CHECKS_QUEUED')
if __name__=='__main__':main()
