from study_common import *
from interfaces import TableInterface
from planning import Predictor,SearchInterface,feature
from known_model import StateResidualHumanModel,high_rom_deployable_prior
from accounting import record,attempts
import fork_core as fc
import copy,gc,random,traceback
OLD=STUDY.parent

def estimated_predictor(b):
 predictor=Predictor();belief=b['belief'];g=copy.deepcopy(belief.geometry)
 predictor.model=StateResidualHumanModel(g,np.asarray(belief.beta).copy(),high_rom_deployable_prior(),residual_weights_nm=np.zeros((2,5)))
 return predictor

class AttributionInterface(SearchInterface):
 def __init__(self,condition,seed,prefix):
  super().__init__('P',seed,None,prefix);self.condition=condition;self.research_parameters=None
 def choose(self,b,c):
  if self.research_parameters is None:
   if self.condition=='EST':self.predictor=estimated_predictor(b)
   m=self.predictor.model
   self.research_parameters=dict(condition=self.condition,beta=np.asarray(b['belief'].beta if self.condition=='EST' else read('KNOWN_MODEL_PARAMETERS.json')['beta']),estimated_geometry=asdict(b['belief'].geometry),estimated_residual_weights=np.asarray(b['belief'].state_residual_weights_nm),parameters_only=True)
   save('CURRENT_ESTIMATED_PARAMETERS_'+self.condition+'.json',self.research_parameters)
  return super().choose(b,c)
 def finish(self,env,metric):
  super().finish(env,metric);save(metric['name']+'_PARAMETERS.json',self.research_parameters)

class AuditForkInterface(TableInterface):
 def __init__(self,case):
  super().__init__(case['parent_table']);self.case=case;self.finished=False;self.child=None;self.search=None;self.events=[];self.initial=None;self.child_start_wall=None;self.branch_output_dir=None
 def manifest(self,b):
  m=fc.state_manifest(b,self);m['audit_interface']=dict(table=self.table,count=self.count,previous=self.previous)
  m['audit_hash']=digest(dict(native=m['manifest'],interface=m['audit_interface']));return m
 def frozen_pool(self,b,c):
  from inference import Networks
  network=Networks(self.case['weights']);known=Predictor();est=estimated_predictor(b);rows=[]
  for item in self.case['candidates']:
   row=dict(item=item,context=c,counts=self.count.copy())
   for condition,predictor in (('KNOWN',known),('EST',est)):
    pred=predictor.predict(b,c,item['plan'],self.count)
    delta=network.value(pred['terminal']['feature']) if condition=='KNOWN' else None
    row[condition]=dict(screening_accepted=pred['matched_model_feasible'],near_cost=pred['near_cost'],V_base=pred['V_base'],DeltaV=delta,P_score=pred['total_cost'],PV_score=None if delta is None else pred['total_cost']+delta,prediction=pred)
   if item['committed_source']:
    old=json.loads(Path(item['committed_source']).read_text());p=old['value_rows'][0]['model_prediction']
    row['old_model_score_difference']=row['KNOWN']['P_score']-p['total_cost'];assert abs(row['old_model_score_difference'])<1e-7,'DIAGNOSTIC_INSTRUMENTATION_CHANGED_PREDICTION'
   rows.append(row)
  save(self.case['state']+'_POOL.json',dict(state=self.case['state'],rows=rows,estimated_beta=b['belief'].beta,estimated_geometry=asdict(b['belief'].geometry),estimated_residual_weights=b['belief'].state_residual_weights_nm,known_parameters=read('KNOWN_MODEL_PARAMETERS.json'),weights=self.case['weights']))
  return rows
 def choose(self,b,c):
  if self.child is None and not self.finished and [c['phase'],self.count[c['phase']]]==self.case['target']:
   self.finished=True;fc.quiesce(b);gc.collect();before=self.manifest(b)
   expected=self.case['expected_context'];equal=np.array_equal(np.asarray(c['observation']),np.asarray(expected['observation'])) and np.array_equal(c['richer_previous_residual'],expected['richer_previous_residual']) and self.count==self.case['expected_counts']
   save(self.case['state']+'_REPLAY_PROOF.json',dict(context_equal=equal,current=c,expected=expected,counts=self.count,snapshot=before,old_snapshot=self.case['old_snapshot'],prefix_J_F=float(b['sac_hooks'].force_integral),prefix_M=float(b['sac_hooks'].moment_integral),physical_time=float(b['physical_now'])))
   assert equal,'OLD_CAUSAL_PREFIX_NOT_REPRODUCED'
   self.frozen_pool(b,c)
   assert self.manifest(b)['audit_hash']==before['audit_hash'],'POOL_CHANGED_PHYSICAL_STATE'
   for item in self.case['candidates']:
    for mode in ('COMMITTED','P_RECEDING','PV_RECEDING'):
     if mode=='COMMITTED' and item['committed_source']:continue
     guard();assert attempts()<50
     base=f'{self.case["state"]}_c{item["diagnostic_index"]}_{mode}'
     completed=sorted(L.glob(base+'*_OUTCOME.json'))
     if any(json.loads(p.read_text()).get('status')=='COMPLETE' for p in completed):continue
     name=base;n=0
     while (O/name).exists():n+=1;name=base+'_retry'+str(n)
     out=O/name;out.mkdir(exist_ok=False)
     config=dict(state=self.case['state'],candidate=item,mode=mode,snapshot_hash=before['audit_hash'],search_seed=self.case['post_forcing_search_seed'])
     record('START',name,config=config)
     py=random.getstate();nr=np.random.get_state();pid=os.fork()
     if pid==0:
      random.setstate(py);np.random.set_state(nr)
      assert self.manifest(b)['audit_hash']==before['audit_hash'],'FORK_STATE_CHANGED'
      self.child=dict(label=name,kind='outcome',start_J_F=float(b['sac_hooks'].force_integral),start_M=float(b['sac_hooks'].moment_integral),start_task_s=c['task_s'],physical_time_at_fork=float(b['physical_now']),snapshot_hash=before['audit_hash'],mode=mode,item=item,main_api_counter_at_fork=0,native_api_counter_at_fork=0)
      from traction_mpc_stage4 import estimator_v2 as ma
      self.child['main_api_counter_at_fork']=getattr(ma,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0)
      self.child['native_api_counter_at_fork']=native_model_calls(getattr(b['lifecycle'],'_events',{}))
      self.child_start_wall=time.monotonic();self.branch_output_dir=out;b['sac_hooks'].episode_dir=out;self.table=np.asarray(item['plan']).copy();self.initial=dict(context=c,count=self.count.copy(),plan=self.table.copy());self.events=[]
      if mode!='COMMITTED':
       self.search=SearchInterface('P' if mode=='P_RECEDING' else 'P+V',self.case['post_forcing_search_seed'],self.case['weights'] if mode=='PV_RECEDING' else None)
       self.search.previous_plan=self.table.copy();self.search.count=self.count.copy();self.search.previous=self.previous.copy()
       self.search.search_rows=[dict(audit_forced_candidate=True)]
      self._apply_forced(b,c)
      return
     _,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
     path=L/(name+'_OUTCOME.json');result=json.loads(path.read_text()) if path.exists() else dict(status='FAILED_NO_OUTCOME')
     record('END',name,status=result['status'],returncode=code,result=str(path))
     assert self.manifest(b)['audit_hash']==before['audit_hash'],'PARENT_STATE_CHANGED_AFTER_FORK'
   self.action={};b['planner'].residual_spec={}
  if self.child is not None:
   mode=self.child['mode']
   if mode=='COMMITTED':
    self._log_boundary(b,c,self.table,'committed');return super().choose(b,c)
   self.search.count=self.count.copy();self.search.previous=self.previous.copy();self.search.choose(b,c)
   self._log_boundary(b,c,self.search.previous_plan,self.search.search_rows[-1]['selected_source'])
   self.count=self.search.count.copy();self.previous=self.search.previous.copy();self.table=self.search.previous_plan.copy();self.action=self.search.action;self.labels.append(self.search.labels[-1]);return
  return super().choose(b,c)
 def _apply_forced(self,b,c):
  self._log_boundary(b,c,self.table,'forced_same_first_row');super().choose(b,c)
  if self.search is not None:self.search.count=self.count.copy();self.search.previous=self.previous.copy()
 def _log_boundary(self,b,c,plan,source):
  old=np.asarray(self.child['item']['plan']);counts=self.count.copy();mask=np.ones((2,5,3),bool)
  for k,p in enumerate(('OUTBOUND','RETURN')):mask[k,:counts[p]]=False
  row=dict(decision_index=len(self.events),context=c,count=counts,selected_plan=np.asarray(plan),source=source,original_pending_suffix_retained=bool(np.array_equal(np.asarray(plan)[mask],old[mask])),physical_time=float(b['physical_now']),prefix_J_F=float(b['sac_hooks'].force_integral),prefix_M=float(b['sac_hooks'].moment_integral))
  if self.search is not None and len(self.search.search_rows)>1:
   s=self.search.search_rows[-1];accepted=[r for r in s['candidates'] if not r['rejected']]
   if accepted:chosen=min(accepted,key=lambda r:r['score']);row['selected_prediction']=chosen['prediction'];row['selected_deltaV']=chosen['deltaV'];row['selected_score']=chosen['score']
   row['carry_candidates']=[dict(generation=r['generation'],rejected=r['rejected'],score=r.get('score'),reason=r.get('reason')) for r in s['candidates'] if r['source']=='remaining_plan']
  self.events.append(row)
 def finish(self,env,metric):
  super().finish(env,metric)
  if self.child is not None:
   name=self.child['label'];metric['actual_new_simulation_seconds']=metric['simulation_seconds']-self.child['physical_time_at_fork'];metric['actual_new_native_physics_steps']=round(metric['actual_new_simulation_seconds']/.00025)
   searchrows=[] if self.search is None else self.search.search_rows[1:]
   save(name+'_OUTCOME.json',dict(status='COMPLETE',child=self.child,initial=self.initial,metric=metric,remaining_J_F=metric['J_F']-self.child['start_J_F'],remaining_M=metric['moment_integral']-self.child['start_M'],events=self.events,search_rows=searchrows,wall_seconds=time.monotonic()-self.child_start_wall,network_calls=0 if self.search is None else self.search.network.calls if self.search.network is not None else 0))
  else:save(metric['name']+'_PARENT.json',dict(state=self.case['state'],metric=metric,target_reached=self.finished))
