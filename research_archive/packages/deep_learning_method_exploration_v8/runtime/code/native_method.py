from study_common import *
from interfaces import TableInterface
from native_core import candidates,native_local,feature,masked
class PrefixBInterface(TableInterface):
 """Common lawful-prefix interventions, then original B with no new scoring."""
 def __init__(self,request):
  super().__init__();self.request=request;self.prefix=request.get('prefix',{})
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value
  if phase not in self.prefix or self.count.get(phase,5)>=len(self.prefix[phase]):
   self.last_physical_time_s=float(b['physical_now']);self.action={};b['planner'].residual_spec={};return
  super().decision_boundary(b)
 def choose(self,b,c):
  phase=c['phase'];i=self.count[phase];self.count[phase]+=1;self.apply(b,c,np.asarray(self.prefix[phase][i]),np.zeros(3));self.labels[-1].update(native_index=i,legal_shared_prefix=True)
class NativeInterface(TableInterface):
 def __init__(self,request):
  super().__init__();self.request=request;self.method=request.get('method','M0');self.rng=np.random.default_rng(request.get('seed',1));self.carry=np.zeros((2,5,3));self.search_rows=[];self.network=None;self.prefix=request.get('prefix',{});self.context_s=0
  if self.method in ('M2','M3','M4'):
   from native_inference import Networks
   self.network=Networks(request['weights'])
 def context(self,b):
  t=time.monotonic();out=super().context(b);self.context_s=time.monotonic()-t;return out
 def choose(self,b,c):
  start=time.monotonic();phase=c['phase'];i=self.count[phase]
  if phase in self.prefix and i<len(self.prefix[phase]):
   a=np.asarray(self.prefix[phase][i]);self.count[phase]+=1;self.apply(b,c,a,np.zeros(3));self.labels[-1].update(native_index=i,legal_shared_prefix=True,measured_prefix_J_F=b['sac_hooks'].force_integral);return
  if self.method=='M0':super().choose(b,c);return
  generated=time.monotonic();pool=candidates(c,self.count,self.carry,int(self.rng.integers(1,2**31)),6)
  if self.method in ('M3','M4'):
   g=self.network.proposals(feature(c,np.zeros((2,5,3)),self.count,self.carry))
   pool=pool[:3]+[(masked(p,self.count),'G_head_'+str(j)) for j,p in enumerate(g)]
  generation_s=time.monotonic()-generated;evaluation_s=0.;records=[]
  for plan,source in pool:
   t=time.monotonic()
   try:ev=native_local(b,c,plan,self.count)
   except (ValueError,RuntimeError) as e:ev=dict(feasible=False,proposal_accepted=False,reason=str(e))
   evaluation_s+=time.monotonic()-t;records.append(dict(plan=plan,source=source,**ev))
  valid=[j for j,r in enumerate(records) if r['feasible'] and r['proposal_accepted']]
  inference_s=0.
  if self.method in ('M2','M4') and valid:
   t=time.monotonic();values=self.network.values(np.asarray([feature(c,records[j]['plan'],self.count,self.carry) for j in valid]));inference_s=time.monotonic()-t
   for j,v in zip(valid,values):records[j]['Q']=float(v)
   selected=min(valid,key=lambda j:records[j]['Q'])
  else:selected=min(valid,key=lambda j:records[j]['S']) if valid else 0
  # A missed new decision never replaces the legal declared remaining plan.
  measured_s=time.monotonic()-start+self.context_s
  timing=json.loads((STUDY/'TIMING_BASELINE.json').read_text())
  native_rows=[r for r in timing['rows'] if r.get('stage')=='TASK']
  compute_reserve=max([r.get('compute_ms',0) or 0 for r in native_rows] or [0])/1000.
  command_reserve=max([r.get('validation_and_command_construction_ms',0) or 0 for r in native_rows] or [0])/1000.
  # Conservative prerecorded native reserves, frozen before test. Do not
  # pretend the whole bridge/activation budget belongs to the coordinator.
  budget=max(0.,min(.040-compute_reserve,.055-compute_reserve-command_reserve))
  late=measured_s>budget
  used=records[selected]['plan'] if valid else self.carry.copy();late_discard=False
  if self.request.get('delay_replay') and late:
   used=self.carry.copy();late_discard=True
  action=used[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3)
  changed=not np.array_equal(masked(used,self.count),masked(self.carry,self.count));self.table=used.copy();self.carry=used.copy();self.count[phase]+=1
  t=time.monotonic();self.apply(b,c,action,np.zeros(3));submission_s=time.monotonic()-t
  self.labels[-1].update(native_index=i,measured_prefix_J_F=b['sac_hooks'].force_integral)
  self.search_rows.append(dict(request_id=b['request'].request_id,physical_source_s=float(b['physical_now']),context=c,count_before={**self.count,phase:i},candidate_records=records,selected_index=selected,selected_source=records[selected]['source'],applied_plan=used,plan_changed=changed,candidate_count=len(pool),context_s=self.context_s,generation_s=generation_s,validation_and_S_s=evaluation_s,Q_inference_s=inference_s,submission_s=submission_s,end_to_end_s=time.monotonic()-start+self.context_s,timing_scope='coordinator context through proposal submission; full native activation age is independently saved in summary timing requests',selection_budget_s=budget,native_compute_reserve_s=compute_reserve,native_command_reserve_s=command_reserve,late=late,late_discard=late_discard,delay_mode='deadline-enforced shadow replay' if self.request.get('delay_replay') else 'scientific synchronous',P_performance_calls=0,Q_calls=0 if self.network is None else self.network.Q_calls,G_calls=0 if self.network is None else self.network.G_calls))
 def finish(self,env,metric):
  super().finish(env,metric);save(metric['name']+'_SELECTIONS.json',dict(method=self.method,rows=self.search_rows,network_Q_calls=0 if self.network is None else self.network.Q_calls,network_G_calls=0 if self.network is None else self.network.G_calls,P_performance_calls=0,delay_replay=self.request.get('delay_replay',False)))
