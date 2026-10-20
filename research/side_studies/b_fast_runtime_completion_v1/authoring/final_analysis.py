from pathlib import Path
import json,collections,hashlib,numpy as np,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');OLD=S.parent/'b_multirate_realtime_v1'
def save(n,x):(S/n).write_text(json.dumps(x,indent=2)+'\n')
def read(n):return json.loads((S/n).read_text())
def q(x):return dict(zip(('p50','p95','p99','max'),np.percentile(x,[50,95,99,100]).tolist())) if x else {}
def main():
 budgets=[]
 for ident,phase in (('045_N12_C2b_front_attribution','TASK'),('103_N13_S2_D2_C6_handoff_host','HOLD')):
  cycles=read('output/'+ident+'_EXCLUSIVE_CYCLES.json')['cycles'];rows=[r for r in cycles if (r.get('task_phase') if phase=='HOLD' else r['phase'])==phase]
  assert rows
  for row in rows:assert sum(row['exclusive_ns'].values())==row['duration_ns'],'NONEXCLUSIVE_CYCLE'
  cats=collections.Counter()
  for row in rows:
   for k,v in row['exclusive_ns'].items():cats[k]+=v
  budgets.append(dict(id=ident,phase=phase,actual_cycles=len(rows),exclusive_mean_ms={k:v/len(rows)/1e6 for k,v in cats.items()},whole_cycle_ms=q([x['duration_ns']/1e6 for x in rows]),sum_exclusive_means_ms=sum(cats.values())/len(rows)/1e6,all_cycles_close_exactly=True,attribution_only=True))
 save('reports/FINAL_EXCLUSIVE_BUDGET.json',dict(status='PASS',budgets=budgets,physics_steps=0,model_API_calls=0,quantiles='Quantiles describe the same measured cycles; independent component medians are never added. cProfile cumulative times are not cycle budgets.'))
 root=[]
 for ident in ('102_N13_S2_D2_C6_handoff_science','103_N13_S2_D2_C6_handoff_host'):
  rows=read('output/'+ident+'_HOLD_HANDOFF_ATTRIBUTION.json')['rows'];g=[x for x in rows if x['event']=='ORIGINAL_REFERENCE_SAFE_TASK_TRANSITION'];clock=[x for x in rows if x['event']=='ORIGINAL_SENSOR_TASK_CLOCK'];first=next(x for x in clock if x['before_phase']=='HOLD' and x['proposed_phase']=='RETURN');deferred=[x for x in g if x['deferred']];after=[x for x in deferred if x['before_phase_elapsed_s']>=1.-1e-10]
  root.append(dict(id=ident,first_sensor_dwell_proposal=first,shared_minimum_HOLD_s=1.,original_sensor_dwell_s=.5,total_deferrals=len(deferred),deferrals_at_or_after_shared_1s_minimum=len(after),post_minimum_deferrals=after,final_original_transition=g[-1],interpretation='The reference_ready field includes original reference completion and original frozen interface transition_allowed. Before1s, merged false readiness cannot be attributed exclusively to native progress. At/after1s the shared minimum permits transition, but the original reference readiness still delays handoff. No future-state request, changed HOLD duration, tolerance credit or guard bypass is implemented.'))
 save('reports/HOLD_ROOT_CAUSE.json',dict(status='OBSERVED_FINITE_COUNTEREXAMPLE_NOT_GLOBAL_IMPOSSIBILITY',rows=root,scope='Instrumented full SCI102 is bit-exact to R3. Host103 is attribution-only, not used to qualify B. Non-instrumented099/101 remain R2 failures.',original_R2_max_HOLD_s=1.020))
 pure=[];notpure=[]
 for item in read('reports/R3_TO_FAST_CHANGES.json')['modified_or_added']:
  n=item['path']
  if not n.startswith(('source/','deps/')):continue
  before=(OLD/n).read_text();after=(S/n).read_text();expected=before.replace(str(OLD),str(S)).replace('"b_multirate_realtime_v1"','"b_fast_runtime_completion_v1"')
  (pure if expected==after else notpure).append(n)
 assert not notpure
 save('reports/ORIGINAL_SOURCE_MATHEMATICS_PRESERVATION.json',dict(status='PASS',relocation_only_files=pure,other_source_changes=notpure,scope='Existing source/ and deps/ differences against R3 are exact path relocation only. New native/runtime adapters and their gates are independently enumerated.'))
 save('reports/ENGINEERING_PRE_REJECT_GUARD_AUDIT.json',dict(status='AUDITED_UNCHANGED',B_path='PrefixBInterface clears residual_spec for original B; it does not call NativeInterface.choose or QFirstInterface.choose.',guard_location=['code/native_method.py:53','code/q_first_method.py'],budget_formula='max(0,min(.040-native_compute_reserve,.055-native_compute_reserve-native_command_reserve))',interpretation='The historical research proposal headroom combines original bridge40ms and strict55 engineering reserves. It does not cause current original-B HOLD failure. Pure strict55 removal is not enabled; mixed original bridge headroom is preserved. M2 remains gated by actual B R2 failure.',source_timestamps_reset=False))
 print('FINAL_ANALYSIS_PASS',[(x['phase'],x['actual_cycles']) for x in budgets])
if __name__=='__main__':main()
