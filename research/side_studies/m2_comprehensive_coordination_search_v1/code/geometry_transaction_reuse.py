"""GEO1: pure geometry results scoped to one original request/control call.

Every call rekeys the complete envelope and arguments. Cached bytes cannot be
mutated by the caller. No model API, source clock or state admission is cached.
"""
import contextvars,pickle,functools
SCOPE=contextvars.ContextVar('complete_geometry_transaction',default=None)
INSTALLED=False;ROWS={}
def transaction(function):
 @functools.wraps(function)
 def call(*a,**k):
  token=SCOPE.set({})
  try:return function(*a,**k)
  finally:SCOPE.reset(token)
 return call
def wrap(original):
 @functools.wraps(original)
 def call(*a,**k):
  cache=SCOPE.get()
  if cache is None:return original(*a,**k)
  from loaded_context_reuse import raw
  key=(original,raw(a),raw(k));counts=ROWS.setdefault(original.__qualname__,dict(hit=0,miss=0))
  if key in cache:
   counts['hit']+=1;return pickle.loads(cache[key])
  value=original(*a,**k);cache[key]=pickle.dumps(value,protocol=5);counts['miss']+=1;return value
 return call
def install(*,parent=False):
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import rigid_table_reference as r,monotonic_clearance as m
 from loaded_context_reuse import aliases
 for name in ('margins','cuff_centers','check_quintic'):
  setattr(r.RigidTableReferenceEnvelopeV1,name,wrap(getattr(r.RigidTableReferenceEnvelopeV1,name)))
 original=m.monotonic_certificate;aliases(original,wrap(original))
 if parent:
  import study_common as sc
  sc.rt._execute_interval=transaction(sc.rt._execute_interval)
 INSTALLED=True
