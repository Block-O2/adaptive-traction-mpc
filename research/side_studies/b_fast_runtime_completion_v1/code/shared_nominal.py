"""E1: exact nominal B reuse within one immutable native boundary only."""
import threading,pickle,hashlib,contextlib,time
LOCAL=threading.local();EVENTS=[];INSTALLED=False
@contextlib.contextmanager
def boundary(b):
 from coordination_adapter import snapshot_task_call
 payload=snapshot_task_call(b['adaptive_planner'],b['arguments'])
 request=b['request'];state=dict(owner=request.request_id,source_capture_ns=request.sensor_capture_ns,input_sha256=hashlib.sha256(payload).hexdigest(),entries={},hits=0,misses=0,created_ns=time.monotonic_ns())
 assert getattr(LOCAL,'active',None) is None
 LOCAL.active=state
 try:yield
 finally:
  LOCAL.active=None;EVENTS.append({k:v for k,v in state.items() if k!='entries'}|dict(released_ns=time.monotonic_ns(),lifetime='one decision_boundary call; no state/reference/belief/ownership reuse across boundaries'))
def install():
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import TerminalSetHumanWaypointPlannerV1 as C
 original=C.decide
 def reused(self,**kwargs):
  active=getattr(LOCAL,'active',None)
  if active is None:return original(self,**kwargs)
  # Full candidate-independent planner/model/geometry/history plus current
  # numerical arguments; only residual_spec is ignored because this original
  # terminal-B method never reads it. Checker closure is generated identically
  # from the immutable adaptive snapshot and represented by its input hash.
  state={k:v for k,v in vars(self).items() if k!='residual_spec'}
  args={k:v for k,v in kwargs.items() if k not in ('execution_feasibility_checker','candidate_value_evaluator')}
  assert kwargs.get('candidate_value_evaluator') is None
  key=hashlib.sha256(pickle.dumps((active['input_sha256'],state,args),protocol=5)).hexdigest()
  if key not in active['entries']:
   result=original(self,**kwargs);active['entries'][key]=pickle.dumps((vars(self),result),protocol=5);active['misses']+=1;return result
  residual=getattr(self,'residual_spec',{});after,result=pickle.loads(active['entries'][key]);self.__dict__.clear();self.__dict__.update(after);self.residual_spec=residual;active['hits']+=1;return result
 C.decide=reused
