import sys,json,hashlib,argparse,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'stages/stage5_personalized_motion_learning';DOC=Path(__file__).resolve().parent
sys.path[:0]=[str(STAGE/'scripts/high_rom_v1'),str(STAGE/'docs/waypoint_smoothness_v1')]
from score_return_endpoint_v2 import score_v2
from runtime_benchmark import case_timing
from analyze_repair import inspect

def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mapping():
    old=read(DOC/'STARTUP.json')['source_map'];old={p:sha(ROOT/p) for p in old}
    rel='stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/safe_fallback.py';old[rel]=sha(ROOT/rel)
    return old
def fingerprint(m):return hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def freeze(version):
    m=mapping();old=read(STAGE/'docs/simulation_research_baseline_v1/PREREGISTRATION.json')
    original=next(r for r in old['development49'] if r['id']=='high_rom_function_fresh_03_v1')
    rows=[dict(original,run_id='original_natural',delay_ms=-1),dict(original,run_id='delay_0',delay_ms=0),dict(original,run_id='delay_100',delay_ms=100),dict(original,run_id='delay_200',delay_ms=200)]
    for id in ('low_ordinary','high_120_sync','high_120_hip','high_120_start_8_13'):
        r=next(r for r in old['representative'] if r['id']==id);rows.append(dict(r,run_id='targeted_'+id,delay_ms=200 if id=='high_120_hip' else -1))
    for r in rows:assert sha(ROOT/r['case'])==r['case_sha256']
    f={'version':version,'created_utc':datetime.now(timezone.utc).isoformat(),'source_fingerprint':fingerprint(m),'source_map':m,'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'rows':rows,
       'hypothesis':'Prevalidated stop removes dependence on future result readiness while preserving baseline task/safety and strict stale rejection.',
       'evidence_category':'development targeted; no held-out claims','exclusions':'none; retain every attempted run','dynamic_budget':8,
       'delay_rule':'third RETURN prefetch visible at worker compute_finish + registered delay; other results unmodified',
       'pass_rule':'scorer-v2 COMPLETE/safety/arrival/dwell/RETURN; C2 <=1e-6 deg-based; stale activation=0; positive-delay targeted request must commit fallback then stop/hold/fresh resume and complete',
       'normal_smoothness':'same baseline cap (0.15 low ordinary; 0.175 high representative); original failure case <0.35 s. Intended fallback stops separately recorded.',
       'unchanged':'scorer, task, physical model, costs/search, safety thresholds, ROM, durations and source-age origin',
       'optional_8':'Only if targeted passes and original quota/time gates permit; not dispatched by this script',
       'harness_sha256':sha(DOC/'run_case.py')}
    dest=DOC/('FREEZE_'+version+'.json');assert not dest.exists();save(dest,f);print(f['source_fingerprint'])
def score(version,run_id):
    f=read(DOC/('FREEZE_'+version+'.json'));assert mapping()==f['source_map'];row=next(r for r in f['rows'] if r['run_id']==run_id)
    out=STAGE/'results/safe_fallback_execution_v1'/version/run_id; launch=read(out/'HIGH_ROM_CASE_RESULT.json')
    r=dict(row,version=version,output=str(out),source_fingerprint=f['source_fingerprint'],run_status=launch['status'],abort_reason=launch.get('abort_reason'),elapsed_host_s=launch['elapsed_host_s'])
    artifacts=read(out/'runtime_artifacts.json') if (out/'runtime_artifacts.json').exists() else {}
    events=artifacts.get('safe_fallback_events',[]);r['fallback_events']=events
    r['stale_activated']=sum(x.get('activation_ns') is not None and (x['activation_ns']-x['sensor_capture_ns'])>=100_000_000 for x in artifacts.get('requests',[]))
    r['pass_all']=False
    if launch['status']=='COMPLETE':
        case=read(ROOT/row['case']);descriptor={'case_key':case['case_key'],'physical_variant':case.get('physical_variant','original_low_rom' if row['plant']=='low_rom' else 'registered_interpolated'),'candidate':case.get('coordination_candidate','original_low_rom'),'path':row['case'],'sha256':row['case_sha256']}
        scored=score_v2(out,descriptor,read(STAGE/'docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'],goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
        smooth,_=inspect(out);r['scorer_v2']=scored;r['smoothness']=smooth
        c2=all(abs(smooth[k])<=1e-6 for k in ('exact_switch_max_q_jump_deg','exact_switch_max_dq_jump_deg_s','exact_switch_max_ddq_jump_deg_s2'))
        injection=read(out/'PLANNER_READINESS_INJECTION.json');r['injection']=injection
        names=[e['event'] for e in events];fallback='FALLBACK_COMMITTED' in names
        progression=all(name in names for name in ('FALLBACK_COMMITTED','FALLBACK_STOPPED','FALLBACK_HOLD','FRESH_REPLAN_REQUESTED','RESUME_ACTIVATED'))
        delayed=row['delay_ms']>0
        delay_exercised=bool(injection['release_events'] and injection['release_events'][0]['source_age_ms']>=row['delay_ms']) if delayed else True
        cap=.15 if row['id']=='low_ordinary' else .35 if row['id']=='high_rom_function_fresh_03_v1' else .175
        normal=bool(smooth['non_task_reference_near_stop_longest_s'] <= cap + 1e-9)
        r.update(c2=c2,fallback_used=fallback,fallback_progression=progression,delay_exercised=delay_exercised,normal_smoothness_pass=normal)
        r['pass_all']=bool(scored['pass'] and c2 and r['stale_activated']==0 and ((delayed and progression and delay_exercised) or (not delayed and normal)))
    dest=DOC/(version+'_'+run_id+'_RESULT.json');assert not dest.exists();save(dest,r)
    manifest=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()];save(DOC/(version+'_'+run_id+'_RAW_MANIFEST.json'),manifest)
    print(json.dumps({k:r.get(k) for k in ('run_id','run_status','abort_reason','pass_all','fallback_used','normal_smoothness_pass','stale_activated')}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','score'));p.add_argument('--version',default='v1');p.add_argument('--run-id');a=p.parse_args()
    freeze(a.version) if a.command=='freeze' else score(a.version,a.run_id)
