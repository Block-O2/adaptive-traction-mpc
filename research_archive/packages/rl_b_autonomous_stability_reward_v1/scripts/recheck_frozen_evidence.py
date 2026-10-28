"""Independent-process rerun of original saved-physics auditors; no simulation."""
from pathlib import Path
import argparse,json,os,signal,sys,time,shutil
from research_common import ROOT,RUNTIME,HARD_STOP,read,atomic,sha,now,same_pid,pid_identity
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
sys.path.insert(0,str(RUNTIME))
from cloud_case_audit import audit as execution_audit
from force_audit import audit as dose_audit
from native_boundary_motion_audit import audit as motion_audit

def timeout(signum,frame):raise TimeoutError('SAVED_EVIDENCE_RECHECK_DEADLINE')

def run(jobs,final):
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    frozen=[x for x in rows if x['mode']=='evaluation']
    if jobs:
        assert len(set(jobs))==len(jobs)
        assert set(jobs)<={x['job_id'] for x in frozen},'UNKNOWN_OR_UNCLOSED_EVALUATION'
        frozen=[x for x in frozen if x['job_id'] in jobs]
    ledger=read(ROOT/'LEDGER.json');ledger_sha=sha(ROOT/'LEDGER.json')
    if final:
        assert not jobs and (ROOT/'STOP_REQUESTED').exists(),'FINAL_ADMISSION_MUST_BE_STOPPED'
        assert not any(not a['settled'] for a in ledger['attempts']),'OPEN_PHYSICAL_RESERVATION'
        assert len(frozen)==ledger['evaluation_attempts'],'FROZEN_ATTEMPT_COVERAGE_MISSING'
        assert not any(same_pid(read(p).get('worker')) for p in (ROOT/'owned').glob('*.json')),'PHYSICAL_WORKER_STILL_LIVE'
    contract=read(RUNTIME/'FROZEN_CONTRACT_MANIFEST.json')['files']
    bad=[name for name,expected in contract.items() if sha(RUNTIME/name)!=expected]
    assert not bad,'FROZEN_SCIENTIFIC_SOURCE_CHANGED:'+str(bad)
    out=ROOT/'audit/frozen_rechecks'/f'{int(time.time())}_{os.getpid()}';out.mkdir(parents=True)
    atomic(out/'START.json',dict(time_utc=now(),pid=os.getpid(),identity=pid_identity(os.getpid()),jobs=[x['job_id'] for x in frozen],final=final,
        original_runtime_files_verified=len(contract),source_sha256=sha(Path(__file__)),new_physics=0,new_Adam=0))
    signal.signal(signal.SIGALRM,timeout);cases=[]
    for row in frozen:
        if time.time()>=HARD_STOP-35:break
        runpath=Path(row['run']);ep=runpath/'env/episode_0001';case_dir=out/row['job_id'];case_dir.mkdir()
        source_paths=[ep/'CLOUD_CASE_AUDIT.json',ep/'FORCE_INDEPENDENT_AUDIT.json',ep/'ACTUAL_HUMAN_MOTION_AUDIT.json',runpath/'NATIVE_BOUNDARY_MOTION_AUDIT.json']
        prior=[]
        for p in source_paths:
            if p.exists():
                dest=case_dir/'prior_derived'/p.relative_to(runpath);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
                prior.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),snapshot=str(dest.relative_to(ROOT))))
        started=time.time();checks={};error=None
        try:
            signal.setitimer(signal.ITIMER_REAL,min(150,max(.1,HARD_STOP-time.time()-25)))
            outer=read(ROOT/'jobs'/row['job_id']/'END.json');assert outer and outer['success'] and outer['child_joined'],'OUTER_WORKER_NOT_CLOSED'
            execution=execution_audit(runpath);dose=dose_audit(ep);motion=motion_audit(runpath)
            parent=read(Path(row['parent']).with_suffix('.json'));resume=read(runpath.parent/'RESUME_AUDIT.json')
            identity=read(ROOT/'jobs'/row['job_id']/'SOURCE_IDENTITY.json');worker=Path(identity['path'])/'worker.py';body=worker.read_text()
            checks=dict(original_execution_checks=execution['pass'] and all(execution['checks'].values()),
                original_reward_terminal_checks=execution['reward']['pass'] and all(execution['reward']['checks'].values()),
                original_dose_independent=dose['pass'],original_native_motion_safety=motion['pass'] and all(motion['checks'].values()),
                original_status_matches=execution['status']==row['status'],
                original_completion_matches=execution['reward']['success']==row['success']==row['complete_evidence'],
                full_partial_scope=(row['integral_scope']=='COMPLETE_TASK')==row['success'],
                duration_native_grid=abs(row['task_native_steps']*.00025-row['task_s'])<1e-7,
                recomputed_duration=abs(dose['task_duration_s']-row['task_s'])<1e-7,
                recomputed_JF=abs(dose['independent_J_F_N_s']-row['JF'])<1e-7,
                recomputed_JM=abs(dose['independent_J_M_Nm_s']-row['JM'])<1e-7,
                all_actual_TASK_native_states=motion['TASK_native_steps']==row['task_native_steps'],
                frozen_policy_hashes=row['policy_before']==row['policy_after']==parent['policy_sha256'],
                no_real_Adam_or_update=row['gradient_updates']==0 and row['update'] is None,
                full_parent_restore=resume['pass_'] and all(resume['checks'].values()),
                executed_worker_optimizer_hash_assert_present='FROZEN_POLICY_MUTATED' in body and "before['optimizer']==after_frozen['optimizer']" in body,
                worker_source_identity=sha(worker)==identity['files']['worker.py'])
            metric=read(runpath/'COMMON_MOTION_METRICS.json')
            checks['common_native_motion_present_and_consistent']=bool(metric) and metric['success']==row['success'] and abs(metric['JF']-dose['independent_J_F_N_s'])<1e-7 and abs(metric['JM']-dose['independent_J_M_Nm_s'])<1e-7
            details=dict(execution=execution,dose=dose,native_motion=motion)
            atomic(case_dir/'RECOMPUTED.json',details)
        except BaseException as exc:error=repr(exc)
        finally:signal.setitimer(signal.ITIMER_REAL,0)
        case=dict(job=row['job_id'],run=row['run'],success=row['success'],integral_scope=row['integral_scope'],
            checks=checks,pass_=bool(checks) and all(checks.values()) and error is None,error=error,wall_s=time.time()-started,prior_derived=prior,
            recomputed=str((case_dir/'RECOMPUTED.json').relative_to(ROOT)),
            frozen_optimizer_evidence='Original verified worker enforced before/after optimizer-hash equality and froze learning/backward; the post-optimizer hash is not separately serialized, so no such file is claimed.')
        cases.append(case);atomic(case_dir/'RESULT.json',case)
        atomic(out/'LIVE.json',dict(time_utc=now(),completed=len(cases),expected=len(frozen),latest_job=row['job_id'],latest_pass=case['pass_']))
        print(json.dumps(dict(job=row['job_id'],pass_=case['pass_'],wall_s=case['wall_s'],error=error)),flush=True)
    complete=len(cases)==len(frozen)
    unchanged=sha(ROOT/'LEDGER.json')==ledger_sha
    result=dict(time_utc=now(),category='INDEPENDENT_PROCESS_ORIGINAL_SAVED_NATIVE_RECOMPUTATION',final=final,
        expected_frozen=len(frozen),rechecked=len(cases),coverage_complete=complete,all_pass=complete and all(x['pass_'] for x in cases),cases=cases,
        ledger_unchanged_during_recheck=unchanged,background_physics_allowed=not final,
        original_runtime_files_verified=len(contract),runtime_source_mismatches=bad,source_sha256=sha(Path(__file__)),
        new_physics=0,new_Adam=0,analysis_directory=str(out.relative_to(ROOT)),
        scope='Recompute original terminal/reward/native ownership/receipt/force/moment/true Human safety on preserved evidence. No new environment, training, changed thresholds, matched qualification or independent physical initial states. Prior derived audits are snapshotted before original auditors rewrite them.')
    if final:result['all_pass']=result['all_pass'] and unchanged
    atomic(out/'END.json',result)
    if final:atomic(ROOT/'audit/FINAL_FROZEN_PHYSICS_RECHECK.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jobs',nargs='+');p.add_argument('--all',action='store_true');p.add_argument('--final',action='store_true');a=p.parse_args()
    assert a.all or a.jobs,'EXPLICIT_RECHECK_SCOPE_REQUIRED'
    assert not (a.all and a.jobs)
    result=run(a.jobs,a.final)
    print(json.dumps({k:result[k] for k in ['all_pass','expected_frozen','rechecked','analysis_directory','new_physics','new_Adam']}))
    raise SystemExit(0 if result['all_pass'] else 1)
