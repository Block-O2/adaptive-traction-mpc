"""E2 SOURCE_ONLY pure numerical definitions. No NumPy import/calls on import.

Only separately approved fit_e2_candidate_v1 supplies np, data and work budget.
Paired heads are delta14/deltaJF/deltaJM, never norm(delta-wrench) costs.
"""
import hashlib
import json


def need(test,reason):
    if not test:raise ValueError(reason)


def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def ridge_design(z,actions,kind,np):
    if kind=='RIDGE_ACTION_BLIND39':return np.c_[np.ones(len(z)),z]
    one=np.eye(5)[actions]
    if kind=='RIDGE_ACTION_ONLY':return one
    if kind=='RIDGE_PAIRED':one=one[:,1:]
    return np.c_[one,(one[:,:,None]*z[:,None,:]).reshape(len(z),-1)]


def fit_ridge(design,target,*,paired,work,label,np):
    work.guard();need(design.ndim==target.ndim==2 and len(design)==len(target) and design.shape[1]<=200 and target.shape[1]==16,'E2_RIDGE_SHAPE')
    center=np.zeros(16) if paired else target.mean(axis=0);scale=target.std(axis=0);scale=np.where(scale<1e-9,1.,scale)
    work.c['matrix_solve_attempts']+=1;work.c['scalar_head_solutions_attempted']+=16;work.c['linear_design_training_rows']+=len(design)
    need(work.c['matrix_solve_attempts']<=704,'E2_NO_ADDITIONAL_RIDGE_FITS')
    work.event('RIDGE_SOLVE_START',label=label,dimension=design.shape[1],heads=16,train_rows=len(design))
    weights=np.linalg.solve(design.T@design+10.*np.eye(design.shape[1]),design.T@((target-center)/scale))
    need(np.all(np.isfinite(weights)),'E2_NONFINITE_RIDGE');work.c['matrix_solve_successes']+=1
    model=dict(weights=weights.tolist(),target_center=center.tolist(),target_scale=scale.tolist(),ridge_alpha=10.,paired=paired)
    work.event('RIDGE_SOLVE_RETURN',label=label,model_sha256=digest(model));return model


def predict_knots(design,model,work,np):
    work.prediction('RIDGE_KNOT_MATRIX',len(design))
    answer=design@np.asarray(model['weights'])*np.asarray(model['target_scale'])+np.asarray(model['target_center'])
    need(np.all(np.isfinite(answer)),'E2_NONFINITE_KNOT');return answer


def interpolate_knots(times,knots,predictions,work,np):
    """Piecewise linear; last-interval extrapolation is explicit, never clip."""
    work.prediction('KNOTWISE_INTERPOLATION',len(times))
    segment=np.clip(np.searchsorted(knots,times,side='right')-1,0,len(knots)-2)
    fraction=(times-knots[segment])/(knots[segment+1]-knots[segment])
    return predictions[segment]*(1.-fraction[:,None])+predictions[segment+1]*fraction[:,None]


def nn_inputs(z,actions,times,action_only,np):
    one=np.eye(5)[actions];u=np.asarray(times,float)[:,None]/20.
    return np.c_[one,u] if action_only else np.c_[z,one,u]


def forward(inputs,parameters,work,np,*,training,branch_B=False):
    work.guard()
    if training:
        work.c['network_training_forward_API_calls']+=1;work.c['network_training_forward_query_vectors']+=len(inputs)
        if branch_B:work.c['shared_B_training_forward_API_calls']+=1
    else:
        work.prediction('NEURAL_FORWARD_B' if branch_B else 'NEURAL_FORWARD_A',len(inputs))
        if branch_B:work.c['shared_B_inference_forward_API_calls']+=1
    h=np.tanh(inputs@parameters['W1']+parameters['b1']);out=h@parameters['W2']+parameters['b2']
    need(np.all(np.isfinite(out)),'E2_NONFINITE_FORWARD');return out,(inputs,h)


def backward(cache,grad_output,parameters,work,np,*,branch_B=False):
    work.guard();work.c['network_backward_API_calls']+=1;work.c['network_backward_query_vectors']+=len(grad_output)
    if branch_B:work.c['shared_B_backward_API_calls']+=1
    inputs,h=cache;hidden=(grad_output@parameters['W2'].T)*(1.-h*h)
    return dict(W1=inputs.T@hidden,b1=hidden.sum(axis=0),W2=h.T@grad_output,b2=grad_output.sum(axis=0))


def fit_mlp(z,actions,times,target,initial16,*,kind,work,label,np):
    """200 fixed Adam steps; paired network has two paid shared branches."""
    work.guard();work.c['neural_initialization_attempts']+=1
    need(work.c['neural_initialization_attempts']<=66,'E2_NEURAL_INITIALIZATION_ATTEMPT_CAP')
    paired=kind=='MLP_PAIRED';action_only=kind=='MLP_ACTION_ONLY';inputs=nn_inputs(z,actions,times,action_only,np)
    baseline=np.zeros_like(target) if paired else initial16
    transformed=(target-baseline)/(np.asarray(times)[:,None]/20.)
    center=np.zeros(16) if paired else transformed.mean(axis=0);scale=transformed.std(axis=0);scale=np.where(scale<1e-9,1.,scale);truth=(transformed-center)/scale
    rng=np.random.default_rng(0);d=inputs.shape[1]
    parameters=dict(W1=rng.normal(0.,(2./d)**.5,(d,16)),b1=np.zeros(16),W2=rng.normal(0.,(2./16)**.5,(16,16)),b2=np.zeros(16))
    init_sha=digest({k:v.tolist() for k,v in parameters.items()});work.c['neural_initializations']+=1
    need(work.c['neural_initializations']<=66,'E2_NO_EXTRA_SEED_MODELS')
    first={k:np.zeros_like(v) for k,v in parameters.items()};second={k:np.zeros_like(v) for k,v in parameters.items()}
    state=dict(label=label,kind=kind,initial_weights_sha256=init_sha,parameters=parameters,adam_first=first,adam_second=second,completed_steps=0)
    work.current_neural_state=state;work.event('NEURAL_INITIALIZE',label=label,parameters=sum(v.size for v in parameters.values()),initial_weights_sha256=init_sha)
    B_inputs=nn_inputs(z,np.zeros(len(actions),int),times,action_only,np) if paired else None
    for step in range(1,201):
        work.guard();work.c['gradient_update_attempts']+=1;need(work.c['gradient_update_attempts']<=13200,'E2_UPDATE_CAP')
        work.event('GRADIENT_STEP_START',label=label,step=step)
        batch=rng.integers(0,len(inputs),size=128);a,cache=forward(inputs[batch],parameters,work,np,training=True)
        if paired:b,Bcache=forward(B_inputs[batch],parameters,work,np,training=True,branch_B=True);prediction=a-b
        else:prediction=a
        error=prediction-truth[batch];loss=float(np.mean(error*error));derivative=2.*error/error.size
        gradient=backward(cache,derivative,parameters,work,np)
        if paired:
            other=backward(Bcache,-derivative,parameters,work,np,branch_B=True)
            gradient={k:gradient[k]+other[k] for k in gradient}
        norm=float(np.sqrt(sum(np.sum(g*g) for g in gradient.values())))
        need(np.isfinite(loss) and np.isfinite(norm),'E2_NONFINITE_LOSS_OR_GRADIENT');clip=min(1.,5./max(norm,1e-300))
        for key in parameters:
            g=gradient[key]*clip;first[key]=.9*first[key]+.1*g;second[key]=.999*second[key]+.001*g*g
            parameters[key]-=.003*(first[key]/(1.-.9**step))/(np.sqrt(second[key]/(1.-.999**step))+1e-8)
            need(np.all(np.isfinite(parameters[key])),'E2_NONFINITE_ADAM_STEP')
        work.c['parameter_gradient_updates']+=1;state.update(completed_steps=step,adam_first=first,adam_second=second)
        work.event('GRADIENT_STEP_RETURN',label=label,step=step,normalized_16head_loss=loss,raw_gradient_norm=norm,gradient_clip=clip)
    model=dict(kind=kind,paired=paired,action_only=action_only,parameters={k:v.tolist() for k,v in parameters.items()},target_center=center.tolist(),target_scale=scale.tolist(),initial_weights_sha256=init_sha,
               optimizer=dict(kind='ADAM',step=200,learning_rate=.003,betas=[.9,.999],epsilon=1e-8,gradient_clip_norm=5.,first={k:v.tolist() for k,v in first.items()},second={k:v.tolist() for k,v in second.items()}),
               training_loss_semantics='equal standardized16head MSE, not a JF/JM policy reward',seed=0,hidden=16)
    work.current_neural_state=None;return model


def predict_mlp(z,actions,times,initial16,model,work,np):
    parameters={k:np.asarray(v) for k,v in model['parameters'].items()};inputs=nn_inputs(z,actions,times,model['action_only'],np)
    a,_=forward(inputs,parameters,work,np,training=False)
    if model['paired']:
        Binputs=nn_inputs(z,np.zeros(len(actions),int),times,model['action_only'],np);b,_=forward(Binputs,parameters,work,np,training=False,branch_B=True);answer=(a-b)*np.asarray(model['target_scale'])*np.asarray(times)[:,None]/20.
    else:answer=initial16+(a*np.asarray(model['target_scale'])+np.asarray(model['target_center']))*np.asarray(times)[:,None]/20.
    need(np.all(np.isfinite(answer)),'E2_NONFINITE_MLP_CURVE');return answer
