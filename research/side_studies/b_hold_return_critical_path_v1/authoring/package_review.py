"""Read existing evidence only; no model/planner/physical run is imported."""
from pathlib import Path
import json,sys,collections,hashlib,contextlib,io,time
import numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');W=Path(__file__).parent
sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(W))
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def distribution(a):return dict(count=len(a),values=a,**(dict(zip(('min','p50','p95','max'),np.percentile(a,[0,50,95,100]).tolist())) if a else {}))
def main():
 ledger=read(S/'TASK_LEDGER.json');assert not any(r['status']=='RUNNING' for r in ledger.values())
 records=[]
 import transition_metrics
 for ident,row in ledger.items():
  cfg=row['config'];host=cfg['execution_mode']!='SCIENTIFIC_SIMULATION'
  rpath=S/'output'/f'{ident}_RESULT.json';result=read(rpath) if rpath.exists() else {}
  fpath=S/'reports'/f'{ident}_FUNCTIONAL.json';f=read(fpath) if fpath.exists() else {}
  gate=S/'versions'/f'{ident}_SCI_GATE.json';g=read(gate) if gate.exists() else {}
  checks=f.get('functional_checks',{});legacy=f.get('legacy_result',{})
  summary=S/'source/results'/ident/'summary.json'
  if summary.exists():
   if host and checks.get('full_OUT_HOLD_RETURN'):
    sys.argv=['transition_metrics.py',ident]
    if not (S/'reports'/f'{ident}_TRANSITION_METRICS.json').exists():
     with contextlib.redirect_stdout(io.StringIO()):transition_metrics.main()
   if not (S/'reports'/f'{ident}_CACHE_USAGE.json').exists() and (S/'output'/f'{ident}_DIRECT_IPC.json').exists():
    # cache_usage's older script is top-level. Reproduce its data extraction
    # without importing that script (which would execute under stale argv).
    raw=read(S/'output'/f'{ident}_DIRECT_IPC.json')['rows'];last=next((x['hold_static_mechanics'] for x in reversed(raw) if 'hold_static_mechanics' in x),None)
    save(S/'reports'/f'{ident}_CACHE_USAGE.json',dict(id=ident,pure_cache=last,background_model_API_calls=sum(x['model_API_calls'] for x in last['rows']) if last else 0,authority='One final cumulative worker snapshot per run, never sum overlapping snapshots'))
  tm=S/'reports'/f'{ident}_TRANSITION_METRICS.json';timing=read(tm) if tm.exists() else {}
  cache=S/'reports'/f'{ident}_CACHE_USAGE.json';cache=read(cache) if cache.exists() else {}
  joins=[];ipc=S/'output'/f'{ident}_DIRECT_IPC.json'
  if ipc.exists():joins=[x for x in read(ipc)['rows'] if x.get('event')=='JOIN']
  commission=S/'output'/f'{ident}_COMMISSIONING_OWNER.json';closed=read(commission).get('closed') if commission.exists() else None
  records.append(dict(id=ident,version=row['version'],mode=cfg['execution_mode'],case=cfg.get('case',cfg.get('name')),kind='legal_deviation' if 'deviation' in ident else 'nominal',group=cfg.get('qualification_group','development_diagnostic'),worker_status=row.get('worker_status'),ledger_status=row['status'],error=row.get('error'),full_physical=checks.get('full_OUT_HOLD_RETURN',False) if host else result.get('metric',{}).get('status')=='COMPLETE',scientific=g.get('status'),cache_exercised_scientific=ident not in ('005_C8_science_nominal','006_C8_science_deviation'),functional=f.get('functional'),original_R2=checks.get('original_R2'),original_physical_safety=checks.get('original_physical_safety'),legacy_strict55=f.get('legacy_strict'),failed_checks=[k for k,v in checks.items() if not v],phase_durations=legacy.get('phase_durations',{}),HOLD_s=timing.get('HOLD_s',legacy.get('phase_durations',{}).get('HOLD')),service_gap_ms=f.get('service_gap_ms'),transition=timing.get('RETURN'),nonoverlap_ms=timing.get('RETURN_nonoverlap_ms'),all_actual_write_source_age_ms=timing.get('all_actual_write_source_age_ms'),task_source_to_lifecycle_activation_ms=timing.get('task_source_to_lifecycle_activation_ms'),collection_services=timing.get('collection_services'),compute=row.get('compute'),background_model_API_calls=cache.get('background_model_API_calls',0),wall_seconds=row.get('wall_seconds'),causal_violations=f.get('causal_violations'),maximum_backlog_s=f.get('wall_physics',{}).get('maximum_backlog_s'),TASK_joins=joins,commissioning_owner_closed=closed,code_manifest_scope='source/deps/code/native/build' if any(k.startswith('source/') for k in row['code_manifest']) else 'code/native/build; source imported hashes and version chronology retained separately'))
 hosts=[r for r in records if r['mode']!='SCIENTIFIC_SIMULATION'];scis=[r for r in records if r['mode']=='SCIENTIFIC_SIMULATION'];complete=[r for r in hosts if r['full_physical']]
 model={key:dict(known=sum((r['compute'] or {}).get(key) or 0 for r in records),unknown_ids=[r['id'] for r in records if (r['compute'] or {}).get(key) is None]) for key in ('main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')}
 native=sum((r['compute'] or {}).get('native_physics_steps') or 0 for r in records)
 offline=[]
 for p in sorted((S/'output').glob('*LOCAL_EQUIVALENCE.json')):
  x=read(p);offline.append(dict(path=str(p.relative_to(S)),status=x.get('status'),model_API_calls=x.get('model_API_calls',x.get('model_calls')),physics_steps=x.get('physics_steps'),sha256=sha(p)))
 for name in ('RETURN_PLANNER_DEPENDENCY.json','RETURN_CONSISTENT_STATE_DEPENDENCY.json','C9_LOCAL_CACHE_NOT_EXERCISED.json'):
  p=S/'reports'/name
  if p.exists():x=read(p);offline.append(dict(path=str(p.relative_to(S)),model_API_calls=x.get('model_API_calls'),physics_steps=x.get('physics_steps'),sha256=sha(p)))
 out=dict(status='REVIEWED',review_unix=time.time(),attempts=len(records),science_attempts=len(scis),science_gates_pass=sum(r['scientific']=='PASS' for r in scis),scientific_bypassed_cache_ids=[r['id'] for r in scis if not r['cache_exercised_scientific']],host_attempts=len(hosts),complete_host_tasks=len(complete),complete_original_R2_PASS=sum(r['full_physical'] and r['original_R2'] is True for r in hosts),formal_qualification=dict(cold_nominal_VALID=0,same_interpreter_nominal_VALID=0,legal_deviation_VALID=0,formal_runs_dispatched=0,reason='No development nominal PASS; original primary gate fails, so formal expansion and conditional robustness/freeze/M2 are not entered'),HOLD_distribution_all_complete=distribution([r['HOLD_s'] for r in complete]),HOLD_distribution_nominal=distribution([r['HOLD_s'] for r in complete if r['kind']=='nominal']),HOLD_distribution_legal=distribution([r['HOLD_s'] for r in complete if r['kind']=='legal_deviation']),quiet_C13=[r for r in hosts if r['group']=='quiet_development_smoke'],physical_native_steps_known=native,physical_seconds_known=native*.00025,model_compute=model,background_preparation_API_calls=sum(r['background_model_API_calls'] for r in records),offline_compute_records=offline,offline_failure_counter_policy='Failed local tests without exported counters are UNKNOWN, never assigned zero. Native physical steps of those saved-input tests are zero.',service_authority='Original feedback _execute_interval transactions only; request-only collection services separately reported; no cross-run median addition.',records=records)
 save(S/'reports/PACKAGE_RESULTS.json',out)
 print(json.dumps({k:out[k] for k in ('attempts','science_attempts','science_gates_pass','host_attempts','complete_host_tasks','complete_original_R2_PASS','HOLD_distribution_all_complete','physical_native_steps_known','physical_seconds_known','model_compute','background_preparation_API_calls')}))
if __name__=='__main__':main()
