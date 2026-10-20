"""Fixed causal input attribution only; no live plant/physics."""
from pathlib import Path
import sys,runpy,collections,time,json,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc,native_bool_reductions as b
original_install=b.install;counts=collections.Counter();elapsed=collections.Counter()
def wrapped_install():
 original_install()
 for name,module in list(sys.modules.items()):
  old=getattr(module,'np',None)
  if not name.startswith(('traction_mpc_stage3.','traction_mpc_stage4.','traction_mpc_stage5.')) or old is None:continue
  proxy=types.ModuleType(old.__name__);proxy.__dict__.update(vars(old));original=old.cross
  def measured(a,b,*args,_fn=original,_module=name,**kwargs):
   key=str((_module,getattr(a,'shape',None),getattr(b,'shape',None),getattr(a,'dtype',None),getattr(b,'dtype',None),bool(args or kwargs)))
   start=time.monotonic_ns()
   try:return _fn(a,b,*args,**kwargs)
   finally:counts[key]+=1;elapsed[key]+=time.monotonic_ns()-start
  proxy.cross=measured;module.np=proxy
b.install=wrapped_install
sys.argv=[str(S/'code/full_controller_replay.py'),'030_N5_V3_A1_C1c_science_nominal','FAST_N13_TAIL']
# Instrumented measurements use a separate result label to preserve uninstrumented evidence.
oldsave=sc.save
def save(name,value):
 if 'FULL_CONTROLLER' in name:name=name.replace('_REPLAY.json','_CROSS_ATTRIBUTION_REPLAY.json')
 return oldsave(name,value)
sc.save=save
runpy.run_path(str(S/'code/full_controller_replay.py'),run_name='__main__')
out=dict(status='PASS',no_physics=True,controller_inputs=120,counts=[dict(key=k,calls=n,total_cross_ns=elapsed[k]) for k,n in counts.most_common()],note='Function durations on instrumented saved-input replay; not a whole-cycle budget or host benchmark.')
oldsave('N13_CROSS_SHAPE_ATTRIBUTION.json',out);print(json.dumps(out))
