"""Replay preserved legal actions to an exact test state, then commit branches.
Diagnostic outcomes are permanently excluded from all training splits.
"""
from native_diagnostic import DiagnosticInterface
from native_core import *

class ReplayDiagnosticInterface(DiagnosticInterface):
 def __init__(self,request):
  super().__init__(request);self.carry=np.zeros((2,5,3));self.replay=request['replay_rows'];self.lookup={(r['context']['phase'],r['count_before'][r['context']['phase']]):r for r in self.replay};self.matched=[]
 def choose(self,b,c):
  if self.child is not None:return super().choose(b,c)
  key=(c['phase'],self.count[c['phase']]);row=self.lookup.get(key)
  if row is None:raise RuntimeError('REPLAY_HAS_NO_NATIVE_ACTION:'+str(key))
  assert digest(c)==digest(row['context']),'REPRESENTATIVE_CAUSAL_STATE_CHANGED'
  self.matched.append(dict(phase=key[0],index=key[1],causal_context_equal=True,original_request=row['request_id']))
  super().choose(b,c)
  if self.child is None:self.carry=np.asarray(row['applied_plan']).copy()
 def make_plans(self,b,c,label):
  row=self.lookup[(c['phase'],self.count[c['phase']])]
  pool=[(np.asarray(r['plan']),'ordinary_'+r['source']) for r in row['candidate_records']]
  g=self.net.proposals(feature(c,np.zeros((2,5,3)),self.count,self.carry));pool += [(masked(p,self.count),'G_head_'+str(i)) for i,p in enumerate(g)]
  q=self.net.values(np.asarray([feature(c,p,self.count,self.carry) for p,s in pool]));records=[]
  for (p,source),value in zip(pool,q):
   try:s=native_local(b,c,p,self.count)
   except (ValueError,RuntimeError) as error:s=dict(feasible=False,proposal_accepted=False,reason=str(error))
   records.append(dict(source=source,plan=p,Q=float(value),**s))
  save(label+'_OFFLINE_PREDICTIONS.json',dict(rows=records,weights=self.request['weights'],replayed_source=self.request['replay_source'],original_selected_index=row['selected_index'],original_applied_plan=row['applied_plan'],incoming_carry=self.carry,causal_context_equal=True,original_ordinary_pool_exact=True,online_budget_unchanged=6,offline_union_n=len(pool),split='diagnostic permanently excluded from fitting',continuation='commit declared candidate suffix; compare with preserved rolling source separately'))
  return pool
 def finish(self,env,metric):
  super().finish(env,metric)
  if self.child is None:
   with np.load(R/self.request['replay_trace']) as x,np.load(R/metric['trace']) as y:
    for key in x.files:
     assert x[key].shape==y[key].shape,key
     if x[key].dtype.kind in 'fiu':assert np.array_equal(x[key],y[key],equal_nan=True),key
     else:assert np.array_equal(x[key],y[key]),key
   save(metric['name']+'_REPLAY_GATE.json',dict(status='PASS',all_trace_fields_exact=True,contexts=self.matched,source=self.request['replay_source'],J_F=metric['J_F']))
