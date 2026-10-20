"""Secondary earlier finite-action value model, frozen before any U outcome."""
from pathlib import Path
import sys,os,json,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from dataset import P,read,put,margins
from value_model import fit,predict,choose
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'control'))
from early_features import vector,NAMES
ACTIONS=['B','H150','HIP','KNEE','ZERO']
def reconstruct(g,a):
    origin=read(P/'audit'/(g+'_FORK_CONTEXT.json'))['physical_s'];cond=read(P/(g+'_PLAN.json'))['condition']
    z=np.load(P/'source/results'/(g+'_'+a)/'trace.npz');ix=np.flatnonzero((z['stage']=='TASK')&(z['time_s']<origin-1e-9));i=int(ix[-1]);first=int(np.flatnonzero(z['stage']=='TASK')[0]);assert origin-z['time_s'][i]<=.0100001
    return vector(z['estimated_human_state_rad_rad_s'][i],z['reference_q_rad'][i],z['reference_dq_rad_s'][i],z['physical_cuff_force_world_n'][i],z['physical_cuff_moment_world_nm'][i],z['time_s'][i]-z['time_s'][first],cond['prefix']['RETURN'][0])
def main():
    assert not (P/'models/EARLY_VALUE_FREEZE.json').exists()
    assert not any(json.loads(s)['id'].startswith('U') for s in (P/'ATTEMPTS.jsonl').read_text().splitlines())
    groups=['D01R','D02','D03','D04','D05','D06','V01','V02'];X=[];J=[];M=[];Q=[];records=[];protocol=read(P/'MOTION_ACCEPTANCE_PROTOCOL.json')['primary']
    for g in groups:
        result=read(P/(g+'_RESULTS.json'));by={r['candidate']['id']:r for r in result['rows']};b=read(P/'reports'/(g+'_B_MEASURED.json'));xs=[];js=[];ms=[];qs=[]
        for a in ACTIONS:
            x=reconstruct(g,a);m=read(P/'reports'/(g+'_'+a+'_MEASURED.json'));names,margin=margins(m,b,protocol);xs.append(x);js.append(m['J_F_N_s']);ms.append(margin);qs.append(by[a]['all_original_qualifications'])
            records.append(dict(parent=g,action=a,features=x.tolist(),qualified=bool(qs[-1]),J_F_N_s=js[-1],source='reports/'+g+'_'+a+'_MEASURED.json'))
        assert all(np.array_equal(xs[0],x) for x in xs[1:]),'EARLY_CONTEXT_NOT_MATCHED:'+g
        X.append(xs[0]);J.append(js);M.append(ms);Q.append(qs)
    x=np.array(X);j=np.array(J);m=np.array(M);q=np.array(Q);delta=j-j[:,[0]];tr=np.arange(6);va=np.arange(6,8);search=[];models={}
    for alpha in [.1,1.,10.,100.]:
        c=fit(x[tr],delta[tr],alpha);mm=fit(x[tr],m[tr],alpha);ce=[];me=[]
        for i in tr:
            keep=tr[tr!=i];ce.append(abs(predict(fit(x[keep],delta[keep],alpha),x[i])[0]-delta[i]));me.append(abs(predict(fit(x[keep],m[keep],alpha),x[i])[0]-m[i]))
        ce=np.max(ce,0);me=np.max(me,0);tz=(x[tr]-c['mu'])/c['sd'];dd=np.linalg.norm(tz[:,None]-tz[None,:],axis=-1);np.fill_diagonal(dd,np.inf);radius=float(dd.min(1).max())
        cp=predict(c,x[va]);mp=predict(mm,x[va]);choices=[]
        for k,i in enumerate(va):
            distance=np.min(np.linalg.norm((x[tr]-x[i])/c['sd'],axis=1));choices.append(choose(cp[k],mp[k],ce,me) if distance<=radius else 0)
        bad=int(sum(not q[i,a] for i,a in zip(va,choices)));regret=[float(j[i,a]-j[i,q[i]].min()) for i,a in zip(va,choices) if q[i,a]]
        row=dict(alpha=alpha,failed_selected=bad,mean_qualified_regret_N_s=float(np.mean(regret)) if regret else 0.,delta_RMSE_N_s=float(np.sqrt(np.mean((cp-delta[va])**2))),selected=[ACTIONS[a] for a in choices]);search.append(row);models[alpha]=(c,mm,ce,me,radius)
    best=min(search,key=lambda r:(r['failed_selected'],r['mean_qualified_regret_N_s'],r['delta_RMSE_N_s'],r['alpha']));c,mm,ce,me,radius=models[best['alpha']]
    f=P/'models/early_value_ridge.npz';np.savez_compressed(f,mu=c['mu'],sd=c['sd'],cost_w=c['w'],margin_mu=mm['mu'],margin_sd=mm['sd'],margin_w=mm['w'],margin_shape=np.array(mm['shape']),cost_error=ce,margin_error=me,train_x=x[tr],support_radius=radius,actions=np.array(ACTIONS),alpha=best['alpha'])
    good=np.flatnonzero(np.all(q[tr],0));global_action=ACTIONS[int(good[np.argmin(j[tr][:,good].mean(0))])]
    put('derived/EARLY_DATASET_development.json',dict(rows=records,groups=groups,features=NAMES,actions=ACTIONS,context_matches_all_five_actions=True,origin_rule='last completed trace sample strictly earlier than registered fork physical time; planned RETURN prefix is known configuration, never future outcome'))
    put('models/EARLY_VALUE_FREEZE.json',dict(frozen_unix=time.time(),model_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),model_file='models/early_value_ridge.npz',train=groups[:6],validation=groups[6:],selected_alpha=best['alpha'],search=search,global_qualified_train_action=global_action,state_rank=int(np.linalg.matrix_rank(x[tr]-x[tr].mean(0))),state_dimensions=10,algorithm='contextual terminal cost plus learned original qualification margins; empirical buffer; earlier full remaining-strategy selection',fallback='B remaining strategy, preserving original admission',previous_repetition_feedback=False,stage='secondary pre-test registered comparison, primary RETURN2 experiment preserved',training_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),training_physics_starts=0,ridge_solves=56))
    print('EARLY_VALUE_FROZEN',json.dumps(best),flush=True)
if __name__=='__main__':main()
