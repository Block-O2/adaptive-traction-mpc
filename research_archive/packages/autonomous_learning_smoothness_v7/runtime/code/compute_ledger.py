"""Append-only accounting; child wall is a subset of its parent's wall."""
from task_bootstrap import *
import os,fcntl
def main():
 lock=(STUDY/'compute.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
 path=STUDY/'COMPUTE_LEDGER.jsonl';seen={r['id'] for r in [json.loads(x) for x in path.read_text().splitlines()]}
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts={r['id']:r for r in events if r['event']=='START'};ends={r['id']:r for r in events if r['event']=='END'}
 ledger=json.loads((STUDY/'TASK_LEDGER.json').read_text());new=[]
 for id,end in ends.items():
  if id in seen:continue
  metric=None;source=None;parent='snapshot' not in starts[id].get('config',{})
  p=STUDY/'output'/(id+'_DATA.json')
  if p.exists():r=json.loads(p.read_text());metric=r.get('metric');source=p
  elif id in ledger:
   p=Path(ledger[id]['config']['result_path'])
   if p.exists():r=json.loads(p.read_text());metric=r.get('metric');source=p
  partial=STUDY/'output'/(id+'_PARTIAL_COMPUTE.json')
  if metric is None and partial.exists():metric=json.loads(partial.read_text());source=partial
  cfg=starts[id].get('config',{});row=dict(id=id,started_unix=starts[id]['unix'],ended_unix=end['unix'],status=end.get('worker_status',end.get('status')),wall_s=end['unix']-starts[id]['unix'],wall_role='top-level inclusive; disjoint top-level intervals only' if parent else 'child subset of parent wall; never add to parent wall',input_hash=starts[id].get('input_hash',starts[id].get('input_sha256')),config_version=cfg.get('version',1),code_manifest_sha256=starts[id].get('code_manifest_sha256'),output=str(source) if source else None,physics_attempt_count=1,metric_available=metric is not None)
  if metric:row.update(actual_new_simulation_s=metric.get('actual_new_simulation_seconds'),actual_new_native_steps=metric.get('actual_new_native_physics_steps'),main_model_calls=metric.get('actual_new_main_model_inverse_dynamics_api_calls'),native_worker_model_calls=metric.get('actual_new_native_worker_model_inverse_dynamics_api_calls'),model_accounting='native worker calls separate; same-process calls can be a subset of main API count',valid=metric.get('valid'),J_F=metric.get('J_F'))
  else:row.update(actual_new_simulation_s=None,actual_new_native_steps=None,unknown_work_retained=True)
  with path.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
  new.append(id)
 allrows=[json.loads(x) for x in path.read_text().splitlines()]
 summary=dict(entries=len(allrows),attempts_started=len(starts),open_attempts=[x for x in starts if x not in ends],actual_new_simulation_s_lower_bound=sum(r.get('actual_new_simulation_s') or 0 for r in allrows),actual_new_native_steps_lower_bound=sum(r.get('actual_new_native_steps') or 0 for r in allrows),main_model_calls_lower_bound=sum(r.get('main_model_calls') or 0 for r in allrows),native_worker_model_calls_separate_lower_bound=sum(r.get('native_worker_model_calls') or 0 for r in allrows),top_level_inclusive_wall_s=sum(r['wall_s'] for r in allrows if r['wall_role'].startswith('top-level')),missing_metric_ids=[r['id'] for r in allrows if not r['metric_available']],append_only=True)
 save(STUDY/'COMPUTE_SUMMARY.json',summary);print(json.dumps(dict(appended=len(new),entries=len(allrows))))
if __name__=='__main__':main()
