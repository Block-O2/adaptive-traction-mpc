"""Pure frozen C3B inference: no reads, writes, fit, native state, or physics."""
import numpy as np
from trial_interface import feature_vector


def design(context, action_index, kind):
    one=np.zeros(3);one[action_index]=1.
    z=np.asarray(context,float)
    if kind=='ACTION_ONLY':return one
    if kind=='HISTORY_ADDITIVE':return np.r_[one,z]
    if kind in ('HISTORY_INTERACTION','COMMISSIONED25_INTERACTION'):
        return np.r_[one,z,np.outer(z,one[1:]).ravel()]
    raise ValueError('UNKNOWN_MODEL_KIND')


def select(snapshot, *, history=None, commissioned25=None,
           model_id='HISTORY_INTERACTION', history_disabled=False,
           expected_recipe_hashes=None):
    if snapshot.get('schema')!='v8.c3b.frozen_relative_recipe.v1':
        raise ValueError('FROZEN_MODEL_SCHEMA')
    if expected_recipe_hashes is not None and expected_recipe_hashes!=snapshot['recipe_hashes']:
        raise ValueError('FROZEN_RECIPE_PERMISSION_MISMATCH')
    if model_id=='HISTORY_DISABLED':
        model_id='HISTORY_INTERACTION';history_disabled=True
    model=snapshot['models'][model_id]
    if model_id=='ACTION_ONLY':
        z=np.zeros(0)
    elif history_disabled:
        if history is not None:
            raise ValueError('DISABLED_POLICY_MUST_NOT_RECEIVE_CURRENT_HISTORY')
        z=np.zeros(len(model['mean']))
    else:
        if model_id=='COMMISSIONED25_INTERACTION':
            if commissioned25 is None or len(commissioned25)!=25:
                raise ValueError('COMMISSIONED25_REQUIRED')
            v=np.asarray(commissioned25,float)
        else:
            if history is None:raise ValueError('COMPLETED_CAUSAL_HISTORY_REQUIRED')
            names,values=feature_vector(history)
            if names!=snapshot['history_feature_names']:
                raise ValueError('HISTORY_FEATURE_ORDER_MISMATCH')
            v=np.asarray(values,float)
        if not np.all(np.isfinite(v)):raise ValueError('NONFINITE_CONTEXT')
        z=(v-np.asarray(model['mean']))/np.asarray(model['scale'])
    x=np.array([design(z,i,model_id) for i in range(3)])
    pred=x@np.asarray(model['weights'])
    paired=pred[:,:2]-pred[0,:2]
    probabilities=np.clip(pred[:,2],0.,1.)
    eligible=probabilities>=.5;eligible[0]=True
    chosen=int(np.argmin(np.where(eligible,paired[:,0],np.inf)))
    return dict(selected_index=chosen,selected_tag=snapshot['actions'][chosen],
        selected_recipe_sha256=snapshot['recipe_hashes'][chosen],
        model_id=model_id,history_disabled=history_disabled,
        normalized_context=z.tolist(),
        paired_JF_prediction_N_s=paired[:,0].tolist(),
        paired_JM_prediction_Nm_s=paired[:,1].tolist(),
        predicted_qualification=probabilities.tolist(),eligible=eligible.tolist(),
        predicted_margin=(pred[:,3].tolist() if pred.shape[1]>3 else None),
        unconstrained_mean_best_tag=snapshot['actions'][int(np.argmin(paired[:,0]))],
        qualification_probability_calibrated=False,original_gates_replaced=False,
        scope='COLD_REPLAY_HISTORY_CONDITIONED_SELECTION_NOT_PERSISTENT_TRIAL_ADAPTATION',
        current_history_sha256=None if history is None else history['history_sha256'])
