from optimized_method import OptimizedNativeInterface
import shared_nominal,certified_snapshot
class E3Interface(OptimizedNativeInterface):
 def __init__(self,request):
  super().__init__(request)
  if request.get('certificate_version')=='v2':
   import certified_snapshot_v2
   self.certificate_module=certified_snapshot_v2
  else:self.certificate_module=certified_snapshot
  self.certificate_module.install()
 def choose(self,b,c):
  import capture_states
  capture_states.capture(self,b,c)
  from q_first_method import QFirstInterface
  return QFirstInterface.choose(self,b,c)
 def decision_boundary(self,b):
  with self.certificate_module.boundary(b):
   with shared_nominal.boundary(b):
    result=super(OptimizedNativeInterface,self).decision_boundary(b)
    if self.request.get('certify_final_payload'):
     import certified_apply
     certified_apply.ensure(self.certificate_module,b)
    return result
 def finish(self,env,metric):
  super().finish(env,metric)
  import capture_states
  capture_states.finish(metric['name'])
  if self.request.get('certify_final_payload'):
   import certified_apply
   from study_common import save
   save(metric['name']+'_FINAL_PAYLOAD_CERTIFICATION.json',dict(rows=certified_apply.EVENTS))
  from study_common import save
  save(metric['name']+'_CERTIFICATE_REUSE.json',dict(rows=self.certificate_module.EVENTS,scope='same original request owner and capture, exact serialized planner/model/belief/reference/numeric args hash; single consumption; original generic100ms expiry retained'))
