import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/hankli/Desktop/coding/adaptive-traction-mpc-learning')
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
OLD = STAGE / 'docs/safe_fallback_execution_v1'
BASE = STAGE / 'docs/simulation_research_baseline_v1'
DOC = STAGE / 'docs/safe_fallback_verification_v1'
sys.path[:0] = [str(STAGE/'scripts/high_rom_v1'), str(STAGE/'docs/waypoint_smoothness_v1')]
from score_return_endpoint_v2 import score_v2
from runtime_benchmark import case_timing
from analyze_repair import inspect

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def source():
    f=read(OLD/'FREEZE_v1.json')
    current={p:sha(ROOT/p) for p in f['source_map']}
    if current != f['source_map']: raise RuntimeError('PRODUCTION_FINGERPRINT_DRIFT')
    fingerprint=hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if fingerprint != f['source_fingerprint']: raise RuntimeError('SOURCE_FINGERPRINT_DRIFT')
    return fingerprint

def prepare(stage):
    if stage=='representative':
        old=read(BASE/'PREREGISTRATION.json');rows=old['representative']
        assert len(rows)==8
        payload=dict(schema='safe_fallback_representative_freeze_v1',evidence='development_representative',
            created_utc=datetime.now(timezone.utc).isoformat(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_fingerprint=source(),
            source_map_sha256=sha(OLD/'FREEZE_v1.json'),old_case_manifest_sha256=sha(BASE/'PREREGISTRATION.json'),
            rows=rows,run_order=[r['id'] for r in rows],budget=8,exclusions='none; every attempted run retained',
            scorer='scorer-v2-return-physical-commit',
            pass_rule='COMPLETE; all scorer-v2 task/safety conditions; arrival/dwell/RETURN; C2 <=1e-6; zero >=100ms stale activation; frozen representative near-stop caps; committed fallback certified, before bridge endpoint, irrevocable, stop-hold-fresh replan-resume-COMPLETE',
            smoothness_caps_s={'low_ordinary':0.15,'low_near_upper':0.19,'high_rom':0.175},
            runtime_rule='characterization only; historical 55ms activation FAIL retained; no hardware qualification',
            scientific_variables_changed=[],scorer_changed=False,production_changed=False)
        target=DOC/'REPRESENTATIVE_PREREGISTRATION.json'
    else:
        old=read(BASE/'PREREGISTRATION.json');rows=old['development49']
        assert len(rows)==49
        payload=dict(schema='safe_fallback_development49_freeze_v1',evidence='development',
            created_utc=datetime.now(timezone.utc).isoformat(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_fingerprint=source(),
            source_map_sha256=sha(OLD/'FREEZE_v1.json'),old_case_manifest_sha256=sha(BASE/'PREREGISTRATION.json'),
            rows=rows,run_order=[r['id'] for r in rows],budget=49,exclusions='none; every attempted run retained',
            scorer='scorer-v2-return-physical-commit',
            pass_rule='COMPLETE; all scorer-v2 task/safety conditions; arrival/dwell/RETURN; C2 <=1e-6; zero >=100ms stale activation; reference near-stop <0.350s regression trigger; committed fallback certified, before bridge endpoint, irrevocable, stop-hold-fresh replan-resume-COMPLETE',
            runtime_rule='characterization only; historical 55ms activation FAIL retained; no hardware qualification',
            scientific_variables_changed=[],scorer_changed=False,production_changed=False)
        target=DOC/'DEVELOPMENT49_PREREGISTRATION.json'
    if target.exists(): raise FileExistsError(target)
    for r in rows:
        if sha(ROOT/r['case'])!=r['case_sha256']: raise RuntimeError('CASE_HASH_DRIFT '+r['id'])
    save(target,payload)
    print(json.dumps({'prepared':stage,'count':len(rows),'fingerprint':payload['source_fingerprint']}),flush=True)

def prereg(stage): return read(DOC/('REPRESENTATIVE_PREREGISTRATION.json' if stage=='representative' else 'DEVELOPMENT49_PREREGISTRATION.json'))
def row_for(stage,id): return next(r for r in prereg(stage)['rows'] if r['id']==id)
def output(stage,id): return STAGE/'results/safe_fallback_verification_v1'/stage/id

def check_fallback(events):
    admitted=[x for x in events if x['event']=='ESCAPE_ADMITTED']
    commits=[i for i,x in enumerate(events) if x['event']=='FALLBACK_COMMITTED']
    details=[]
    for i in commits:
        x=events[i];following=events[i+1:]
        def after(name): return next((e for e in following if e['event']==name),None)
        stop=after('FALLBACK_STOPPED');hold=after('FALLBACK_HOLD');fresh=after('FRESH_REPLAN_REQUESTED');resume=after('RESUME_ACTIVATED')
        cert=next((a['certificate'] for a in reversed(admitted) if a['host_ns']<=x['host_ns'] and a['phase']==x['phase']),None)
        valid=bool(cert and cert['bridge_mechanics']['feasible'] and cert['stop_mechanics']['feasible'] and cert['shifted_rom_valid'] and not cert['truth_consumed']
            and x['commit_progress_s']<cert['normal_bridge_duration_s'] and stop and hold and fresh and resume
            and x['host_ns']<=stop['host_ns']<=hold['host_ns']<=fresh['host_ns']<=resume['host_ns']
            and not any(e['event']=='RESUME_ACTIVATED' for e in events[i+1:events.index(stop)]))
        details.append(dict(valid=valid,reason='certified_branch' if cert else 'missing_certificate',
            phase=x['phase'],commit_physics_s=x['physics_s'],commit_progress_s=x['commit_progress_s'],
            endpoint_s=cert['normal_bridge_duration_s'] if cert else None,
            braking_duration_s=stop['physics_s']-x['physics_s'] if stop else None,
            hold_duration_s=resume['physics_s']-hold['physics_s'] if hold and resume else None,
            fresh_replan_latency_ms=(resume['host_ns']-fresh['host_ns'])/1e6 if fresh and resume else None,
            old_primary_dropped=sum(e['event']=='OLD_PRIMARY_DROPPED' for e in following[:following.index(resume)] if resume) if resume else None))
    return all(d['valid'] for d in details),details

def run_case(stage,id):
    p=prereg(stage);assert source()==p['source_fingerprint'];row=row_for(stage,id)
    if sha(ROOT/row['case'])!=row['case_sha256']: raise RuntimeError('CASE_HASH_DRIFT')
    out=output(stage,id)
    if out.exists(): raise FileExistsError(out)
    cmd=[sys.executable,str(STAGE/'scripts/high_rom_v1/run_dev_case.py'),'--plant-mode',row['plant'],'--case',str(ROOT/row['case']),'--output',str(out),'--host-monitor-limit-s','300']
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR='/private/tmp/fallback-mpl',OPENBLAS_NUM_THREADS='1')
    result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (DOC/(stage+'_'+id+'_CONSOLE.txt')).write_text(result.stdout)
    save(DOC/(stage+'_'+id+'_COMMAND.json'),dict(command=cmd,returncode=result.returncode,source_fingerprint=p['source_fingerprint'],head=p['head'],timestamp_utc=datetime.now(timezone.utc).isoformat()))
    print(result.stdout.strip(),flush=True)
    print(json.dumps({'executed':id,'returncode':result.returncode}),flush=True)
    score_case(stage,id)

def score_case(stage,id):
    p=prereg(stage);assert source()==p['source_fingerprint'];row=row_for(stage,id);out=output(stage,id)
    dest=DOC/(stage+'_'+id+'_RESULT.json')
    if dest.exists(): raise FileExistsError(dest)
    launch=read(out/'HIGH_ROM_CASE_RESULT.json')
    r=dict(id=id,stage=stage,plant=row['plant'],case=row['case'],case_sha256=row['case_sha256'],source_fingerprint=p['source_fingerprint'],
        head=p['head'],output=str(out),run_status=launch['status'],abort_reason=launch.get('abort_reason'),elapsed_host_s=launch['elapsed_host_s'],pass_all=False)
    try:
        if launch['status']=='COMPLETE':
            case=read(ROOT/row['case']);descriptor=dict(case_key=case['case_key'],physical_variant=case.get('physical_variant','original_low_rom' if row['plant']=='low_rom' else 'registered_interpolated'),candidate=case.get('coordination_candidate','original_low_rom'),path=row['case'],sha256=row['case_sha256'])
            scored=score_v2(out,descriptor,read(STAGE/'docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'],goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
            smooth,_=inspect(out)
            timing=case_timing(dict(id=id,plant=row['plant'],case=row['case'].removeprefix('stages/stage5_personalized_motion_learning/')),out)
            artifacts=read(out/'runtime_artifacts.json');events=artifacts.get('safe_fallback_events',[])
            stale=sum(x.get('activation_ns') is not None and x['activation_ns']-x['sensor_capture_ns']>=100_000_000 for x in artifacts.get('requests',[]))
            fallback_valid,fallback_details=check_fallback(events)
            c2=all(abs(smooth[k])<=1e-6 for k in ('exact_switch_max_q_jump_deg','exact_switch_max_dq_jump_deg_s','exact_switch_max_ddq_jump_deg_s2'))
            near=smooth['non_task_reference_near_stop_longest_s']
            cap=(0.15 if id=='low_ordinary' else 0.19 if id=='low_near_upper' else 0.175) if stage=='representative' else 0.35
            smooth_pass=near<=cap+1e-9 if stage=='representative' else near<cap
            r.update(scorer_version=scored['scorer_version'],scorer_pass=scored['pass'],failed_conditions=[k for k,v in scored['conditions'].items() if not v],
                dwell_s=scored['true_goal_continuous_dwell_s'],true_return=scored['true_return'],force_peak_n=scored['peak_force_n'],moment_peak_nm=scored['peak_moment_nm'],
                clearance_min_m=scored['minimum_session_shank_clearance_m'],near_stop_s=near,smoothness_cap_s=cap,smoothness_pass=smooth_pass,
                c2_pass=c2,c2_jumps={k:smooth[k] for k in ('exact_switch_max_q_jump_deg','exact_switch_max_dq_jump_deg_s','exact_switch_max_ddq_jump_deg_s2')},
                stale_activated=stale,fallback_count=len(fallback_details),fallback_valid=fallback_valid,fallback_details=fallback_details,
                planning_compute_ms=timing['planning_compute_ms'],activation_ms=timing['sample_to_activation_ms'],control_miss_ratio=timing['control_cycle_miss_ratio'],
                longest_consecutive_control_misses=timing['longest_consecutive_control_misses'],request_outcomes=timing['request_outcomes'])
            r['pass_all']=bool(scored['pass'] and smooth_pass and c2 and stale==0 and timing['expired_activated']==0 and fallback_valid)
            r['classification']='PASS' if r['pass_all'] else ('STALE_PLAN_FAILURE' if stale else 'FALLBACK_FAILURE' if not fallback_valid else 'SCORER/EVIDENCE_FAILURE' if not scored['pass'] else 'SMOOTHNESS_REGRESSION')
        else:r['classification']='TASK_FAILURE' if launch['status']!='EXCEPTION' else 'SETUP_FAILURE_OR_RUNTIME_EXCEPTION'
    except Exception as e:
        r['classification']='SCORER/EVIDENCE_FAILURE';r['scoring_exception']=type(e).__name__+': '+str(e)
    save(dest,r)
    manifest=[dict(path=str(q.relative_to(ROOT)),bytes=q.stat().st_size,sha256=sha(q)) for q in sorted(out.rglob('*')) if q.is_file()]
    save(DOC/(stage+'_'+id+'_RAW_MANIFEST.json'),manifest)
    print(json.dumps({k:r.get(k) for k in ('id','run_status','pass_all','classification','fallback_count','stale_activated','near_stop_s')}),flush=True)
    if not r['pass_all']: raise SystemExit(2)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('command',choices=('prepare','run','score'));a.add_argument('--stage',choices=('representative','development49'),required=True);a.add_argument('--id');v=a.parse_args()
    if v.command=='prepare':prepare(v.stage)
    elif v.command=='run':run_case(v.stage,v.id)
    else:score_case(v.stage,v.id)
