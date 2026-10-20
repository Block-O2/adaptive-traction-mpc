from common import *
import numpy as np
def compare(rows,score_key,cost_key):
 accepted=[r for r in rows if r['accepted'] and r['qualified']];valid=[r for r in rows if r['qualified']];p=sorted(accepted,key=lambda r:(r[score_key],r['index']));truth=sorted(accepted,key=lambda r:(r[cost_key],r['index']));k=min(3,len(p));pos={r['identity']:i for i,r in enumerate(truth)}
 rankcorr=float(np.corrcoef(np.arange(len(p)),[pos[r['identity']] for r in p])[0,1]) if len(p)>1 else None
 return dict(top1_identity=p[0]['identity'],top1_index=p[0]['index'],selected_actual_cost=p[0][cost_key],accepted_pool_regret=p[0][cost_key]-truth[0][cost_key],screening_loss=truth[0][cost_key]-min(r[cost_key] for r in valid),topk=[r['identity'] for r in p[:k]],topk_mean_actual_cost=float(np.mean([r[cost_key] for r in p[:k]])),rank_correlation=rankcorr,ranking=[r['identity'] for r in p],forecast_RMSE=float(np.sqrt(np.mean([(r[score_key]-r[cost_key])**2 for r in accepted]))),accepted_size=len(p),topk_size=k)
def main():
 selected=read(NEW/'SEMANTIC_SUITABILITY.json');assert selected['status']=='PASS';data=read(AUDIT/'SCORE_DECOMPOSITION.json');states=[]
 for s in data['states']:
  rows=[dict(identity=r['identity'],index=r['index'],accepted=r['screening_accepted'],qualified=all(x['qualified'] for x in r['mode_metrics'].values()),plan_hash=digest(r['plan']),P=r['P_score'],V1=r['PV_score'],COMMITTED=r['mode_costs']['COMMITTED'],ROLLING_P=r['mode_costs']['P_RECEDING']) for r in s['rows']]
  comparisons={}
  for contract in ('COMMITTED','ROLLING_P'):
   for r in rows:
    r['DeltaJ_'+contract]=r[contract]-r['P'];r['ORACLE_'+contract]=r['P']+r['DeltaJ_'+contract];assert abs(r['ORACLE_'+contract]-r[contract])<1e-7
   baseline=compare(rows,'P',contract);oracle=compare(rows,'ORACLE_'+contract,contract);v1=compare(rows,'V1',contract)
   benefit=baseline['accepted_pool_regret']-oracle['accepted_pool_regret']
   comparisons[contract]=dict(P=baseline,P_V1=v1,P_ORACLE=oracle,top1_changed=baseline['top1_identity']!=oracle['top1_identity'],top3_set_changed=set(baseline['topk'])!=set(oracle['topk']),top3_order_changed=baseline['topk']!=oracle['topk'],regret_reduction_Ns=benefit,corrected_bad_selection=baseline['accepted_pool_regret']>1e-6 and benefit>1e-6,newly_damaged_selection=oracle['selected_actual_cost']>baseline['selected_actual_cost']+1e-6,V1_helpful_flip=v1['selected_actual_cost']<baseline['selected_actual_cost']-1e-6,V1_harmful_flip=v1['selected_actual_cost']>baseline['selected_actual_cost']+1e-6)
  states.append(dict(state=s['state'],rows=rows,comparisons=comparisons))
 summary={}
 for contract in ('COMMITTED','ROLLING_P'):
  records=[s['comparisons'][contract] for s in states];corrected=sum(r['corrected_bad_selection'] for r in records);damaged=sum(r['newly_damaged_selection'] for r in records)
  summary[contract]=dict(pools=len(records),accepted_P_regret_sum_Ns=sum(r['P']['accepted_pool_regret'] for r in records),accepted_oracle_regret_sum_Ns=sum(r['P_ORACLE']['accepted_pool_regret'] for r in records),macro_mean_regret_reduction_Ns=float(np.mean([r['regret_reduction_Ns'] for r in records])),corrected_bad_selections=corrected,newly_damaged_selections=damaged,top1_changes=sum(r['top1_changed'] for r in records),top3_set_changes=sum(r['top3_set_changed'] for r in records),top3_order_changes=sum(r['top3_order_changed'] for r in records),mean_P_rank_correlation=float(np.mean([r['P']['rank_correlation'] for r in records])),V1_regret_sum_Ns=sum(r['P_V1']['accepted_pool_regret'] for r in records),V1_helpful_flips=sum(r['V1_helpful_flip'] for r in records),V1_harmful_flips=sum(r['V1_harmful_flip'] for r in records),GO=corrected>=2 and damaged==0,scope='five distinct saved parent states, shared Human truth; finite diagnostic subsets and prescribed continuation RNG states, not independent Human samples')
 primary=selected['PRIMARY_V2_CONTRACT'];passed=summary[primary]['GO'];result=dict(unix=time.time(),PRIMARY_V2_CONTRACT=primary,gate='PASS' if passed else 'FAIL',V2_STATUS='ORACLE_GATE_PASSED_PENDING_OFFLINE_LEARNING' if passed else 'V2_NOT_DECISION_RELEVANT',training_authorized_by_gate=passed,reason='Multiple-parent top1/selection-regret leverage criterion evaluated before any fitting; rank-order improvements alone do not meet the gate',summary=summary,states=states,oracle_entered_online_controller=False,trained_networks=0,new_physics=0)
 save(NEW/'ORACLE_GATE.json',result);print(json.dumps({k:v for k,v in result.items() if k!='states'}))
if __name__=='__main__':main()
