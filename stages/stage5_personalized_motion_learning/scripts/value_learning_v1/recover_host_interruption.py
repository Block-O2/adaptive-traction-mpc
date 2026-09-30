from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/value_learning_research_v1';RAW=S/'results/value_learning_research_v1'
records=[]
for p in sorted((RAW/'runs').glob('*/rollout_result.json')):
 row=json.loads(p.read_text())
 if row['status']!='RUNNING':continue
 before=p.with_name('rollout_result_before_host_interrupt_v1.json')
 if not before.exists():before.write_bytes(p.read_bytes())
 retry=row['run_id']+'_retry1'
 row.update(status='INTERRUPTED_HOST_RESOURCE',failure_reason='Ubuntu WSL VM stopped; kernel prior boot recorded read-error on swap-device; startup E_UNEXPECTED. No task validity/completed-cost claim.',retry_run_id=retry,original_record_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),interruption_classification='INFRASTRUCTURE_NOT_SCIENTIFIC_FAILURE')
 p.write_text(json.dumps(row,indent=2,sort_keys=True)+'\n');records.append({'interrupted_run_id':row['run_id'],'retry_run_id':retry,'original_record_sha256':row['original_record_sha256']})
log=subprocess.check_output(['journalctl','-b','-1','-p','warning','--no-pager'],text=True)
(RAW/'host_interruption_prior_boot.log').write_text(log)
old=json.loads((D/'STATE.json').read_text());old.update(phase='HOST_RECOVERED_RESUME_PENDING',repair_cycles_used=1,next_action='Resume CEM with 2 workers and one-step branches with 1 worker; do not exceed three simultaneous simulations')
(D/'STATE.json').write_text(json.dumps(old,indent=2,sort_keys=True)+'\n')
repair={'schema':'bounded_repair_log_v1','cycles':[{'cycle':1,'kind':'scientific_host_infrastructure','evidence':'Prior boot kernel swap-device read errors, Ubuntu STOPPED, CreateInstance/E_UNEXPECTED','repair':'wsl --shutdown then restart Ubuntu; all distributions were already stopped','concurrency_change':'cap total scientific simulations at 3; search2 + branch1; no scientific/safety change','interrupted_attempts':records,'prior_boot_log_sha256':hashlib.sha256(log.encode()).hexdigest(),'recovered_utc':datetime.now(timezone.utc).isoformat(),'root_cause':'swap IO failure observed; precise underlying host failure not established'}],
 'logging_repairs':[{'change':'restore previous executed delta before logging research candidate legacy score; only dimensionless comparator logging affected, no force/safety/execution change','replay_regression_required':True},{'change':'add opt-in deployable snapshot capture and exact research-source hashes per rollout','scope':'provenance/profiling only'}],
 'push_block':'Automatic approval review rejected GitHub upload to unverified destination. Local-only commits continue; final explicit destination approval required.'}
(D/'REPAIR_LOG.json').write_text(json.dumps(repair,indent=2,sort_keys=True)+'\n')
print(json.dumps({'marked_interrupted':records,'host_recovered':True}),flush=True)
