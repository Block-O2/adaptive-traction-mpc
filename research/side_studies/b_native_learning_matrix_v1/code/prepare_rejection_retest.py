from task_bootstrap import *
from prepare import enqueue

def main():
 prior=json.loads((STUDY/'queue/020_parent_dev_0.json').read_text())
 enqueue('024_context_rejection_retest',mode='branches',group=prior['group'],split=prior['split'],table=prior['table'],targets=[['RETURN',1]],candidates=6,budget_children=1,reason='Exact same causal parent/group seed. Five successful siblings are reused by hash; only the retained failed candidate receives an explicit retry ID to verify native rejection finalization after advisory-context repair.')
 save(STUDY/'REJECTION_RETEST_PLAN.json',dict(unix=time.time(),maximum_new_attempts=2,original_failure='parent_dev_0_RETURN_1_candidate2',expected='either native complete-valid or explicit native aborted/unqualified metric; no interface bypass or constraint relaxation',completed_siblings_reused=True,failed_attempt_preserved=True))
 print('REJECTION_RETEST_QUEUED')
if __name__=='__main__':main()
