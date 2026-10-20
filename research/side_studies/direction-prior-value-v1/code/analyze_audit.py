from freeze import *
import numpy as np
def main():
 states=[]
 for file in sorted((STUDY/'output').glob('heldout_audit_*_AUDIT_POOL.json')):
  spec=json.loads(file.read_text());label=spec['label'];records={}
  for i in range(spec['unique_candidates']):
   paths=[STUDY/'output'/f'{label}_candidate{i}_DATA.json',*sorted((STUDY/'output').glob(f'{label}_candidate{i}_retry*_DATA.json'))]
   found=next((p for p in paths if p.exists()),None)
   if found:
    record=json.loads(found.read_text());metric=record['metric'];record['qualified']=bool(metric.get('valid') and metric.get('matched_eligible') and metric['status']=='COMPLETE');records[i]=record
  methods={};quality={};union_best=min((r['remaining_J_F'] for r in records.values() if r['qualified']),default=None)
  for base,pool in spec['pools'].items():
   candidates=pool['candidates'];actual=[(c,records.get(c['physical_candidate_index'])) for c in candidates]
   qualified=[(c,r) for c,r in actual if r and r['qualified']];eligible=[(c,r) for c,r in qualified if not c['rejected']]
   best=min((r['remaining_J_F'] for c,r in qualified),default=None);best_accepted=min((r['remaining_J_F'] for c,r in eligible),default=None)
   g=[(c,r) for c,r in actual if c['source']=='G'];quality[base]=dict(total_candidates=len(candidates),unique_candidates=len({c['physical_candidate_index'] for c in candidates}),model_rejected=sum(c['rejected'] for c in candidates),physical_qualified=sum(bool(r and r['qualified']) for c,r in actual),best_physical_remaining_Ns=best,best_accepted_physical_remaining_Ns=best_accepted,G_generated=len(g),G_model_rejected=sum(c['rejected'] for c,r in g),G_physical_qualified=sum(bool(r and r['qualified']) for c,r in g),full_model_inverse_dynamics_calls=pool['full_model_inverse_dynamics_calls'],decision_wall_s=pool['decision_wall_s'],network_inference_s=pool['network_inference_s'],offline_V_rescoring_s=pool['offline_value_rescoring_inference_s'])
   for use_value in (False,True):
    method=base if not use_value else base+'+V';key='same_pool_PV_score' if use_value else 'score';accepted=[c for c in candidates if not c['rejected']]
    selected=min(accepted,key=lambda c:c[key]) if accepted else next(c for c in candidates if c['source']=='B');record=records.get(selected['physical_candidate_index']);qualified_choice=bool(record and record['qualified'])
    methods[method]=dict(selected_candidate_index=selected['physical_candidate_index'],selected_source=selected['source'],qualified=qualified_choice,actual_remaining_J_F_Ns=record['remaining_J_F'] if record else None,selection_regret_Ns=(record['remaining_J_F']-best) if qualified_choice and best is not None else None,same_pool_candidates=True,candidate_generation_policy=base)
    methods[method]['selection_regret_vs_union_Ns']=(record['remaining_J_F']-union_best) if qualified_choice and union_best is not None else None
    methods[method]['selection_regret_within_accepted_Ns']=(record['remaining_J_F']-best_accepted) if qualified_choice and best_accepted is not None else None
    methods[method]['model_filter_opportunity_gap_Ns']=(best_accepted-best) if best_accepted is not None and best is not None else None
  synergy={}
  for name,i in spec.get('synergy_candidates',{}).items():
   record=records.get(i)
   if record:synergy[name]=dict(qualified=record['qualified'],remaining_J_F_Ns=record['remaining_J_F'],remaining_M_Nms=record['remaining_M'],prefix_costs=[dict(phase=row['context']['phase'],counts=row['count'],J_F=row['prefix_J_F'],M=row['prefix_M']) for row in record['value_rows'] if 'prefix_J_F' in row])
  if 'B' in synergy:
   for name,row in synergy.items():row['J_F_improvement_vs_B_Ns']=synergy['B']['remaining_J_F_Ns']-row['remaining_J_F_Ns']
  states.append(dict(label=label,completed_unique=len(records),expected_unique=spec['unique_candidates'],quality=quality,methods=methods,synergy=synergy,contract_sha256=sha(file),best_union_physical_remaining_Ns=union_best,planner_state_basis='Fresh SearchInterface at the held-out causal/native snapshot; no inherited closed-loop search history. Its registered initial K3 carry and ordinary search remain available.'))
 save(STUDY/'HELDOUT_SNAPSHOT_ANALYSIS.json',dict(states=states,complete=len(states)==2 and all(s['completed_unique']==s['expected_unique'] for s in states),semantics='Fixed-pool same-state diagnostic; V does not alter second-generation proposals here. Actual closed-loop V runs may adapt the CEM center differently.',no_training_use=True,high_budget_reference='best qualifying measured candidate in the fixed union, not global optimum',continuation='native-certified-committed-K3-suffix-v1'))
 print(json.dumps(states,indent=2))
if __name__=='__main__':main()
