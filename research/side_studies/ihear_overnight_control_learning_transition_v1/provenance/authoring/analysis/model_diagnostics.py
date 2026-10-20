"""Read-only model capacity and development decisions; no model refit or physics."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
R=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
sys.path[:0]=[str(P/'control'),str(P/'learning')]
from early_selector import select as early_select
from frozen_selector import select as late_select
from train_early import reconstruct
def read(n):return json.loads((P/n).read_text())
def rank_info(x):
    centered=x-x.mean(0)
    scale=np.maximum(x.std(0),1e-7)
    # Exactly center again after scaling to remove mean roundoff. A centered
    # six-parent matrix can have at most five independent rows.
    z=centered/scale;z=z-z.mean(0)
    sv=np.linalg.svd(z,compute_uv=False)
    return dict(parents=len(x),features=x.shape[1],centered_rank_upper_bound=len(x)-1,
                rank_at_absolute_standardized_tolerance_1e_9=int(np.sum(sv>1e-9)),
                standardized_singular_values=sv.tolist(),feature_ranges=np.ptp(x,axis=0).tolist(),
                caution='Frozen metadata used default unscaled floating-point matrix_rank; roundoff can report rank above n-1. This diagnostic corrects interpretation only and does not change weights or decisions.')
def main():
    data=np.load(P/'derived/DATASET_development.npz')
    x=data['X'];groups=data['groups'].tolist();tr=np.flatnonzero(data['splits']=='train')
    ex=np.array([reconstruct(g,'B') for g in groups])
    records=[]
    states=read('derived/DATASET_development.json')['records']
    for i,g in enumerate(groups):
        state=next(r['state'] for r in states if r['parent']==g)
        q=late_select(state)
        e=early_select(dict(features=ex[i].tolist(),truth_used=False,future_outcomes_used=False))
        records.append(dict(parent=g,split=str(data['splits'][i]),late=q,early=e))
    result=dict(status='PASS',unix=time.time(),scope='development-only diagnostic; no fitting, test labels, or policy changes',
                late_rank=rank_info(x[tr]),early_rank=rank_info(ex[tr]),development_decisions=records,
                early_development_all_B=all(r['early']['selected']=='B' for r in records),
                early_no_alternative_eligible_on_development=all(not any(r['early']['eligible'][1:]) for r in records),
                model_hashes={n:hashlib.sha256((P/'models'/n).read_bytes()).hexdigest() for n in ['Q_value_ridge.npz','early_value_ridge.npz']})
    (P/'derived/MODEL_CAPACITY_DIAGNOSTIC.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MODEL_CAPACITY_DIAGNOSTIC',result['late_rank']['rank_at_absolute_standardized_tolerance_1e_9'],result['early_rank']['rank_at_absolute_standardized_tolerance_1e_9'],flush=True)
if __name__=='__main__':main()
