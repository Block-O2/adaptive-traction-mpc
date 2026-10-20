"""Correct superseded prose only; never alter execution, labels, or limits."""
from freeze import *
def main():
 path=STUDY/'RUN_PLAN.json';old=json.loads(path.read_text())
 amendment=STUDY/'PLAN_AMENDMENT_13_PLAN_DOCUMENTATION.json'
 assert not amendment.exists()
 backup=STUDY/'RUN_PLAN_before_documentation_clarification.json';assert not backup.exists();shutil.copy2(path,backup)
 current=json.loads(path.read_text());prior=current['V']['policy_continuation']
 current['V']['policy_continuation']='native-certified-committed-K3-suffix-v1: execute the declared pending K3 table with native certification/rejection and B-owned HOLD/terminal handling; no SearchInterface replanning during Monte Carlo continuation'
 budget=json.loads((STUDY/'PLAN_AMENDMENT_09_REMAINING_BUDGET.json').read_text())
 current['stages_initial_estimates']=current['stages'];current['stages']=budget['remaining'];current['stage_budget_authority']='PLAN_AMENDMENT_09_REMAINING_BUDGET.json, registered before first fit/test; original estimates superseded'
 current['already_started_at_budget_amendment']=budget['already_started_including_failures'];current['conditional_pilot_max']=15;current['conditional_extra_tests_max']=16
 current['documentation_revision_unix']=time.time()
 for field in ('start_unix','deadline_unix','dispatch_cutoff_unix','max_physics_attempts','resources','planner'):assert current[field]==old[field]
 save(amendment,dict(unix=time.time(),scope='documentation clarification only',previous_continuation_prose=prior,actual_continuation_version='native-certified-committed-K3-suffix-v1',basis='All actual branch requests, DATA, training metadata and TableInterface implementation already used committed native-certified suffix; replanning text was an unexecuted initial design description',policy_updated=False,labels_relabelled=False,physics_or_algorithm_changed=False,old_plan_preserved=str(backup),budget_authority='pre-fit/test amendment 09, not a new budget',clock_reset=False))
 save(path,current);print('PLAN_DOCUMENTATION_CLARIFIED_WITH_ORIGINAL_PRESERVED')
if __name__=='__main__':main()
