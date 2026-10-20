"""Read-only final-checkpoint Q and actor comparisons on the causal Native demo."""
from common import *
import gc
def stats(x):
    a=np.asarray(x);return dict(mean=float(a.mean()),min=float(a.min()),max=float(a.max()))
def run():
    assert json.loads((D/'STATE.json').read_text())['status']=='PAIRED_50K_COMPLETE_STOP'
    check_lock();demo=np.load(O/'NATIVE_DEMO.npz');ob=demo['observations'];da=demo['actions'];phase=ob[:,41:44].argmax(1)
    outputs={};rows=[]
    w=memory.windows();mem=memory.memfile('/proc/meminfo');assert mem['MemAvailable']>=1.5*2**30 and w['CommitLimit']-w['CommittedBytes']>=2*2**30
    assert mem['SwapTotal']-mem['SwapFree']==0
    for arm in ('A','B'):
        folder=O/arm/'step_0050000_final';receipt=json.loads((folder/'BUNDLE.json').read_text())
        for name,h in receipt['files'].items():assert sha(folder/name)==h
        model=SAC.load(folder/'policy.zip',device='cuda');model.policy.set_training_mode(False)
        ph=policy_hash(model);optim=memory.optimizer_hash(model);before=rng()
        assert ph==receipt['policy_hash'] and optim==receipt['optimizers']
        with (folder/'online_and_sampler.pkl').open('rb') as f:rb=pickle.load(f)
        idx=np.random.default_rng(SEED).integers(0,rb.size(),len(da));alt=rb.actions[idx,0].copy()
        with torch.no_grad():
            obs=torch.as_tensor(ob,device=model.device);action=torch.as_tensor(da,device=model.device);fa=torch.as_tensor(alt,device=model.device)
            actor=model.actor(obs,deterministic=True)
            qt=torch.cat(model.critic(obs,action),1).min(1).values.cpu().numpy()
            qa=torch.cat(model.critic(obs,fa),1).min(1).values.cpu().numpy()
            qp=torch.cat(model.critic(obs,actor),1).min(1).values.cpu().numpy();actor=actor.cpu().numpy()
        assert all(np.isfinite(x).all() for x in (qt,qa,qp,actor))
        cohorts={name:phase==i for i,name in enumerate(('OUTBOUND','HOLD','RETURN'))}
        outbound=np.flatnonzero(phase==0);cohorts['OUTBOUND_first64']=np.isin(np.arange(len(phase)),outbound[:64]);cohorts['OUTBOUND_last64']=np.isin(np.arange(len(phase)),outbound[-64:])
        cohorts['RETURN_last64']=np.isin(np.arange(len(phase)),np.flatnonzero(phase==2)[-64:])
        report={}
        for name,m in cohorts.items():
            report[name]=dict(count=int(m.sum()),teacher_Q=stats(qt[m]),online_action_counterfactual_Q=stats(qa[m]),actor_Q=stats(qp[m]),teacher_advantage_Q=stats(qt[m]-qa[m]),teacher_preferred_rate=float((qt[m]>qa[m]).mean()),actor_teacher_action_MAE=np.abs(actor[m]-da[m]).mean(0).tolist(),actor_near_bound_rate=float((np.abs(actor[m])>=.95).any(1).mean()))
        outputs[arm]=dict(checkpoint=str(folder/'policy.zip'),policy_hash=ph,alpha=float(model.log_ent_coef.exp()),online_phase=phases(rb.observations[:rb.size()]),cohorts=report,updates=model._n_updates)
        for i in range(len(da)):rows.append(dict(arm=arm,teacher_transition=i,phase=('OUTBOUND','HOLD','RETURN')[phase[i]],teacher_Q=float(qt[i]),online_action_counterfactual_Q=float(qa[i]),actor_Q=float(qp[i]),teacher_hip_action=float(da[i,0]),teacher_knee_action=float(da[i,1]),actor_hip_action=float(actor[i,0]),actor_knee_action=float(actor[i,1])))
        assert policy_hash(model)==ph and memory.optimizer_hash(model)==optim
        restore(before);del model,rb;gc.collect();torch.cuda.empty_cache()
    out=dict(status='READ_ONLY_PASS',results=outputs,new_online_steps=0,new_training_updates=0,teacher_data_sha256=sha(O/'NATIVE_DEMO.npz'),limits=['Q differences compare raw actions at identical causal teacher states, not realized physical counterfactuals.','High Q on successful-demo phases does not establish forward visitation or physically valid action execution.','Phase-specific Q values do not isolate a unique failure mechanism or measure exact Bellman propagation speed.'])
    save('OFFLINE_Q_PHASE_AUDIT.json',out);table('OFFLINE_Q_PHASE_CURVE.csv',rows)
    md=['# Read-only final checkpoint value/actor audit','', 'Native causal teacher states only; no rollout, learning, imitation, normalization update or buffer write. Alternative raw actions are sampled from the arm\'s own final online replay at identical teacher states. Q scores are estimates, not physical success.','', '|Arm|Teacher cohort|N|Teacher Q|Online-action Q|Actor Q|Teacher preferred|Actor action MAE hip/knee|','|---|---|---:|---:|---:|---:|---:|---|']
    for a,v in outputs.items():
        for name,x in v['cohorts'].items():md.append(f"|{a}|{name}|{x['count']}|{x['teacher_Q']['mean']:.4f}|{x['online_action_counterfactual_Q']['mean']:.4f}|{x['actor_Q']['mean']:.4f}|{x['teacher_preferred_rate']:.4f}|{x['actor_teacher_action_MAE']}|")
    md+=['','The earliest OUTBOUND and late RETURN cohorts describe the final learned value profile; they cannot by themselves prove how values propagated during learning. Actual training visitation is in PHASE_COVERAGE_COMPARISON.json. Combine these Q estimates with actor discrepancy and saved-trace goal settling evidence; never rank invalid task costs.']
    prose('OFFLINE_Q_PHASE_AUDIT.md','\n'.join(md)+'\n')
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    print(json.dumps(clean(out),indent=2))
if __name__=='__main__':run()
