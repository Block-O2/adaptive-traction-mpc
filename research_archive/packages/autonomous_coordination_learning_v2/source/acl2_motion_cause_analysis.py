"""Read-only outcomes of the four preregistered original-chain interventions."""
import json,gzip,collections
import numpy as np
from acl2_shared import P,R,read,put,utc,sha

def main():
    registration=read('MOTION_CAUSE_PREREGISTRATION.json');allrows=[json.loads(s) for s in (P/'ALL_RESULTS.jsonl').read_text().splitlines()];D={r['id']:r for r in allrows};out=[]
    for ident in ['CORE_C_019']+['MOTION_CAUSE_'+v['tag'] for v in registration['variants']]:
        r=D.get(ident)
        if r is None:out.append(dict(id=ident,status='NOT_RUN'));continue
        row=dict(id=ident,status='EXECUTED',complete=r['complete'],qualified=r['qualified'],JF=r.get('JF'),JM=r.get('JM'),worst_ratio=r.get('worst_ratio'),failure_requirements=r.get('motion_vs_B',{}).get('failed_requirements'),action=r['action'],native_steps=r['actual_new_native_steps'])
        rawpath=R/'source/results'/ident/'runtime_artifacts.json.gz';motionpath=R/'motion_series'/(ident+'.npz')
        if r['complete'] and rawpath.exists():
            with gzip.open(rawpath,'rt') as f:raw=json.load(f)
            events=[e for e in raw['execution_attempts'] if e.get('clearance_feedback')];event=min(events,key=lambda e:e['clearance_feedback']['model_curvature_m_s2']);counts=collections.Counter(e['clearance_feedback']['active'] for e in events)
            row.update(clearance_feedback_active_cycles=counts[True],worst_curvature_time_s=event['source_sample_time_s'],minimum_guard_curvature_m_s2=event['clearance_feedback']['model_curvature_m_s2'],correction_at_worst_curvature_Nm=event['clearance_feedback']['correction_nm'],internal_model_constraint_satisfied=event['clearance_feedback']['constraint_satisfied'],raw_sha256=sha(rawpath))
            row['accepted_RETURN_durations']=[dict(slot=e['modal'].get('slot'),duration_s=e['modal'].get('actually_selected_duration_s')) for e in r.get('execution',[]) if e.get('modal') and e['modal']['phase']=='RETURN' and e['modal']['status']=='ACCEPTED']
        if r['complete'] and motionpath.exists():
            with np.load(motionpath) as z:
                jerk=np.degrees(z['jerk_rad_s3']);acc=np.degrees(z['acceleration_rad_s2']);t=z['time_s'];idx=np.argmax(abs(jerk),axis=0);energy=jerk*jerk;top=np.argsort(energy.sum(1))[-20:]
                row.update(native_acceleration_max_deg_s2=np.max(abs(acc),axis=0),native_jerk_RMS_deg_s3=np.sqrt(np.mean(jerk*jerk,axis=0)),native_jerk_peak_deg_s3=np.max(abs(jerk),axis=0),native_jerk_peak_times_s=[t[i] for i in idx],top20_native_jerk_squared_fraction=float(energy[top].sum()/energy.sum()))
        out.append(row)
    result=dict(utc=utc(),status='NOT_RUN' if all(r['status']=='NOT_RUN' for r in out[1:]) else 'OBSERVED_PREREGISTERED_INTERVENTIONS',reference_failed_attempt='CORE_C_019',new_candidate_attempts=sum(r['status']=='EXECUTED' for r in out[1:]),new_candidate_budget=4,rows=out,scope='All four fixed variants retained. Original guard, physical plant, safety/task/scorer unchanged. Timing interventions are conditional on this trajectory and can affect later accepted plans; do not infer a universal sole cause or future guard safety proof.',overhead='Cold parent and B/H150/strong charged separately in full physical ledger; not primary A/B/C/PPO feedback.',source_sha256=sha(__file__))
    put('MOTION_CAUSE_RESULTS.json',result);return result

if __name__=='__main__':main()
