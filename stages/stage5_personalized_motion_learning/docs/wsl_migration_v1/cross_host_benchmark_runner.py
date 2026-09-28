"""One-run-at-a-time frozen WSL benchmark launcher; no controller changes."""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, json, os, platform, statistics, subprocess, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
DOC=STAGE/'docs/wsl_migration_v1'

def read(p: Path): return json.loads(p.read_text())
def sha(p: Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def source_fingerprint():
    freeze=read(STAGE/'docs/safe_fallback_execution_v1/FREEZE_v1.json')
    current={p:sha(ROOT/p) for p in freeze['source_map']}
    if current!=freeze['source_map']: raise RuntimeError('PRODUCTION_SOURCE_DRIFT')
    got=hashlib.sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if got!=freeze['source_fingerprint']: raise RuntimeError('SOURCE_FINGERPRINT_DRIFT')
    return got

def verify(expected_head: str):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if head!=expected_head: raise RuntimeError(f'HEAD_MISMATCH {head} != {expected_head}')
    if subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=no'],cwd=ROOT,text=True).strip():
        raise RuntimeError('TRACKED_WORKTREE_DIRTY')
    spec=read(DOC/'CROSS_HOST_BENCHMARK_V1.json')
    if source_fingerprint()!=spec['source']['source_fingerprint']: raise RuntimeError('SOURCE_DRIFT')
    for row in spec['run_order']:
        if sha(ROOT/row['case'])!=row['case_sha256']: raise RuntimeError('CASE_HASH_DRIFT '+row['run_id'])
    return spec,head

def stats(values):
    if not values: return {'count':0,'mean':None,'median':None,'p95':None,'max':None}
    v=sorted(float(x) for x in values); n=len(v); i=.95*(n-1); lo=int(i); hi=min(lo+1,n-1)
    return {'count':n,'mean':statistics.mean(v),'median':statistics.median(v),'p95':v[lo]+(v[hi]-v[lo])*(i-lo),'max':v[-1]}

def analyze(out: Path, row: dict):
    launch=read(out/'HIGH_ROM_CASE_RESULT.json')
    report={'run_status':launch.get('status'),'abort_reason':launch.get('abort_reason'),'elapsed_host_s':launch.get('elapsed_host_s'),'scorer_v2':'NOT_EVALUABLE','unavailable_metrics':[]}
    art=out/'runtime_artifacts.json'; summ=out/'summary.json'
    if art.exists() and summ.exists():
        a=read(art); s=read(summ); req=s.get('timing',{}).get('requests',[])
        compute=[x['compute_ms'] for x in req if x.get('compute_ms') is not None]
        activated=[x for x in req if x.get('outcome')=='ACTIVATED']
        ages=[x['activation_age_ms'] for x in activated if x.get('activation_age_ms') is not None]
        worker=[x['worker_to_main_scheduling_ms'] for x in req if x.get('worker_to_main_scheduling_ms') is not None]
        report.update(planning_compute_ms=stats(compute),activation_ms=stats(ages),activation_over_55_ms=sum(x>55 for x in ages),planning_over_100_ms=sum(x>=100 for x in compute),source_age_over_100_ms=sum(float(x['disposition_age_ms'])>=100 for x in req if x.get('disposition_age_ms') is not None),worker_to_main_ms=stats(worker),stale_rejection_count=sum(x.get('outcome')!='ACTIVATED' and ('STALE' in str(x.get('reason','')).upper() or 'EXPIRED' in str(x.get('outcome','')).upper()) for x in req),stale_activation_count=sum(x>=100 for x in ages),safe_fallback_count=sum(x.get('event')=='FALLBACK_COMMITTED' for x in a.get('safe_fallback_events',[])))
        wall=a.get('wall_physics',{}); report['control_cycle_misses']=wall.get('control_cycle_misses')
        receipts=wall.get('command_receipts',[])
        stamp=[x['apply_ns'] for x in receipts if x.get('applied') and x.get('apply_ns') is not None]
        report['max_actual_command_gap_ms']=max((b-a)/1e6 for a,b in zip(stamp,stamp[1:])) if len(stamp)>1 else None
        if report['max_actual_command_gap_ms'] is None: report['unavailable_metrics'].append('max_actual_command_gap_ms')
        task=s.get('task',{});report.update(peak_force_n=task.get('peak_force_n'),peak_moment_nm=task.get('peak_moment_nm'),minimum_session_clearance_m=task.get('minimum_session_clearance_m_deployable'),phase_transitions=task.get('phase_transitions'))
        if launch.get('status')=='COMPLETE':
            sys.path[:0]=[str(STAGE/'scripts/high_rom_v1'),str(STAGE/'docs/waypoint_smoothness_v1')]
            from runtime_benchmark import case_timing
            from score_return_endpoint_v2 import score_v2
            from analyze_repair import inspect
            c=read(ROOT/row['case']);desc={'case_key':c['case_key'],'physical_variant':c.get('physical_variant','original_low_rom' if row['plant']=='low_rom' else 'registered_interpolated'),'candidate':c.get('coordination_candidate','original_low_rom'),'path':row['case'],'sha256':row['case_sha256']}
            scored=score_v2(out,desc,read(STAGE/'docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'],goal_deg=c['task']['goal_deg'],start_deg=c['task']['start_deg'])
            timing=case_timing({'id':row['case_id'],'plant':row['plant'],'case':row['case'].removeprefix('stages/stage5_personalized_motion_learning/')},out)
            smooth,_=inspect(out)
            report.update(scorer_v2={'pass':scored['pass'],'failed_conditions':[k for k,v in scored['conditions'].items() if not v]},arrival=scored.get('arrival'),dwell_s=scored.get('true_goal_continuous_dwell_s'),true_return=scored.get('true_return'),control_miss_ratio=timing['control_cycle_miss_ratio'],longest_consecutive_miss=timing['longest_consecutive_control_misses'],reference_near_stop_s=smooth.get('non_task_reference_near_stop_longest_s'))
    else: report['unavailable_metrics'].append('runtime_artifacts_or_summary_missing')
    return report

def main():
    ap=argparse.ArgumentParser(); group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--list',action='store_true');group.add_argument('--run-one')
    ap.add_argument('--expected-head',required=True);ap.add_argument('--output-root',type=Path,default=STAGE/'results/cross_host_benchmark_v1')
    args=ap.parse_args();spec,head=verify(args.expected_head)
    if args.list:
        print(json.dumps({'head':head,'fingerprint':spec['source']['source_fingerprint'],'runs':[x['run_id'] for x in spec['run_order']]}));return
    row=next((x for x in spec['run_order'] if x['run_id']==args.run_one),None)
    if row is None: raise ValueError('UNREGISTERED_RUN_ID')
    root=args.output_root if args.output_root.is_absolute() else ROOT/args.output_root
    out=root/row['run_id']
    if out.exists(): raise FileExistsError(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(STAGE/'scripts/high_rom_v1/run_dev_case.py'),'--plant-mode',row['plant'],'--case',str(ROOT/row['case']),'--output',str(out),'--host-monitor-limit-s','300']
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(Path(tempfile.gettempdir())/'fallback-mpl'),OPENBLAS_NUM_THREADS='1')
    start=time.time();result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    out.mkdir(parents=True,exist_ok=True)
    (out/'BENCHMARK_CONSOLE.txt').write_text(result.stdout)
    record={'schema':'cross_host_benchmark_run_v1','run_id':row['run_id'],'case_id':row['case_id'],'repetition':row['repetition'],'head':head,'fingerprint':spec['source']['source_fingerprint'],'case_sha256':row['case_sha256'],'command':cmd,'returncode':result.returncode,'started_epoch_s':start,'finished_epoch_s':time.time(),'host':{'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'cpu_count':os.cpu_count(),'python':sys.version,'mujoco':importlib.metadata.version('mujoco'),'load_average':os.getloadavg() if hasattr(os,'getloadavg') else None,'linux_proc_version':Path('/proc/version').read_text().strip() if Path('/proc/version').exists() else None,'ram_bytes':os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES') if hasattr(os,'sysconf') else None},'scientific_variables_changed':[]}
    try:record['analysis']=analyze(out,row)
    except Exception as exc:record['analysis_error']=type(exc).__name__+': '+str(exc)
    (out/'BENCHMARK_RESULT.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'run_id':row['run_id'],'returncode':result.returncode,'status':record.get('analysis',{}).get('run_status'),'analysis_error':record.get('analysis_error')}))
    if result.returncode or 'analysis_error' in record: raise SystemExit(2)

if __name__=='__main__':main()
