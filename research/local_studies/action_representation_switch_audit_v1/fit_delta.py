from common import *
def run():
    lock();resources('OFFLINE_FIT');spec=json.loads((BC/'PREREGISTRATION.json').read_text());z=np.load(O/'REPRESENTATION_LABELS.npz')
    x=z['observations'];y=z['R2'];absolute=z['R1'];ph=z['phase'];prev=x[:,49:51];ti=np.array(spec['split']['train_indices']);vi=np.array(spec['split']['validation_indices'])
    groups=[ti[ph[ti]==p] for p in ('OUTBOUND','HOLD','RETURN')];device='cuda' if torch.cuda.is_available() else 'cpu';xt=torch.tensor(x,device=device);yt=torch.tensor(y,device=device)
    def balanced(pred,ids):return float(np.mean([np.mean((pred[ids[ph[ids]==p]]-y[ids[ph[ids]==p]])**2) for p in ('OUTBOUND','HOLD','RETURN')]))
    results=[];begin=time.monotonic()
    for seed in spec['seeds']:
        a=actor(seed,device);a.train();opt=torch.optim.Adam([p for p in a.parameters() if p.requires_grad],lr=spec['optimizer']['learning_rate']);rng=np.random.default_rng(seed+1000)
        best=float('inf');significant=float('inf');last=0;best_state=None;curve=[];stop='EPOCH_CAP';start=time.monotonic()
        for epoch in range(1,spec['budget']['max_epochs']+1):
            for _ in range(spec['sampling']['batches_per_epoch']):
                ids=np.concatenate([rng.choice(g,size=96,replace=True) for g in groups]);rng.shuffle(ids)
                loss=torch.mean((a(xt[ids],deterministic=True)-yt[ids])**2);opt.zero_grad(set_to_none=True);loss.backward();opt.step()
            if epoch%20:continue
            a.eval()
            with torch.no_grad():pred=a(xt,deterministic=True).cpu().numpy()
            a.train();val=balanced(pred,vi);train=balanced(pred,ti)
            curve.append(dict(epoch=epoch,train_MSE=train,validation_MSE=val,full_MSE=np.mean((pred-y)**2),elapsed_s=time.monotonic()-start))
            if val<best:best=val;best_epoch=epoch;best_state={k:v.detach().cpu().clone() for k,v in a.state_dict().items()}
            if val<significant-spec['budget']['balanced_validation_mse_min_delta']:significant=val;last=epoch
            if epoch%500==0:print(json.dumps(dict(representation='R2',seed=seed,epoch=epoch,train_MSE=train,val_MSE=val)),flush=True)
            if epoch>=spec['budget']['min_epochs'] and epoch-last>=spec['budget']['early_stopping_patience_epochs']:stop='VALIDATION_PLATEAU';break
            if time.monotonic()-begin>spec['budget']['training_total_wall_s']:stop='TOTAL_TRAINING_WALL_CAP';break
        a.load_state_dict(best_state);a.eval()
        with torch.no_grad():pred=a(xt,deterministic=True).cpu().numpy()
        decoded=np.clip(prev+2*pred,-1,1);wins={}
        for radius in (0,1,2,5):
            ids=np.arange(75-radius,76+radius);wins[str(radius)]=dict(native=error(pred[ids],y[ids]),decoded_absolute=error(decoded[ids],absolute[ids]))
        result=dict(seed=seed,representation='R2_DELTA_PREVIOUS_RAW',epochs=epoch,best_epoch=best_epoch,stop=stop,elapsed_s=time.monotonic()-start,full_native=error(pred,y),full_decoded_absolute=error(decoded,absolute),decoded_degree_MAE=62.5*error(decoded,absolute)['MAE'],decoded_degree_RMSE=62.5*error(decoded,absolute)['RMSE'],train_native=error(pred[ti],y[ti]),validation_native=error(pred[vi],y[vi]),switch_windows=wins,per_phase={p:dict(native=error(pred[ph==p],y[ph==p]),decoded_absolute=error(decoded[ph==p],absolute[ph==p])) for p in np.unique(ph)},checkpoint_context='offline representation learnability only; never deployed; teacher forcing previous-raw feature from original trajectory; autonomous history errors untested')
        torch.save(dict(state_dict=best_state,seed=seed,representation='R2_DELTA_PREVIOUS_RAW',best_epoch=best_epoch),O/f'DELTA_actor_seed_{seed}.pt')
        np.savez_compressed(O/f'DELTA_PREDICTIONS_seed_{seed}.npz',predictions=pred,labels=y,decoded_absolute=decoded,absolute_labels=absolute)
        save(f'DELTA_LOSS_seed_{seed}.json',curve);results.append(result);save('DELTA_FIT_RESULTS.json',results)
        print(json.dumps(clean(dict(seed=seed,epochs=epoch,native=result['full_native'],decoded=result['full_decoded_absolute']))),flush=True)
    save('FIT_COMPARISON.json',dict(R1='read-only existing three validation-selected BC checkpoints; exact same original architecture/split/seeds/hyperparameters',R2=results,R3='SKIPPED_NO_EQUIVALENT_DEPLOYABLE_SAFE_ADAPTER',hyperparameter_search=False,SAC_steps=0,validation='correlated single-trajectory interpolation, already exposed; no independent robustness or control claim',total_fit_wall_s=time.monotonic()-begin))
    lock()
if __name__=='__main__':run()
