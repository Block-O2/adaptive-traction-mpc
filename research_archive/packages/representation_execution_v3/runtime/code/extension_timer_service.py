"""Shadow 5ms main-loop service during retained-state native B computation.

No physical environment, command, clock emulation or deployment qualification.
All decisions are compared to the unmodified original saved-state decision.
"""
from extension_common import *
import pickle,concurrent.futures as cf,multiprocessing as mp,math,os
from dataclasses import replace
PERIOD=5_000_000

def warm(version):
    import study_common as sc
    def forbidden(*a,**k):raise AssertionError('PHYSICS_FORBIDDEN_IN_EXTENSION')
    sc.SACExpertEnv.__init__=forbidden
    from traction_mpc_stage5.full3d_adaptive_integration_v1 import wall_physics as wp
    wp.WallPhysicsSession.__init__=forbidden
    if version=='C2':
        import batched_mechanics
        batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
    from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import _warm_planner_process
    ready=_warm_planner_process()
    return dict(pid=os.getpid(),ready_ns=ready)

def execute(payload):
    import study_common as sc
    from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import execute_task_snapshot
    start=time.monotonic_ns();cpu=time.thread_time_ns();decision=execute_task_snapshot(payload)
    finish=time.monotonic_ns();cpu_finish=time.thread_time_ns()
    return dict(worker_start_ns=start,worker_finish_ns=finish,worker_cpu_ms=(cpu_finish-cpu)/1e6,decision=sc.clean(replace(decision,runtime_ms=0.)),pid=os.getpid())

def equivalent(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(equivalent(a[k],b[k]) for k in a)
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and not isinstance(a,bool):return isinstance(b,(int,float)) and abs(a-b)<=1e-10
    return a==b

def one(surface,executor,payload,baseline,version):
    enqueue=time.monotonic_ns();next_due=enqueue+PERIOD;last_service=enqueue;services=[]
    def service():
        nonlocal next_due,last_service
        now=time.monotonic_ns()
        if now>=next_due:
            skipped=(now-next_due)//PERIOD
            services.append(dict(due_ns=next_due,actual_ns=now,lateness_ms=(now-next_due)/1e6,service_gap_ms=(now-last_service)/1e6,skipped_periods=int(skipped)))
            next_due+=(skipped+1)*PERIOD;last_service=now
    if surface=='main':
        value=execute(payload);service()
    elif surface=='idle':
        target=enqueue+20_000_000
        while time.monotonic_ns()<target:
            service();time.sleep(min(.001,max(0.,(next_due-time.monotonic_ns())/1e9)))
        service();value=None
    else:
        future=executor.submit(execute,payload)
        if surface=='process_duplicate':execute(payload)
        while not future.done():
            service();time.sleep(min(.001,max(0.,(next_due-time.monotonic_ns())/1e9)))
        service();value=future.result(timeout=60)
    collected=time.monotonic_ns()
    exact=value is None or equivalent(value['decision'],baseline)
    assert exact,'SAVED_STATE_B_DECISION_CHANGED'
    return dict(surface=surface,version=version,enqueue_ns=enqueue,collected_ns=collected,elapsed_ms=(collected-enqueue)/1e6,services=services,service_count=len(services),skipped_periods=sum(r['skipped_periods'] for r in services),max_service_gap_ms=max([r['service_gap_ms'] for r in services],default=None),maximum_lateness_ms=max([r['lateness_ms'] for r in services],default=None),decision_exact=exact,worker=None if value is None else {k:v for k,v in value.items() if k!='decision'})

def main():
    guard(1800);attempt_sha=sha(STUDY/'ATTEMPTS.jsonl');started=time.time()
    import study_common as sc
    from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import snapshot_task_call
    from causal_timing_report import quantile
    paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));assert len(paths)==22
    items=[];warm('T0')
    for p in paths:
        raw=pickle.loads(p.read_bytes());planner,args=pickle.loads(raw['payload']);planner.planner.residual_spec={}
        payload=snapshot_task_call(planner,args);baseline=execute(payload)['decision']
        items.append(dict(path=str(p),input_sha256=sha(p),payload_sha256=hashlib.sha256(payload).hexdigest(),payload=payload,baseline=baseline))
    conditions=[('idle','T0'),('main','T0'),('thread','T0'),('process','T0'),('process_duplicate','T0'),('main','C2'),('thread','C2'),('process','C2'),('process_duplicate','C2')]
    contract=dict(conditions=conditions,independent_sessions=4,states_per_session=22,condition_order='Rotated by session; each condition executes in a fresh spawn process so C2 never leaks into T0.',service_period_ms=5,service_policy='Sample once at first service opportunity; retain fixed schedule, count skipped periods, never issue synthetic catchup callbacks.',timer_only=True,physical_feedback_cost_included=False,native_physics_steps_added=0,physics_attempts_added=0,Q_updates=0,max_job_wall_s=1200,unprofiled_timing=True)
    save(EXT/'TIMER_SERVICE_CONTRACT.json',contract)
    rows=[];sessions=[]
    for cold in range(4):
        for surface,version in conditions[cold:]+conditions[:cold]:
            guard(1800);assert time.time()-started<1200
            config=EXT/f'TIMER_CONFIG_{cold}_{surface}_{version}.json'
            save(config,dict(cold=cold,surface=surface,version=version,items=[{k:v for k,v in x.items() if k!='payload'} for x in items]))
            result=EXT/f'TIMER_RESULT_{cold}_{surface}_{version}.json'
            code=subprocess.call([sys.executable,str(Path(__file__)), '--session',str(config),str(result)])
            assert code==0,'SESSION_FAILED'
            data=json.loads(result.read_text());rows+=data['rows'];sessions.append(data['session'])
            save(EXT/'TIMER_SERVICE_PARTIAL.json',dict(rows=rows,sessions=sessions))
            print(json.dumps(dict(session=cold+1,condition=[surface,version],completed_rows=len(rows))),flush=True)
    groups={}
    for surface,version in conditions:
        rs=[r for r in rows if (r['surface'],r['version'])==(surface,version)]
        groups[surface+'/'+version]=dict(n=len(rs),elapsed_ms=quantile([r['elapsed_ms'] for r in rs]),max_service_gap_ms=quantile([r['max_service_gap_ms'] for r in rs if r['max_service_gap_ms'] is not None]),maximum_lateness_ms=quantile([r['maximum_lateness_ms'] for r in rs if r['maximum_lateness_ms'] is not None]),skipped_periods=sum(r['skipped_periods'] for r in rs),service_count=sum(r['service_count'] for r in rs),all_saved_decisions_equivalent=all(r['decision_exact'] for r in rs))
    assert sha(STUDY/'ATTEMPTS.jsonl')==attempt_sha
    register_imports('TIMER_SERVICE')
    out=dict(status='PASS_OFFLINE_TIMER_ONLY',contract=contract,rows=rows,sessions=sessions,groups=groups,wall_seconds=time.time()-started,physics_attempts_added=0,actual_physics_steps_added=0,Q_updates=0,attempt_ledger_unchanged=True,interpretation='Timer service isolation evidence only, at retained already-occurred states. A process condition omits real control, sensors, 4kHz plant integration, receipt catchup and current-model activation. Neither low timer jitter nor native decision equivalence qualifies B or M2, and no third public-B repair is promoted.')
    save(EXT/'TIMER_SERVICE.json',out);print(json.dumps(dict(status=out['status'],groups=groups,wall_seconds=out['wall_seconds'])))

def session(config,result):
    import study_common as sc
    from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import snapshot_task_call
    cfg=json.loads(Path(config).read_text());surface=cfg['surface'];version=cfg['version'];ready=warm(version)
    executor=None;created=time.monotonic_ns()
    if surface in ('process','process_duplicate'):
        executor=cf.ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn'));ready=executor.submit(warm,version).result(timeout=90)
    elif surface=='thread':
        executor=cf.ThreadPoolExecutor(max_workers=1);ready=executor.submit(warm,version).result(timeout=90)
    warm_end=time.monotonic_ns();rows=[]
    try:
        for i,item in enumerate(cfg['items']):
            guard(900);p=Path(item['path']);assert sha(p)==item['input_sha256']
            raw=pickle.loads(p.read_bytes());planner,args=pickle.loads(raw['payload']);planner.planner.residual_spec={};payload=snapshot_task_call(planner,args)
            assert hashlib.sha256(payload).hexdigest()==item['payload_sha256']
            row=one(surface,executor,payload,item['baseline'],version);row.update(cold_session=cfg['cold']+1,state_index=i,snapshot=item['path'],snapshot_sha256=item['input_sha256'],first_after_prewarm=i==0);rows.append(row)
    finally:
        if executor:executor.shutdown(wait=True,cancel_futures=True)
    save(Path(result),dict(session=dict(surface=surface,version=version,cold=cfg['cold']+1,pid=os.getpid(),worker=ready,prewarm_ms=(warm_end-created)/1e6),rows=rows))

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--session':session(*sys.argv[2:])
    else:main()
