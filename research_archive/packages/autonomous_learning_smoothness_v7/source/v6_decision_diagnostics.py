"""Frozen-model diagnostics only. No refit, candidate generation or new physics."""
from pathlib import Path
import json,time,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from v6_selection import select
from v6_prescreen import canonical
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
    model=read('models/COMMON_COMPOSE_FROZEN.json');library=read('freeze/LIBRARY.json')['library'];out=[];all_rejected=[];movement=[]
    for path in sorted((P/'analysis/evaluation').glob('TEST_*.json')):
        e=json.loads(path.read_text());g=e['group'];bundle=model['phases'][e['phase']]
        rows=[r for r in read('data/'+g+'.json') if r['horizon_s']==.5 and r['tag'] in e['primary_menu']]
        def inputs(delta):
            result=[]
            for r in rows:
                v=list(r['features'])
                for i,n in enumerate(r['feature_names']):
                    if n in ['phase_elapsed_s_0','task_elapsed_s_0']:v[i]+=delta
                    elif n=='contract_time_remaining_s_0':v[i]-=delta
                result.append(dict(tag=r['tag'],feature_names=r['feature_names'],features=v,
                    local_risk_features=r['local_risk_features'],history_risk_features=r['history_risk_features'],
                    short_JF=r['labels']['short_JF']))
            return result
        perturb=[]
        for delta in [-.015,0.,.015]:
            d=select(bundle,inputs(delta));perturb.append(dict(delta_clock_s=delta,choice=d['choice'],
                candidate_distance={r['tag']:r['distance'] for r in d['rows']},
                candidate_score={r['tag']:r['score'] for r in d['rows']}))
        for pr,r in zip(e['decision']['rows'],rows):
            why=[]
            if pr['distance']>bundle['ood_distance_limit']:why.append('OOD_DISTANCE')
            if pr['risk'] is not None and pr['risk']>=.5:why.append('PAST_RISK_HEAD')
            if pr['eligibility_risk'] is not None and pr['eligibility_risk']>=.5:why.append('FULL_ELIGIBILITY_HEAD')
            if why:all_rejected.append(dict(id=r['id'],reasons=why,actual_original_qualified=r['qualified'],
                tail_JF=r['labels']['tail_JF'],offline_reference_tag=e['methods']['E_REAL_FULL_REFERENCE']['choice']))
        a=e['methods']['A_FIXED_SMOOTH'];d=e['methods']['D_CRITIC']
        if d['choice']!='ABSTAIN':
            av=np.r_[a['full_jerk_RMS_deg_s3'],a['wrench']['force_norm_rate_RMS_N_s']]
            dv=np.r_[d['full_jerk_RMS_deg_s3'],d['wrench']['force_norm_rate_RMS_N_s']]
            movement.append(dict(group=g,critic=d['choice'],fixed_compose_original_qualified=a['qualified'],
                critic_original_qualified=d['qualified'],
                critic_minus_fixed_JF=d['full_JF']-a['full_JF'],critic_minus_fixed_JM=d['full_JM']-a['full_JM'],
                critic_vs_fixed_hip_knee_jerk_force_rate_percent=((dv/av-1)*100).tolist()))
        def physical_choice(tag):return None if tag is None else canonical(library[tag],e['phase'])
        out.append(dict(group=g,clock_perturbation=perturb,
            selection_label_changed_by_15ms=any(r['choice']!=perturb[1]['choice'] for r in perturb),
            selection_changed_by_15ms=any(physical_choice(r['choice'])!=physical_choice(perturb[1]['choice']) for r in perturb),
            physical_change_definition='phase-active canonical action, not candidate string; HANDOFF/PATTERN alias in OUTBOUND',
            maximum_perturbed_distance=max(v for r in perturb for v in r['candidate_distance'].values()),
            frozen_ood_distance_limit=bundle['ood_distance_limit']))
    put('analysis/FROZEN_DECISION_DIAGNOSTICS.json',dict(evaluated_unix=time.time(),
        model_frozen_unix=model['frozen_unix'],states=out,rejected_candidates=all_rejected,
        original_qualified_candidates_rejected=sum(r['actual_original_qualified'] for r in all_rejected),
        motion_force_tradeoffs=movement,
        scope='Numerical clock stress and retrospective diagnosis of already frozen predictions. '
              'Clock-only perturbations are not new legal physical states, do not validate dynamics, '
              'do not enter training, and are not additional independent tests. '
              'Risk rejection mistakes are assessed only where complete outcomes were actually paid for.'))
    print('FROZEN_DIAGNOSTICS',len(out),'states','qualified_rejections',sum(r['actual_original_qualified'] for r in all_rejected),flush=True)
if __name__=='__main__':main()
