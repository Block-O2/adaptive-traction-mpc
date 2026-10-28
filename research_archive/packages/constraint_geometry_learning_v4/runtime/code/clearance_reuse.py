"""Exact geometry certificate reuse within ONE immutable native request."""
import pickle,hashlib,threading,contextlib,time
LOCAL=threading.local();EVENTS=[];INSTALLED=False
@contextlib.contextmanager
def boundary(b,shadow=False):
 from coordination_adapter import snapshot_task_call
 request=b['request'];payload=snapshot_task_call(b['adaptive_planner'],b['arguments'])
 state=dict(owner=request.request_id,source_capture_ns=request.sensor_capture_ns,input_sha256=hashlib.sha256(payload).hexdigest(),cache={},objects={},hits=0,misses=0,shadow_hits=0,created_ns=time.monotonic_ns(),shadow=shadow)
 assert getattr(LOCAL,'active',None) is None;LOCAL.active=state
 try:yield
 finally:
  try:
   for obj,expected in state['objects'].values():assert constructor_hash(obj)==expected,'IMMUTABLE_CLEARANCE_INPUT_MUTATED'
  finally:
   LOCAL.active=None;EVENTS.append({k:v for k,v in state.items() if k not in ('cache','objects')}|dict(released_ns=time.monotonic_ns(),constructor_objects_verified=len(state['objects']),scope='one request, immutable geometry/reference/model inputs; all constructor fingerprints reverified before function can return; no cross-boundary reuse'))
def constructor_hash(obj):
 state={k:v for k,v in vars(obj).items() if k!='last_certificate'}
 assert set(state)=={'shank_contract','envelope','use_monotonic_certificate'},'CLEARANCE_INPUT_SCHEMA_CHANGED'
 return hashlib.sha256(pickle.dumps(state,protocol=5)).hexdigest()
def install():
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1 as C
 for name in ('certified_minimum',):
  original=getattr(C,name)
  def wrap(original=original,name=name):
   def reused(self,*args,**kwargs):
    active=getattr(LOCAL,'active',None)
    if active is None:return original(self,*args,**kwargs)
    # Only last_certificate is an output. All constructor inputs and every
    # numeric query are in the key, in addition to the original request hash.
    identity=id(self)
    if identity not in active['objects']:active['objects'][identity]=(self,constructor_hash(self))
    owner,constructor=active['objects'][identity];assert owner is self
    key=hashlib.sha256(pickle.dumps((active['input_sha256'],name,constructor,args,kwargs),protocol=5)).hexdigest()
    cache=active['cache']
    if key not in cache:
     result=original(self,*args,**kwargs);proof=getattr(self,'last_certificate',None) if name=='certified_minimum' else None
     cache[key]=pickle.dumps((result,proof),protocol=5);active['misses']+=1;return result
    result,proof=pickle.loads(cache[key]);active['hits']+=1
    if active['shadow']:
     expected=original(self,*args,**kwargs);expected_proof=getattr(self,'last_certificate',None) if name=='certified_minimum' else None
     import study_common as sc
     assert sc.digest((result,proof))==sc.digest((expected,expected_proof)),'CLEARANCE_CERTIFICATE_REUSE_NOT_EXACT'
     active['shadow_hits']+=1
    if name=='certified_minimum':object.__setattr__(self,'last_certificate',proof)
    return result
   return reused
  setattr(C,name,wrap())
