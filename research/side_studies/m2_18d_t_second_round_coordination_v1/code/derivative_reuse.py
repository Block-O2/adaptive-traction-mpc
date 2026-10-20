"""Request-local memo of original polynomial derivative maximum only.

Constant coefficient does not enter polyder; shifted tracking certificates
retain their full margins/proofs and all state-dependent geometry checks.
"""
import ast,inspect,textwrap,contextvars,time,numpy as np
from contextlib import contextmanager
ACTIVE=contextvars.ContextVar('original_derivative_max_request',default=None);EVENTS=[];ORIGINAL=None
def compute(coef):
 deriv=np.polynomial.polynomial.polyder(coef)
 accel=np.polynomial.polynomial.polyder(deriv)
 roots=np.polynomial.polynomial.polyroots(accel)
 inside=[float(root.real) for root in roots if abs(float(root.imag))<1e-10 and 0.0<=float(root.real)<=1.0]
 return max(abs(float(np.polynomial.polynomial.polyval(t,deriv))) for t in (0.0,1.0,*inside))
def memo(coef):
 state=ACTIVE.get()
 if state is None:return compute(coef)
 a=np.asarray(coef);key=(a.dtype.str,a.shape,a[1:].tobytes());state['calls']+=1
 if key in state['values']:
  state['hits']+=1;v=state['values'][key]
  if state['shadow']:assert np.asarray(v).tobytes()==np.asarray(compute(coef)).tobytes(),'DERIVATIVE_MAX_BYTES_CHANGED'
  return v
 v=compute(coef);state['values'][key]=v;return v
@contextmanager
def boundary(owner,shadow=False):
 assert ACTIVE.get() is None,'NESTED_DERIVATIVE_CACHE_BOUNDARY'
 state=dict(owner=str(owner),shadow=shadow,values={},hits=0,calls=0);token=ACTIVE.set(state);t=time.monotonic_ns()
 try:yield
 finally:
  ACTIVE.reset(token);EVENTS.append(dict(owner=state['owner'],shadow=shadow,hits=state['hits'],calls=state['calls'],unique_inputs=len(state['values']),boundary_ms=(time.monotonic_ns()-t)/1e6,lifetime='same immutable request only',key='all derivative-relevant exact binary64 coefficients dtype/shape/bytes; c0 mathematically and computationally discarded by original polyder'))
def install():
 global ORIGINAL
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1 as cls
 if ORIGINAL is not None:return
 ORIGINAL=cls.check_quintic;tree=ast.parse(textwrap.dedent(inspect.getsource(ORIGINAL)));fn=tree.body[0];changed=0
 for i,node in enumerate(fn.body):
  if isinstance(node,ast.FunctionDef) and node.name=='derivative_max':fn.body[i]=ast.parse('derivative_max = original_derivative_max_request_local').body[0];changed+=1
 assert changed==1;namespace=dict(ORIGINAL.__globals__,original_derivative_max_request_local=memo);exec(compile(ast.fix_missing_locations(tree),'<original_check_quintic_request_local_derivative_only>','exec'),namespace);cls.check_quintic=namespace['check_quintic']
