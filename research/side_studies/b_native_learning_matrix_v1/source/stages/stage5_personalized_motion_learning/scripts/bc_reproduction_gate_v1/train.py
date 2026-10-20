from common import *
import csv

def run():
    check_lock(); assert read('TEACHER_REPRODUCTION.json')['status']=='PASS'; resource('TRAINING')
    spec=read('PREREGISTRATION.json'); z=np.load(DEMO); phases=z['phase']; begin=time.monotonic()
    device='cuda' if torch.cuda.is_available() else 'cpu'
    x=torch.tensor(z['observations'],device=device); y=torch.tensor(z['actions'],device=device)
    ti=np.array(spec['split']['train_indices']); vi=np.array(spec['split']['validation_indices'])
    groups=[ti[phases[ti]==p] for p in ('OUTBOUND','HOLD','RETURN')]
    def balanced(pred,indices):
        return float(np.mean([np.mean((pred[indices[phases[indices]==p]]-z['actions'][indices[phases[indices]==p]])**2) for p in ('OUTBOUND','HOLD','RETURN')]))
    results=[]
    for seed in spec['seeds']:
        actor=make_actor(seed,device); actor.train(); initial={k:v.detach().cpu().clone() for k,v in actor.state_dict().items()}
        optimizer=torch.optim.Adam([p for p in actor.parameters() if p.requires_grad],lr=spec['optimizer']['learning_rate'])
        assert len(optimizer.state)==0
        rng=np.random.default_rng(seed+1000); best=float('inf'); significant=float('inf'); last_improved=0; curve=[]; best_state=None
        folder=O/f'seed_{seed}'; folder.mkdir(exist_ok=False)
        start=time.monotonic(); stop_reason='EPOCH_CAP'
        for epoch in range(1,spec['budget']['max_epochs']+1):
            for batch in range(spec['sampling']['batches_per_epoch']):
                ids=np.concatenate([rng.choice(g,size=96,replace=True) for g in groups]); rng.shuffle(ids)
                pred=actor(x[ids],deterministic=True); loss=torch.mean((pred-y[ids])**2)
                optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
                assert all(p.grad is None for p in actor.log_std.parameters())
            if epoch%20: continue
            actor.eval()
            with torch.no_grad(): pred=actor(x,deterministic=True).cpu().numpy()
            actor.train()
            train=balanced(pred,ti); val=balanced(pred,vi)
            curve.append(dict(epoch=epoch,train_balanced_MSE=train,validation_balanced_MSE=val,full_MSE=float(np.mean((pred-z['actions'])**2)),elapsed_s=time.monotonic()-start))
            if val<best:
                best=val; best_epoch=epoch; best_state={k:v.detach().cpu().clone() for k,v in actor.state_dict().items()}
            if val<significant-spec['budget']['balanced_validation_mse_min_delta']:
                significant=val;last_improved=epoch
            if epoch%500==0: print(json.dumps(dict(seed=seed,epoch=epoch,train_MSE=train,val_MSE=val,elapsed_s=time.monotonic()-start)),flush=True)
            if epoch>=1000 and epoch-last_improved>=600: stop_reason='VALIDATION_PLATEAU';break
            if time.monotonic()-begin>spec['budget']['training_total_wall_s']: stop_reason='TOTAL_TRAINING_WALL_CAP';break
        assert best_state is not None
        for k in initial:
            if k.startswith('log_std.'): assert torch.equal(initial[k],best_state[k])
        actor.load_state_dict(best_state); actor.eval()
        checkpoint=dict(state_dict=best_state,seed=seed,best_epoch=best_epoch,architecture=spec['architecture'],preregistration_sha256=sha(D/'PREREGISTRATION.json'),teacher_sha256=sha(DEMO),normalization_hash=read('SCIENTIFIC_LOCK.json')['normalization_hash'],inherited_weights=False,critic_exists=False,optimizer_saved=False)
        torch.save(checkpoint,folder/'actor.pt'); shutil.copy2(folder/'actor.pt',L/f'actor_seed_{seed}.pt')
        with torch.no_grad(): pred=actor(x,deterministic=True).cpu().numpy()
        cpu=make_actor(seed);cpu.load_state_dict(best_state);cpu.eval()
        with torch.no_grad(): cp=cpu(torch.tensor(z['observations']),deterministic=True).numpy()
        np.testing.assert_allclose(pred,cp,atol=2e-6,rtol=0)
        # Verify native .predict applies the same identity scaling used for evaluation.
        public,_=cpu.predict(z['observations'],deterministic=True)
        np.testing.assert_allclose(public,cp,atol=1e-7,rtol=0)
        m=metrics(cp,z['actions'],phases); gate=spec['offline_gate']
        passed=(m['MAE']<=gate['MAE_max'] and m['RMSE']<=gate['RMSE_max'] and m['max_error']<=gate['max_abs_error_max'] and all(v['RMSE']<=gate['per_phase_RMSE_max'] for v in m['per_phase'].values()))
        row=dict(seed=seed,epochs=epoch,best_epoch=best_epoch,stop_reason=stop_reason,elapsed_s=time.monotonic()-start,metrics=m,offline_pass=passed,train_balanced_MSE=balanced(cp,ti),validation_balanced_MSE=balanced(cp,vi),checkpoint=str(folder/'actor.pt'),checkpoint_sha256=sha(folder/'actor.pt'),CPU_CUDA_max_difference=float(np.max(np.abs(cp-pred))),action_transform_verified=True,initialization_sha256=hashlib.sha256(b''.join(v.numpy().tobytes() for v in initial.values())).hexdigest())
        save(f'OFFLINE_seed_{seed}.json',row);save(f'LOSS_CURVE_seed_{seed}.json',curve)
        for base in (folder,L): np.savez_compressed(base/f'EXACT_TEACHER_PREDICTIONS_seed_{seed}.npz',observations=z['observations'],teacher_actions=z['actions'],actor_actions=cp,error=cp-z['actions'],phase=phases,train_indices=ti,validation_indices=vi)
        results.append(row);save('OFFLINE_RESULTS.json',results)
        print(json.dumps(dict(seed=seed,offline_pass=passed,MAE=m['MAE'],RMSE=m['RMSE'],max_error=m['max_error'],epochs=epoch)),flush=True)
        del actor,optimizer
    assert len({r['initialization_sha256'] for r in results})==3
    state('OFFLINE_GATE_PASS_CLOSED_LOOP_NEXT' if all(r['offline_pass'] for r in results) else 'BC_REPRESENTATION_FIT_FAILED',seeds=len(results),offline_pass_count=sum(r['offline_pass'] for r in results),training_wall_s=time.monotonic()-begin)

if __name__=='__main__': run()
