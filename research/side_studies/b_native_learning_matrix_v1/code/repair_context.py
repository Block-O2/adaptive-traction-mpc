from study_common import *
from task_bootstrap import save as write
from prepare import enqueue

def main():
 if len(sys.argv)<2 or sys.argv[1]=='prepare':
  enqueue('030_zero_context_repair')
  write(STUDY/'CONTEXT_REPAIR.json',dict(unix=time.time(),scope='advisory context only',reason='A rejected original-B candidate raised from the advisory clone before the original runtime could handle native rejection/fallback.',change='Catch only no-feasible-candidate ValueError, record a skip, issue no residual, then submit to unchanged B runtime.',preserved='All geometry, mechanics, original candidate search and task rules.',original_failure='parent_dev_0_RETURN_1_candidate2',historical_failure_retained=True,regression='030_zero_context_repair versus 002_original_B_retry1'))
 else:
  a=read('002_original_B_retry1_RESULT.json');b=read('030_zero_context_repair_RESULT.json');assert b['status']=='COMPLETE' and b['metric']['valid']
  differences={}
  with np.load(R/a['metric']['trace']) as x,np.load(R/b['metric']['trace']) as y:
   for key in x.files:
    assert x[key].shape==y[key].shape
    if x[key].dtype.kind in 'fiu':
     assert np.array_equal(np.isnan(x[key]),np.isnan(y[key]));mask=np.isfinite(x[key]);differences[key]=float(np.max(np.abs(x[key][mask]-y[key][mask]))) if mask.any() else 0.
    else:assert np.array_equal(x[key],y[key]);differences[key]=0.
  assert max(differences.values())<1e-10
  write(STUDY/'B_ZERO_CONTEXT_REPAIR_GATE.json',dict(status='PASS',differences=differences,J_F=b['metric']['J_F'],P_calls=b['P_full_performance_calls']))
  print('CONTEXT_REPAIR_ZERO_PASS')
if __name__=='__main__':main()
