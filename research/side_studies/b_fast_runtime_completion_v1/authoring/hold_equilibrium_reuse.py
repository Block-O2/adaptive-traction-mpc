"""H1: exact pure loaded-equilibrium calculation reuse, never command reuse.

All original statics arguments and full object state enter the bitwise key.
Only calls leaving every argument unchanged may be cached. Caller outputs are
fresh pickle reconstructions. Current feedback, native screening and ownership
remain outside this cache and run normally for each command.
"""
import pickle,collections,sys,io
CACHE=collections.OrderedDict();ROWS=collections.Counter();ORIGINAL=None;ENABLED=True
MAX_ENTRIES=16
def key(args,kwargs):
 from loaded_context_reuse import raw
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((args,kwargs)));return stream.getvalue()
def solve(*args,**kwargs):
 if not ENABLED:return ORIGINAL(*args,**kwargs)
 # Preserve original signature/error behavior and exclude arbitrary callables.
 if len(args)!=3 or set(kwargs)-{'interface','target_q_rad','target_dq_rad_s'}:
  ROWS['signature_fallback']+=1;return ORIGINAL(*args,**kwargs)
 expected=('traction_mpc_stage5.task.GoalTaskSpec','traction_mpc_stage5.architecture_recovery_v2.functional_benchmark.StateResidualHumanModel','traction_mpc_stage4.cuff_allocator.CuffAwareSagittalAllocator')
 if tuple(type(v).__module__+'.'+type(v).__qualname__ for v in args)!=expected:
  ROWS['unregistered_type_fallback']+=1;return ORIGINAL(*args,**kwargs)
 import traction_mpc_stage5.hold_stabilizer as hs
 if type(kwargs.get('interface',hs.CONTROLLER_NOMINAL_INTERFACE)) is not hs.ControllerNominalInterfaceParameters:
  ROWS['interface_type_fallback']+=1;return ORIGINAL(*args,**kwargs)
 complete=kwargs|dict(interface=kwargs.get('interface',hs.CONTROLLER_NOMINAL_INTERFACE),target_q_rad=kwargs.get('target_q_rad'),target_dq_rad_s=kwargs.get('target_dq_rad_s'))
 try:
  before=key(args,complete)
  if len(before)>1_048_576:raise ValueError('STATIC_INPUT_KEY_LIMIT')
 except Exception:
  ROWS['unsupported_fallback']+=1;return ORIGINAL(*args,**kwargs)
 if before in CACHE:
  ROWS['hits']+=1;CACHE.move_to_end(before);return pickle.loads(CACHE[before])
 ROWS['misses']+=1;value=ORIGINAL(*args,**kwargs)
 try:
  after=key(args,complete)
  if after!=before:ROWS['argument_side_effect_not_cached']+=1;return value
  raw=pickle.dumps(value,protocol=5)
  if len(raw)>1_048_576:ROWS['output_limit_not_cached']+=1;return value
  CACHE[before]=raw
  if len(CACHE)>MAX_ENTRIES:CACHE.popitem(last=False);ROWS['evictions']+=1
 except Exception:ROWS['output_fallback_not_cached']+=1
 return value
def install():
 global ORIGINAL
 import traction_mpc_stage5.hold_stabilizer as hs
 if ORIGINAL is not None:return
 ORIGINAL=hs.solve_loaded_hold_equilibrium
 for name,module in list(sys.modules.items()):
  if not name.startswith('traction_mpc_stage5.') or module is None:continue
  for attr,value in list(vars(module).items()):
   if value is ORIGINAL:setattr(module,attr,solve)
