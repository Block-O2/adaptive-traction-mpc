"""Independent error summaries of H-time frozen outputs; no prediction refit."""
from pathlib import Path
import os,json,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from v6_prescreen import canonical
P=Path(__file__).resolve().parents[1]
def main():
    states=[];library=json.loads((P/'freeze/LIBRARY.json').read_text())['library']
    for path in sorted((P/'analysis/evaluation').glob('*.json')):
        e=json.loads(path.read_text());data=json.loads((P/'data'/f"{e['group']}.json").read_text())
        rows=[r for r in data if r['horizon_s']==.5 and r['tag'] in e['primary_menu']]
        predicted=[];actual=[];stds=[];pair_rows=[];seen=set()
        for r in rows:
            q=json.loads((P/'predictions'/(r['id']+'_H05.json')).read_text())
            predicted.append(q['cost']['mean'][:3]);stds.append(q['cost']['std'][:3])
            actual.append([r['labels']['tail_JF'],r['labels']['tail_JM'],r['labels']['remaining_time_s']])
            identity=canonical(library[r['tag']],e['phase']) if e['group'].startswith('TEST_') else (r['tag'],)
            if identity in seen:continue
            seen.add(identity);pair_rows.append(dict(tag=r['tag'],half=r['labels']['short_JF'],
                one=next(z['labels']['short_JF'] for z in data if z['tag']==r['tag'] and z['horizon_s']==1.),
                critic=q['score'],full=r['labels']['full_remaining_JF'],qualified=r['qualified']))
        err=np.array(predicted)-actual;relative=err-err.mean(0);std=np.array(stds);pairs=[]
        for i,x in enumerate(pair_rows):
            for y in pair_rows[i+1:]:
                if not(x['qualified'] and y['qualified']) or abs(x['full']-y['full'])<1e-8:continue
                sign=np.sign(x['full']-y['full']);pairs.append(dict(a=x['tag'],b=y['tag'],
                    actual_JF_gap=x['full']-y['full'],half_correct=bool(np.sign(x['half']-y['half'])==sign),
                    one_correct=bool(np.sign(x['one']-y['one'])==sign),critic_correct=bool(np.sign(x['critic']-y['critic'])==sign)))
        states.append(dict(group=e['group'],components=['tail_JF_N_s','tail_JM_Nm_s','remaining_duration_s'],
            absolute_RMSE=np.sqrt(np.mean(err**2,0)).tolist(),absolute_MAE=np.mean(abs(err),0).tolist(),
            relative_RMSE_after_common_menu_error=np.sqrt(np.mean(relative**2,0)).tolist(),
            mean_ensemble_std=std.mean(0).tolist(),pairwise_order_audit=pairs,
            unique_qualified_pairs=len(pairs),pairwise_accuracy={k:float(np.mean([p[k+'_correct'] for p in pairs])) if pairs else None for k in ['half','one','critic']}))
    (P/'analysis/FROZEN_PREDICTION_ERROR_AUDIT.json').write_text(json.dumps(dict(evaluated_unix=time.time(),states=states,
        deployed_score='short JF plus frozen score_index. Main score_index3 is menu-centered tailJF; its additive constant does not affect ranking. Absolute tail predictions are audited separately.',
        scope='All outputs taken from actually saved H-time predictions. Pairwise audit uses actual complete outcomes only retrospectively; no new fitting/selection. Ensemble spread is not calibrated coverage; A/B/C fixed/short-only methods have no tail prediction to score.'),indent=2)+'\n')
    print('PREDICTION_ERROR_AUDIT',len(states),'states',flush=True)
if __name__=='__main__':main()
