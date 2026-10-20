"""Origin-only prediction; truth is read solely as a supervised target/evaluation."""
from pathlib import Path
import os,sys,json,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'ihear_model_terminal_compensation_v1'
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def metrics(x):return dict(rmse=np.sqrt(np.mean(x*x,axis=0)),p95_abs=np.quantile(abs(x),.95,axis=0),bias=x.mean(axis=0),n=len(x))
def rows(root,ident):
    z=np.load(root/'source/results'/ident/'trace.npz');sel=z['stage']=='TASK'
    t=z['time_s'][sel];x=z['estimated_human_state_rad_rad_s'][sel]
    rq=z['reference_q_rad'][sel];rv=z['reference_dq_rad_s'][sel]
    ac=z['actual_human_acceleration_rad_s2'][sel]
    f=z['physical_cuff_force_world_n'][sel];m=z['physical_cuff_moment_world_nm'][sel]
    u=z['applied_generalized_action_nm'][sel]
    # Causal inputs frozen at each origin. Future truth is not a feature.
    feat=np.c_[x,np.rad2deg(rq-x[:,:2]),np.rad2deg(rv-x[:,2:]),ac,f,m,u]
    y=z['evaluation_only_human_state_rad_rad_s'][sel]
    with np.load(root/'motion_series'/(ident+'.npz')) as native:
        na=np.column_stack([np.interp(t,native['time_s'],native['acceleration_rad_s2'][:,j]) for j in range(2)])
    return dict(t=t-t[0],x=x,rq=rq,rv=rv,ac=ac,f=f,m=m,u=u,features=feat,y=y,na=na)
def main():
    cases=[('W1',A,'Ctrl_'+a,'train') for a in ['B','ER','H150']]+[('W2',A,'W2_'+a,'historical_trajectory_validation') for a in ['B','ER','H150']]
    cases += [(g,P,g+'_H150','prospective_new_parent_validation') for g in ['D03','D04','D05','D06'] if (P/(g+'_DONE.json')).exists()]
    data={ident:rows(root,ident) for fam,root,ident,split in cases}
    results=[];weights={};plots=[]
    for h in [20,40]:
        X=[];Y=[]
        for fam,root,ident,split in cases:
            if split!='train':continue
            d=data[ident];ix=np.arange(20,len(d['t'])-h,10)
            base=d['x'][ix,:2]+h*.005*d['x'][ix,2:]+.5*(h*.005)**2*d['ac'][ix]
            X.append(d['features'][ix]);Y.append(np.rad2deg(d['y'][ix+h,:2]-base))
        X=np.concatenate(X);Y=np.concatenate(Y);mu=X.mean(0);sd=X.std(0);sd=np.maximum(sd,1e-6)
        design=np.c_[np.ones(len(X)),(X-mu)/sd];reg=np.eye(design.shape[1]);reg[0,0]=0
        w=np.linalg.solve(design.T@design+10.*reg,design.T@Y)
        weights[str(h)]=dict(mu=mu,sd=sd,w=w)
        for fam,root,ident,split in cases:
            d=data[ident];ix=np.arange(20,len(d['t'])-h,10);dt=h*.005
            cv=d['x'][ix,:2]+dt*d['x'][ix,2:];ca=cv+.5*dt*dt*d['ac'][ix]
            residual=np.c_[np.ones(len(ix)),(d['features'][ix]-mu)/sd]@w
            target=np.rad2deg(d['y'][ix+h,:2]);preds=dict(constant_velocity=np.rad2deg(cv),causal_constant_acceleration=np.rad2deg(ca),ridge_residual=np.rad2deg(ca)+residual)
            for method,pred in preds.items():
                for region,mask in [('full',np.ones(len(ix),bool)),('terminal',(d['t'][ix]>=15.3)&(d['t'][ix]<=17.6))]:
                    results.append(dict(parent=fam,id=ident,split=split,horizon_s=dt,method=method,region=region,**metrics((pred-target)[mask])))
            if ident=='W2_H150' and h==20:plots=[d['t'][ix],target,preds]
    put('models/RESIDUAL_PREDICTOR.json',dict(alpha=10.,train_parents=['W1'],weights=weights,frozen_feature_rule='origin-only estimated q/dq, tracking error, causal observed acceleration, measured cuff wrench, existing generalized request; no future input',scope='rolling origin 100/200ms position regression, not closed-loop stopping or action-conditioned counterfactual model'))
    align=[]
    for ident,d in data.items():
        pd=(d['rq']-d['x'][:,:2])*[180,140]+(d['rv']-d['x'][:,2:])*[28,22]
        mask=(d['t']>=15.3)&(d['t']<=17.6)
        align.append(dict(id=ident,PD_request_minus_native_acceleration_deg_s2=metrics(np.rad2deg(pd[mask]-d['na'][mask])),causal_accel_estimate_minus_native_deg_s2=metrics(np.rad2deg(d['ac'][mask]-d['na'][mask]))))
    put('PREDICTION_VALIDATION.json',dict(status='COMPLETED',created_unix=time.time(),train_parents=['W1'],historical_validation_parents=['W2'],prospective_validation_parents=sorted({r['parent'] for r in results if r['split']=='prospective_new_parent_validation'}),rows=results,acceleration_alignment=align,model_promoted_to_controller=False,reason='Forecast model has no candidate-action input; origin error and candidate separation must be checked. Observational correlation does not isolate transmission mechanisms.',future_truth_used_only_for_supervised_labels=True,independent_Human=False))
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,dt in zip(axs,[.1,.2]):
        for method in ['constant_velocity','causal_constant_acceleration','ridge_residual']:
            rs=[r for r in results if r['horizon_s']==dt and r['region']=='terminal' and r['id'].endswith('H150') and r['method']==method]
            ax.plot([r['parent'] for r in rs],[r['rmse'][1] for r in rs],marker='o',label=method)
        ax.set_title(f'{int(dt*1000)} ms rolling prediction');ax.set_ylabel('Knee angle RMSE (deg)');ax.grid(alpha=.25)
    axs[0].legend(fontsize=8);fig.savefig(P/'figures/02_prediction_validation.png',dpi=150);plt.close(fig)
    d=data['Ctrl_H150'];pd=(d['rq']-d['x'][:,:2])*[180,140]+(d['rv']-d['x'][:,2:])*[28,22]
    fig,axs=plt.subplots(3,1,figsize=(11,9),sharex=True,layout='constrained')
    axs[0].plot(d['t'],np.rad2deg(pd[:,1]),label='PD request');axs[0].plot(d['t'],np.rad2deg(d['na'][:,1]),label='Native actual');axs[0].plot(d['t'],np.rad2deg(d['ac'][:,1]),label='Causal acceleration estimate')
    axs[1].plot(d['t'],np.rad2deg(d['x'][:,2:]),label=['Hip estimate','Knee estimate'])
    axs[2].plot(d['t'],np.linalg.norm(d['f'],axis=1),label='Cuff force norm')
    for ax,lab in zip(axs,['Acceleration (deg/s²)','Velocity (deg/s)','Force (N)']):ax.set_xlim(15.3,18);ax.set_ylabel(lab);ax.legend();ax.grid(alpha=.2)
    axs[-1].set_xlabel('Task time (s)');fig.savefig(P/'figures/03_request_response.png',dpi=150);plt.close(fig)
    print('PREDICTION_COMPLETE',len(results),'ROWS',flush=True)
if __name__=='__main__':main()
