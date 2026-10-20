"""Held-out same-state pools: model-only generation, physical continuation offline."""
from data_collection import BranchInterface
from planning import SearchInterface
from study_common import *
class AuditInterface(BranchInterface):
 def __init__(self,group,weights,seed,parent_table,targets):
  super().__init__(group,'test',parent_table,32,targets);self.weights=weights;self.audit_seed=seed
 def make_plans(self,b,c,label):
  original=b['planner'].residual_spec;plans=[];pools={};before=self.manifest(b)['hash']
  try:
   for method in ('P','P+G'):
    search=SearchInterface(method,self.audit_seed,self.weights);search.count=self.count.copy();search.previous=self.previous.copy()
    # One actual online-budget search; rescore the identical generated pool with V.
    search.choose(b,c);pool=search.search_rows[-1];pool['method']=method
    pool['full_model_inverse_dynamics_calls']=search.predictor.full_model_api_calls
    pool['network_inference_s']=0 if search.network is None else search.network.inference_s
    from inference import Networks
    value=Networks(self.weights)
    for row in pool['candidates']:
     key=digest(np.asarray(row['plan']).tolist())
     found=next((i for i,p in enumerate(plans) if digest(np.asarray(p).tolist())==key),None)
     if found is None:found=len(plans);plans.append(np.asarray(row['plan']).copy())
     row['physical_candidate_index']=found
     if not row['rejected']:
      row['same_pool_V_delta']=value.value(row['prediction']['terminal']['feature']);row['same_pool_PV_score']=row['score']+row['same_pool_V_delta']
    pool['offline_value_rescoring_inference_s']=value.inference_s;pools[method]=pool
  finally:b['planner'].residual_spec=original
  assert self.manifest(b)['hash']==before,'AUDIT_MODEL_SEARCH_CHANGED_SNAPSHOT'
  synergy={}
  if c['phase']=='OUTBOUND' and self.count['OUTBOUND']==0:
   reference=np.asarray(read('HISTORICAL_K3_DESIGN_REFERENCE.json')['table']).reshape(2,5,3)
   for length in (1,2,3):
    plan=np.zeros((2,5,3));plan[0,:length]=reference[0,:length];synergy['OUT_prefix_'+str(length)]=len(plans);plans.append(plan)
   synergy['full_K3']=next(i for i,p in enumerate(plans) if np.allclose(p,reference,rtol=0,atol=0))
   synergy['B']=next(i for i,p in enumerate(plans) if np.allclose(p,0,rtol=0,atol=0))
  save(label+'_AUDIT_POOL.json',dict(label=label,pools=pools,synergy_candidates=synergy,unique_candidates=len(plans),weights=self.weights,seed=self.audit_seed,online_physics_predictions=0,physical_consequence='offline held-out committed suffix only; no training',snapshot_hash=before))
  return plans
