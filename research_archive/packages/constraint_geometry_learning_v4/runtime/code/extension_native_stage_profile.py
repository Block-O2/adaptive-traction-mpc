"""Localize retained-state original B work without allocating a plant."""
from extension_common import *
import pickle,cProfile,pstats,numpy as np
from dataclasses import replace

def main():
    guard(1800);begin=time.time();before=sha(STUDY/'ATTEMPTS.jsonl')
    import study_common as sc
    from extension_timer_service import warm,equivalent
    warm('T0')
    from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import snapshot_task_call,execute_task_snapshot
    from causal_timing_report import quantile
    import profiling_instrumentation as pi
    paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'))
    assert len(paths)==22;items=[]
    for p in paths:
        raw=pickle.loads(p.read_bytes());planner,args=pickle.loads(raw['payload']);planner.planner.residual_spec={};payload=snapshot_task_call(planner,args)
        t=time.monotonic_ns();d=execute_task_snapshot(payload);end=time.monotonic_ns()
        items.append(dict(path=str(p),sha256=sha(p),payload=payload,baseline=sc.clean(replace(d,runtime_ms=0.)),initial_elapsed_ms=(end-t)/1e6,argument_types={k:type(v).__module__+'.'+type(v).__qualname__ for k,v in args.items()},planner_attributes={k:type(v).__module__+'.'+type(v).__qualname__ for k,v in vars(planner).items()}))
    pi.install();rows=[];aggregated=cProfile.Profile()
    for i,item in enumerate(items):
        pi.EVENTS.clear();t=time.monotonic_ns();d=execute_task_snapshot(item['payload']);end=time.monotonic_ns();assert equivalent(sc.clean(replace(d,runtime_ms=0.)),item['baseline'])
        events=list(pi.EVENTS)
        prof=cProfile.Profile();prof.enable();d2=execute_task_snapshot(item['payload']);prof.disable();assert equivalent(sc.clean(replace(d2,runtime_ms=0.)),item['baseline'])
        stats=pstats.Stats(prof);top=[]
        for (path,line,name),(cc,nc,tt,ct,callers) in sorted(stats.stats.items(),key=lambda v:v[1][3],reverse=True)[:40]:
            top.append(dict(path=path,line=line,function=name,primitive_calls=cc,total_calls=nc,self_ms=tt*1000,cumulative_ms=ct*1000))
        rows.append(dict(state_index=i,snapshot=item['path'],snapshot_sha256=item['sha256'],initial_unprofiled_ms=item['initial_elapsed_ms'],wrapped_unprofiled_ms=(end-t)/1e6,whole_decision_equivalent=True,events=events,cprofile_top=top,argument_types=item['argument_types'],planner_attributes=item['planner_attributes']))
    assert sha(STUDY/'ATTEMPTS.jsonl')==before
    groups={}
    for name in sorted({e['name'] for r in rows for e in r['events']}):
        values=[e['elapsed_ms'] for r in rows for e in r['events'] if e['name']==name]
        groups[name]=dict(n=len(values),elapsed_ms=quantile(values))
    register_imports('NATIVE_STAGE_PROFILE')
    out=dict(status='PASS_OFFLINE_LOCALIZATION',rows=rows,event_groups=groups,initial_unprofiled_ms=quantile([r['initial_unprofiled_ms'] for r in rows]),wrapped_unprofiled_ms=quantile([r['wrapped_unprofiled_ms'] for r in rows]),wall_seconds=time.time()-begin,physics_attempts_added=0,actual_physics_steps_added=0,Q_updates=0,interpretation='Original B decide on immutable already-occurred causal snapshots, empty residual. Initial unprofiled elapsed, elapsed wrappers and cProfile localization have separate scopes. Nested/cumulative times are not additive and profiled timing is not deployment latency. No activation certificate inputs or physics advance are synthesized from these snapshots.')
    save(EXT/'NATIVE_STAGE_PROFILE.json',out);print(json.dumps(dict(status=out['status'],states=len(rows),initial_unprofiled_ms=out['initial_unprofiled_ms'],event_groups=groups,wall_seconds=out['wall_seconds'])))

if __name__=='__main__':main()
