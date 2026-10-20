"""Evaluate the pre-test frozen earlier model with actual QE branches."""
from pathlib import Path
import sys,json
import numpy as np
from dataset import P,read,put
from train_early import reconstruct,ACTIONS
sys.path.insert(0,str(P/'control'));from early_selector import select
def main():
    complete_records=[]
    for group in ['D01R','D02','D03','D04','D05','D06','V01','V02','U01','U02','U03']:
        result=read(P/(group+'_RESULTS.json'))
        for r in result['rows']:
            a=r['candidate']['id']
            if a not in ACTIONS:continue
            m=read(P/'reports'/(group+'_'+a+'_MEASURED.json'))
            complete_records.append(dict(id=group+'_'+a,parent=group,split=result['condition']['split'],causal_features=reconstruct(group,a).tolist(),action=r['candidate'],activation=dict(accepted=r['intervention_executed'],actual_postures=r['posture_execution'],actual_early=r['early_execution'],actual_timing=r['timing_execution']),receipt_path='reports/'+group+'_'+a+'_EXECUTED_RESIDUAL_RECEIPTS.json',full_task_outcome=dict(complete=r['complete_task'],task=r['task'],absolute_safety=r['absolute_safety'],causal=r['receipt'],original_motion=r['motion']),qualified=r['all_original_qualifications'],cost_rankable=r['all_original_qualifications'],J_F_N_s=r['J_F_N_s'],source_hashes=m['sources']))
    put('derived/EARLY_DATASET_all.json',dict(rows=complete_records,parent_states=11,action_rows=len(complete_records),physical_data_reused_not_additional_independent_states=True,truth_used_as_online_input=False))
    rows=[];cost=[];qualified=[];selected=[]
    for g in ['U01','U02','U03']:
        d=read(P/'output'/(g+'_QE_POLICY_DECISION.json'));assert d==select(d['state'])
        xr=reconstruct(g,'B');assert np.allclose(xr,d['state']['features'],rtol=0,atol=1e-12),'LIVE_EARLY_STATE_DIFFERS_FROM_PREREGISTERED_RECONSTRUCTION'
        result=read(P/(g+'_RESULTS.json'));rr={r['candidate']['id']:r for r in result['rows']};a=d['selected'];actual=rr['QE'];fixed=rr[a]
        assert abs(actual['J_F_N_s']-fixed['J_F_N_s'])<1e-9 and actual['all_original_qualifications']==fixed['all_original_qualifications']
        j=np.array([rr[k]['J_F_N_s'] for k in ACTIONS]);q=np.array([rr[k]['all_original_qualifications'] for k in ACTIONS]);idx=ACTIONS.index(a);good=np.flatnonzero(q)
        rows.append(dict(parent=g,selected=a,direct_force_argmin=d['direct_force_argmin'],qualified=bool(q[idx]),J_F_N_s=float(j[idx]),gain_vs_B_N_s=float(j[0]-j[idx]) if q[idx] and q[0] else None,gain_vs_qualified_H150_N_s=float(j[1]-j[idx]) if q[idx] and q[1] else None,qualified_recovery_vs_H150=bool(q[idx] and not q[1]),regret_N_s=float(j[idx]-min(j[good])) if q[idx] else None,fixed_costs=dict(zip(ACTIONS,j.tolist())),fixed_qualified=dict(zip(ACTIONS,q.tolist())),decision=d))
        cost.append(j);qualified.append(q);selected.append(idx)
    j=np.array(cost);q=np.array(qualified);global_good=np.flatnonzero(np.all(q,axis=0));global_best=int(global_good[np.argmin(j[:,global_good].mean(0))]) if len(global_good) else None
    actual_mean=float(np.mean([r['J_F_N_s'] for r in rows]));best_mean=None if global_best is None else float(j[:,global_best].mean())
    passed=bool(all(r['qualified'] for r in rows) and len(set(selected))>1 and any(r['qualified_recovery_vs_H150'] for r in rows) and any(r['gain_vs_B_N_s'] is not None and r['gain_vs_B_N_s']>.01 for r in rows) and best_mean is not None and actual_mean<best_mean-.01)
    put('EARLY_VALUE_EVALUATION.json',dict(status='COMPLETED',EARLY_VALUE_TRAINED=True,EARLY_POLICY_ALL_TESTS_QUALIFIED=all(r['qualified'] for r in rows),EARLY_CONDITIONAL_BENEFIT_PASS=passed,rows=rows,mean_policy_J_F_N_s=actual_mean,best_all_test_qualified_fixed_action=None if global_best is None else ACTIONS[global_best],best_all_test_qualified_fixed_mean_J_F_N_s=best_mean,comparison_scope='best fixed action on all test states is an evaluation-only oracle comparator, never policy input',force_ranking_is_state_conditioned=len(set(r['direct_force_argmin'] for r in rows))>1,selection_is_state_conditioned=len(set(selected))>1,previous_repetition_feedback=False,primary_Q_GENERALIZATION_flag_unchanged=True,interpretation='Changes due to the learned qualification head are reported separately from force-Q ranking. A constant B fallback is qualified behavior, not a learning success.'))
    print('EARLY_VALUE_EVALUATED',passed,[r['selected'] for r in rows],flush=True)
if __name__=='__main__':main()
