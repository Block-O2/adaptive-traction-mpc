"""Finite branch execution primitives. No simulator or learning imports."""
import json
class GlobalStop(RuntimeError):pass
class BranchFailure(RuntimeError):pass
GLOBAL_MARKERS=('INDEPENDENT_AUDIT_FAILED','NONFINITE_GRADIENT','RESTORE_','CONTRACT_','HASH_MISMATCH','SOURCE_CHANGED','SAMPLING_DENSITY','GLOBAL_RAM','GLOBAL_DISK','HARD_STOP','OWNED_JOB_WALL','STOP_REQUESTED','RESOURCE_STOP','RESOURCE_GUARD','OUTPUT_','UNCLOSED_OWNER')
def classify(end):
 if end.get('success'):return 'OK'
 text=json.dumps(end,sort_keys=True)
 if any(x in text for x in GLOBAL_MARKERS):return 'GLOBAL'
 worker=end.get('worker_end')
 # Unclassified compute failures cannot silently bypass missing safety/integrity evidence.
 if worker and worker.get('owner_joined') and end.get('child_joined') and end.get('safe_branch_failure'):return 'BRANCH'
 return 'GLOBAL'
def run_finite(jobs,execute,persist,admit=lambda j:None):
 results=[];failed=set()
 for job in jobs:
  if job.get('branch') in failed:
   result=dict(job=job['id'],status='SKIPPED_FAILED_BRANCH');results.append(result);persist(result);continue
  try:
   admit(job);outcome=execute(job)
   result=dict(job=job['id'],status='COMPLETE' if outcome.get('task_success',True) else 'SCIENTIFIC_FAIL',outcome=outcome)
  except BranchFailure as exc:
   failed.add(job.get('branch'));result=dict(job=job['id'],status='BRANCH_FAIL',error=str(exc))
  except GlobalStop as exc:
   result=dict(job=job['id'],status='GLOBAL_STOP',error=str(exc));results.append(result);persist(result);return results
  results.append(result);persist(result)
 return results
