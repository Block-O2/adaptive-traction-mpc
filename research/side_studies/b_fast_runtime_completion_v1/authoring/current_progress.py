from pathlib import Path
import json,sys,time,collections
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import runner
plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text());now=time.time()
rows={k:dict(status=v['status'],worker_status=v.get('worker_status'),error=v.get('error'),compute=v.get('compute'),result_path=v.get('result_path')) for k,v in ledger.items() if int(k[:3])>=53}
totals={key:sum(value for r in ledger.values() if isinstance(value:=(r.get('compute') or {}).get(key),(int,float))) for key in ('native_physics_steps','simulation_seconds','main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')}
resource=runner.sample(owner='CURRENT_PACKAGE_CHECKPOINT')
out=dict(status='ACTIVE',unix=now,t0_unix=plan['t0_unix'],elapsed_h=(now-plan['t0_unix'])/3600,physics_attempts=len(ledger),physics_budget=plan['physics_budget'],recorded_totals_lower_bound=totals,model_scope_caution='Main deltas and TASK counters recorded; older commissioning, owner warm and some direct offline probes not fully counted. Reconciliation required before final exact-total claim.',recent=rows,resource=resource,BEST_RUNTIME=None,M2=False,Q=False,training_updates=0,remaining='C6 nominal/deviation host full physical/current/causal/service PASS but original R2 HOLD1.030 FAIL. C5c and N14 scope closed without useful HOLD gain. Moving escape audit PASS. No unchanged failing hosts queued for dispatch; protected verification, accounting, manifests and reproducible handoff remain.')
(S/'CURRENT_PROGRESS.json').write_text(json.dumps(out,indent=2)+'\n')
with (S/'PROGRESS.md').open('a') as f:
 f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(now))} UTC checkpoint: elapsed{out["elapsed_h"]:.3f}h, attempts{len(ledger)}/120. Four cold/four repaired same-interpreter episodes preserved. C6 nominal/legal scientific bit-exact; both full hosts pass physical/current/causal/service but fail original R2 HOLD1.030. Moving TASK7 delay/expiry cancel into original certified stop/fresh-replan; separate escape horizon audit PASS. N14 scope closes offline: bit-exact, HOLD gains0.334/53.245us. No qualified BEST/M2/Q/training. Closing reproducible delivery.\n')
print(json.dumps(dict(elapsed_h=out['elapsed_h'],attempts=len(ledger),totals=totals,mem_available=resource['mem_available'],windows_commit_headroom=resource['windows'].get('commit_headroom'))))
