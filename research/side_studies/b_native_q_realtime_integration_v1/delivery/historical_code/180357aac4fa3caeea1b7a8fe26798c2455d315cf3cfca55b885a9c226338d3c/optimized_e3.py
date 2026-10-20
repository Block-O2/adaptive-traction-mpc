from optimized_method import OptimizedNativeInterface
import shared_nominal,certified_snapshot
class E3Interface(OptimizedNativeInterface):
 def __init__(self,request):
  super().__init__(request);certified_snapshot.install()
 def choose(self,b,c):
  from q_first_method import QFirstInterface
  return QFirstInterface.choose(self,b,c)
 def decision_boundary(self,b):
  with certified_snapshot.boundary(b):
   with shared_nominal.boundary(b):return super(OptimizedNativeInterface,self).decision_boundary(b)
 def finish(self,env,metric):
  super().finish(env,metric)
  from study_common import save
  save(metric['name']+'_CERTIFICATE_REUSE.json',dict(rows=certified_snapshot.EVENTS,scope='same original request owner and capture, exact serialized planner/model/belief/reference/numeric args hash; single consumption; original generic100ms expiry retained'))
