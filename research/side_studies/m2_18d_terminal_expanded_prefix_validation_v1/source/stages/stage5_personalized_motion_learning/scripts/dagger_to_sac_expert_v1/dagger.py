from common import *
from expert import CausalHipLeadingExpert
FIELDS=('observations','expert_actions','expert_label_available','actions','executed_actions','next_observations','rewards','terminated','truncated','phase','round','rollout','termination','recovery_success','mixture_beta','expert_executed')
def empty():return {k:[] for k in FIELDS}
def append_dataset(total,new):
    for k in FIELDS:total[k].extend(new[k])
def persist(total,path):
    np.savez_compressed(path,**{k:np.asarray(v) for k,v in total.items()})
def rollout(a,name,scope='NATIVE',expert=None,beta=0.,rng=None,round_=0,collection=False):
    # Pure evaluations never invoke an expert or read any teacher data.
    check();config=read('PREREGISTRATION.json');case,options=load_case_options()
    env=SACExpertEnv(O/name,case,options,.02,scope,True);data=empty();terminal=False
    try:
        obs,info=env.reset(seed=config['initial_condition_seed'])
        assert env.model_hash==read('SCIENTIFIC_LOCK.json')['frozen_model_hash']
        for i in range(1600):
            predicted,_=a.predict(obs,deterministic=True)
            if collection:
                label,_=expert.query(obs);take=bool(rng.random()<beta);action=label if take else predicted
            else:label=np.zeros(2,np.float32);take=False;action=predicted # Masked placeholder; no expert query or valid label.
            before=obs.copy();phase=info['phase']
            obs,reward,term,trunc,info=env.step(action)
            for k,v in dict(observations=before,expert_actions=label,expert_label_available=collection,actions=action.copy(),executed_actions=env.last_row['executed'],
                next_observations=obs.copy(),rewards=reward,terminated=term,truncated=trunc,phase=phase,round=round_,
                rollout=name,mixture_beta=beta,expert_executed=take).items():data[k].append(v)
            if term or trunc:terminal=True;break
        assert terminal,'UNFINISHED_ROLLOUT'
        row=metric(env,name,scope);row.update(beta=beta,teacher_execution_count=sum(data['expert_executed']),
            expert_queries=len(data['observations']) if collection else 0,steps=len(data['observations']),
            actor_checkpoint_only=True,recovery_semantics='episode outcome under stated mixture; not per-state counterfactual recovery')
        reason=env.summary.get('abort_reason') or env.summary['status']
        data['termination']=[reason]*len(data['observations']);data['recovery_success']=[row['valid']]*len(data['observations'])
        path=env.episode_dir/'POLICY_TRANSITIONS.npz';persist(data,path);row['transitions']=str(path)
        save('ROLLOUT_'+name.replace('/','_')+'_'+scope+'.json',row);compact_archive(env)
        print(json.dumps(clean(dict(rollout=name,scope=scope,valid=row['valid'],gates=row['gates'],J_F=row['J_F'],steps=row['steps'],teacher_execution=row['teacher_execution_count']))),flush=True)
        return row,data
    finally:env.close()
def train(a,opt,dataset,rng,updates,round_):
    check();resource('TRAIN_ROUND_'+str(round_));cfg=read('PREREGISTRATION.json')['dagger']
    x=torch.tensor(np.asarray(dataset['observations']),device='cuda',dtype=torch.float32)
    y=torch.tensor(np.asarray(dataset['expert_actions']),device='cuda',dtype=torch.float32)
    phase=np.asarray(dataset['phase']);groups=[np.flatnonzero(phase==p) for p in ('OUTBOUND','HOLD','RETURN')]
    assert all(len(g) for g in groups),'PHASE_MISSING'
    a.to('cuda');a.train();curve=[]
    for u in range(1,updates+1):
        idx=np.concatenate([rng.choice(g,96,replace=True) for g in groups]);rng.shuffle(idx)
        pred=a(x[idx],deterministic=True);loss=torch.mean((pred-y[idx])**2)
        assert torch.isfinite(loss),'NAN_IMITATION'
        opt.zero_grad(set_to_none=True);loss.backward();opt.step()
        if u%2000==0:
            with torch.no_grad():full=a(x,deterministic=True)
            mse=float(torch.mean((full-y)**2).item());curve.append(dict(update=u,batch_MSE=float(loss),full_MSE=mse))
            print(json.dumps(dict(round=round_,update=u,n=len(x),full_MSE=mse)),flush=True)
            check()
    a.eval();save('TRAINING_round_'+str(round_)+'.json',dict(curve=curve,phase_counts={p:int(sum(phase==p)) for p in ('OUTBOUND','HOLD','RETURN')},updates=updates))
    checkpoint(a,opt,rng,O/f'actor_round_{round_:02d}.pt',round=round_,dataset_size=len(x),config_sha256=sha(D/'PREREGISTRATION.json'))
    cpu=actor(read('PREREGISTRATION.json')['seed']);cpu.load_state_dict(a.state_dict());cpu.eval()
    with torch.no_grad():
        cp=cpu(torch.as_tensor(np.asarray(dataset['observations']),dtype=torch.float32),deterministic=True).numpy()
        gp=a(x,deterministic=True).cpu().numpy()
    np.testing.assert_allclose(cp,gp,atol=2e-6,rtol=0)
    return cpu
def run():
    assert read('EXPERT_GATE.json')['status']=='PASS','EXPERT_GATE_REQUIRED'
    check();cfg=read('PREREGISTRATION.json');dc=cfg['dagger'];rng=np.random.default_rng(cfg['seed']+1000)
    a=actor(cfg['seed'],'cuda');opt=torch.optim.Adam([p for p in a.parameters() if p.requires_grad],lr=dc['learning_rate'])
    assert len(opt.state)==0;expert=CausalHipLeadingExpert(cfg['expert'],SCALES)
    z=np.load(DEMO);total=empty();n=len(z['actions'])
    for k,v in dict(observations=z['observations'],expert_actions=z['actions'],expert_label_available=[True]*n,actions=z['actions'],
        executed_actions=z['executed_actions'] if 'executed_actions' in z else z['actions'],next_observations=z['next_observations'],
        rewards=z['rewards'],terminated=z['terminated'],truncated=z['truncated'],phase=z['phase'],round=np.zeros(n,int),
        rollout=['teacher']*n,termination=['COMPLETE']*n,recovery_success=[True]*n,mixture_beta=[1.]*n,expert_executed=[True]*n).items():total[k].extend(v)
    persist(total,O/'aggregated_round_00.npz');state('DAGGER_INITIAL_TRAINING',dataset_size=n)
    cpu=train(a,opt,total,rng,dc['initial_updates'],0);results=[];consecutive=0;first=None
    for round_ in range(1,dc['max_rounds']+1):
        check();resource('ROUND_'+str(round_));beta=dc['beta'][round_-1];collection=[]
        state('DAGGER_COLLECTION',dagger_rounds=round_,beta=beta)
        for j in range(dc['collection_rollouts']):
            row,data=rollout(cpu,f'round_{round_:02d}/collection_{j+1}',expert=expert,beta=beta,rng=rng,round_=round_,collection=True)
            append_dataset(total,data);collection.append(row)
            persist(total,O/f'aggregated_round_{round_:02d}.npz')
            checkpoint(a,opt,rng,O/f'collection_resume_round_{round_:02d}.pt',round=round_,completed_collection=j+1,dataset_size=len(total['observations']))
        state('DAGGER_TRAINING',dataset_size=len(total['observations']))
        cpu=train(a,opt,total,rng,dc['round_updates'],round_);evaluations=[]
        for j in range(dc['evaluation_rollouts']):
            row,_=rollout(cpu,f'round_{round_:02d}/evaluation_{j+1}',round_=round_);evaluations.append(row)
            assert row['teacher_execution_count']==0 and row['expert_queries']==0
        valid=sum(r['valid'] for r in evaluations);consecutive=consecutive+1 if valid==3 else 0
        if valid and first is None:first=round_
        results.append(dict(round=round_,beta=beta,dataset_size=len(total['observations']),collection=collection,
            evaluations=evaluations,valid_count=valid,consecutive_qualified_rounds=consecutive))
        save('DAGGER_RESULTS.json',dict(rounds=results,first_VALID_round=first,qualified=consecutive>=2))
        state('DAGGER_ROUND_COMPLETE',dagger_rounds=round_,dataset_size=len(total['observations']),pure_success=f'{valid}/3',first_VALID_round=first)
        if consecutive>=2:
            shutil.copy2(O/f'actor_round_{round_:02d}.pt',O/'qualified_actor.pt')
            shutil.copy2(O/f'aggregated_round_{round_:02d}.npz',O/'qualified_aggregated.npz')
            save('DAGGER_QUALIFICATION.json',dict(status='PASS',round=round_,two_rounds=[round_-1,round_],dataset_size=len(total['observations']),
                actor=O/'qualified_actor.pt',actor_sha256=sha(O/'qualified_actor.pt'),evaluations=evaluations,
                first_VALID_round=first,success='3/3 in each of 2 consecutive rounds; same deterministic exposed nominal condition, not independent Human robustness'))
            state('DAGGER_QUALIFIED_SAC_NEXT',next_action='Automatically initialize fresh SAC and verify exact deterministic actor mean identity.');return True
    save('DAGGER_QUALIFICATION.json',dict(status='FAIL',round=8,dataset_size=len(total['observations']),first_VALID_round=first,reason='Covariate shift not resolved under frozen expert/training; observation/action limitation not established'))
    state('DAGGER_8_ROUNDS_UNQUALIFIED',next_action='Preserve final failure diagnosis; STOP without SAC.');return False
if __name__=='__main__':run()
