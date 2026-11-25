from pathlib import Path
import json,sys
import numpy as np
R=Path(__file__).resolve().parents[4];G=R/'research/local_studies/ihear_lab_stage1g_v1';H=R/'research/local_studies/ihear_lab_stage1k_v1'
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,default=lambda v:v.tolist() if isinstance(v,np.ndarray) else v.item()))
def arrays(path,kind):
    if kind=='B':
        z=np.load(path/'trace.npz');save(H/'analysis/B_KEYS.json',list(z.keys()))
        mask=z['stage']=='TASK';t=z['time_s'][mask];ph=z['task_phase'][mask]
        # Include the completion boundary to own the final physical interval.
        inds=np.where(mask)[0];idx=np.arange(inds[0],min(inds[-1]+2,len(z['time_s'])))
        a={k:z[n][idx] for k,n in dict(t='time_s',ph='task_phase',f='physical_cuff_force_world_n',m='physical_cuff_moment_world_nm',q='estimated_human_state_rad_rad_s',ref='reference_q_rad',v='reference_dq_rad_s',acc='reference_ddq_rad_s2').items()}
        a['q']=a['q'][:,:2]
        truthkey=next((k for k in z.keys() if k in ('evaluation_only_human_state_rad_rad_s','human_state_rad_rad_s','human_state_true_rad_rad_s','true_human_state_rad_rad_s')),None)
        if truthkey:a['truth']=z[truthkey][idx]
        else:
            art=load(path/'runtime_artifacts.json');nr=art['wall_physics']['native_states_evaluation_only'];nt=np.array([r['time_s'] for r in nr]);a['truth']=np.array([np.r_[nr[np.argmin(abs(nt-t))]['qpos_evaluation_only'][:2],nr[np.argmin(abs(nt-t))]['qvel_evaluation_only'][:2]] for t in a['t']])
    else:
        tr=load(path/'D_TRACE.json');ev=load(path/'D_EVENTS.json');a={k:np.array([r[n] for r in tr]) for k,n in dict(t='time_s',ph='phase',f='measured_force_n',m='measured_moment_nm',q='estimated_state',ref='reference_q_rad',v='reference_dq_rad_s',acc='reference_ddq_rad_s2',truth='evaluation_only_human_state').items()};a['q']=a['q'][:,:2]
        for e in ev:
            if e['event']=='PHASE_CHANGE':a['ph'][a['t']>=e['time_s']]=e['new']
    a['t']=a['t']-a['t'][0]
    return a
def compute(a):
    t=a['t'];dt=np.diff(t);assert np.all(dt>0) and np.allclose(dt,.005,rtol=0,atol=1e-9)
    fn=np.linalg.norm(a['f'],axis=1);mn=np.linalg.norm(a['m'],axis=1);fr=np.linalg.norm(np.diff(a['f'],axis=0)/dt[:,None],axis=1);jr=np.diff(a['acc'],axis=0)/dt[:,None]
    hv=a['truth'][:,2:];ha=np.diff(hv,axis=0)/dt[:,None];hj=np.diff(ha,axis=0)/((dt[:-1]+dt[1:])/2)[:,None]
    theta=np.unwrap(np.arctan2(abs(a['v'][:,1]),abs(a['v'][:,0])));speed=np.linalg.norm(a['v'],axis=1)
    rows={}
    for phase in ('TASK','OUTBOUND','HOLD','RETURN'):
        own=np.ones(len(dt),bool) if phase=='TASK' else a['ph'][:-1]==phase
        w=dt[own];dur=w.sum()
        if not dur:continue
        rms=lambda x:np.sqrt(np.sum(x[own]**2*w.reshape((-1,)+(1,)*(x.ndim-1)),axis=0)/dur)
        hjmask=own[:-1]&(own[1:] if phase!='TASK' else True);hw=dt[:-1][hjmask]
        moving=own&(speed[:-1]>1e-12)
        rows[phase]=dict(duration_s=dur,JF_Ns=fn[:-1][own]@w,force_mean_N=fn[:-1][own]@w/dur,force_peak_N=fn[:-1][own].max(),JM_Nms=mn[:-1][own]@w,moment_mean_Nm=mn[:-1][own]@w/dur,moment_peak_Nm=mn[:-1][own].max(),force_rate_RMS_N_s=rms(fr),force_rate_peak_N_s=fr[own].max(),reference_jerk_RMS_rad_s3=rms(jr),reference_jerk_peak_rad_s3=np.max(abs(jr[own]),axis=0),human_jerk_RMS_rad_s3=np.sqrt(np.sum(hj[hjmask]**2*hw[:,None],axis=0)/hw.sum()),human_jerk_peak_rad_s3=np.max(abs(hj[hjmask]),axis=0),tracking_RMS_deg=rms((a['q'][:-1]-a['ref'][:-1])*180/np.pi),true_tracking_RMS_deg=rms((a['truth'][:-1,:2]-a['ref'][:-1])*180/np.pi),speed_mean_rad_s=speed[:-1][own]@w/dur,speed_quantiles_rad_s=np.quantile(speed[:-1][own],[0,.25,.5,.75,1]),direction_range_deg=(np.array([theta[:-1][moving].min(),theta[:-1][moving].max()])*180/np.pi if moving.any() else None))
    def top(v,n=8):
        ids=np.argsort(v)[-n:][::-1];return [dict(task_s=t[i],phase=a['ph'][i],value=v[i],force_before=a['f'][i],force_after=a['f'][i+1],reference_v=a['v'][i],reference_acc=a['acc'][i],next_reference_acc=a['acc'][i+1]) for i in ids]
    # Descriptive ranking only: no event acceptance threshold is introduced.
    summary=dict(rows=rows,dt_minmax=[dt.min(),dt.max()],top_force_rate=top(fr),top_reference_jerk=top(np.linalg.norm(jr,axis=1)),top_human_jerk=top(np.linalg.norm(hj,axis=1)),force_rate_quantiles=np.quantile(fr,[.5,.9,.95,.99,1]),force_rate_squared_integral_top10_share=np.sort(fr**2*dt)[-10:].sum()/(fr**2@dt),human_jerk_method='second forward difference of saved true velocity at 5ms; two-interval stencils within phase only; no smoothing',terminal=dict(q_deg=a['truth'][-1,:2]*180/np.pi,v_rad_s=hv[-1],ref_deg=a['ref'][-1]*180/np.pi))
    # Reference direction reversals only when both adjacent increments are moving;
    # epsilon is numerical reporting only, never an execution/evaluation gate.
    dth=np.diff(theta);valid=(speed[:-1]>1e-12)&(speed[1:]>1e-12);turns=np.where(valid[1:]&valid[:-1]&(dth[1:]*dth[:-1]<0)&(abs(dth[1:])>1e-10)&(abs(dth[:-1])>1e-10))[0]+1
    summary['direction_turns']=[dict(task_s=t[i],phase=a['ph'][i],theta_deg=theta[i]*180/np.pi,force_N=fn[i],force_rate_N_s=fr[i]) for i in turns]
    for stride in (2,4):
        td=t[::stride];vd=hv[::stride];hd=np.diff(vd,axis=0)/np.diff(td)[:,None];jd=np.diff(hd,axis=0)/np.diff(td)[:-1,None];summary[f'human_jerk_{stride*5}ms_RMS_rad_s3']=np.sqrt(np.mean(jd**2,axis=0))
    return summary
