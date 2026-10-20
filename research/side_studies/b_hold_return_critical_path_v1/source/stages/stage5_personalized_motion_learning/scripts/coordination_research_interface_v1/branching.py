"""Process-scoped full-state branch API; parent waits for every child.

Fork preserves the entire native MuJoCo object, mutable model, Python graph,
observer RNG/history, task stack, reference/planner ownership and cost prefixes.
Snapshots are NOT claimed to be portable serialized restarts. Quiescence is
mandatory, and the cloned branch alone advances physics while parent waits.
"""
from common import *
from interface import CoordinationInterface
from schedule import ResidualAction,DifferentialSchedule,certify
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
 roots={k:b[k] for k in ('runtime','updater','observer','scheduler','planner','adaptive_planner','task_state','reference_state','reference_acceleration','active_schedule','schedule_start_time','reference_governor','pending','planning_wait','async_pending','rolling_splice_pending','active_escape','fallback_latch','fallback_bridge','activation_backup','last_adaptation','next_adaptation_time','task_start_time','task_last_physics_time','step','decisions','transitions','learning_records','trace','sac_hooks') if k in b}
 roots['coordination_state']={k:getattr(interface,k) for k in ('replay_mode','actions','tapes','phase','epoch','schedule','current_context')}
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

class BranchSmoke(CoordinationInterface):
 def __init__(self):
  super().__init__(replay=False);self.targets=[('early_OUTBOUND','OUTBOUND',1.),('mid_OUTBOUND','OUTBOUND',4.5),('late_OUTBOUND','OUTBOUND',7.5),('mid_RETURN','RETURN',4.5)];self.finished=[];self.child=None;self.current_candidate=None;self.branch_rows=[]
 def boundary(self,b):
  if self.child is not None:return
  phase=b['task_state'].phase.value
  applicable=[x for x in self.targets if x[0] not in self.finished and x[1]==phase and b['task_state'].phase_elapsed_s>=x[2]-1e-9]
  if not applicable:return
  label,phase,at=applicable[0];self.finished.append(label)
  quiesce(b);before=state_manifest(b,self);snapshot_folder=O/'snapshots'/label;snapshot_folder.mkdir(parents=True,exist_ok=False)
  (snapshot_folder/'manifest.json').write_text(json.dumps(clean(before),sort_keys=True,indent=2)+'\n')
  for kind,amplitude in (('baseline',0.),('hip',.025),('knee',-.025)):
   guard();folder=O/'branches'/(label+'_'+kind);folder.mkdir(parents=True,exist_ok=False)
   python_rng=random.getstate();numpy_rng=np.random.get_state()
   pid=os.fork()
   if pid==0:
    # CPython automatically reseeds the global random singleton after fork.
    # Restore it explicitly; observer-local RNGs are already fork-preserved.
    random.setstate(python_rng);np.random.set_state(numpy_rng)
    self.child=dict(label=label,kind=kind,folder=folder,hash=before['hash'],start_task_s=float(b['physical_now']-b['task_start_time']),start_J_F=float(b['sac_hooks'].force_integral),human_model_hash=digest(b['belief'].value_state_record()))
    after=state_manifest(b,self) if False else None
    # Verify equality BEFORE changing the interface or any labels/output paths.
    # self.child assignment above is not part of the comparison; temporarily
    # restore it to the parent's state when hashing.
    child=self.child;self.child=None;after=state_manifest(b,self);self.child=child
    if before['hash']!=after['hash']:
     (folder/'fork_mismatch_manifest.json').write_text(json.dumps(clean(after),sort_keys=True,indent=2)+'\n')
     raise RuntimeError('FORK_SNAPSHOT_HASH_MISMATCH')
    env=b['sac_hooks'];env.episode_dir=folder
    # The runtime function's output_dir is a local binding. Redirect only file
    # output by using a cloned hook-provided path in the versioned runtime.
    self.branch_output_dir=folder
    t=float(b['physical_now']-b['task_start_time']);tape=self.tapes[phase];z=np.load(L/'B_TAPE.npz');phase_origin=float(z['t'][z['phase']==phase][0]);offset=max(0.,t-phase_origin);s=offset/tape.duration_s
    if s>=.98:raise RuntimeError('SNAPSHOT_TOO_LATE_FOR_CHUNK')
    end=min(.98,s+.15);knots=((s+(end-s)/2,amplitude),(end,0.))
    action=ResidualAction(phase,s,(0.,0.,0.),knots,end,provenance='branch_smoke_'+kind)
    if amplitude==0:result=dict(status='IDENTICAL_ZERO_RESIDUAL_B',certificate=None)
    else:
     schedule=DifferentialSchedule(tape,action,b['spec'],b['task_state'].phase,offset_s=offset)
     cert=certify(schedule,spec=b['spec'],belief=b['belief'],clearance=b['clearance'],owned=(b['reference'].q_rad,b['reference'].dq_rad_s,b['reference'].ddq_rad_s2),scheduler=b['scheduler'],tracking_error=b['state'][:2]-b['reference'].q_rad)
     result=dict(status='REJECTED_RETAIN_B' if not cert['feasible'] else 'ACCEPTED',certificate=cert)
     if cert['feasible']:
      # Same schedule and execution route as an E action; zero suffix is the
      # versioned B-pacing continuation after the declared candidate chunk.
      self.replay_mode=True;self.phase=phase;self.epoch=b['physical_now']-offset;self.schedule=schedule
      self.current_context=dict(spec=b['spec'],belief=b['belief'],clearance=b['clearance'],scheduler=b['scheduler'],estimated_state=b['state'],phase=b['task_state'].phase)
    self.current_candidate=dict(action=action.record(),candidate_horizon_s=(end-s)*tape.duration_s,realization=result,start_hash=after['hash'])
    return
   _,status=os.waitpid(pid,0)
   row=dict(snapshot=label,candidate=kind,exit_code=os.waitstatus_to_exitcode(status),snapshot_hash=before['hash'])
   label_path=L/(label+'_'+kind+'_label.json')
   if label_path.exists():row.update(json.loads(label_path.read_text()))
   self.branch_rows.append(row);save('BRANCH_SMOKE_PROGRESS.json',dict(rows=self.branch_rows,completed=len(self.branch_rows),budget=12))
   if row['exit_code']!=0:raise RuntimeError('BRANCH_CHILD_FAILED_STOP:'+label+'_'+kind)
   assert state_manifest(b,self)['hash']==before['hash'],'PARENT_STATE_CHANGED_DURING_BRANCH'
  self.branch_output_dir=None
 def finish(self,env,metric):
  if self.child is not None:
   c=self.child;name=c['label']+'_'+c['kind'];task_J=metric['J_F'];remaining=task_J-c['start_J_F']
   record=dict(snapshot=name,start_snapshot_hash=c['hash'],candidate=self.current_candidate,candidate_horizon=self.current_candidate['candidate_horizon_s'],continuation_policy_id='B_pacing_zero_residual_after_declared_C2_chunk_v1',Human_model_hash=c['human_model_hash'],timing_mode='MATCHED_R2',complete_task_validity=metric['valid'],complete_task_J_F=task_J,remaining_J_F=remaining,force_peak=metric['force_peak'],moment_integral=metric['moment_integral'],moment_peak=metric['moment_peak'],duration=metric['duration_s'],remaining_duration=metric['duration_s']-c['start_task_s'],metric=metric,same_state_verified=True,candidate_executed=self.current_candidate['realization']['status']=='ACCEPTED',interpretation='remaining cost under declared B continuation with candidate acceptance/rejection; not Q* or V*')
   save(name+'_label.json',record);compact(env.episode_dir);print(json.dumps(dict(branch=name,valid=metric['valid'],J_F=task_J,candidate_status=self.current_candidate['realization']['status'])),flush=True);os._exit(0)
  save('BRANCH_SMOKE.json',dict(rows=self.branch_rows,complete=len(self.branch_rows)==12,same_state_pass=all(r.get('same_state_verified',False) and r['exit_code']==0 for r in self.branch_rows),complete_valid_count=sum(r.get('complete_task_validity',False) for r in self.branch_rows),distinct_candidate_execution=False,pass_=False,limitation='hip/knee candidates explicitly rejected; all branches retain B; no expressivity or V readiness promotion'))
if __name__=='__main__':run('B_branch_parent',BranchSmoke())
