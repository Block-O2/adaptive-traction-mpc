"""Check receipt completion fields and future-truncation invariance, no fitting."""
from pathlib import Path
import json,time,os,sys,hashlib,copy,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];V=P.parent/'smoothness_critic_research_v5'
sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
from v6_observed_history import arrays,with_guards
from v6_selection import select
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def main():
    start=time.time();usage=resource.getrusage(resource.RUSAGE_SELF)
    put('owned/CAUSAL_EVENT_AUDIT_START.json',dict(pid=os.getpid(),started_unix=start,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    rows=[];fail=[]
    try:
        sources=json.loads((P/'models/WHOLE_HISTORY_RISK_V5_FROZEN.json').read_text())['source_trajectories']
        for ident in sources:
            events=list(array_items(V/'runtime/source/results'/ident/'runtime_artifacts.json.gz','execution_attempts'))
            missing=[i for i,e in enumerate(events) if 'end_physics_s' not in e]
            backwards=[i for i,e in enumerate(events) if e.get('end_physics_s',e['source_sample_time_s'])<e['source_sample_time_s']-1e-9]
            rows.append(dict(id=ident,events=len(events),missing_end_indices=missing,backwards_end_indices=backwards))
            if missing or backwards:fail.append(ident)
        # Actual held-out trace; replacing all future signals must leave history unchanged.
        data=json.loads((P/'data/TEST_O1.json').read_text());r=next(x for x in data if x['tag']=='COMPOSE' and x['horizon_s']==.5)
        at=r['causal_physical_s'];ident=r['id']
        with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
            u=z['stage']=='TASK';t=z['time_s'][u];x=z['estimated_human_state_rad_rad_s'][u];f=z['physical_cuff_force_world_n'][u];m=z['physical_cuff_moment_world_nm'][u]
        original=arrays(t,x,f,m,at,r['phase']);future=t>at+1e-9
        xx,ff,mm=x.copy(),f.copy(),m.copy();xx[future]=1e9;ff[future]=-1e9;mm[future]=1e8
        changed=arrays(t,xx,ff,mm,at,r['phase']);error=float(np.max(np.abs(np.array(original)-changed)))
        assert error==0.,'FUTURE_SIGNAL_DEPENDENCE'
        event=dict(source_sample_time_s=at+.1,end_physics_s=at+.2,applied=False,clearance_feedback=dict(active=True,constraint_satisfied=False,correction_nm=[1e9,1e9]))
        unfinished=dict(source_sample_time_s=at-.1,end_physics_s=at+.1,applied=False,clearance_feedback=event['clearance_feedback'])
        base=with_guards(original,[],[],float(t[0]),at)
        changed=with_guards(original,[event,unfinished],[dict(physics_s=at+.1)],float(t[0]),at)
        assert base==changed,'FUTURE_EVENT_DEPENDENCE'
        menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];half=[q for q in data if q['tag'] in menu and q['horizon_s']==.5]
        inp=[dict(tag=q['tag'],feature_names=q['feature_names'],features=q['features'],local_risk_features=q['local_risk_features'],history_risk_features=q['history_risk_features'],short_JF=q['labels']['short_JF']) for q in half]
        model=json.loads((P/'models/COMMON_COMPOSE_FROZEN.json').read_text())['phases'][r['phase']]
        before=select(model,inp);aug=copy.deepcopy(inp)
        for q in aug:q.update(qualified=False,labels={'tail_JF':-1e12},future_human=[1e12]*4,future_torque=-1e12,future_receipt='FORGED_PASS')
        after=select(model,aug);assert before==after,'FUTURE_OUTCOME_API_DEPENDENCE'
        out=dict(status='PASS' if not fail else 'REVIEW_REQUIRED',started_unix=start,ended_unix=time.time(),
            source_trajectories=len(rows),events=sum(q['events'] for q in rows),rows=rows,
            ambiguous_or_backwards_event_trajectories=fail,future_signal_max_feature_change=error,
            future_and_unfinished_events_ignored=True,future_outcome_fields_ignored_by_selection=True,
            original_failure_is_absorbing=select(model,inp,known_original_failure=True)['choice'] is None,
            resources=dict(wall_s=time.time()-start,cpu_user_s=resource.getrusage(resource.RUSAGE_SELF).ru_utime-usage.ru_utime,new_native_steps=0),
            scope='All old trajectories used in operative V5 risk training have explicit physics completion times; '
                  'actual prefix features invariant to future signal/event/outcome perturbations. '
                  'This checks implemented data flow, not sufficiency of the observer for native qualification.')
        put('audit/CAUSAL_EVENT_AVAILABILITY_AND_TRUNCATION.json',out)
        print('CAUSAL_EVENT_AUDIT',out['status'],len(rows),'trajectories','ambiguous',len(fail),flush=True)
        assert not fail,'AMBIGUOUS_PAST_RECEIPT_AVAILABILITY'
    finally:put('owned/CAUSAL_EVENT_AUDIT_END.json',dict(pid=os.getpid(),ended_unix=time.time()))
if __name__=='__main__':main()
