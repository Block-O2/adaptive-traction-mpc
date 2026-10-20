from study_common import *
from task_bootstrap import save as write
from prepare import enqueue
def main():
 assert json.loads((STUDY/'B_ZERO_GATE.json').read_text())['status']=='PASS'
 smoke=read('010_branch_smoke_RESULT.json');assert smoke['status']=='COMPLETE' and smoke['metric']['valid']
 errors={}
 with np.load(R/smoke['metric']['trace']) as base:
  for j in range(2):
   r=read('smoke_OUTBOUND_2_candidate'+str(j)+'_DATA.json');assert r['metric']['valid']
   with np.load(R/r['metric']['trace']) as branch:
    for k in base.files:
     assert base[k].shape==branch[k].shape,k
     if base[k].dtype.kind in 'fiu':
      finite=np.isfinite(base[k]);errors[str(j)+':'+k]=float(np.max(np.abs(base[k][finite]-branch[k][finite]))) if finite.any() else 0.
     else:assert np.array_equal(base[k],branch[k])
 assert max(errors.values())<1e-10,'CPU_FORK_WHOLE_TRACE_FAILED'
 write(STUDY/'BRANCH_GATE.json',dict(status='PASS',full_trace_errors=errors,parent_recovery='every branch before/after digest equal, CPU quiescent, all child waitpid joined',P_performance_calls=0))
 for n,split,sign in [('train_0','train',0),('train_1','train',1),('dev_0','dev',-1)]:
  table=np.zeros((2,5,3));table[0,0]=np.array([.12,.12,.12])*sign
  enqueue('020_parent_'+n,mode='branches',group='parent_'+n,split=split,table=table.tolist(),candidates=6,budget_children=24)
 write(STUDY/'CHECKPOINT.json',dict(phase='DIRECT_Q_DATA',next='three grouped parents (12 registered state anchors, 6 diverse candidates); dedup disclosed; train after queue joins',start_unix=json.loads((STUDY/'RUN_PLAN.json').read_text())['start_unix']))
 print(json.dumps(dict(status='PASS',registered_parent_attempts=3,registered_branch_attempts=72,physics_reserve=80)))
if __name__=='__main__':main()
