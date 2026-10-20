"""Train only on grouped development parents; validation chooses regularization."""
from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from dataset import P,put,read,ACTIONS
from value_model import fit,predict,choose
def main():
    started=time.time()
    assert not (P/'models/VALUE_FREEZE.json').exists(),'MODEL_ALREADY_FROZEN'
    plan=read(P/'RUN_PLAN.json');assert time.time()<plan['no_new_physics_after_unix']
    d=np.load(P/'derived/DATASET_development.npz');x=d['X'];j=d['J'];m=d['M'];qualified=d['qualified'];groups=d['groups'];splits=d['splits']
    assert set(splits)<=set(['train','validation']) and not any(str(g).startswith('U') for g in groups)
    train=np.flatnonzero(splits=='train');val=np.flatnonzero(splits=='validation');delta=j-j[:,[0]]
    search=[];models={}
    global_delta=delta[train].mean(0)
    globally_qualified=np.flatnonzero(np.all(qualified[train],axis=0))
    global_a=int(globally_qualified[np.argmin(global_delta[globally_qualified])]) if len(globally_qualified) else 0
    put('models/GLOBAL_FIXED_BASELINE.json',dict(action=ACTIONS[global_a],fully_qualified_on_all_train_exists=bool(len(globally_qualified)),fully_qualified_actions=[ACTIONS[i] for i in globally_qualified],rule='min mean full cost among actions qualified on every train parent; otherwise H150 is only a reference fallback, not a globally qualified winner',mean_delta_cost_diagnostic=global_delta))
    for alpha in [.1,1.,10.,100.]:
        cost=fit(x[train],delta[train],alpha);margin=fit(x[train],m[train],alpha)
        loo_c=[];loo_m=[]
        for i in train:
            ids=train[train!=i];loo_c.append(abs(predict(fit(x[ids],delta[ids],alpha),x[i])[0]-delta[i]));loo_m.append(abs(predict(fit(x[ids],m[ids],alpha),x[i])[0]-m[i]))
        ce=np.max(loo_c,axis=0);me=np.max(loo_m,axis=0)
        cp=predict(cost,x[val]);mp=predict(margin,x[val]);selected=np.array([choose(c,q,ce,me) for c,q in zip(cp,mp)])
        ztrain=(x[train]-cost['mu'])/cost['sd'];dist=np.linalg.norm(ztrain[:,None]-ztrain[None,:],axis=-1);np.fill_diagonal(dist,np.inf)
        radius=float(np.max(np.min(dist,axis=1)))
        query=(x[val]-cost['mu'])/cost['sd'];nearest=np.min(np.linalg.norm(query[:,None]-ztrain[None,:],axis=-1),axis=1)
        selected[nearest>radius]=0
        bad=int(np.sum(~qualified[val,selected]));regrets=[]
        for ii,a in zip(val,selected):
            good=j[ii][qualified[ii]]
            regrets.append(None if not qualified[ii,a] or not len(good) else float(j[ii,a]-good.min()))
        valid_regret=sum(v for v in regrets if v is not None)/max(1,sum(v is not None for v in regrets))
        rmse=float(np.sqrt(np.mean((cp-delta[val])**2)))
        row=dict(alpha=alpha,failed_selected=bad,mean_qualified_regret_N_s=valid_regret,delta_cost_rmse_N_s=rmse,selected=[ACTIONS[a] for a in selected],direct_argmin=[ACTIONS[a] for a in cp.argmin(1)],loo_max_error_N_s=ce.tolist())
        search.append(row);models[alpha]=(cost,margin,ce,me)
    selected=min(search,key=lambda r:(r['failed_selected'],r['mean_qualified_regret_N_s'],r['delta_cost_rmse_N_s'],r['alpha']))
    alpha=selected['alpha'];cost,margin,ce,me=models[alpha]
    # Model remains trained on train only. Validation data never merged after selection.
    standardized=(x[train]-cost['mu'])/cost['sd'];dist=np.linalg.norm(standardized[:,None,:]-standardized[None,:,:],axis=-1);np.fill_diagonal(dist,np.inf);support=float(np.max(np.min(dist,axis=1)))
    out=P/'models/Q_value_ridge.npz'
    np.savez_compressed(out,cost_mu=cost['mu'],cost_sd=cost['sd'],cost_w=cost['w'],margin_mu=margin['mu'],margin_sd=margin['sd'],margin_w=margin['w'],margin_shape=np.array(margin['shape']),cost_error=ce,margin_error=me,train_x=x[train],support_radius=support,global_delta=global_delta,global_action=global_a,alpha=alpha,actions=np.array(ACTIONS))
    put('models/VALUE_FREEZE.json',dict(status='Q_TRAINED',algorithm='contextual terminal Monte Carlo Q/cost regression; gamma=0 at full-task terminal, no multi-step Q-learning claim',training_parents=groups[train].tolist(),validation_parents=groups[val].tolist(),test_parents_not_read=['U01','U02','U03'],hyperparameters=search,selected_alpha=alpha,training_rows=int(len(train)*len(ACTIONS)),state_dimensions=x.shape[1],state_rank=int(np.linalg.matrix_rank(x[train]-x[train].mean(0))),explicit_state_action_interaction=True,model_file='models/Q_value_ridge.npz',model_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),dataset_sha256=hashlib.sha256((P/'derived/DATASET_development.npz').read_bytes()).hexdigest(),force_error_buffer=ce,margin_error_buffer=me,support_radius=support,global_action=ACTIONS[global_a],frozen_unix=time.time(),inference_fallback='H150 when no evidence, outside support, or no certified proposal; H150 itself not universally motion-qualified'))
    put('models/TRAINING_CODE_MANIFEST.json',dict(files={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),Path(__file__).with_name('dataset.py'),Path(__file__).with_name('value_model.py')]},execution_manifest_sha256=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST_v2.json').read_bytes()).hexdigest(),seed=None,deterministic_closed_form=True,optimizer_updates='closed-form ridge solves; includes leave-one-parent-out and validation model selection',ridge_solve_count=2*(1+len(train))*4,started_unix=started,finished_unix=time.time(),wall_seconds=time.time()-started,new_physical_starts=0))
    print('VALUE_TRAINED',json.dumps(selected),flush=True)
if __name__=='__main__':main()
