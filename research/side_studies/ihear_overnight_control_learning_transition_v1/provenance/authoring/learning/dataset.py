"""Full-task labels are separate from the live causal state. No physics imports."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
ACTIONS=['H150','HIP','KNEE','ZERO']
def read(p):return json.loads(p.read_text())
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def margins(a,b,pr):
    v=[];names=[]
    def add(name,x):
        xx=np.atleast_1d(x)
        for j,e in enumerate(xx):names.append(name+':'+str(j));v.append(float(e))
    for sig,key in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
        for met in pr[key]:
            av=np.array(a['motion']['raw']['full'][sig][met]);bv=np.array(b['motion']['raw']['full'][sig][met])
            add(sig+'/'+met,1-av/(bv*pr['burden_ratio']))
    da=a['dose'];db=b['dose']
    add('excursion',1-abs(np.array(da['excursion_deg'])-db['excursion_deg'])/pr['excursion_abs_delta_deg'])
    ratio=np.array(da['cumulative_travel_deg'])/db['cumulative_travel_deg']
    add('travel_upper',(pr['cumulative_ratio_upper']-ratio)/.05);add('travel_lower',(ratio-pr['cumulative_ratio_lower'])/.05)
    add('endpoint',1-abs(np.array(da['endpoint_deg'])-db['endpoint_deg'])/pr['endpoint_and_phase_boundary_abs_delta_deg'])
    boundary=max(np.max(abs(np.array(da['phase_boundaries'][ph][k])-db['phase_boundaries'][ph][k])) for ph in ['OUTBOUND','HOLD','RETURN'] for k in ['start_deg','end_deg'])
    add('boundary',1-boundary/pr['endpoint_and_phase_boundary_abs_delta_deg'])
    add('duration',1-abs(da['duration_s']-db['duration_s'])/pr['total_duration_abs_delta_s'])
    for ph in ['OUTBOUND','HOLD','RETURN']:add(ph+'_duration',1-abs(a['phase_durations'][ph]-b['phase_durations'][ph])/pr['each_phase_duration_abs_delta_s'])
    for k,lim in [('moment_integral_Nm_s','moment_integral_ratio'),('force_peak_N','force_peak_ratio'),('moment_peak_Nm','moment_peak_ratio')]:add(k,1-a[k]/(b[k]*pr[lim]))
    add('tracking',1-(np.array(a['tracking_RMS_deg'])-b['tracking_RMS_deg'])/pr['tracking_RMS_add_deg'])
    return names,np.array(v)
def build(groups,label):
    pr=read(P/'MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];records=[];allrows=[];families=[];X=[];J=[];M=[];Q=[]
    for g in groups:
        result=read(P/(g+'_RESULTS.json'));b=read(P/'reports'/(g+'_B_MEASURED.json'))
        rr={r['candidate']['id']:r for r in result['rows']};xs=[];js=[];ms=[];qs=[]
        if not all(a in rr for a in ACTIONS):raise ValueError('INCOMPLETE_ACTION_MATRIX:'+g)
        for a in ACTIONS:
            ident=g+'_'+a;r=rr[a];causal=read(P/'output'/(ident+'_CAUSAL_STATE.json'));m=read(P/'reports'/(ident+'_MEASURED.json'))
            assert causal['truth_used'] is False and causal['future_matched_B_used'] is False
            names,margin=margins(m,b,pr)
            assert bool(np.min(margin)>=-1e-6)==bool(r['motion']['acceptance_pass'])
            with np.load(P/'motion_series'/(ident+'.npz')) as z:
                ret=z['phase']=='RETURN';q=np.rad2deg(z['true_q_rad']);v=np.rad2deg(z['true_dq_rad_s']);acc=np.rad2deg(z['acceleration_rad_s2'])
                overshoot=max(0.,9.5-float(q[ret,1].min()));tv=np.sum(abs(np.diff(v,axis=0)),axis=0);av=np.sum(abs(np.diff(acc,axis=0)),axis=0)
            rec=dict(id=ident,parent=g,split=result['condition']['split'],state=causal,proposed_action=r['candidate'],activation=dict(intervention_accepted=r['intervention_executed'],postures=r['posture_execution'],timing=r['timing_execution'],early=r['early_execution']),receipt_path='reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json',full_task_outcome=dict(complete=True,task=r['task'],safety=r['absolute_safety'],causal=r['receipt'],motion=r['motion']['acceptance_pass'],qualified=r['all_original_qualifications']),offline_labels=dict(J_F_N_s=m['J_F_N_s'],cost_rankable=r['all_original_qualifications'],force_peak_N=m['force_peak_N'],moment_integral_Nm_s=m['moment_integral_Nm_s'],moment_peak_Nm=m['moment_peak_Nm'],tracking_RMS_deg=m['tracking_RMS_deg'],knee_overshoot_deg=overshoot,velocity_TV_deg_s=tv,acceleration_variation_deg_s2=av,native_motion=m['motion']['raw']['full'],dose=m['dose'],qualification_margins=margin,margin_names=names,failed_requirements=r['motion']['failed_requirements']),source_hashes=m['sources'])
            rec['actual_applied_action'] = r['candidate'] if r['intervention_executed'] else dict(kind='original_certified_fallback_or_partial_acceptance',exact_reference_and_commands='see positive native receipts',successful_proposed_action_reward=False)
            records.append(rec);xs.append(causal['features']);js.append(m['J_F_N_s']);ms.append(margin);qs.append(r['all_original_qualifications'])
        assert all(np.array_equal(xs[0],v) for v in xs[1:]),'STATE_ACTION_MATCHING_FAILURE:'+g
        assert len({rr[a]['branch']['full_hash'] for a in ACTIONS})==1,'LIVE_PARENT_NOT_MATCHED'
        X.append(xs[0]);J.append(js);M.append(ms);Q.append(qs);families.append(g)
        allrows+=result['rows']
    starts=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(x)['event']=='START']
    excluded=[dict(id=r['id'],reason='parent/B comparator, incomplete or not in this version; never fabricated as action reward') for r in starts if r['id'] not in {x['id'] for x in records}]
    put('derived/DATASET_'+label+'.json',dict(status='LEARNING_DATA_READY',groups=families,feature_names=records[0]['state']['feature_names'],actions=ACTIONS,margin_names=names,records=records,excluded_starts=excluded,parent_split_no_overlap=True,actual_sequential_repetitions=False))
    np.savez_compressed(P/'derived'/('DATASET_'+label+'.npz'),X=np.array(X),J=np.array(J),M=np.array(M),qualified=np.array(Q),groups=np.array(families),actions=np.array(ACTIONS),splits=np.array([read(P/(g+'_PLAN.json'))['condition']['split'] for g in groups]))
    print('DATASET',label,len(groups),'PARENTS',len(records),'ACTION_ROWS',flush=True)
if __name__=='__main__':build(sys.argv[2:],sys.argv[1])
