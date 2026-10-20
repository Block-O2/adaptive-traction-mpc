"""Archive-only force/motion diagnosis. No plant, planner, or controller imports.

All force integrals use stored 5 ms boundary force, left rectangular rule.
Native derivatives use stored 0.25 ms actual Human velocity. Lag features are
aggregated independently onto phase-local bins; native force is never invented.
"""
from pathlib import Path
import os, sys, json, gzip, hashlib, shutil, subprocess, platform, csv
from datetime import datetime
from zoneinfo import ZoneInfo
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', MPLBACKEND='Agg')
import numpy as np
from scipy.signal import detrend, savgol_filter
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

S = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
OLD = S/'adaptive_continuous_coordination_optimization_v1'
HIST = S/'ihear_overnight_research_retrospective_v1'
MAIN = Path('/home/hank/coding/adaptive-traction-mpc-learning')
P = Path(os.environ.get('IHEAR_DIAG_OUTPUT', str(S/'force_motion_coupling_diagnosis_v2')))
WIDTHS = [.05, .1, .25, .5, 1.]
FEATURES = ['velocity_TV_rate', 'acceleration_variation_rate', 'jerk_RMS', 'acceleration_RMS', 'tracking_velocity_RMS']
CORE = ['B0', '18D', 'legacy002', 'legacy005', 'legacy005_repeat', 'D1_coupled_inverse', 'adaptive_D2', 'S_fixed_knots_late', 'PS_early']
PHASES = ['OUTBOUND', 'HOLD', 'RETURN']
SOURCE_FILES = {}

def clean(x):
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if isinstance(x, np.ndarray): return clean(x.tolist())
    if isinstance(x, np.generic): return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x): return None
    return x

def put(name, obj):
    f=P/name; f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def sha(f):
    h=hashlib.sha256()
    with open(f,'rb') as stream:
        for b in iter(lambda:stream.read(2**20),b''): h.update(b)
    return h.hexdigest()

def source(f):
    f=Path(f).resolve()
    if str(f) not in SOURCE_FILES: SOURCE_FILES[str(f)]={'size':f.stat().st_size,'sha256':sha(f)}
    return f

def read(f): return json.loads(source(f).read_text())

def snapshot():
    git={}
    for label,args in [('HEAD',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('staged',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]:
        b=subprocess.check_output(['git','-C',str(MAIN)]+args);git[label]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
        if label in ['HEAD','branch']: git[label]['value']=b.decode().strip()
        (P/'audit'/('git_'+label+'_before.txt')).write_bytes(b)
    git['index_sha256']=sha(MAIN/'.git/index') if (MAIN/'.git/index').exists() else None
    meta={str(f.relative_to(MAIN)):[f.stat().st_size,f.stat().st_mtime_ns] for f in MAIN.rglob('*') if f.is_file() and '.git' not in f.relative_to(MAIN).parts}
    return {'git':git,'main_file_metadata':meta}

def array_items(path,key):
    # Bounded JSON array reader, adapted from archived stream_runtime_evidence;
    # intentionally removes its wildcard task_bootstrap/controller dependency.
    with gzip.open(path,'rt') as f:
        buf='';needle='"'+key+'":';decoder=json.JSONDecoder()
        while True:
            part=f.read(65536)
            if not part: raise ValueError('MISSING_ARRAY:'+key)
            buf+=part; pos=buf.find(needle)
            if pos>=0:
                buf=buf[pos+len(needle):].lstrip()
                while not buf: buf+=f.read(65536);buf=buf.lstrip()
                if not buf.startswith('['): raise ValueError('NOT_ARRAY:'+key)
                buf=buf[1:];break
            buf=buf[-len(needle):]
        while True:
            buf=buf.lstrip(', \n\r\t')
            if buf.startswith(']'): return
            try: value,end=decoder.raw_decode(buf)
            except json.JSONDecodeError:
                part=f.read(65536)
                if not part: raise ValueError('INCOMPLETE_ARRAY:'+key)
                buf+=part
                if len(buf)>16*2**20: raise ValueError('ITEM_LIMIT:'+key)
                continue
            yield value;buf=buf[end:]

def integral(t,x,lo,hi):
    w=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo))
    return np.tensordot(w,x[:-1],axes=(0,0))

def stats(x):
    return {'rms':np.sqrt(np.mean(x*x,axis=0)),'p95_abs':np.quantile(abs(x),.95,axis=0),'max_abs':abs(x).max(axis=0)}

def r(x,y):
    return float(np.corrcoef(x,y)[0,1]) if len(x)>=8 and min(np.std(x),np.std(y))>1e-11 else np.nan

def curve(x,y,width):
    lags=[]; vals=[]; ns=[]
    for k in range(-int(round(1/width)),int(round(1/width))+1):
        a,b=(x[:-k],y[k:]) if k>0 else ((x[-k:],y[:k]) if k<0 else (x,y))
        lags.append(k*width);vals.append(r(a,b));ns.append(len(a))
    return np.array(lags),np.array(vals),ns

def lag_record(x,y,width,surrogate=False):
    lag,vals,ns=curve(x,y,width); valid=np.isfinite(vals)
    if not valid.any(): return {'status':'INSUFFICIENT_OR_CONSTANT','n':len(x)}
    ix=np.nanargmax(abs(vals)); out={'lag_s':lag,'pearson':vals,'n_pairs':ns,'zero_lag_r':r(x,y),'zero_lag_spearman':float(spearmanr(x,y).statistic) if min(np.std(x),np.std(y))>1e-11 else None,'peak_abs_r':vals[ix],'peak_lag_s':lag[ix]}
    if surrogate:
        # Exploratory autocorrelation-preserving circular shifts within phase.
        # Max |r| over all lags is compared, avoiding uncorrected best-lag tests.
        shifts=np.arange(int(2/width),len(y)-int(2/width))
        if len(shifts):
            rng=np.random.default_rng(2026101602)
            shifts=rng.choice(shifts,size=min(199,len(shifts)),replace=False)
            peaks=[np.nanmax(abs(curve(x,np.roll(y,int(k)),width)[1])) for k in shifts]
            out['circular_shift_maxlag_null']={'n_shifts':len(shifts),'q95':float(np.quantile(peaks,.95)),'exceedance_fraction':float((1+np.sum(np.array(peaks)>=abs(vals[ix])))/(len(peaks)+1)),'interpretation':'descriptive, not a causal/stationary p value; finite periodic task and multiple metrics/scales remain confounded'}
    return out

def bins(s,width,filter_window=0):
    t,v,a,j=s['t'],s['v'],s['a'],s['j']
    if filter_window:
        v=savgol_filter(v,filter_window,3,axis=0,mode='interp');a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2)
    cv=np.r_[0,np.cumsum(np.linalg.norm(np.diff(v,axis=0),axis=1))]
    ca=np.r_[0,np.cumsum(np.linalg.norm(np.diff(a,axis=0),axis=1))]
    rows=[]
    for ph,lo,hi in zip(PHASES,s['bounds'],s['bounds'][1:]):
        # Phase-local full bins. Short residual tails retained separately in
        # phase metrics; omitted only from equal-width correlation features.
        for start in np.arange(lo,hi-width+1e-8,width):
            end=start+width; sel=(t>=start-1e-8)&(t<end-1e-8); fi=(s['tf']>=start-1e-8)&(s['tf']<end-1e-8)
            rows.append({'start_s':start,'end_s':end,'phase':ph,'mean_force_N':integral(s['tf'],s['f'],start,end)/width,'J_F_N_s':integral(s['tf'],s['f'],start,end),'velocity_TV_rate':(np.interp(end,t,cv)-np.interp(start,t,cv))/width,'acceleration_variation_rate':(np.interp(end,t,ca)-np.interp(start,t,ca))/width,'jerk_RMS':np.sqrt(np.mean(np.sum(j[sel]**2,axis=1))),'acceleration_RMS':np.sqrt(np.mean(np.sum(a[sel]**2,axis=1))),'tracking_velocity_RMS':np.sqrt(np.mean(np.sum(s['verr'][fi]**2,axis=1)))})
    return rows

def load_case(root,ident,label,qualification):
    run=root/'source/results'/ident
    for f in [run/'trace.npz',run/'summary.json',run/'config_snapshot.json',run/'native_reference.npz',run/'runtime_artifacts.json.gz',root/'motion_series'/(ident+'.npz')]: source(f)
    z=np.load(root/'motion_series'/(ident+'.npz'));tr=np.load(run/'trace.npz');su=read(run/'summary.json')
    t0=float(z['time_s'][0]);t=z['time_s']-t0;q=z['true_q_rad'];v=z['true_dq_rad_s'];a=np.gradient(v,z['time_s'],axis=0,edge_order=2);j=np.gradient(a,z['time_s'],axis=0,edge_order=2)
    assert np.array_equal(a,z['acceleration_rad_s2']) and np.array_equal(j,z['jerk_rad_s3'])
    m=tr['stage']=='TASK';tf=tr['time_s'][m]-t0;f=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1);moment=np.linalg.norm(tr['physical_cuff_moment_world_nm'][m],axis=1)
    assert np.max(abs(np.diff(t)-.00025))<1e-9 and np.max(abs(np.diff(tf)-.005))<1e-9
    assert np.max(abs(t[::20]-tf))<1e-8
    assert np.max(abs(q[::20]-tr['evaluation_only_human_state_rad_rad_s'][m,:2]))<1e-12
    assert np.max(abs(v[::20]-tr['evaluation_only_human_state_rad_rad_s'][m,2:]))<1e-12
    trans={r['to']:r['time_s']-t0 for r in su['task']['phase_transitions']};bounds=[0,trans['HOLD'],trans['RETURN'],trans['COMPLETE']]
    cf=np.r_[0,np.cumsum(f[:-1]*np.diff(tf))];verr=tr['evaluation_only_human_state_rad_rad_s'][m,2:]-tr['reference_dq_rad_s'][m]
    s=dict(label=label,root=str(root),ident=ident,t0=t0,t=t,q=q,v=v,a=a,j=j,tf=tf,f=f,moment=moment,cf=cf,refq=tr['reference_q_rad'][m],refv=tr['reference_dq_rad_s'][m],verr=verr,bounds=bounds,torque=tr['cr12_actuator_command_nm'][m],components={k:tr['robot_torque_component_'+k+'_nm'][m] for k in ['base','position','velocity','allocator','clipping']})
    components=sum(s['components'].values());closure=components-s['torque']
    valid_components=np.isfinite(closure).all(axis=1)
    assert valid_components[:-1].all() and not valid_components[-1]
    assert np.max(abs(closure[:-1]))<1e-9
    phases={}
    for ph,lo,hi in zip(PHASES,bounds,bounds[1:]):
        ni=(t>=lo-1e-8)&(t<=hi+1e-8);fi=(tf>=lo-1e-8)&(tf<=hi+1e-8)
        phases[ph]={'J_F_N_s':integral(tf,f,lo,hi),'duration_s':hi-lo,'mean_force_N':integral(tf,f,lo,hi)/(hi-lo),'force_RMS_N':np.sqrt(integral(tf,f*f,lo,hi)/(hi-lo)),'force_peak_N':f[fi].max(),'velocity_TV_rad_s':np.linalg.norm(np.diff(v[ni],axis=0),axis=1).sum(),'acceleration_variation_rad_s2':np.linalg.norm(np.diff(a[ni],axis=0),axis=1).sum(),'jerk_combined_rad_s3':stats(np.linalg.norm(j[ni],axis=1))}
    rec={'label':label,'archive_case':ident,'source_root':str(root),'qualification_origin':'historical archived evaluation, no new qualification/promotion','qualification':qualification,'absolute_task_start_s':t0,'task_bounds_s':bounds,'force_dt_s':np.median(np.diff(tf)),'native_dt_s':np.median(np.diff(t)),'force_samples':len(tf),'native_samples_including_initial_boundary':len(t),'J_F_N_s':cf[-1],'force_peak_N':f.max(),'force_RMS_N':np.sqrt(integral(tf,f*f,0,tf[-1])/tf[-1]),'moment_integral_Nm_s':integral(tf,moment,0,tf[-1]),'phase_metrics':phases,'velocity_TV_rad_s':np.linalg.norm(np.diff(v,axis=0),axis=1).sum(),'velocity_TV_per_joint_rad_s':abs(np.diff(v,axis=0)).sum(axis=0),'acceleration_variation_rad_s2':np.linalg.norm(np.diff(a,axis=0),axis=1).sum(),'acceleration_variation_per_joint_rad_s2':abs(np.diff(a,axis=0)).sum(axis=0),'velocity_rad_s':stats(v),'acceleration_rad_s2':stats(a),'jerk_rad_s3':stats(j),'jerk_combined_rad_s3':stats(np.linalg.norm(j,axis=1)),'tracking_q_deg':stats(np.degrees(q[::20]-s['refq'])),'tracking_dq_deg_s':stats(np.degrees(verr)),'torque_component_closure_max_Nm':np.max(abs(closure[:-1])),'torque_component_terminal_boundary_excluded':{'row':len(tf)-1,'reason':'completed task boundary has no next command/component decomposition; no NaN filtering elsewhere'},'archive_online_accumulator_J_F_N_s':su['task']['force_integral_n_s'],'online_accumulator_difference_N_s':cf[-1]-su['task']['force_integral_n_s']}
    assert abs(sum(x['J_F_N_s'] for x in phases.values())-cf[-1])<1e-8
    events=[]
    for d in su['decisions']:
        for k,field in [('request','decision_request_time_s'),('activation','actual_schedule_start_physics_s')]:
            if d.get(field) is not None: events.append({'kind':k,'task_s':d[field]-t0,'absolute_s':d[field],'request_id':d['timing_request_id'],'phase':d['phase'],'outcome':d.get('activation_outcome')})
        # Actual selected waypoint/segment endpoint, not a new planner request.
        schedule=d.get('selected_schedule') or d.get('schedule')
        if schedule and 'duration_s' in schedule and d.get('actual_schedule_start_physics_s') is not None:
            events.append({'kind':'planned_waypoint_end','task_s':d['actual_schedule_start_physics_s']+schedule['duration_s']-t0,'request_id':d['timing_request_id'],'qualification':'planned endpoint, may be replaced before arrival'})
    for e in array_items(run/'runtime_artifacts.json.gz','rolling_splice_events'):
        if e.get('actual_splice_physics_s') is not None:events.append({'kind':'splice','task_s':e['actual_splice_physics_s']-t0,'absolute_s':e['actual_splice_physics_s'],'request_id':e.get('request_id'),'outcome':e.get('outcome')})
    # Waypoint identity from activated selected plan records; does not infer
    # actual arrival from a planned endpoint or C2 boundary.
    for d in su.get('learning_records',[]):
        if d.get('selected_plan_activated'):
            sc=d['selected_plan']['schedule']; ix=d.get('decision_index')
            dec=next((x for x in su['decisions'] if x.get('decision_index')==ix),None)
            if dec is None and isinstance(ix,int) and ix<len(su['decisions']): dec=su['decisions'][ix]
            if dec and dec.get('actual_schedule_start_physics_s') is not None:
                origin=dec['actual_schedule_start_physics_s']
                events.append({'kind':'planned_waypoint_end','task_s':origin+sc['duration_s']-t0,'absolute_s':origin+sc['duration_s'],'request_id':dec['timing_request_id'],'target_q_rad':sc.get('target_q_rad'),'qualification':'planned waypoint, not proof of actual arrival'})
    s['events']=events;put('events/'+label+'.json',{'events':events,'phase_bounds_task_s':bounds})
    np.savez_compressed(P/'series'/(label+'.npz'),**{k:s[k] for k in ['t','q','v','a','j','tf','f','cf','refq','refv','verr','torque']})
    return rec,s

def verify_raw(s):
    run=Path(s['root'])/'source/results'/s['ident'];raw=run/'runtime_artifacts.json.gz'
    receipts=[x for x in array_items(raw,'command_receipts') if x.get('applied') and x.get('native_steps',0)>0]
    starts=np.array([x['start_physics_s'] for x in receipts]);ends=np.array([x['end_physics_s'] for x in receipts]);counts=np.zeros(len(receipts),int)
    assert np.max(abs(starts[1:]-ends[:-1]))<1e-8
    qerr=verr=0.;n=task_n=0; first=None;last=None
    for row in array_items(raw,'native_states_evaluation_only'):
        n+=1;now=row['time_s'];idx=np.searchsorted(starts,now-.00025+1e-9,side='right')-1
        assert idx>=0 and starts[idx]-1e-8<=now-.00025<ends[idx]+1e-8
        assert np.array_equal(row['command_torque_nm'],receipts[idx]['command_torque_nm']);counts[idx]+=1
        if now>s['t0']+1e-8:
            ni=int(round((now-s['t0'])/.00025));assert 0<ni<len(s['t'])
            # Native Human coordinates are the final two generalized axes.
            qq=np.asarray(row['qpos_evaluation_only'])[-2:];vv=np.asarray(row['qvel_evaluation_only'])[-2:]
            qerr=max(qerr,float(np.max(abs(qq-s['q'][ni]))));verr=max(verr,float(np.max(abs(vv-s['v'][ni]))));task_n+=1
        first=now if first is None else first;last=now
    assert np.array_equal(counts,[x['native_steps'] for x in receipts]) and task_n==len(s['t'])-1
    assert max(qerr,verr)<1e-12
    # Complete positive-step receipt provenance retained, no native Human replay.
    with gzip.open(P/'provenance'/(s['label']+'_receipts.json.gz'),'wt') as f:json.dump(receipts,f,separators=(',',':'))
    return {'case':s['label'],'native_rows':n,'task_native_rows':task_n,'positive_step_receipts':len(receipts),'native_q_max_error':qerr,'native_dq_max_error':verr,'exact_command_receipt_ownership':True,'receipt_native_counts_exact':True,'raw_first_last_absolute_s':[first,last],'initial_task_boundary_source':'stored TASK trace, then raw native rows','raw_sha256':sha(raw)}

def main():
    resume='--resume-engineering' in sys.argv
    if P.exists() and not resume: raise RuntimeError('Output exists; use IHEAR_DIAG_OUTPUT for a fresh reproduction directory')
    if resume:
        assert (P/'audit/PROTECTION_BEFORE.json').exists() and not (P/'RAW_DERIVED_METRICS.json').exists()
        shutil.copy2(P/'control/analyze.py',P/'audit/analyze_attempt1.py')
        put('audit/ENGINEERING_ATTEMPTS.json',[{'attempt':1,'status':'FAIL','stage':'first archive case torque closure','reason':'terminal TASK boundary has NaN components because no following command','physics_starts':0},{'attempt':2,'status':'START','repair':'assert exactly final row invalid; evaluate original 1e-9 closure on all 3806 real command intervals; no threshold change','physics_starts':0}])
    for d in ['audit','control','series','events','provenance','figures','derived','logs']: (P/d).mkdir(parents=True,exist_ok=True)
    shutil.copy2(__file__,P/'control/analyze.py')
    put('RUN_PLAN.json',{'question':'Does actual Human motion variation stably precede/coincide with instantaneous cuff-force change and explain cumulative burden?','evidence':'archive-only exploratory diagnosis; existing same-Human development traces; repeats are not independent samples','time_basis':'absolute physics time and task time t_abs-10.05, independently confirmed per case; never host wall time','metrics':'5ms left force integral; native raw dq gradients edge_order=2; combined Euclidean TV, acceleration variation, jerk RMS/p95/max; phase-local independent aggregation','lag_convention':'corr(motion[t],force[t+lag]); positive lag means motion leads force; ±1s; no crossing phase boundaries','sensitivity':{'bin_width_s':WIDTHS,'native_velocity_SG_windows_samples':[0,21,101],'detrend':['none','linear per phase','first difference per phase'],'null':'within-phase circular shifts excluding ±2s; maximum absolute lag correlation; descriptive only'},'phase2_gate':'Only stable time-local correspondence with consistent direction/lag across B/18D and OUTBOUND/RETURN plus contrasts may motivate bounded physical sensitivity. Pooled correlation, cumulative slope, or isolated peak cannot pass this gate. Otherwise branch D; unsupported exact temporal interface additionally branch E.','physics_starts_authorized_conditionally':True,'physics_started':0,'learning':False,'thresholds':'all original qualification thresholds unchanged; no new diagnostic score used for candidate promotion','stop':'No stable coupling -> stop waypoint/speed expansion, preserve all outcomes, study tracking/allocator/replan mechanisms.'})
    if not resume:
        before=snapshot();put('audit/PROTECTION_BEFORE.json',before)
    for root,names in [(MAIN,['AGENTS.md','CURRENT_RESEARCH_BASELINE.md']),(OLD,['REPORT.md','REPRODUCTION.md','MOTION_ACCEPTANCE_PROTOCOL.json','CANDIDATE_PLAN.json','CANDIDATE_RESULTS.jsonl','ANOMALY_MECHANISM_DIAGNOSTIC.json','ANOMALY_REPEAT_GATE.json','TIMEWARP_INTERFACE_CEILING.json','ATTEMPTS.jsonl','EXECUTION_CODE_MANIFEST.json','METRICS_CONTRACT.md','NATIVE_PROVENANCE_AUDIT.json']),(S/'adaptive_continuous_coordination_interface_v1',['REPORT.md','REPRODUCTION.md','NEXT_RESEARCH_DECISION.md'])]:
        for name in names:
            f=source(root/name);shutil.copy2(f,P/'provenance'/(root.name+'__'+name))
    rows=read(OLD/'PHYSICAL_ARM_RESULTS.json')['rows']; specs={x['id']:x for x in read(OLD/'CANDIDATE_PLAN.json')['coarse']}
    cases=[]
    for row in rows:
        label=row['id'].removeprefix('development_')
        qual={'task':row['task'],'receipt':row['receipt'],'motion':row['motion_pass'],'safety':row['native_physical_audit']['pass_'],'original_comparison':row['comparison'],'parameters':row.get('candidate',specs.get(label)),'level':'PHYSICAL_LEVEL1 development; host plan_age FAIL preserved'}
        cases.append((OLD,row['id'],label,qual))
    cases.insert(1,(HIST,'development_repair2_quality_NATIVE_SCALAR_18_063','18D',{'task':'PASS historical','receipt':'PASS historical','motion':'PASS development, 0/4 historical new prefix','safety':'PASS historical','parameters_source':'frozen 18D archive, not reselected','level':'LEVEL1 only'}))
    records=[];allseries={};lag_results={};windows={}
    for root,ident,label,qual in cases:
        rec,s=load_case(root,ident,label,qual);records.append(rec);allseries[label]=s
        windows[label]={};lag_results[label]={}
        for width in WIDTHS:
            rr=bins(s,width);windows[label][str(width)]=rr
            if label not in CORE:continue
            for fw in ([0,21,101] if width==.05 else [0]):
                br=rr if fw==0 else bins(s,width,fw)
                for ph in ['OUTBOUND','RETURN']:
                    rs=[z for z in br if z['phase']==ph];f=np.array([z['mean_force_N'] for z in rs])
                    for feature in FEATURES:
                        x=np.array([z[feature] for z in rs])
                        for transform in ['level','linear_detrend','first_difference']:
                            xx,yy=(x,f) if transform=='level' else ((detrend(x),detrend(f)) if transform=='linear_detrend' else (np.diff(x),np.diff(f)))
                            key=f'{width}|SG{fw}|{ph}|{feature}|{transform}'
                            lag_results[label][key]=lag_record(xx,yy,width,surrogate=(width==.05 and fw==0 and feature in FEATURES[:3] and label in ['B0','18D','legacy005']))
        print('ANALYZED',label,rec['J_F_N_s'],flush=True)
    B=allseries['B0'];base=records[0]
    for rec in records:
        s=allseries[rec['label']];assert np.max(abs(s['tf']-B['tf']))<1e-8
        rec['gain_vs_B_N_s']=base['J_F_N_s']-rec['J_F_N_s']
        rec['actual_trajectory_difference_vs_B_deg']=stats(np.degrees(s['q']-B['q']))
        rec['torque_component_difference_vs_B_Nm']={k:stats(x[:-1]-B['components'][k][:-1]) for k,x in s['components'].items()}
        rec['torque_component_delta_norm_max_vs_B_Nm']={k:np.linalg.norm(x[:-1]-B['components'][k][:-1],axis=1).max() for k,x in s['components'].items()}
        rec['velocity_TV_ratio_vs_B']=rec['velocity_TV_rad_s']/base['velocity_TV_rad_s'];rec['acceleration_variation_ratio_vs_B']=rec['acceleration_variation_rad_s2']/base['acceleration_variation_rad_s2'];rec['jerk_combined_RMS_ratio_vs_B']=rec['jerk_combined_rad_s3']['rms']/base['jerk_combined_rad_s3']['rms']
        put('derived/'+rec['label']+'_metrics.json',rec)
    put('RAW_DERIVED_METRICS.json',{'cases':records,'units':'angles rad, time s, force N, torque Nm unless field says deg','metric_note':'combined TV is sum Euclidean joint-vector increments; differs from sum of per-joint TVs; jerk is numerical derivative diagnostic, not a clinical endpoint'})
    put('derived/WINDOWS.json',windows);put('LAG_ANALYSIS.json',{'convention':'positive lag = motion leads force','cases':lag_results,'not_independent':'B/18D/candidates share same Human/state and task; phase shapes/trends/autocorrelation confound apparent associations','cumulative_J_not_used_as_correlation_signal':True})
    raw_checks=[]
    for label in ['B0','18D','legacy005','legacy005_repeat','legacy002']:
        raw_checks.append(verify_raw(allseries[label]));print('RAW_VERIFIED',label,flush=True)
    put('audit/RAW_NATIVE_RECEIPT_VERIFICATION.json',raw_checks)
    # All candidate negative outcomes remain in the copied original results.
    put('EXECUTION.json',{'status':'ANALYSIS_COMPLETE_REPORT_PENDING','new_physical_START':0,'new_physical_END':0,'new_native_steps':0,'new_validation':0,'new_deterministic_repeats':0,'archive_cases':len(cases),'raw_reaudited_cases':len(raw_checks),'old_physical_attempts_not_recounted_as_new':True,'no_model_or_controller_imports':True,'source_code':str(P/'control/analyze.py'),'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'client_timezone':'Asia/Shanghai','time_warning':'execution host calendar may differ from client date 2026-10-16; raw simulation time is authoritative for all plots'})
    put('SOURCE_MANIFEST.json',{'files':SOURCE_FILES,'raw_policy':'existing full raw archives stay in original canonical packages; this package stores immutable hashes, derived native arrays, complete selected receipt streams and copied contracts/results; no archive modified'})
    print('COMPLETE_ANALYSIS',P,flush=True)

if __name__=='__main__': main()
