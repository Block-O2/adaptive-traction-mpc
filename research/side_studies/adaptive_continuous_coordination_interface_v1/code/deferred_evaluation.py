"""B5 evaluator-only aggregation after physics; original formula retained.

No control/safety consumer reads these fields. Every native/boundary sample is
copied at its original node; no physical truth is supplied to a controller.
"""
import time,math
from types import SimpleNamespace
INSTALLED=False;INSTANCES=[];ORIGINAL_OBSERVE=None;ORIGINAL_RECORD=None

class Positions:
 def __init__(self,shank,bed):self.shank=shank;self.bed=bed;self.row=None
 def __getitem__(self,key):
  assert key in ((self.shank,2),(self.bed,2))
  return self.row[2] if key[0]==self.shank else self.row[4]
class Rotations:
 def __init__(self,shank):self.shank=shank;self.row=None
 def __getitem__(self,key):assert key==(self.shank,8);return self.row[3]
class HumanPositions:
 def __init__(self):self.row=None
 def __getitem__(self,key):return self.row[5]

def observe(self,plant,*,integrated_step=True):
 if not hasattr(self,'_deferred_rows'):
  self._deferred_rows=[];self._deferred_count=0;self._deferred_flush_s=0.;self._deferred_contexts={};INSTANCES.append(self)
 key=(id(plant),id(plant.model));context=self._deferred_contexts.get(key)
 if context is None:
  shank=int(plant.model.geom('shank_geom').id);bed=int(plant.bed_geom_id);assert shank!=bed
  context=dict(model=plant.model,shank=shank,bed=bed,human=plant.human,indices=plant.human_qpos_indices.copy(),geometry_sizes=tuple(float(v) for v in plant.model.geom_size[shank,:2]),human_bounds=(tuple(plant.human.q_min_rad),tuple(plant.human.q_max_rad)));self._deferred_contexts[key]=context
 data=plant.data;shank=context['shank'];bed=context['bed'];touch=False
 for i in range(data.ncon):
  contact=data.contact[i]
  if ((int(contact.geom1)==bed and int(contact.geom2)==shank) or (int(contact.geom1)==shank and int(contact.geom2)==bed)):touch=True;break
 interface=getattr(plant,'_interface_value',None);wrench=getattr(interface,'human_wrench_world',None)
 copied_wrench=None if wrench is None or getattr(wrench,'shape',None)!=(6,) else wrench.copy()
 q=data.qpos[context['indices']].copy()
 self._deferred_rows.append((self.stage,bool(integrated_step),float(data.geom_xpos[shank,2]),float(data.geom_xmat[shank,8]),float(data.geom_xpos[bed,2]),q,copied_wrench,touch,key))
 self._deferred_count+=1

def record(self):
 rows=getattr(self,'_deferred_rows',[])
 if rows:
  begun=time.monotonic();stage=self.stage;proxies={}
  try:
   for row in rows:
    key=row[8]
    if key not in proxies:
     c=self._deferred_contexts[key]
     assert tuple(float(v) for v in c['model'].geom_size[c['shank'],:2])==c['geometry_sizes'] and (tuple(c['human'].q_min_rad),tuple(c['human'].q_max_rad))==c['human_bounds'],'STATIC_EVALUATOR_PARAMETERS_CHANGED'
     positions=Positions(c['shank'],c['bed']);rotations=Rotations(c['shank']);human_positions=HumanPositions()
     data=SimpleNamespace(geom_xpos=positions,geom_xmat=rotations,qpos=human_positions,ncon=0,contact=[SimpleNamespace(geom1=c['bed'],geom2=c['shank'])]);proxy=SimpleNamespace(model=c['model'],data=data,human=c['human'],bed_geom_id=c['bed'],human_qpos_indices=c['indices'],_interface_value=SimpleNamespace(human_wrench_world=None));proxies[key]=proxy
    p=proxies[key];p.data.geom_xpos.row=row;p.data.geom_xmat.row=row;p.data.qpos.row=row;p.data.ncon=int(row[7]);p._interface_value.human_wrench_world=row[6];self.stage=row[0]
    ORIGINAL_OBSERVE(self,p,integrated_step=row[1])
   self._deferred_rows.clear();self._deferred_flush_s+=time.monotonic()-begun
  finally:self.stage=stage
 return ORIGINAL_RECORD(self)

def install():
 global INSTALLED,ORIGINAL_OBSERVE,ORIGINAL_RECORD
 if INSTALLED:return
 import study_common
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_physics_monitor import FastTruePhysicsMonitor as C
 ORIGINAL_OBSERVE=C.observe;ORIGINAL_RECORD=C.record;C.observe=observe;C.record=record;INSTALLED=True

def finish(id):
 if not INSTALLED:return
 from study_common import save
 rows=[]
 for obj in INSTANCES:
  pending=len(getattr(obj,'_deferred_rows',[]));original_record=obj.record()
  rows.append(dict(samples_captured=obj._deferred_count,pending_at_finish=pending,pending_after_flush=len(obj._deferred_rows),postprocess_seconds=obj._deferred_flush_s,original_monitor_record=original_record))
 save(id+'_DEFERRED_EVALUATION.json',dict(version='E7_B5_DEFERRED_EVALUATION',rows=rows,original_equations_used=True,all_original_native_and_boundary_samples=True,control_or_safety_inputs_changed=False,physical_truth_role='Evaluation-only original post-refresh raw samples; original observe aggregation invoked after physics at record time. No forward physics or counterfactual wrench reconstruction.'))
