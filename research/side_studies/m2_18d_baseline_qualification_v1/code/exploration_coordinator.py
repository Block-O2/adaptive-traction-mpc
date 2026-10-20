"""Registered table proposal at the existing C13 immutable native boundary."""
from q_first_method import QFirstInterface
from study_common import np,time
class TableCoordinator(QFirstInterface):
 def __init__(self,config):
  super().__init__({**config,'method':'M0','delay_replay':False});self.registered=np.asarray(config['coordination_table']).reshape(2,5,3)
  assert np.isfinite(self.registered).all() and np.max(abs(self.registered))<=1
 def choose(self,b,c):
  phase=c['phase'];i=self.count[phase];prior=self.carry.copy();used=self.registered.copy()
  from native_core import masked
  used=masked(used,self.count);action=used[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3)
  self.table=used.copy();self.carry=used.copy();self.count[phase]+=1;self.apply(b,c,action,np.zeros(3));self.labels[-1].update(native_index=i)
  self.search_rows.append(dict(request_id=b['request'].request_id,physical_source_s=float(b['physical_now']),context=c,count_before={**self.count,phase:i},candidate_records=[dict(plan=used,source='registered_table',feasible=None,proposal_accepted=None,reason='FULL_NATIVE_CERTIFICATION_IN_ORIGINAL_PREPARED_PATH')],selected_index=0,selected_source='registered_table',applied_plan=used,plan_changed=not np.array_equal(used,prior),candidate_count=1,late=False,late_discard=False,Q_calls=0,G_calls=0,P_performance_calls=0,proposal_only=True))
