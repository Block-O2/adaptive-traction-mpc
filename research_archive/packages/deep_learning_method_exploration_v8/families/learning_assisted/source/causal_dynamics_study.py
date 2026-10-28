"""Whole-context causal observation dynamics; no simulator or future rollout inputs."""
from pathlib import Path
import os, json, time, hashlib, signal, resource
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
import numpy as np

P = Path(__file__).resolve().parents[3]
F = Path(__file__).resolve().parents[1]
V = P.parent / 'autonomous_learning_smoothness_v7'
START = time.time()
signal.alarm(300)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def put(name, obj):
    p = F / name
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def kin(s):
    y = s.copy()
    y[..., :2] += .005 * s[..., 2:4]
    y[..., 4:6] += .005 * s[..., 6:8]
    return y

def features(s, old, tau, phase, action, n_actions, history=False):
    n = len(s)
    a = np.zeros((n, n_actions)); a[:, action] = 1
    ph = np.eye(3)[phase]
    cols = [s, np.asarray(tau)[:, None] / 20., ph, a]
    if history:
        cols += [s-old]
    # Action interactions are known selected recipe, never a hidden patient ID.
    cols += [s[:, [0, 1, 2, 3, 8, 10]] * a[:, i:i+1] for i in range(n_actions)]
    return np.column_stack(cols)

def fit(x, y):
    mu=x.mean(0); sd=x.std(0); sd[sd<1e-8]=1
    z=np.column_stack([np.ones(len(x)),(x-mu)/sd])
    # Fixed regularization, no heldout tuning or per-action future masks.
    reg=np.eye(z.shape[1]); reg[0,0]=0
    w=np.linalg.solve(z.T@z+10.*reg,z.T@y)
    return dict(mu=mu,sd=sd,w=w)

def pred(model, x):
    return np.column_stack([np.ones(len(x)), (x-model['mu'])/model['sd']])@model['w']

def main():
    ident=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),started_unix=START,source_sha256=sha(Path(__file__)),new_physics=0)
    put('analysis/PROCESS_START.json',ident)
    source=P/'families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json'
    data=json.loads(source.read_text()); hashes={str(source):sha(source)}
    recipes=sorted({r['action_recipe_sha256'] for r in data['rows']})
    series=[]; excluded=[]
    for row in data['rows']:
        p=V/'history'/(row['id']+'_CAUSAL_HISTORY.json')
        lab=row['labels_evaluation_only']
        if not p.exists() or not lab.get('complete',False):
            excluded.append(dict(id=row['id'],reason='MISSING_HISTORY_OR_NONCOMPLETE')); continue
        hist=json.loads(p.read_text()); hashes[str(p)]=sha(p)
        if len(hist)<205: continue
        t=np.array([r['time_s'] for r in hist]); t-=t[0]
        assert np.max(abs(np.diff(t)-.005))<1e-8
        s=np.array([r['estimated_q_dq']+r['reference_q_dq']+r['measured_force']+r['measured_moment'] for r in hist],float)
        assert np.isfinite(s).all() and all(r.get('truth_used') is False for r in hist)
        phase=np.array([['OUTBOUND','HOLD','RETURN'].index(r['phase']) for r in hist])
        series.append(dict(id=row['id'],group=row['group'],s=s,t=t,phase=phase,action=recipes.index(row['action_recipe_sha256'])))
    assert series, 'NO_COMPLETE_CAUSAL_SERIES'
    results=[]; fits=0
    for group in sorted({s['group'] for s in series}):
        train=[s for s in series if s['group']!=group]; test=[s for s in series if s['group']==group]
        for variant in ['absolute','residual','history_residual']:
            history=variant=='history_residual'
            X=[];Y=[]
            for s in train:
                ix=np.unique(np.linspace(2,len(s['s'])-2,min(800,len(s['s'])-3)).astype(int))
                X.append(features(s['s'][ix],s['s'][ix-2],s['t'][ix],s['phase'][ix],s['action'],len(recipes),history))
                target=s['s'][ix+1]
                Y.append(target if variant=='absolute' else target-kin(s['s'][ix]))
            model=fit(np.concatenate(X),np.concatenate(Y));fits+=1
            for s in test:
                ix=np.arange(2,len(s['s'])-1)
                x=features(s['s'][ix],s['s'][ix-2],s['t'][ix],s['phase'][ix],s['action'],len(recipes),history)
                y=pred(model,x)+(0 if variant=='absolute' else kin(s['s'][ix]))
                actual=s['s'][ix+1]
                row=dict(group=group,id=s['id'],variant=variant,one_step_RMSE=np.sqrt(np.mean((y-actual)**2,0)).tolist(),kinematic_RMSE=np.sqrt(np.mean((kin(s['s'][ix])-actual)**2,0)).tolist(),persistence_RMSE=np.sqrt(np.mean((s['s'][ix]-actual)**2,0)).tolist(),rollouts=[])
                for horizon in [0.5,1.0]:
                    count=round(horizon/.005)
                    # Test both first available post-action state and a public mid-return time.
                    for start in [2,min(2202,len(s['s'])-count-2)]:
                        if start<2: continue
                        state=s['s'][start].copy(); previous=[s['s'][start-2].copy(),s['s'][start-1].copy()]
                        trajectory=[state.copy()]; diverged=False
                        for step in range(count):
                            elapsed=s['t'][start]+step*.005
                            # Public phase clock is fixed by original task; no future measured ref/wrench.
                            phase=0 if elapsed<9.005 else 1 if elapsed<10.025 else 2
                            xx=features(state[None],previous[-2][None],np.array([elapsed]),np.array([phase]),s['action'],len(recipes),history)
                            next_s=pred(model,xx)[0]+(0 if variant=='absolute' else kin(state))
                            if not np.isfinite(next_s).all() or np.max(abs(next_s))>1e6:
                                diverged=True;break
                            previous.append(state);state=next_s;trajectory.append(state.copy())
                        target=s['s'][start:start+count+1]
                        real_jf=float(np.linalg.norm(target[:-1,8:11],axis=1).sum()*.005)
                        if diverged:
                            rr=dict(start_post_action_s=float(s['t'][start]),horizon_s=horizon,status='DIVERGED',actual_window_JF=real_jf)
                        else:
                            trajectory=np.array(trajectory)
                            pjf=float(np.linalg.norm(trajectory[:-1,8:11],axis=1).sum()*.005)
                            rr=dict(start_post_action_s=float(s['t'][start]),horizon_s=horizon,status='FINITE',terminal_error=(trajectory[-1]-target[-1]).tolist(),window_RMSE=np.sqrt(np.mean((trajectory-target)**2,0)).tolist(),predicted_window_JF=pjf,actual_window_JF=real_jf,JF_error=pjf-real_jf)
                        row['rollouts'].append(rr)
                results.append(row)
            print('DYNAMICS_FOLD',group,variant,'fits',fits,flush=True)
    out=dict(status='COMPLETED_DIAGNOSTIC_ONLY',scope='Whole-context development CV. Start is measured post-action, not pre-action candidate selection. No new control deployment.',rows=results,complete_series=len(series),contexts=len({s['group'] for s in series}),recipe_count=len(recipes),ridge_solves=fits,excluded=excluded,source_files_sha256=hashes,new_physics=0,new_native_steps=0,new_policy_updates=0,wall_s=time.time()-START,cpu_s=time.process_time(),max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    put('analysis/CAUSAL_DYNAMICS_RESULTS_V1.json',out)
    put('analysis/PROCESS_END.json',dict(**ident,ended_unix=time.time(),status='PASS_DIAGNOSTIC_ONLY'))
    print('DYNAMICS_DONE',len(series),len(results),out['wall_s'],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        put('analysis/PROCESS_FAILURE.json',dict(error=str(e),ended_unix=time.time(),wall_s=time.time()-START));raise
