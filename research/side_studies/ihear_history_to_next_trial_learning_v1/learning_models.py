"""Small-data constrained GP and explicit history x action ridge ensemble.
Inputs are completed causal histories and previously executed development labels.
No plant, evaluation-native arrays, or current patient's future labels are read.
"""
from pathlib import Path
import json,hashlib,math
import numpy as np
from scipy.special import ndtr
import history_features as hf
SELECTED=[2,3,4,5]
def phi(z,a):
    z=np.asarray(z);a=np.asarray(a)
    return np.r_[1.,z,a,a*a,np.outer(z,a).ravel()]
def kernel(x,y,length=2.):
    x=np.asarray(x);y=np.asarray(y)
    return np.exp(-.5*np.sum((x[:,None,:]-y[None,:,:])**2,axis=2)/length**2)
def gp(x,y,test,noise=.1,scale=1.):
    k=scale**2*kernel(x,x)+np.eye(len(x))*noise**2
    cross=scale**2*kernel(test,x);prior=scale**2*np.ones(len(test))
    mean=cross@np.linalg.solve(k,y)
    var=np.maximum(prior-np.sum(cross*np.linalg.solve(k,cross.T).T,axis=1),1e-12)
    return mean,np.sqrt(var)
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def select(root,method,history,enabled=True):
    root=Path(root);freeze=json.loads((root/'models/METHOD_FREEZE.json').read_text())
    for name,h in freeze['model_files'].items():assert sha(root/name)==h,'MODEL_IDENTITY_CHANGED'
    weights=np.load(root/'models/history_models.npz');mu=weights['history_mean'];sd=weights['history_std']
    assert (history is not None) if enabled else (history is None), 'DISABLED_POLICY_MUST_NOT_RECEIVE_HISTORY'
    z=(np.array(history['features'])[SELECTED]-mu)/sd if enabled else np.zeros(len(SELECTED))
    actions=hf.grid();a=np.array([hf.encode_action(v) for v in actions]);zq=np.tile(z,(len(a),1))
    query=np.c_[zq,a];X=weights['gp_X'];cost=weights['gp_y_cost'];margin=weights['gp_y_margin']
    applicable=bool(np.max(abs(z))<=3.)
    all_pred=[]
    if method=='BO':
        # The only current-patient observation is the actual previous B trial.
        # Its centered cost is J_F(B,trial1)-J_F(B,trial1)=0, not an observed Trial2 reward.
        # Fixed noise includes measured development repeat-state drift; report this stationarity assumption.
        if enabled:
            Xc=np.vstack([X,np.r_[z,0.,0.]]);yc=np.r_[cost,0.]
        else:Xc=X;yc=cost
        pred,unc=gp(Xc,yc,query,noise=float(weights['gp_noise_cost']),scale=float(weights['gp_scale_cost']))
        mp,ms=gp(X,margin,query,noise=.02,scale=.2)
        p_motion=ndtr(mp/np.maximum(ms,.005))
        # Separate executability estimate, with Beta(1,1) smoothing on actual action outcomes.
        p_task=np.array([(1+np.sum(weights['execution_success'][np.all(weights['gp_A']==v,axis=1)]))/(2+np.sum(np.all(weights['gp_A']==v,axis=1))) for v in a])
        improvement=-pred-.01;u=improvement/np.maximum(unc,1e-9)
        ei=improvement*ndtr(u)+unc*np.exp(-.5*u*u)/np.sqrt(2*np.pi)
        allowed=(p_motion>=.8)&(mp-ms>=0)&(p_task>=.7)&applicable
        acquisition=ei*p_motion*p_task;acquisition[~allowed]=-np.inf;acquisition[0]=0.
        chosen=int(np.argmax(acquisition))
        if not np.isfinite(acquisition[chosen]) or acquisition[chosen]<=.01:chosen=0
        for i in range(len(a)):
            all_pred.append(dict(action=actions[i],predicted_cost_delta_from_trial1_N_s=float(pred[i]),uncertainty_N_s=float(unc[i]),
                predicted_motion_margin=float(mp[i]),motion_uncertainty=float(ms[i]),p_motion=float(p_motion[i]),p_execution=float(p_task[i]),
                acquisition_EI=float(ei[i]),constrained_acquisition=None if not np.isfinite(acquisition[i]) else float(acquisition[i]),eligible=bool(allowed[i])))
        update=dict(actual_previous_action='B',observed_previous_complete_JF_N_s=history['JF_N_s'] if enabled else None,
            current_patient_observations_added=1 if enabled else 0,unexecuted_actions_assigned_rewards=0,
            assumption='previous trial is a noisy local action-cost observation; continuous initial-state drift covered only empirically',
            exploration_budget='one conservative proposal per patient per repetition')
    elif method=='VALUE':
        features=np.array([phi(z,v) for v in a]);ensemble=weights['ridge_ensemble']
        estimates=np.einsum('af,efh->eah',features,ensemble)
        mean=estimates.mean(axis=0);spread=estimates.std(axis=0)
        pred=mean[:,0];unc=np.maximum(spread[:,0],float(weights['value_cost_error_floor']))
        mp=mean[:,1];ms=np.maximum(spread[:,1],float(weights['value_margin_error_floor']))
        ep=np.clip(mean[:,2],0,1);allowed=(mp-ms>=0)&(ep>=.8)&applicable
        # Compare predicted within-context action advantages, not absolute offsets.
        conservative=pred+unc;score=np.where(allowed,conservative,np.inf);score[0]=pred[0]
        chosen=int(np.argmin(score))
        if chosen!=0 and pred[0]-score[chosen]<.01:chosen=0
        for i in range(len(a)):
            all_pred.append(dict(action=actions[i],predicted_cost_delta_from_trial1_N_s=float(pred[i]),uncertainty_N_s=float(unc[i]),
                predicted_motion_margin=float(mp[i]),motion_uncertainty=float(ms[i]),p_execution=float(ep[i]),eligible=bool(allowed[i]),
                evidence='regularized regression/leave-patient-out ensemble; probabilities uncalibrated'))
        update=dict(offline_trained=True,online_parameter_updates=0,context_update=enabled,explicit_history_action_interactions=True)
    else:raise ValueError(method)
    prior=float(history['JF_N_s']) if enabled else float(weights['mean_first_JF'])
    for p in all_pred:p['predicted_full_JF_N_s']=prior+p['predicted_cost_delta_from_trial1_N_s']
    return dict(method=method if enabled else method+'_DISABLED',history_enabled=enabled,action=actions[chosen],
        predictions=all_pred,update=update,applicable=applicable,history_z=z.tolist(),model_sha256=sha(root/'models/history_models.npz'),
        method_freeze_sha256=sha(root/'models/METHOD_FREEZE.json'),data_status='DATA_LIMITED',independent_training_patients=int(weights['training_patients']),
        selected_index=chosen,model_updates=1 if method=='BO' and enabled else 0)
