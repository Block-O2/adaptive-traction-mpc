"""Algebraic dose accounting under unchanged phase/task durations."""
from pathlib import Path
import json,time
P=Path(__file__).resolve().parents[1]
def main():
    rows=[]
    for g in ['DEV_O1','SMOOTH_A1','SMOOTH_A2','RULE_DEV','RULE_T1','RULE_T2','PHASE_RULE_S1','PHASE_RULE_S2']:
        f=P/'data'/f'{g}.json'
        if not f.exists():continue
        rr={r['tag']:r for r in json.loads(f.read_text()) if r['horizon_s']==.5}
        cfg=json.loads((P/'experiments'/f'{g}.json').read_text())
        if cfg.get('matched_reference_group'):
            other={r['tag']:r for r in json.loads((P/'data'/f"{cfg['matched_reference_group']}.json").read_text()) if r['horizon_s']==.5}
            rr=dict(other,**rr)
        if 'COMPOSE' not in rr:continue
        ref=json.loads((P/'attempts'/(rr['COMPOSE']['id']+'_RESULT.json')).read_text())
        for tag,r in rr.items():
            if tag=='B':continue
            d=json.loads((P/'attempts'/(r['id']+'_RESULT.json')).read_text());phase=[]
            for ph in ['OUTBOUND','HOLD','RETURN']:
                x=d['phase_cost'][ph];b=ref['phase_cost'][ph]
                tt=x['integrated_trace_duration_s'];bt=b['integrated_trace_duration_s']
                jf=x['J_F_N_s']-b['J_F_N_s'];jm=x['moment_integral_Nm_s']-b['moment_integral_Nm_s']
                force_time=(tt-bt)*b['mean_force_N'];force_level=tt*(x['mean_force_N']-b['mean_force_N'])
                moment_time=(tt-bt)*b['mean_moment_Nm'];moment_level=tt*(x['mean_moment_Nm']-b['mean_moment_Nm'])
                assert abs(jf-force_time-force_level)<1e-8 and abs(jm-moment_time-moment_level)<1e-8
                phase.append(dict(phase=ph,delta_duration_s=tt-bt,delta_JF=jf,delta_JM=jm,
                    delta_mean_force_N=x['mean_force_N']-b['mean_force_N'],delta_mean_moment_Nm=x['mean_moment_Nm']-b['mean_moment_Nm'],
                    force_duration_term_N_s=force_time,force_level_term_N_s=force_level,
                    moment_duration_term_Nm_s=moment_time,moment_level_term_Nm_s=moment_level))
            assert abs(sum(x['delta_JF'] for x in phase)-(r['metrics']['full_JF']-rr['COMPOSE']['metrics']['full_JF']))<1e-8
            rows.append(dict(group=g,action=tag,reference='COMPOSE',original_qualified=r['qualified'],phases=phase))
    (P/'analysis/FORCE_MOMENT_DOSE_DECOMPOSITION.json').write_text(json.dumps(dict(evaluated_unix=time.time(),rows=rows,
        identity='delta J = (T_new - T_ref)*mean_ref + T_new*(mean_new - mean_ref), applied per original phase left integral',
        scope='Exact algebraic accounting, not a causal mediation attribution. Jerk/force-rate benefits do not imply smaller mean force, JF or JM.'),indent=2)+'\n')
    print('DOSE_DECOMPOSITION',len(rows),'matched complete policies',flush=True)
if __name__=='__main__':main()
