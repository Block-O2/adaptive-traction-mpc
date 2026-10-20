from audit_common import *
import numpy as np
def main():
 assert (STUDY/'SOURCE_SEMANTICS.json').exists() and not (STUDY/'AUDIT_CONTRACT.json').exists()
 weights2=str(OLD/'weights_v2_seed2026100602/networks.npz');weights3=str(OLD/'weights_v2_seed2026100603/networks.npz')
 records=[read(p) for p in (OLD/'output').glob('*_DATA.json')]
 def branch(label,index):return next(r for r in records if r['child']['label']==label and r['child']['kind']==f'candidate{index}')
 def item(label,index,role):
  r=branch(label,index);return dict(identity=f'{label}:candidate{index}',role=role,plan=r['table'],committed_source=str(OLD/'output'/(r['id']+'_DATA.json')),old_trace=r['metric']['trace'])
 a='heldout_audit_normal_OUTBOUND_0';b='heldout_audit_deviation_RETURN_1';c='heldout_known_synergy_OUTBOUND_3';d='parent_dev_0_OUTBOUND_4'
 cases=[]
 for name,label,target,parent_id,indices,roles in [('normal',a,['OUTBOUND',0],'080_audit_0_normal',[1,15,19],['P/PV carry winner','accepted G selected','G physical best/model-filtered']),('return',b,['RETURN',1],'080_audit_1_deviation',[1,17,20],['P/PV carry winner','G selected/ranking conflict','G physical best']),('synergy',c,['OUTBOUND',3],'085_known_nonmyopic_synergy',list(range(5)),['L0','L1','L2','L3','FULL']),('late',d,['OUTBOUND',4],'015_parent_dev_0_retry3',[0,1],['B','qualified K3'])]:
  # Indices of physical-best G are verified against the preserved outcomes.
  if name in ('normal','return'):
   qualified=[r for r in records if r['child']['label']==label and r['metric']['valid'] and r['metric']['matched_eligible']]
   indices[-1]=int(min(qualified,key=lambda r:r['remaining_J_F'])['child']['kind'].replace('candidate',''))
  parent=read(OLD/'output'/(parent_id+'_RESULT.json'))['inputs'];items=[item(label,i,role) for i,role in zip(indices,roles)]
  cases.append(dict(state=name,label=label,target=target,parent_table=parent.get('table'),seed=parent.get('seed',2026100600),weights=weights2,candidates=items,expected_context=branch(label,indices[0])['branch_start']['context'],expected_counts=branch(label,indices[0])['branch_start']['counts'],old_snapshot=str(OLD/'output'/(label+'_SNAPSHOT.json'))))
 ps=read(OLD/'output/130_v2_extra_0_0_P_SEARCH.json');vs=read(OLD/'output/130_v2_extra_0_2_PV_SEARCH.json');i=2
 assert ps['rows'][i]['context']==vs['rows'][i]['context']
 parent=np.zeros((2,5,3))
 for j in range(i):parent[0,j]=np.asarray(ps['rows'][j]['selected_plan'])[0,j]
 cases.append(dict(state='value_failure',label='extra_nominal_OUTBOUND_2',target=['OUTBOUND',2],parent_table=parent.tolist(),seed=2026111200,weights=weights3,expected_context=ps['rows'][i]['context'],expected_counts=ps['rows'][i]['count_before'],old_snapshot=None,old_trace=str(OLD/'source/results/130_v2_extra_0_0_P/trace.npz'),candidates=[dict(identity=f'extra_decision2_{method}',role=role,plan=search['rows'][i]['selected_plan'],committed_source=None) for method,search,role in [('P',ps,'P selected'),('PV',vs,'V changes elite ranking and CEM generation; PV selected')]]))
 for case in cases:
  for n,row in enumerate(case['candidates']):row['diagnostic_index']=n;row['modes']=['COMMITTED_REUSE' if row['committed_source'] else 'COMMITTED','P_RECEDING','PV_RECEDING']
  case['post_forcing_search_seed']=2026101400+len(cases)*100+cases.index(case)
 contract=dict(name='V horizon / continuation / effective parameter source audit',registered_unix=time.time(),cases=cases,questions=['exact horizon','continuation mismatch','parameter source attribution'],reuse_committed_only_after_causal_native_prefix_verification=True,full_fixed_pools_are_diagnostic_subsets_not_original_search_pools=True,all_pool_candidates_receive_P_and_PV_rolling_outcomes=True,ranking_loss_reference='qualified fixed finite diagnostic pool; original full pool diagnostics separately retained',planned_attempts=45,max_attempts=50,attempts_include_parents_failures_replays=True,no_new_training=True,weights_sha256={p:sha(p) for p in (weights2,weights3)},attribution_only_difference='research inverse-dynamics beta/geometry source; B native estimated planner, physics, safety, residual model weights=0, search seeds/budget identical',exclusion='incomplete/invalid/unmatched excluded from force ranking but failures retained',verdict_criteria={'implementation_bug':'source/arithmetic/conditioning violation directly reproduced','continuation_mismatch':'committed prediction sufficiently calibrated yet rolling replacement demonstrably loses gain; otherwise mixed/inconclusive','horizon_boundary':'actual source/label interval omission; error alone insufficient','action_leverage':'same frozen pool ranks/top1/top3 plus actual selected regret; improved RMSE with unchanged choice is no control leverage'},same_first_action='same candidate current K3 row in all A/B/C, then normal rolling begins at next modifiable request',post_forcing_rng='same frozen P/PV generator seed per state; not claimed identical to historical optimizer RNG continuation')
 save(STUDY/'AUDIT_CONTRACT.json',contract)
 for k,case in enumerate(cases):
  name=f'010_state_{k}_{case["state"]}';save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='audit_fork',case=case,seed=case['seed'],result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 prefixes=[{}, {}, {'OUTBOUND':[[.04,.02,-.02]]},{'OUTBOUND':[[.06,.06,.06],[-.04,-.04,-.04]]}]
 for group,prefix in enumerate(prefixes):
  for condition in ('EST','KNOWN'):
   name=f'100_attribution_{group}_{condition}';save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='human_attribution',condition=condition,method='P',group=f'attribution_{group}',seed=2026101500+group,prefix=prefix,result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 print(json.dumps(dict(status='REGISTERED',states=5,pool_candidates=sum(len(c['candidates']) for c in cases),planned_attempts=45)))
if __name__=='__main__':main()
