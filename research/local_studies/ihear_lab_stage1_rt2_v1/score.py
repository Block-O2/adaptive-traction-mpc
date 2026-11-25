from env_rt2 import *
import numpy as np
from collections import Counter
from pathlib import Path
def stats(x):
    x=np.asarray(x,float)
    return [len(x),np.mean(x),*np.percentile(x,[50,95,99,100])]
def main():
    p=HERE/'B/native'
    z=np.load(p/'trace.npz'); zz=np.load(BASE/'trace.npz')
    idx=np.flatnonzero(z['stage']=='TASK');idx=np.arange(idx[0],min(len(z['time_s']),idx[-1]+2))
    t=z['time_s'][idx];dt=np.diff(t);assert np.allclose(dt,.005,atol=1e-9,rtol=0)
    f=z['physical_cuff_force_world_n'][idx];m=z['physical_cuff_moment_world_nm'][idx]
    fn=np.linalg.norm(f,axis=1);mn=np.linalg.norm(m,axis=1);fr=np.linalg.norm(np.diff(f,axis=0)/dt[:,None],axis=1)
    true=z['evaluation_only_human_state_rad_rad_s'][idx];q=true[:,:2];v=true[:,2:];a=np.diff(v,axis=0)/dt[:,None];j=np.diff(a,axis=0)/((dt[:-1]+dt[1:])*.5)[:,None]
    track=np.degrees(q-z['reference_q_rad'][idx]);ph=z['task_phase'][idx][:-1]
    phase={}
    for name in ('TASK','OUTBOUND','HOLD','RETURN'):
        mask=ph==name if name!='TASK' else np.ones(len(dt),bool)
        w=dt[mask];st=float(w.sum());validj=mask[1:]&mask[:-1]
        def rms(x):return np.sqrt(np.average(x[mask]**2,weights=w,axis=0))
        def peak(x):return np.max(np.abs(x[mask]),axis=0)
        phase[name]=dict(n=len(w),time=st,jf=fn[:-1][mask]@w,jm=mn[:-1][mask]@w,
            fmean=fn[:-1][mask]@w/st,mmean=mn[:-1][mask]@w/st,fpeak=peak(fn[:-1]),mpeak=peak(mn[:-1]),
            fr=rms(fr),frpeak=peak(fr),v=rms(v[:-1]),vp=peak(v[:-1]),a=rms(a),ap=peak(a),
            j=np.sqrt(np.average(j[validj]**2,axis=0,weights=dt[:-1][validj])),jp=np.max(abs(j[validj]),axis=0),track=rms(track[:-1]),
            trackpeak=peak(track[:-1]),span_deg=np.ptp(np.degrees(q[:-1][mask]),axis=0))
    art=read(p/'runtime_artifacts.json');wall=art['wall_physics'];rr=[r for r in wall['command_receipts'] if t[0]-1e-9<=r['start_physics_s']<t[-1]-1e-9]
    req=[r for r in art['requests'] if r['stage']=='TASK']
    b=dict(rows=phase,final_deg=np.degrees(q[-1]),final_v=v[-1],matched_trace=sha(p/'trace.npz')==sha(BASE/'trace.npz'),trace_sha=sha(p/'trace.npz'),mismatched_arrays=[k for k in z.files if not np.array_equal(z[k],zz[k],equal_nan=True)] if False else [k for k in z.files if z[k].tobytes()!=zz[k].tobytes()],result=read(HERE/'B/RESULT.json'),receipt_n=len(rr),applied_steps=Counter((str(r['supervisor_mode'])+'/'+str(r['native_steps'])) for r in rr if r['applied']),request_n=len(req),fallback_intervals=sum(r.get('fallback_intervals',0) for r in req),stagekeys=list(art),worker=stats([(r['compute_finish_ns']-r['worker_start_ns'])/1e6 for r in req]),hostage=stats([(r['activation_ns']-r['sensor_capture_ns'])/1e6 for r in req]),hostage_ge100=sum(r['activation_ns']-r['sensor_capture_ns']>=1e8 for r in req),hostage_ge55=sum(r['activation_ns']-r['sensor_capture_ns']>=55e6 for r in req),interval_host=stats(np.diff([r['source_capture_ns'] for r in rr])/1e6),capture_write=stats([(r['apply_ns']-r['source_capture_ns'])/1e6 for r in rr]),task_wall=(rr[-1]['apply_ns']-rr[0]['source_capture_ns'])/1e9)
    save(HERE/'B_score.json',b)
if __name__=='__main__':main()
