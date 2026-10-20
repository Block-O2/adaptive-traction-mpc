from native_data import BranchInterface
from native_core import *
class DiagnosticInterface(BranchInterface):
 def __init__(self,request):
  super().__init__(request)
  from native_inference import Networks
  self.net=Networks(request['weights'])
 def make_plans(self,b,c,label):
  pool=super().make_plans(b,c,label);g=self.net.proposals(feature(c,np.zeros((2,5,3)),self.count,self.carry));pool=pool+[(masked(p,self.count),'G_head_'+str(i)) for i,p in enumerate(g)]
  predictions=self.net.values(np.asarray([feature(c,p,self.count,self.carry) for p,source in pool]));rows=[]
  for (plan,source),q in zip(pool,predictions):
   try:s=native_local(b,c,plan,self.count)
   except (ValueError,RuntimeError) as e:s=dict(feasible=False,proposal_accepted=False,reason=str(e))
   rows.append(dict(source=source,plan=plan,Q=float(q),**s))
  save(label+'_OFFLINE_PREDICTIONS.json',dict(rows=rows,information='Q/S from current causal native state only; actual outcomes measured afterward',weights=self.request['weights'],online_budget_unchanged=6,offline_union_n=len(pool)))
  return pool
