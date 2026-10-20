"""Offline joint-specific motion gate and native timing evidence; no physics imports."""
from pathlib import Path
import argparse, hashlib, json, shutil, sys
from datetime import datetime, timezone
sys.dont_write_bytecode=True
import numpy as np

def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return x.item()
    return x

def extract(package,ids):
    p=Path(package);sources={};rows=[]
    def source(rel):
        f=p/rel;sources[rel]={'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size};return f
    def read(rel,default=None):return json.loads(source(rel).read_text()) if (p/rel).exists() else default
    protocol=read('MOTION_ACCEPTANCE_PROTOCOL.json')['primary']
    for pid in ids:
        done=read(pid+'_DONE.json',{});owner=read('audit/'+pid+'_OWNER.json',{})
        if not done.get('all_children_joined') or not owner.get('joined'):
            rows.append({'patient_id':pid,'status':'WAITING_FOR_JOIN','no_trend_claim':True});continue
        pair=read(pid+'_COMPARISON.json',{})
        if not pair.get('full_integral_comparison_valid'):
            rows.append({'patient_id':pid,'status':'NO_COMPLETE_VALID_PAIR'});continue
        measured={a:read('reports/'+pid+'_'+a+'_MEASURED.json') for a in ['B','H150']}
        per_joint=[]
        for signal,key in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
            for stat in protocol[key]:
                b=np.array(measured['B']['motion']['raw']['full'][signal][stat]);h=np.array(measured['H150']['motion']['raw']['full'][signal][stat])
                for j,joint in enumerate(['hip','knee']):
                    per_joint.append(dict(signal=signal,statistic=stat,joint=joint,B=b[j],H150=h[j],ratio=h[j]/max(b[j],1e-12),
                        threshold=protocol['burden_ratio']*b[j],numerical_tolerance=1e-7,failed=bool(h[j]>protocol['burden_ratio']*b[j]+1e-7)))
        excursion=[]
        for j,joint in enumerate(['hip','knee']):
            b=measured['B']['dose']['excursion_deg'][j];h=measured['H150']['dose']['excursion_deg'][j]
            excursion.append(dict(joint=joint,B=b,H150=h,H150_minus_B=h-b,absolute_delta=abs(h-b),threshold=protocol['excursion_abs_delta_deg'],numerical_tolerance=1e-7,failed=bool(abs(h-b)>protocol['excursion_abs_delta_deg']+1e-7)))
        native={}
        for arm in ['B','H150']:
            with np.load(source('motion_series/'+pid+'_'+arm+'.npz'),allow_pickle=False) as z:
                t=z['time_s'];phase=z['phase'];q=np.rad2deg(z['true_q_rad']);signals={k:np.rad2deg(z[v]) for k,v in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2'),('jerk_deg_s3','jerk_rad_s3')]}
            origins={ph:float(t[np.flatnonzero(phase==ph)[0]]) for ph in ['OUTBOUND','HOLD','RETURN']}
            peaks=[]
            for signal,values in signals.items():
                for j,joint in enumerate(['hip','knee']):
                    idx=int(np.argmax(abs(values[:,j])));ph=str(phase[idx])
                    peaks.append(dict(signal=signal,joint=joint,value=values[idx,j],absolute_value=abs(values[idx,j]),physics_s=t[idx],task_elapsed_s=t[idx]-t[0],phase=ph,phase_elapsed_s=t[idx]-origins[ph],true_q_deg=q[idx]))
            # p95 is a distribution statistic, not a unique event. Show exceedance occupancy.
            cutoff=protocol['burden_ratio']*measured['B']['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]
            values=abs(signals['acceleration_deg_s2'][:,1]);above=values>cutoff+1e-7
            changes=np.diff(np.r_[False,above,False].astype(int));beg=np.flatnonzero(changes==1);end=np.flatnonzero(changes==-1)-1
            intervals=[dict(start_physics_s=t[i],end_physics_s=t[j],start_phase=str(phase[i]),end_phase=str(phase[j]),
                           start_phase_elapsed_s=t[i]-origins[str(phase[i])],end_phase_elapsed_s=t[j]-origins[str(phase[j])],
                           sample_count=int(j-i+1),sample_occupancy_s=(j-i+1)*.00025,max_abs_deg_s2=float(values[i:j+1].max())) for i,j in zip(beg,end)]
            occupancy={ph:dict(samples=int(np.sum(above&(phase==ph))),fraction_of_phase=float(np.mean(above[phase==ph])),
                p95_abs_deg_s2=float(np.quantile(values[phase==ph],.95))) for ph in origins}
            reconstructed=np.quantile(values,.95);reported=measured[arm]['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1]
            assert abs(reconstructed-reported)<1e-8
            native[arm]=dict(native_dt_s=float(np.median(np.diff(t))),native_rows=len(t),phase_origins_physics_s=origins,
                peaks=peaks,knee_accel_p95_context=dict(p95_abs_deg_s2=reconstructed,threshold_deg_s2=cutoff,
                above_threshold_samples=int(above.sum()),above_threshold_fraction=float(above.mean()),phase_occupancy=occupancy,
                largest_occupancy_intervals=sorted(intervals,key=lambda r:r['sample_count'],reverse=True)[:12],
                definition='Absolute native acceleration > 1.10 times B full-task p95 plus1e-7; occupancy diagnostic only, not a new gate. Intervals retain every native sample.'))
        rows.append(dict(patient_id=pid,status='JOINED_PAIR_EXTRACTED',motion_relative=pair.get('motion_relative'),gain_percent=pair.get('gain_percent'),
            declared_failures=pair['H150']['motion_comparison']['failed_requirements'],per_joint_burden_gates=per_joint,excursion_gates=excursion,native=native,
            phase_motion={a:measured[a]['motion']['raw']['phases'] for a in measured},
            motion_extra={a:pair[a]['motion_extra'] for a in measured},
            measurements={a:{k:measured[a].get(k) for k in ['J_F_N_s','moment_integral_Nm_s','force_peak_N','moment_peak_Nm','tracking_RMS_deg']} for a in measured}))
    return clean(dict(schema='IHEAR_OFFLINE_MOTION_FAILURE_DETAIL_V1',generated_utc=datetime.now(timezone.utc).isoformat(),physics_starts=0,protocol=protocol,patients=rows,sources=sources))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--patients',nargs='+',default=['P00','P05','P06']);ap.add_argument('--mirror',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
    out=extract(args.package,args.patients);f=args.output or args.package/'audit_human'/'P05_FAILURE_DETAILS.json';f.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    if args.mirror:args.mirror.mkdir(parents=True,exist_ok=True);shutil.copy2(f,args.mirror/f.name)
    print(json.dumps({'patients':[{k:r.get(k) for k in ['patient_id','status','motion_relative']} for r in out['patients']],'physics_starts':0}))

if __name__=='__main__':main()
