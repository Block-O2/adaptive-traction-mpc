"""Execute one finite, source-bound research plan after the initial queue."""
from pathlib import Path
import argparse,fcntl,json,os,re,signal,shutil,sys,time,traceback
import research_common
import stability_lineages
import run_job as supervisor
from research_common import ROOT,NO_TRAIN,RESERVATION,read,atomic,append,sha,now,same_pid,pid_identity,check_resources,decision


def inspect_plan(path):
    path=Path(path).resolve()
    assert path.is_relative_to(ROOT),'PLAN_OUTSIDE_RESEARCH_PACKAGE'
    plan=read(path)
    assert plan['version']=='FINITE_FOLLOWUP_QUEUE_v1'
    assert re.fullmatch(r'[A-Za-z0-9_]+',plan['queue_id'])
    assert plan['phase'] in ['OPTIONAL_RESEARCH','FINAL_VERIFICATION']
    assert set(plan['required_sources'])=={'worker.py','rewards.py','research_common.py'}
    for name,expected in plan['required_sources'].items():
        assert sha(ROOT/'scripts'/name)==expected,'REQUIRED_SOURCE_CHANGED:'+name
    configs=[];counts={'training':0,'evaluation':0};ids=set();reused=[]
    assert plan['jobs'] and len(plan['jobs'])<=100
    for item in plan['jobs']:
        p=Path(item['config']).resolve()
        assert p.is_relative_to(ROOT/'configs') and sha(p)==item['sha256'],'CONFIG_IDENTITY_CHANGED'
        cfg=read(p);job=cfg['job_id']
        assert re.fullmatch(r'[A-Za-z0-9_]+',job) and job not in ids
        ids.add(job);assert cfg['mode'] in counts
        assert isinstance(cfg['episodes'],int) and cfg['episodes']>0
        assert cfg['mode']=='training' or cfg['episodes']==1
        if cfg['branch'].startswith('RETENTION_'):
            mapping=read(ROOT/'STABILITY_LINEAGES.json',{}).get('branch_to_lineage',{})
            assert cfg['branch'] in mapping,'UNREGISTERED_RETENTION_BRANCH'
            if cfg['mode']=='training':
                parent=read(Path(cfg['parent_checkpoint']).with_suffix('.json'))
                assert parent and mapping.get(parent['branch'],parent['branch'])==mapping[cfg['branch']],'RETENTION_PARENT_LINEAGE_MISMATCH'
                assert cfg['start_episode']==parent['continuation_episodes'],'RETENTION_START_EPISODE_MISMATCH'
                assert stability_lineages.signature(cfg)==stability_lineages.signature(parent['research_config']),'RETENTION_METHOD_CHANGED'
        if plan['phase']=='FINAL_VERIFICATION':assert cfg['mode']=='evaluation'
        end=read(ROOT/'jobs'/job/'END.json')
        if end:
            assert end['success'],'FAILED_JOB_REQUIRES_NEW_ID_AND_EXPLICIT_RECOVERY'
            start=read(ROOT/'jobs'/job/'START.json')
            assert start['config_sha256']==item['sha256'],'EXISTING_JOB_CONFIG_CHANGED'
            reused.append(job)
        else:counts[cfg['mode']]+=cfg['episodes'] if cfg['mode']=='training' else 1
        configs.append(p)
    reserve_eval=8 if plan['phase']=='OPTIONAL_RESEARCH' else 0
    reserve_native=reserve_eval*RESERVATION
    value=read(ROOT/'LEDGER.json');outstanding=sum(a['reserved_native_steps'] for a in value['attempts'] if not a['settled'])
    assert value['training_attempts']+counts['training']<=450,'PLANNED_TRAINING_CAP'
    assert value['evaluation_attempts']+counts['evaluation']+reserve_eval<=60,'PLANNED_EVALUATION_CAP_WITH_FINAL_RESERVE'
    assert value['native_steps']+outstanding+sum(counts.values())*RESERVATION+reserve_native<=50000000,'PLANNED_NATIVE_CAP_WITH_FINAL_RESERVE'
    initial=read(ROOT/'CAMPAIGN_PROCESS.json',{})
    initial_done=(ROOT/'FINITE_QUEUE_COMPLETE.json').exists() and (ROOT/'CAMPAIGN_QUEUE_END.json').exists() and not same_pid(initial.get('identity'))
    workers=[]
    for p in (ROOT/'owned').glob('*.json'):
        d=read(p)
        if same_pid(d.get('worker')):workers.append(d['job'])
    queues=[str(p.parent) for p in (ROOT/'followup_queues').glob('*/START.json') if same_pid(read(p).get('identity'))]
    in_window=time.time()<(NO_TRAIN if counts['training'] else research_common.HARD_STOP-300)
    closing=(ROOT/'STOP_REQUESTED').exists() or (ROOT/'END.json').exists()
    resource=research_common.resources()
    resources_ready=resource['available_bytes']>=6*1024**3 and resource['disk_free_bytes']>=10*1024**3
    ready=initial_done and not workers and not queues and not outstanding and in_window and not closing and resources_ready
    return plan,configs,dict(plan_sha256=sha(path),new_physical_attempts=counts,reused_jobs=reused,
        final_evaluation_reserve=reserve_eval,final_native_reserve=reserve_native,
        maximum_new_native_steps=sum(counts.values())*RESERVATION,
        initial_queue_complete=initial_done,live_workers=workers,live_followup_queues=queues,
        open_native_reservations=outstanding,in_time_window=in_window,closing_requested=closing,
        resources=resource,resources_ready=resources_ready,ready_to_start=ready)


def run_locked(path):
    plan,configs,inspection=inspect_plan(path)
    assert inspection['ready_to_start'],'PREDECESSOR_OR_OTHER_OWNED_WORK_STILL_ACTIVE'
    check_resources()
    if inspection['new_physical_attempts']['training']:
        assert __import__('time').time()<NO_TRAIN,'NO_NEW_TRAINING_WINDOW'
    out=ROOT/'followup_queues'/plan['queue_id'];out.mkdir(parents=True,exist_ok=False)
    source=out/'supervisor_source';source.mkdir()
    sources=[Path(__file__),Path(supervisor.__file__),Path(research_common.__file__),Path(stability_lineages.__file__)]
    for p in sources:shutil.copyfile(p,source/p.name)
    atomic(out/'PLAN.json',plan)
    atomic(out/'START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),
        plan_source=str(Path(path).resolve()),inspection=inspection,purpose=plan['purpose'],
        source_files={p.name:sha(p) for p in sources},formal_campaign=False))
    def stopping(signum,frame):raise RuntimeError('FOLLOWUP_OWNED_CLOSE_REQUEST')
    signal.signal(signal.SIGTERM,stopping)
    state=read(ROOT/'RESEARCH_STATE.json');atomic(ROOT/'RESEARCH_STATE.json',dict(state,status='RUNNING',
        phase=plan['queue_id'],time_utc=now(),followup_queue=str(out)))
    decision('FOLLOWUP_QUEUE_START',dict(queue=str(out),purpose=plan['purpose'],inspection=inspection),
             'Execute only the sealed finite config list, then return for scientific review')
    completed=[];error=None;status='RUNNING'
    try:
        for cfg_path in configs:
            check_resources()
            for name,expected in plan['required_sources'].items():
                assert sha(ROOT/'scripts'/name)==expected,'REQUIRED_SOURCE_CHANGED_BEFORE_JOB:'+name
            item=next(x for x in plan['jobs'] if Path(x['config']).resolve()==cfg_path)
            assert sha(cfg_path)==item['sha256'],'CONFIG_CHANGED_BEFORE_JOB'
            cfg=read(cfg_path)
            atomic(out/'LIVE.json',dict(time_utc=now(),job=cfg['job_id'],mode=cfg['mode'],completed_jobs=completed))
            result=supervisor.run_job(cfg_path)
            append(out/'JOB_RESULTS.jsonl',dict(time_utc=now(),job=cfg['job_id'],result=result))
            if not result['success']:raise RuntimeError('FOLLOWUP_JOB_FAILED:'+cfg['job_id'])
            completed.append(cfg['job_id'])
        status='COMPLETE'
    except BaseException as exc:
        error=dict(error=repr(exc),traceback=traceback.format_exc())
        status='OWNED_CLOSE_REQUEST' if (ROOT/'STOP_REQUESTED').exists() or (ROOT/'END.json').exists() else 'NEEDS_AGENT_DIAGNOSIS'
    finally:
        atomic(out/'END.json',dict(time_utc=now(),status=status,completed=status=='COMPLETE',
            completed_jobs=completed,planned_jobs=len(configs),error=error,formal_campaign=False))
        if not (ROOT/'STOP_REQUESTED').exists() and not (ROOT/'END.json').exists():
            state=read(ROOT/'RESEARCH_STATE.json')
            atomic(ROOT/'RESEARCH_STATE.json',dict(state,
                status='AWAITING_AGENT_RESEARCH_REVIEW' if status=='COMPLETE' else 'NEEDS_AGENT_DIAGNOSIS',
                phase=plan['queue_id'],time_utc=now(),next='Read followup queue END and actual outcomes; no automatic new Reward or final Campaign'))
            decision('FOLLOWUP_QUEUE_END',dict(queue=str(out),status=status,error=error,completed_jobs=completed),
                     'Agent reviews actual evidence and remaining budget; ordinary task failures are not global STOP')
    return status=='COMPLETE'


def execute(path):
    with (ROOT/'.followup_queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run_locked(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('plan');parser.add_argument('--validate-only',action='store_true');args=parser.parse_args()
    if args.validate_only:
        _,_,inspection=inspect_plan(args.plan);print(json.dumps(inspection));raise SystemExit(0)
    raise SystemExit(0 if execute(args.plan) else 1)
