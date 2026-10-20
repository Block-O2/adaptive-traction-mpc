"""Frozen-policy evaluation with actual Q branches and unranked failure preservation."""
from pathlib import Path
import os,sys,json,time,hashlib,itertools,ast,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
from dataset import P,read,put,ACTIONS
from value_model import fit,predict
sys.path.insert(0,str(P/'control'))
from frozen_selector import select
def main():
    frozen=read(P/'models/VALUE_FREEZE.json');ds=read(P/'derived/DATASET_all.json');npz=np.load(P/'derived/DATASET_all.npz')
    x=npz['X'];j=npz['J'];qual=npz['qualified'];groups=npz['groups'];splits=npz['splits'];action_index={a:i for i,a in enumerate(ACTIONS)}
    rows=[];factorial=[];all_outputs=[]
    for i,g in enumerate(groups):
        records={r['proposed_action']['id']:r for r in ds['records'] if r['parent']==g};state=records['H150']['state'];pred=select(state)
        delta=j[i]-j[i,0];choice=action_index[pred['selected']];direct=action_index[pred['direct_Q_argmin']]
        good=np.flatnonzero(qual[i]);best=int(good[np.argmin(j[i,good])]) if len(good) else None
        actual_policy=None
        if splits[i]=='test':
            decision=read(P/'output'/(str(g)+'_Q_POLICY_DECISION.json'))
            assert decision==pred,'RECORDED_LIVE_SELECTION_DIFFERS_FROM_FROZEN_INFERENCE'
            qr=next(r for r in read(P/(str(g)+'_RESULTS.json'))['rows'] if r['candidate']['id']=='Q')
            assert abs(qr['J_F_N_s']-j[i,choice])<1e-9
            assert qr['all_original_qualifications']==bool(qual[i,choice])
            actual_policy=dict(id=qr['id'],J_F_N_s=qr['J_F_N_s'],qualified=qr['all_original_qualifications'],failed=qr['motion']['failed_requirements'],live_decision=decision)
        row=dict(parent=str(g),split=str(splits[i]),force_costs=dict(zip(ACTIONS,j[i].tolist())),qualified=dict(zip(ACTIONS,qual[i].tolist())),predicted_delta_J_F_N_s=pred['predicted_delta_J_F_N_s'],actual_delta_J_F_N_s=delta.tolist(),selected=pred['selected'],direct_argmin=pred['direct_Q_argmin'],best_qualified=None if best is None else ACTIONS[best],selection_qualified=bool(qual[i,choice]),regret_N_s=None if best is None or not qual[i,choice] else float(j[i,choice]-j[i,best]),improvement_vs_H150_N_s=float(j[i,0]-j[i,choice]) if qual[i,choice] and qual[i,0] else None,supported=pred['supported'],actual_policy=actual_policy)
        rows.append(row);all_outputs.append(pred)
        factorial.append(dict(parent=str(g),hip_effect_at_knee_minus_0p3=float(j[i,0]-j[i,2]),hip_effect_at_knee_zero=float(j[i,1]-j[i,3]),knee_effect_at_hip_plus_0p3=float(j[i,0]-j[i,1]),knee_effect_at_hip_zero=float(j[i,2]-j[i,3]),interaction_N_s=float(j[i,0]-j[i,1]-j[i,2]+j[i,3])))
    metrics={}
    fixed_index=action_index[frozen['global_action']]
    for split in ['train','validation','test']:
        ix=np.flatnonzero(splits==split);pp=np.array([all_outputs[i]['predicted_delta_J_F_N_s'] for i in ix]);truth=j[ix]-j[ix,0,None]
        pairwise=[]
        for n,i in enumerate(ix):
            for a,b in itertools.combinations(range(4),2):
                if abs(j[i,a]-j[i,b])>1e-8:pairwise.append(np.sign(pp[n,a]-pp[n,b])==np.sign(j[i,a]-j[i,b]))
        selected=[action_index[rows[i]['selected']] for i in ix]
        metrics[split]=dict(parents=len(ix),qualified_selected=int(sum(qual[i,a] for i,a in zip(ix,selected))),selected_actions=[rows[i]['selected'] for i in ix],direct_actions=[rows[i]['direct_argmin'] for i in ix],delta_J_RMSE_N_s=float(np.sqrt(np.mean((pp-truth)**2))),pairwise_force_ranking_accuracy=float(np.mean(pairwise)),qualified_regret_mean_N_s=float(np.mean([rows[i]['regret_N_s'] for i in ix if rows[i]['regret_N_s'] is not None])) if any(rows[i]['regret_N_s'] is not None for i in ix) else None,fixed_H150_qualified=int(np.sum(qual[ix,0])),fixed_global_action=frozen['global_action'],fixed_global_qualified=int(np.sum(qual[ix,fixed_index])),state_conditioned_selected=len(set(rows[i]['selected'] for i in ix))>1,all_force_best_actions=[ACTIONS[int(np.argmin(j[i]))] for i in ix])
    test=[r for r in rows if r['split']=='test'];testix=np.flatnonzero(splits=='test')
    gain_pass=bool(test and all(r['selection_qualified'] and r['improvement_vs_H150_N_s'] is not None and r['improvement_vs_H150_N_s']>.01 for r in test))
    nonconstant=len(set(r['selected'] for r in test))>1
    fixed_better=all(qual[i,action_index[rows[i]['selected']]] and (not qual[i,fixed_index] or j[i,action_index[rows[i]['selected']]]<j[i,fixed_index]-.01) for i in testix)
    # State permutation diagnostic uses only the already frozen model. No retraining or policy changes.
    permutation=[]
    for k,i in enumerate(testix):
        swapped=select(next(r['state'] for r in ds['records'] if r['parent']==str(groups[testix[(k+1)%len(testix)]]) and r['proposed_action']['id']=='H150'))
        permutation.append(dict(parent=str(groups[i]),original=rows[i]['selected'],permuted_state_selection=swapped['selected'],direct_original=rows[i]['direct_argmin'],direct_permuted=swapped['direct_Q_argmin']))
    result=dict(status='COMPLETED',CONTROL_BASELINE_PASS='see FROZEN_CONTROL_BASELINE.md: specified conditions only',LEARNING_DATA_READY=True,Q_TRAINED=True,Q_GENERALIZATION_PASS=bool(gain_pass and nonconstant and fixed_better),FEW_REPETITION_LEARNING_PASS=False,RL_BASELINE_TRAINED=False,RL_BASELINE_QUALIFIED=False,metrics=metrics,rows=rows,factorial_response=factorial,permuted_state_diagnostic=permutation,model_sha256=frozen['model_sha256'],force_gain_gate= gain_pass,nonconstant_selection_gate=nonconstant,better_than_global_fixed_gate=bool(fixed_better),interpretation='Explicit state-action coefficients alone do not establish useful state-dependent ranking. Apply all qualification and comparison gates.',same_Human=True,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',new_test_policy_runs=len(test))
    put('LEARNING_RESULTS.json',result)
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for a in range(1,4):
        axs[0].plot(groups,j[:,a]-j[:,0],marker='o',label=ACTIONS[a]+' minus H150')
        for i in range(len(groups)):
            if not qual[i,a]:axs[0].scatter(i,j[i,a]-j[i,0],color='red',marker='x',s=65)
    axs[0].axhline(0,c='black',lw=.7);axs[0].set_ylabel('Full-task force cost difference (N s)');axs[0].tick_params(axis='x',rotation=45);axs[0].legend(fontsize=8)
    for split,color in [('train','#7f7f7f'),('validation','#e69f00'),('test','#0072b2')]:
        ix=np.flatnonzero(splits==split);actual=(j[ix]-j[ix,0,None]).ravel();predicted=np.array([all_outputs[i]['predicted_delta_J_F_N_s'] for i in ix]).ravel();axs[1].scatter(actual,predicted,label=split,c=color,alpha=.8)
    lim=max(1.,float(np.max(abs(j-j[:,[0]]))))*1.1;axs[1].plot([-lim,lim],[-lim,lim],ls=':',c='black');axs[1].set_xlabel('Actual full-task difference from H150 (N s)');axs[1].set_ylabel('Frozen Q predicted difference (N s)');axs[1].legend()
    for ax in axs:ax.grid(alpha=.25)
    fig.savefig(P/'figures/04_Q_prediction_actual.png',dpi=170);plt.close(fig)
    print('LEARNING_EVALUATED',json.dumps(metrics['test']),flush=True)
if __name__=='__main__':main()
