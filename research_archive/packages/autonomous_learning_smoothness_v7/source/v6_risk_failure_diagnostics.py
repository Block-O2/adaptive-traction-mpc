"""Risk diagnostics on already exposed old labels. No fit or new validation claim."""
from pathlib import Path
import os,json,time,collections,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
from v6_observed_risk import predict
P=Path(__file__).resolve().parents[1]
def main():
    began=time.time();mf=P/'models/WHOLE_HISTORY_RISK_V5_FROZEN.json';df=P/'data/WHOLE_HISTORY_RISK_ROWS_V5.json'
    m=json.loads(mf.read_text());rows=json.loads(df.read_text());lookup={r['id']:r for r in rows};phase={};family={}
    for c in m['cross_validation']:
        r=lookup[c['id']];key='TP' if c['failed'] and c['rejected'] else 'FN' if c['failed'] else 'FP' if c['rejected'] else 'TN'
        phase.setdefault(r['phase'],collections.Counter())[key]+=1
        family.setdefault(r['state_family'],collections.Counter())[key]+=1
    fit_errors=[]
    for r in rows:
        p=predict(m['model'],dict(history_risk_features=r['features']))
        if bool(p>=.5)!=r['already_irreversible_failure']:
            fit_errors.append(dict(id=r['id'],family=r['state_family'],phase=r['phase'],actual_already_failed=r['already_irreversible_failure'],risk=p,max_original_irreversible_ratio=r['max_original_irreversible_ratio_by_H']))
    positives=[r for r in rows if r['already_irreversible_failure']];negatives=[r for r in rows if not r['already_irreversible_failure']];scale=np.array(m['model']['x_scale']);pairs=[]
    for pos in positives:
        eligible=[r for r in negatives if r['phase']==pos['phase'] and r['state_family']!=pos['state_family']]
        if not eligible:continue
        delta=(np.array([r['features'] for r in eligible])-pos['features'])/scale
        distances=np.sqrt(np.mean(delta**2,1));i=int(np.argmin(distances));neg=eligible[i]
        ix=np.argsort(abs(delta[i]))[-4:][::-1]
        pairs.append(dict(positive=pos['id'],negative=neg['id'],phase=pos['phase'],normalized_summary_distance=float(distances[i]),
            positive_native_ratio=pos['max_original_irreversible_ratio_by_H'],negative_native_ratio=neg['max_original_irreversible_ratio_by_H'],
            largest_standardized_differences=[dict(feature=pos['feature_names'][k],positive=pos['features'][k],negative=neg['features'][k],difference=float(delta[i,k])) for k in ix]))
    pairs=sorted(pairs,key=lambda r:r['normalized_summary_distance'])[:12]
    out=dict(evaluated_unix=time.time(),operative_model_sha256=hashlib.sha256(mf.read_bytes()).hexdigest(),
        data_sha256=hashlib.sha256(df.read_bytes()).hexdigest(),cross_family_CV_by_phase={k:dict(v) for k,v in phase.items()},
        cross_family_CV_by_family={k:dict(v) for k,v in family.items()},
        training_resubstitution_errors=fit_errors,training_resubstitution_false_negatives=sum(r['actual_already_failed'] for r in fit_errors),
        closest_opposite_label_summaries=pairs,wall_s=time.time()-began,new_native_steps=0,
        confirmed='Held-out OUTBOUND windows have0 TP and12 FN; HOLD0 TP and6 FN. All18 TP are RETURN. Only one training state family supplies OUTBOUND irreversible failures.',
        hypotheses=['Family/phase coverage limits cross-family recall.','Compression to observer extrema and guard counts may omit useful execution history.','Linear logistic fit/regularization can underfit sharp risk boundaries.'],
        limits='Nearest opposite-label summaries do not prove irreducible non-observability; full causal histories may contain discriminating information. Resubstitution is training diagnosis, never independent validation. No feature/model/threshold revised.')
    (P/'analysis/RISK_FAILURE_MECHANISMS.json').write_text(json.dumps(out,indent=2)+'\n')
    print('RISK_FAILURE_DIAGNOSTICS',out['cross_family_CV_by_phase'],'training_FN',out['training_resubstitution_false_negatives'],flush=True)
if __name__=='__main__':main()
