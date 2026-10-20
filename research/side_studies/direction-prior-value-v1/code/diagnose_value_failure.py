"""Read-only attribution of a completed held-out V deterioration; no tuning."""
from freeze import *
def main():
 names=['130_v2_extra_0_0_P','130_v2_extra_0_2_PV'];logs=[];results=[];sources={}
 for name in names:
  path=STUDY/'output'/(name+'_SEARCH.json');logs.append(json.loads(path.read_text()));sources[str(path)]=sha(path)
  path=STUDY/'output'/(name+'_RESULT.json');results.append(json.loads(path.read_text()));sources[str(path)]=sha(path)
 first=[r['rows'][0] for r in logs];candidates=[{r['index']:r for r in decision['candidates'] if r['generation']==0} for decision in first]
 same_plans=all(candidates[0][i]['plan']==candidates[1][i]['plan'] for i in candidates[0]);assert same_plans
 summaries=[]
 for log,decision in zip(logs,first):
  accepted=[r for r in decision['candidates'] if not r['rejected']]
  best=min(accepted,key=lambda r:r['score']);model_best=min(accepted,key=lambda r:r['prediction']['total_cost'])
  delta=[r['deltaV'] for r in accepted]
  summaries.append(dict(method=log['method'],network_calls=log['network_calls'],online_physics_branches=log['online_physics_branches'],selected_source=decision['selected_source'],selected_generation=best['generation'],selected_index=best['index'],selected_model_cost_Ns=best['prediction']['total_cost'],selected_deltaV_Ns=best['deltaV'],selected_score_Ns=best['score'],model_only_best_generation=model_best['generation'],model_only_best_index=model_best['index'],deltaV_min_max_Ns=[min(delta),max(delta)]))
 metrics=[r['metric'] for r in results];assert all(m['valid'] and m['matched_eligible'] and m['status']=='COMPLETE' for m in metrics)
 divergence=None
 for index,(p,v) in enumerate(zip(logs[0]['rows'],logs[1]['rows'])):
  if p['selected_plan']==v['selected_plan']:continue
  pc={r['index']:r for r in p['candidates'] if r['generation']==0};vc={r['index']:r for r in v['candidates'] if r['generation']==0}
  divergence=dict(decision_index=index,context_equal=p['context']==v['context'],counts_before=p['count_before'],first_generation_plans_equal=set(pc)==set(vc) and all(pc[i]['plan']==vc[i]['plan'] for i in pc),P_selected_source=p['selected_source'],PV_selected_source=v['selected_source'],scope='First complete-plan divergence; it need not imply a different immediately executed graph.')
  break
 result=dict(source_files=sources,weights_frozen_no_fit=True,first_decision_context_equal=first[0]['context']==first[1]['context'],first_generation_candidate_plans_equal=same_plans,first_selected_plans_equal=first[0]['selected_plan']==first[1]['selected_plan'],first_decision=summaries,force_gain_vs_P_fraction=(metrics[0]['J_F']-metrics[1]['J_F'])/metrics[0]['J_F'],scope='Only the initial same-state search is compared. Subsequent states and second-generation candidate centers may diverge; full closed-loop loss is not assigned to one decision.',no_hyperparameter_or_algorithm_change=True)
 result['first_complete_plan_divergence']=divergence;save(STUDY/'V_FAILURE_DIAGNOSIS.json',result);print(json.dumps(result))
if __name__=='__main__':main()
