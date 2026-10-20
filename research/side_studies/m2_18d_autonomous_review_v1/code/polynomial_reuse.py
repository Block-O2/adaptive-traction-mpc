"""Memoize identical pure polynomial subproblems within one native request."""
import threading,pickle,hashlib,contextlib,time,collections
LOCAL=threading.local();EVENTS=[];INSTALLED=False
@contextlib.contextmanager
def boundary(b,shadow=False):
 from coordination_adapter import snapshot_task_call
 payload=snapshot_task_call(b['adaptive_planner'],b['arguments']);req=b['request'];state=dict(owner=req.request_id,source_capture_ns=req.sensor_capture_ns,input_sha256=hashlib.sha256(payload).hexdigest(),cache={},hits=collections.Counter(),misses=collections.Counter(),created_ns=time.monotonic_ns(),shadow=shadow)
 assert getattr(LOCAL,'active',None) is None;LOCAL.active=state
 try:yield
 finally:LOCAL.active=None;EVENTS.append({k:(dict(v) if isinstance(v,collections.Counter) else v) for k,v in state.items() if k!='cache'}|dict(released_ns=time.monotonic_ns(),scope='same request; complete pure-function numeric inputs; independent current-model/geometry/phase safety checks retained'))
def install():
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 import numpy as np
 for obj,name,label in [(np,'roots','descending_roots'),(np.polynomial.polynomial,'polyroots','ascending_roots')]:
  original=getattr(obj,name)
  def wrap(original=original,label=label):
   def reused(*args,**kwargs):
    active=getattr(LOCAL,'active',None)
    if active is None:return original(*args,**kwargs)
    if len(args)!=1 or kwargs:return original(*args,**kwargs)
    coefficients=np.asarray(args[0])
    if coefficients.ndim!=1 or len(coefficients)<4:return original(*args,**kwargs)
    # Full byte keys give exact equality without a redundant cryptographic
    # hash/serialization on every tiny pure-function invocation. The dict is
    # born and destroyed with this one original immutable request.
    key=(label,coefficients.dtype.str,coefficients.shape,coefficients.tobytes());cache=active['cache']
    if key not in cache:
     result=original(*args,**kwargs);cache[key]=result.copy();active['misses'][label]+=1;return result
    result=cache[key].copy();active['hits'][label]+=1
    if active['shadow']:
     expected=original(*args,**kwargs);assert np.asarray(result).dtype==np.asarray(expected).dtype and np.array_equal(result,expected,equal_nan=True),'PURE_POLYNOMIAL_CACHE_CHANGED_RESULT'
    return result
   return reused
  setattr(obj,name,wrap())
