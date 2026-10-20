from gates import *
import threading,random,types,mujoco,pickle,traceback
def state_manifest(b,interface):
 plant=b['plant'];model=plant.model;data=plant.data
 flag=mujoco.mjtState.mjSTATE_INTEGRATION;native=np.empty(mujoco.mj_stateSize(model,flag));mujoco.mj_getState(model,data,native,flag)
 seen={};excluded=[]
 def walk(x,path):
  if x is None or isinstance(x,(str,int,float,bool,np.generic)):return clean(x)
  if isinstance(x,np.ndarray):return dict(dtype=str(x.dtype),shape=list(x.shape),sha256=hashlib.sha256(x.tobytes()).hexdigest())
  if isinstance(x,Path):return str(x)
  if isinstance(x,types.FunctionType):return dict(function=x.__module__+'.'+x.__qualname__)
  if isinstance(x,(types.ModuleType,type)):return dict(type=str(type(x)),name=getattr(x,'__name__',''))
  ident=id(x)
  if ident in seen:return dict(reference=seen[ident])
  seen[ident]=path
  if isinstance(x,dict):return {str(k):walk(v,path+'.'+str(k)) for k,v in sorted(x.items(),key=lambda kv:str(kv[0]))}
  if isinstance(x,(list,tuple)):return [walk(v,path+'.'+str(i)) for i,v in enumerate(x)]
  if isinstance(x,(set,frozenset)):return sorted([walk(v,path+'.set') for v in x],key=str)
  if isinstance(x,mujoco.MjData):return dict(native_integration_sha256=hashlib.sha256(native.tobytes()).hexdigest())
  if isinstance(x,mujoco.MjModel):
   return {name:walk(getattr(x,name),path+'.'+name) for name in dir(x) if not name.startswith('_') and isinstance(getattr(x,name),(np.ndarray,int,float))}
  if hasattr(x,'__dict__'):
   return dict(type=type(x).__module__+'.'+type(x).__qualname__,state=walk(vars(x),path+'.__dict__'))
  # Locks and native cache handles are fork-copied, never reconstructed. Their
  # visible state is noted; no opaque object is silently dropped from manifest.
  note=dict(path=path,type=type(x).__module__+'.'+type(x).__qualname__,fork_preserved=True)
  if hasattr(x,'locked'):note['locked']=x.locked()
  excluded.append(note);return note
 roots={k:b[k] for k in ('lifecycle','arguments','request','runtime','updater','observer','scheduler','planner','adaptive_planner','task_state','reference_state','reference_acceleration','active_schedule','schedule_start_time','reference_governor','pending','planning_wait','async_pending','rolling_splice_pending','active_escape','fallback_latch','fallback_bridge','activation_backup','last_adaptation','next_adaptation_time','task_start_time','task_last_physics_time','step','decisions','transitions','learning_records','trace','sac_hooks') if k in b}
 roots['coordination_state']={'action':interface.action,'reference_rows':interface.rows}
 roots['python_rng']=random.getstate();roots['numpy_rng']=np.random.get_state();roots['native_integration']=native
 manifest=walk(roots,'research');return dict(hash=digest(manifest),manifest=manifest,opaque_fork_preserved=excluded,native_state_mask=int(flag),native_state_count=len(native),branch_kind='Linux fork complete address-space; process-scoped only')

def quiesce(b):
 life=b['lifecycle']
 future=getattr(life,'_future',None)
 if future is not None and not future.done():raise RuntimeError('FORK_REQUIRES_COMPLETED_PLANNER_FUTURE')
 # Shut down only computational workers, preserving lifecycle requests, future
 # result, pending activation and all ownership records in the snapshot.
 executor=getattr(life,'_executor',None)
 if executor is not None:
  executor.shutdown(wait=True,cancel_futures=False);life._executor=None
 if threading.active_count()!=1:raise RuntimeError('FORK_REQUIRES_SINGLE_THREAD:'+str(threading.enumerate()))
 assert b['runtime']['wall_session'].__class__.__name__=='ScientificPhysicsSession','SCIENTIFIC_ONLY'


