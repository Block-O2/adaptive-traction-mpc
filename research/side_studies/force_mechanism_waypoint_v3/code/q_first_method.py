"""E2: Q ordering with complete native certification and close-rank fallback."""
from native_method import *
class QFirstInterface(NativeInterface):
 def choose(self,b,c):
  phase=c['phase'];i=self.count[phase]
  if self.method!='M2' or (phase in self.prefix and i<len(self.prefix[phase])):return NativeInterface.choose(self,b,c)
  start=time.monotonic();t=time.monotonic();pool=candidates(c,self.count,self.carry,int(self.rng.integers(1,2**31)),self.request.get('candidate_budget',6));generation_s=time.monotonic()-t
  features=np.asarray([feature(c,p,self.count,self.carry) for p,s in pool]);t=time.monotonic();values=self.network.values(features);inference_s=time.monotonic()-t
  # Same deployed float32 input normalization. A conservative standard dot
  # roundoff bound guards changes of BLAS batch size after rejected candidates.
  z=self.network.scale(features);w=self.network.w;eps=np.finfo(np.float32).eps;gamma=features.shape[1]*eps/(1-features.shape[1]*eps)
  bounds=2*gamma*(np.abs(z)@np.abs(w['linear_W']))*abs(float(w['y_scale']))+4*eps*np.abs(values)
  order=sorted(range(len(pool)),key=lambda j:(float(values[j]),j));records=[dict(plan=p,source=s,feasible=None,proposal_accepted=None,reason='NOT_EVALUATED_AFTER_CERTIFIED_Q_MINIMUM') for p,s in pool]
  evaluated=[];evaluation_s=0.;selected=None;fallback=False;shadow_s=0.;fast_end=None
  def evaluate(j):
   nonlocal evaluation_s
   t=time.monotonic()
   try:ev=native_local(b,c,pool[j][0],self.count)
   except (ValueError,RuntimeError) as e:ev=dict(feasible=False,proposal_accepted=False,reason=str(e))
   evaluation_s+=time.monotonic()-t;records[j].update(ev);evaluated.append(j)
  for pos,j in enumerate(order):
   evaluate(j)
   if records[j]['feasible'] and records[j]['proposal_accepted']:
    selected=j
    fallback=any(float(values[k]-values[j])<=float(bounds[k]+bounds[j]) for k in order[pos+1:])
    break
  if fallback:
   for j in range(len(pool)):
    if j not in evaluated:evaluate(j)
  fast_end=time.monotonic();fast_evaluated=evaluated.copy()
  shadow=self.request.get('execution_mode')=='SCIENTIFIC_SIMULATION'
  if shadow:
   t=time.monotonic()
   for j in range(len(pool)):
    if j not in evaluated:evaluate(j)
   shadow_s=time.monotonic()-t
  valid=[j for j,r in enumerate(records) if r['feasible'] and r['proposal_accepted']]
  if fallback or shadow:
   baseline_values=self.network.values(np.asarray([features[j] for j in valid])) if valid else []
   for j,v in zip(valid,baseline_values):records[j]['Q']=float(v)
   baseline_selected=min(valid,key=lambda j:records[j]['Q']) if valid else 0
   if shadow and not fallback:assert (selected if selected is not None else 0)==baseline_selected,'Q_FIRST_SELECTION_NOT_EQUIVALENT'
   if fallback:selected=baseline_selected
  else:
   for j in evaluated:records[j]['Q']=float(values[j])
  selected=selected if selected is not None else 0
  measured_s=time.monotonic()-start+self.context_s;timing=json.loads((STUDY/'TIMING_BASELINE.json').read_text());native_rows=[r for r in timing['rows'] if r.get('stage')=='TASK'];compute_reserve=max([r.get('compute_ms',0) or 0 for r in native_rows] or [0])/1000;command_reserve=max([r.get('validation_and_command_construction_ms',0) or 0 for r in native_rows] or [0])/1000
  budget=max(0.,min(.040-compute_reserve,.055-compute_reserve-command_reserve))
  if 'selection_budget_s' in self.request:
   reserves=self.request['registered_native_reserves'];compute_reserve=reserves['compute_s'];command_reserve=reserves['validation_command_s'];budget=max(0.,min(.040-compute_reserve,.055-compute_reserve-command_reserve));assert abs(budget-self.request['selection_budget_s'])<1e-12
  late=measured_s>budget;used=records[selected]['plan'] if valid else self.carry.copy();late_discard=False
  if self.request.get('delay_replay') and late:used=self.carry.copy();late_discard=True
  action=used[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3);changed=not np.array_equal(masked(used,self.count),masked(self.carry,self.count));self.table=used.copy();self.carry=used.copy();self.count[phase]+=1
  t=time.monotonic();self.apply(b,c,action,np.zeros(3));submission_s=time.monotonic()-t;self.labels[-1].update(native_index=i,measured_prefix_J_F=b['sac_hooks'].force_integral)
  self.search_rows.append(dict(request_id=b['request'].request_id,physical_source_s=float(b['physical_now']),context=c,count_before={**self.count,phase:i},candidate_records=records,selected_index=selected,selected_source=records[selected]['source'],applied_plan=used,plan_changed=changed,candidate_count=len(pool),context_s=self.context_s,generation_s=generation_s,validation_and_S_s=evaluation_s,Q_inference_s=inference_s,submission_s=submission_s,end_to_end_s=time.monotonic()-start+self.context_s,timing_scope='actual coordinator elapsed includes SCI shadow; fast prefix separately recorded',selection_budget_s=budget,native_compute_reserve_s=compute_reserve,native_command_reserve_s=command_reserve,late=late,late_discard=late_discard,delay_mode='deadline-enforced shadow replay' if self.request.get('delay_replay') else 'scientific synchronous',P_performance_calls=0,Q_calls=self.network.Q_calls,G_calls=0,q_first_order=order,q_all=values,roundoff_bounds=bounds,close_rank_fallback=fallback,fast_evaluated_indices=fast_evaluated,scientific_full_validation_shadow=shadow,shadow_s=shadow_s,fast_coordinator_s=fast_end-start+self.context_s))
