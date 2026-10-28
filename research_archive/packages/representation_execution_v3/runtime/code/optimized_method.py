from native_method import NativeInterface
import shared_nominal
class OptimizedNativeInterface(NativeInterface):
 def __init__(self,request):
  super().__init__(request);self.timing_version=request['timing_version'];shared_nominal.install()
 def decision_boundary(self,b):
  with shared_nominal.boundary(b):return super().decision_boundary(b)
 def choose(self,b,c):
  if self.timing_version.startswith('E2'):
   from q_first_method import QFirstInterface
   return QFirstInterface.choose(self,b,c)
  return super().choose(b,c)
 def finish(self,env,metric):
  super().finish(env,metric)
  from study_common import save
  save(metric['name']+'_CACHE_EVIDENCE.json',dict(version=self.timing_version,rows=shared_nominal.EVENTS,scope='same immutable native boundary only',candidate_specific_certificates_unchanged=True))
