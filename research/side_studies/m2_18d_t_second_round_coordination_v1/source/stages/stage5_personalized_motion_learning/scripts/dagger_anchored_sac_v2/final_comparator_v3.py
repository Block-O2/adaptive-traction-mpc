"""Cold replay of existing fixed comparators, same R2 protocol, new output routing."""
from common import *
from operational_memory_v3 import install,phase,evidence,descendants
from sac_env import rt
def main():
 req=json.loads(Path(sys.argv[1]).read_text());install(rt);phase('EVALUATION_PHYSICS')
 # Existing implementations and matched eligibility remain unmodified.
 f=r2.f;f.O=O/'final_verification_50000';f.O.mkdir(exist_ok=True)
 f.save=lambda name,value:save('FINAL_REPLAY_'+name,value)
 original=f.metric_record
 def full_metric(env,name,scope):
  row=r2.metric(env,name,scope);row.pop('raw_actions',None);ts=[x['to'] for x in env.summary['task']['phase_transitions']]
  row.update(gates=dict(settled_OUTBOUND='HOLD' in ts,completed_HOLD='RETURN' in ts,completed_RETURN='COMPLETE' in ts),termination=env.summary.get('abort_reason') or env.summary['status'],safety_mode_counts=env.summary['safety_mode_counts'],teacher_queries=0,teacher_execution=0,normalization_updates=0,steps=env.step_count,physics_task_samples=sum(r['stage']=='TASK' for r in env.capture.get('runtime',{}).get('trace',[])),evaluation_policy_steps_not_collection=True)
  return row
 f.metric_record=full_metric
 try:
  row={'original_controller':f.old_comparator,'CEM':f.cem_comparator,'fixed_hip_leading':f.simple_comparator}[req['kind']](req['scope']);row.update(final_verification=True,process_pid=os.getpid(),collection_steps_used=0,strategy=req['kind']);save(req['result'],row);print(json.dumps({k:row[k] for k in ('name','scope','valid','J_F','duration_s')}),flush=True)
 finally:phase('EVALUATION_CHILD_EXIT');evidence('FINAL_COMPARATOR_CHILD_EXIT',descendants=descendants(os.getpid()))
if __name__=='__main__':main()
